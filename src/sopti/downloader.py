from __future__ import annotations
from subprocess import Popen, PIPE
from time import sleep
from pathlib import Path
from threading import Event
from .models import SongRecord


class SpotDLWrapper:
    def __init__(self, dest: Path, preferred_format: str | None = None, bitrate: str | None = None, client_id: str | None = None, client_secret: str | None = None, verbose: bool = True, user_auth: bool = False):
        self.dest = dest
        self.preferred_format = preferred_format
        self.bitrate = bitrate
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_auth = user_auth
        self.verbose = verbose
        self.dest.mkdir(parents=True, exist_ok=True)
        self.log_file = Path.home() / ".cache" / "sopti" / "sopti.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.archive_file = self.dest / ".sopti-archive.txt"

    def _cleanup_partials(self) -> None:
        try:
            for p in self.dest.glob("**/*.part"):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass

    def _append_log(self, message: str) -> None:
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception:
            pass

    def download(self, song: SongRecord, cancel_event: Event | None = None) -> bool:
        base_cmd = [
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
            base_cmd += ["--format", self.preferred_format]
        if self.bitrate:
            base_cmd += ["--bitrate", self.bitrate]
        if self.client_id:
            base_cmd += ["--client-id", self.client_id]
        if self.client_secret:
            base_cmd += ["--client-secret", self.client_secret]
        if self.user_auth:
            base_cmd += ["--user-auth"]

        attempts = 0
        max_attempts = 5
        backoff_seconds = 2.0

        while attempts < max_attempts and (cancel_event is None or not cancel_event.is_set()):
            attempts += 1
            proc: Popen | None = None
            try:
                proc = Popen(
                    base_cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    text=True,
                )
                stdout_buf: list[str] = []
                stderr_buf: list[str] = []
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        self._cleanup_partials()
                        return False
                    ret = proc.poll()
                    if ret is not None:
                        try:
                            out, err = proc.communicate(timeout=1)
                            if out:
                                stdout_buf.append(out)
                            if err:
                                stderr_buf.append(err)
                        except Exception:
                            pass
                        if ret == 0:
                            return True
                        else:
                            if not self.verbose:
                                self._append_log(f"Download failed for {song.url}:\nSTDOUT:\n{''.join(stdout_buf)}\nSTDERR:\n{''.join(stderr_buf)}")
                            break
                    try:
                        if proc.stdout is not None and not proc.stdout.closed and proc.stdout.readable():
                            chunk = proc.stdout.readline()
                            if chunk:
                                stdout_buf.append(chunk)
                        if proc.stderr is not None and not proc.stderr.closed and proc.stderr.readable():
                            errc = proc.stderr.readline()
                            if errc:
                                stderr_buf.append(errc)
                    except Exception:
                        pass
                    sleep(0.2)
            except Exception as e:
                if not self.verbose:
                    self._append_log(f"Exception while downloading {song.url}: {e}")
                pass
            finally:
                if proc is not None and proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

            self._cleanup_partials()
            if attempts < max_attempts and (cancel_event is None or not cancel_event.is_set()):
                sleep(backoff_seconds)
                backoff_seconds *= 2

        return False
