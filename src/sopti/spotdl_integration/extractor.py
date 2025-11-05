from __future__ import annotations
from subprocess import Popen, PIPE, TimeoutExpired
from re import sub
from typing import List
from json import loads as _json_loads
from ..models import SongRecord
from ..utils.logging import setup_logging

logger = setup_logging(__name__)


class PlaylistExtractor:
    def __init__(
        self,
        profile_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_auth: bool = False,
    ):
        self.profile_url = profile_url.rstrip(":")
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_auth = user_auth

    def _build_base_cmd(self, subcommand: str) -> list[str]:
        cmd = ["spotdl", subcommand, self.profile_url]
        if self.client_id:
            cmd.extend(["--client-id", self.client_id])
        if self.client_secret:
            cmd.extend(["--client-secret", self.client_secret])
        if self.user_auth:
            cmd.append("--user-auth")
        return cmd

    def get_playlist_name(self) -> str:
        cmd = self._build_base_cmd("meta")
        cmd.append("--json")

        proc: Popen | None = None
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
            out, err = proc.communicate(timeout=30)

            if proc.returncode == 0 and out:
                try:
                    data = _json_loads(out)
                    candidate = None
                    if isinstance(data, dict):
                        for key in (
                            "name",
                            "title",
                            "playlist_name",
                            "album",
                            "album_name",
                        ):
                            val = data.get(key)
                            if isinstance(val, str) and val.strip():
                                candidate = val.strip()
                                break
                    if candidate is None and isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                for key in (
                                    "name",
                                    "title",
                                    "playlist_name",
                                    "album",
                                    "album_name",
                                ):
                                    val = item.get(key)
                                    if isinstance(val, str) and val.strip():
                                        candidate = val.strip()
                                        break
                            if candidate:
                                break
                    if candidate:
                        logger.info(f"Extracted playlist name: {candidate}")
                        return candidate
                except Exception as e:
                    logger.warning(
                        f"Failed to parse JSON for playlist name from {self.profile_url}: {e}"
                    )
            else:
                logger.warning(
                    f"SpotDL meta command failed for {self.profile_url}. Return code: {proc.returncode}, Error: {err.strip()}"
                )
        except TimeoutExpired:
            logger.error(f"SpotDL meta command timed out for {self.profile_url}.")
            if proc:
                proc.kill()
        except FileNotFoundError:
            logger.error(
                "SpotDL command not found. Please ensure spotdl is installed and in your PATH."
            )
        except Exception as e:
            logger.error(
                f"Exception during playlist name extraction for {self.profile_url}: {e}",
                exc_info=True,
            )
        finally:
            if proc and proc.poll() is None:
                proc.kill()

        # Fallback: derive from URL path, strip query params like ?si=...
        url = self.profile_url.split("?")[0].rstrip("/")
        parts = url.split("/")
        tail = parts[-1] if parts else "playlist"
        fallback_name = tail or "playlist"
        logger.info(f"Falling back to URL-derived playlist name: {fallback_name}")
        return fallback_name

    def extract(self) -> List[SongRecord]:
        cmd = self._build_base_cmd("url")
        proc: Popen | None = None
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
            while proc.poll() is None:
                try:
                    if proc.stdout and proc.stdout.readable():
                        line = proc.stdout.readline()
                        if line:
                            stdout_chunks.append(line)
                            logger.debug(f"SpotDL STDOUT: {line.strip()}")
                    if proc.stderr and proc.stderr.readable():
                        line = proc.stderr.readline()
                        if line:
                            stderr_chunks.append(line)
                            logger.debug(f"SpotDL STDERR: {line.strip()}")
                except Exception as e:
                    logger.warning(f"Error reading process output: {e}")

            # Ensure all output is read after process exits
            out, err = proc.communicate()
            if out:
                stdout_chunks.append(out)
            if err:
                stderr_chunks.append(err)

        except KeyboardInterrupt:
            logger.info("Playlist extraction interrupted by user.")
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except TimeoutExpired:
                    proc.kill()
            raise
        except FileNotFoundError:
            logger.error(
                "SpotDL command not found. Please ensure spotdl is installed and in your PATH."
            )
            raise RuntimeError("SpotDL not found.")
        except Exception as e:
            logger.error(
                f"Exception during URL extraction for {self.profile_url}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to extract playlist URLs: {e}")
        finally:
            if proc and proc.poll() is None:
                proc.kill()

        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)

        if proc is None or proc.returncode != 0:
            error_msg = f"SpotDL URL command failed for {self.profile_url}. Return code: {proc.returncode if proc else 'N/A'}.\nSTDERR:\n{stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        urls = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not urls:
            logger.info(f"No URLs extracted for {self.profile_url}.")
            return []

        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        logger.info(f"Extracted {len(unique_urls)} unique URLs for {self.profile_url}.")

        records: List[SongRecord] = []
        for url in unique_urls:
            safe_id = sub(r"[^a-zA-Z0-9]", "", url)[-32:]
            record = SongRecord(
                id=safe_id,
                title="",  # spotdl url command doesn't provide metadata
                artists=[],
                album="",
                playlist_id="unknown",
                url=url,
            )
            records.append(record)
        return records
