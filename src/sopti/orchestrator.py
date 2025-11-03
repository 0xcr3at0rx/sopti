from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from threading import Event
from signal import getsignal, signal, SIGINT, SIGTERM
from re import sub as _re_sub
from tqdm import tqdm
from .playlist import PlaylistExtractor
from .downloader import SpotDLWrapper
from .database import DBManager
from .models import SongRecord



class Orchestrator:
    def __init__(self, profile_url: str, dest: Path, max_workers: int | None = None):
        self.profile_url = profile_url
        self.dest = dest
        self.db = DBManager()
        self.max_workers = max_workers or 3
        # Optional attributes set by caller
        self.preferred_format: str | None = None
        self.bitrate: str | None = None
        self.client_id: str | None = None
        self.client_secret: str | None = None
        self.user_auth: bool = False
        self.verbose: bool = True


    def _safe_folder(self, name: str) -> Path:
        safe = _re_sub(r"[^\w\-\. ]+", "_", name).strip().strip("._")
        if not safe:
            safe = "playlist"
        # Truncate to avoid OS path length issues
        if len(safe) > 80:
            safe = safe[:80]
        return self.dest / safe

    def _download_batch(self, wrapper: SpotDLWrapper, songs: list[SongRecord], cancel_event: Event) -> tuple[int, int, bool]:
        success_count = 0
        fail_count = 0
        executor: ThreadPoolExecutor | None = None
        futures: dict[Future, SongRecord] = {}
        pbar: tqdm | None = None
        cancelled = False

        old_sigint = getsignal(SIGINT)
        old_sigterm = getsignal(SIGTERM)

        def _on_signal(signum, frame):
            cancel_event.set()

        signal(SIGINT, _on_signal)
        signal(SIGTERM, _on_signal)

        try:
            executor = ThreadPoolExecutor(max_workers=self.max_workers)
            if self.verbose:
                pbar = tqdm(total=len(songs), desc="Downloading", unit="track")

            iterator = iter(songs)
            try:
                for _ in range(self.max_workers):
                    song = next(iterator)
                    futures[executor.submit(wrapper.download, song, cancel_event)] = song
            except StopIteration:
                pass

            while futures and not cancel_event.is_set():
                for finished in as_completed(list(futures.keys()), timeout=None):
                    song = futures.pop(finished)
                    try:
                        ok = finished.result()
                    except KeyboardInterrupt:
                        cancel_event.set()
                        raise
                    except Exception:
                        ok = False
                    if ok:
                        self.db.add(song)
                        success_count += 1
                    else:
                        fail_count += 1
                    if pbar is not None:
                        pbar.update(1)

                    if cancel_event.is_set():
                        break

                    try:
                        next_song = next(iterator)
                        futures[executor.submit(wrapper.download, next_song, cancel_event)] = next_song
                    except StopIteration:
                        pass
        except KeyboardInterrupt:
            cancelled = True
            cancel_event.set()
        finally:
            if pbar is not None:
                try:
                    pbar.close()
                except Exception:
                    pass
            if executor is not None:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
            try:
                signal(SIGINT, old_sigint)
                signal(SIGTERM, old_sigterm)
            except Exception:
                pass

        return success_count, fail_count, cancelled

    def run(self) -> None:
        extractor = PlaylistExtractor(self.profile_url, client_id=self.client_id, client_secret=self.client_secret, user_auth=self.user_auth)
        try:
            songs = extractor.extract()
        except KeyboardInterrupt:
            self.db.close()
            if self.verbose:
                print("\nCancelled by user during extraction.")
            return

        # If this is a playlist URL, create a subfolder with the playlist name
        dest = self.dest
        if "/playlist/" in self.profile_url:
            try:
                playlist_name = extractor.get_playlist_name()
                dest = self._safe_folder(playlist_name)
                dest.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        wrapper = SpotDLWrapper(dest, preferred_format=self.preferred_format, bitrate=self.bitrate, client_id=self.client_id, client_secret=self.client_secret, verbose=self.verbose, user_auth=self.user_auth)

        cancel_event = Event()
        max_passes = 3
        total_songs = len(songs)
        previous_downloaded = len([s for s in songs if self.db.exists(s.id)])

        for attempt in range(1, max_passes + 1):
            pending = [s for s in songs if not self.db.exists(s.id)]
            if not pending:
                break
            if self.verbose:
                print(f"Pass {attempt}/{max_passes}: {len(pending)} tracks pending")
            s_ok, s_fail, cancelled = self._download_batch(wrapper, pending, cancel_event)
            if cancelled:
                self.db.close()
                return
            now_downloaded = len([s for s in songs if self.db.exists(s.id)])
            if now_downloaded == previous_downloaded:
                # No progress; stop early
                if self.verbose:
                    print("No further progress detected. Stopping.")
                break
            previous_downloaded = now_downloaded

        if self.verbose:
            downloaded_total = len([s for s in songs if self.db.exists(s.id)])
            print(f"Completed: {downloaded_total}/{total_songs} in database")

        self.db.close()
