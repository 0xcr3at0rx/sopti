from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, TimeoutError
from threading import Event
from signal import getsignal, signal, SIGINT, SIGTERM
from tqdm import tqdm
from .spotdl_integration.extractor import PlaylistExtractor
from .spotdl_integration.downloader import SpotDLWrapper
from .database import DBManager
from .models import SongRecord
from .config import Config
from .utils.logging import setup_logging
from .utils.path_utils import safe_folder_name

logger = setup_logging(__name__)


class Orchestrator:
    def __init__(self, profile_url: str, dest: Path, max_workers: int | None = None):
        self.profile_url = profile_url
        self.dest = dest
        self.db = DBManager()
        self.config = Config()
        self.max_workers = max_workers or self.config.data.get("workers", 3)
        self._set_default_attributes()

    def _set_default_attributes(self) -> None:
        self.preferred_format: str = self.config.data.get("preferred_format", "flac")
        self.bitrate: str = self.config.data.get("bitrate", "auto")
        self.client_id: str = self.config.data.get("spotify_client_id", "")
        self.client_secret: str = self.config.data.get("spotify_client_secret", "")
        self.user_auth: bool = False
        self.verbose: bool = True

    def _download_batch(
        self, wrapper: SpotDLWrapper, songs: list[SongRecord], cancel_event: Event
    ) -> tuple[int, int, bool]:
        success_count = 0
        fail_count = 0
        cancelled = False

        # Store original signal handlers
        old_sigint = getsignal(SIGINT)
        old_sigterm = getsignal(SIGTERM)

        def _on_signal(signum, frame):
            logger.info(f"Signal {signum} received. Setting cancellation event.")
            cancel_event.set()

        # Set new signal handlers
        signal(SIGINT, _on_signal)
        signal(SIGTERM, _on_signal)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            pbar = None
            if self.verbose:
                pbar = tqdm(
                    total=len(songs), desc="Downloading", unit="track", leave=True
                )

            futures: dict[Future, SongRecord] = {
                executor.submit(wrapper.download, song, cancel_event): song
                for song in songs[: self.max_workers]
            }
            song_iterator = iter(songs[self.max_workers :])

            try:
                while futures and not cancel_event.is_set():
                    try:
                        # Wait for any future to complete, with a small timeout to check cancel_event
                        finished_futures = as_completed(futures.keys(), timeout=0.5)
                        for finished in finished_futures:
                            song = futures.pop(finished)
                            try:
                                ok = finished.result()
                            except Exception as e:
                                logger.error(
                                    f"Error in download task for {song.url}: {e}",
                                    exc_info=True,
                                )
                                ok = False

                            if ok:
                                self.db.add(song)
                                success_count += 1
                            else:
                                fail_count += 1

                            if pbar:
                                pbar.update(1)

                            # Submit a new task if available
                            try:
                                next_song = next(song_iterator)
                                futures[
                                    executor.submit(
                                        wrapper.download, next_song, cancel_event
                                    )
                                ] = next_song
                            except StopIteration:
                                pass
                    except TimeoutError:
                        # No future completed in the last 0.5 seconds, check cancellation event
                        pass
                    except KeyboardInterrupt:
                        logger.info("KeyboardInterrupt detected during download batch.")
                        cancelled = True
                        cancel_event.set()
                        break
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt detected outside future loop.")
                cancelled = True
                cancel_event.set()
            finally:
                if pbar:
                    pbar.close()
                # Restore original signal handlers
                signal(SIGINT, old_sigint)
                signal(SIGTERM, old_sigterm)
                if cancelled:
                    # If cancelled, ensure all running futures are cancelled
                    for future in futures:
                        future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                else:
                    executor.shutdown(
                        wait=True
                    )  # Wait for all tasks to complete if not cancelled

        return success_count, fail_count, cancelled

    def run(self) -> None:
        try:
            extractor = self._get_extractor()
            songs = self._extract_songs(extractor)
            if songs is None:
                return

            dest = self._get_destination(extractor)
            self._download_songs(songs, dest)
        finally:
            self.db.close()

    def _download_songs(self, songs: list[SongRecord], dest: Path) -> None:
        wrapper = SpotDLWrapper(
            dest,
            preferred_format=self.preferred_format,
            bitrate=self.bitrate,
            client_id=self.client_id,
            client_secret=self.client_secret,
            verbose=self.verbose,
            user_auth=self.user_auth,
        )

        cancel_event = Event()
        max_passes = 3
        total_songs = len(songs)

        # Initial count of already downloaded songs
        initial_downloaded_count = sum(1 for s in songs if self.db.exists(s.id))
        previous_downloaded_count = initial_downloaded_count

        logger.info(
            f"Starting download process for {total_songs} songs. {initial_downloaded_count} already in DB."
        )

        for attempt in range(1, max_passes + 1):
            pending_songs = [s for s in songs if not self.db.exists(s.id)]
            if not pending_songs:
                logger.info(
                    "All pending songs downloaded or no songs to download. Breaking loop."
                )
                break

            if self.verbose:
                print(
                    f"Pass {attempt}/{max_passes}: {len(pending_songs)} tracks pending download."
                )
            logger.info(
                f"Pass {attempt}/{max_passes}: {len(pending_songs)} tracks pending download."
            )

            s_ok, s_fail, cancelled = self._download_batch(
                wrapper, pending_songs, cancel_event
            )

            if cancelled:
                logger.info("Download process cancelled by user.")
                if self.verbose:
                    print("\nDownload process cancelled.")
                return

            current_downloaded_count = sum(1 for s in songs if self.db.exists(s.id))
            if current_downloaded_count == previous_downloaded_count:
                logger.info(
                    "No further progress detected in this pass. Stopping early."
                )
                if self.verbose:
                    print("No further progress detected. Stopping.")
                break
            previous_downloaded_count = current_downloaded_count

        final_downloaded_count = sum(1 for s in songs if self.db.exists(s.id))
        logger.info(
            f"Download process finished. Total completed: {final_downloaded_count}/{total_songs}"
        )
        if self.verbose:
            print(f"Completed: {final_downloaded_count}/{total_songs} in database")

    def _get_destination(self, extractor: PlaylistExtractor) -> Path:
        if "/playlist/" in self.profile_url:
            try:
                playlist_name = extractor.get_playlist_name()
                dest = safe_folder_name(playlist_name, self.dest)
                dest.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created playlist subfolder: {dest}")
                return dest
            except Exception as e:
                logger.error(
                    f"Failed to create playlist subfolder for {self.profile_url}: {e}",
                    exc_info=True,
                )
                if self.verbose:
                    print(
                        f"Warning: Could not create playlist subfolder. Using default destination. Error: {e}"
                    )
        return self.dest

    def _get_extractor(self) -> PlaylistExtractor:
        return PlaylistExtractor(
            self.profile_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_auth=self.user_auth,
        )

    def _extract_songs(self, extractor: PlaylistExtractor) -> list[SongRecord] | None:
        try:
            songs = extractor.extract()
            if not songs:
                logger.info(f"No songs found for {self.profile_url}. Exiting.")
                return None
            return songs
        except KeyboardInterrupt:
            logger.info("Playlist extraction cancelled by user.")
            if self.verbose:
                print("\nCancelled by user during extraction.")
            return None
        except Exception as e:
            logger.error(
                f"Error during playlist extraction for {self.profile_url}: {e}",
                exc_info=True,
            )
            if self.verbose:
                print(f"\nError during extraction: {e}")
            return None
