from __future__ import annotations
from subprocess import Popen, PIPE, TimeoutExpired
from time import sleep
from pathlib import Path
from threading import Event
from ..models import SongRecord
from ..utils.logging import setup_logging

logger = setup_logging(__name__)


class SpotDLWrapper:
    def __init__(
        self,
        dest: Path,
        preferred_format: str | None = None,
        bitrate: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        verbose: bool = True,
        user_auth: bool = False,
    ):
        self.dest = dest
        self.preferred_format = preferred_format
        self.bitrate = bitrate
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_auth = user_auth
        self.verbose = verbose
        self.dest.mkdir(parents=True, exist_ok=True)
        self.archive_file = self.dest / ".sopti-archive.txt"

    def _cleanup_partials(self) -> None:
        for p in self.dest.glob("**/*.part"):
            try:
                p.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to remove partial file {p}: {e}")

    def download(self, song: SongRecord, cancel_event: Event | None = None) -> bool:
        cmd = [
            "spotdl",
            "download",
            song.url,
            "--output",
            str(self.dest),
            "--overwrite",
            "skip",
            "--threads",
            "1",
            "--archive",
            str(self.archive_file),
        ]
        if self.preferred_format:
            cmd.extend(["--format", self.preferred_format])
        if self.bitrate:
            cmd.extend(["--bitrate", self.bitrate])
        if self.client_id:
            cmd.extend(["--client-id", self.client_id])
        if self.client_secret:
            cmd.extend(["--client-secret", self.client_secret])
        if self.user_auth:
            cmd.append("--user-auth")

        max_attempts = 5
        backoff_factor = 2.0

        for attempt in range(1, max_attempts + 1):
            if cancel_event and cancel_event.is_set():
                logger.info(f"Download cancelled for {song.url}")
                self._cleanup_partials()
                return False

            proc: Popen | None = None
            try:
                logger.info(f"Attempt {attempt}/{max_attempts} to download {song.url}")
                proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
                stdout_lines: list[str] = []
                stderr_lines: list[str] = []

                while proc.poll() is None:
                    if cancel_event and cancel_event.is_set():
                        logger.info(
                            f"Cancellation detected for {song.url}. Terminating process."
                        )
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except TimeoutExpired:
                            proc.kill()
                        self._cleanup_partials()
                        return False

                    try:
                        if proc.stdout and proc.stdout.readable():
                            line = proc.stdout.readline()
                            if line:
                                stdout_lines.append(line)
                                if self.verbose:
                                    logger.info(f"STDOUT: {line.strip()}")
                        if proc.stderr and proc.stderr.readable():
                            line = proc.stderr.readline()
                            if line:
                                stderr_lines.append(line)
                                if self.verbose:
                                    logger.error(f"STDERR: {line.strip()}")
                    except Exception as e:
                        logger.error(
                            f"Error reading process output for {song.url}: {e}"
                        )
                    sleep(0.2)

                # Process has finished, read any remaining output
                out, err = proc.communicate()
                if out:
                    stdout_lines.append(out)
                    if self.verbose:
                        logger.info(f"STDOUT: {out.strip()}")
                if err:
                    stderr_lines.append(err)
                    if self.verbose:
                        logger.error(f"STDERR: {err.strip()}")

                if proc.returncode == 0:
                    logger.info(f"Successfully downloaded {song.url}")
                    return True
                else:
                    logger.error(
                        f"Download failed for {song.url} with exit code {proc.returncode}.\n"
                        f"STDOUT:\n{''.join(stdout_lines)}\nSTDERR:\n{''.join(stderr_lines)}"
                    )

            except FileNotFoundError:
                logger.error(
                    "SpotDL command not found. Please ensure spotdl is installed and in your PATH."
                )
                break
            except Exception as e:
                logger.error(
                    f"Exception during download of {song.url}: {e}", exc_info=True
                )
            finally:
                if proc and proc.poll() is None:
                    logger.warning(
                        f"Force killing process for {song.url} due to unhandled exception."
                    )
                    proc.kill()

            self._cleanup_partials()
            if attempt < max_attempts and (
                cancel_event is None or not cancel_event.is_set()
            ):
                sleep(backoff_factor**attempt)

        logger.error(f"Failed to download {song.url} after {max_attempts} attempts.")
        return False
