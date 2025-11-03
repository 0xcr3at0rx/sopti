from __future__ import annotations
from subprocess import Popen, PIPE
from re import sub
from typing import List, Optional
from .models import SongRecord


class PlaylistExtractor:
    def __init__(self, profile_url: str, client_id: str | None = None, client_secret: str | None = None, user_auth: bool = False):
        self.profile_url = profile_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_auth = user_auth

    def get_playlist_name(self) -> str:
        cmd = ["spotdl", "meta", self.profile_url, "--json"]
        if self.client_id:
            cmd += ["--client-id", self.client_id]
        if self.client_secret:
            cmd += ["--client-secret", self.client_secret]
        if self.user_auth:
            cmd += ["--user-auth"]
        proc: Popen | None = None
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
            out, err = proc.communicate(timeout=30)
            if proc.returncode == 0 and out:
                from json import loads as _json_loads
                try:
                    data = _json_loads(out)
                    # Try dict first
                    candidate = None
                    if isinstance(data, dict):
                        for key in ("name", "title", "playlist_name", "album", "album_name"):
                            val = data.get(key)
                            if isinstance(val, str) and val.strip():
                                candidate = val.strip()
                                break
                    # Sometimes spotdl may return a list
                    if candidate is None and isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                for key in ("name", "title", "playlist_name", "album", "album_name"):
                                    val = item.get(key)
                                    if isinstance(val, str) and val.strip():
                                        candidate = val.strip()
                                        break
                            if candidate:
                                break
                    if candidate:
                        return candidate
                except Exception:
                    pass
        except Exception:
            pass
        # Fallback: derive from URL path, strip query params like ?si=...
        url = self.profile_url
        try:
            url = url.split("?")[0]
        except Exception:
            pass
        parts = url.rstrip("/").split("/")
        tail = parts[-1] if parts else "playlist"
        return tail or "playlist"

    def extract(self) -> List[SongRecord]:
        cmd = ["spotdl", "url", self.profile_url]
        if self.client_id:
            cmd += ["--client-id", self.client_id]
        if self.client_secret:
            cmd += ["--client-secret", self.client_secret]
        if self.user_auth:
            cmd += ["--user-auth"]
        proc: Popen | None = None
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            while True:
                ret = proc.poll()
                if ret is not None:
                    try:
                        out, err = proc.communicate(timeout=1)
                        if out:
                            stdout_chunks.append(out)
                        if err:
                            stderr_chunks.append(err)
                    except Exception:
                        pass
                    break
                try:
                    if proc.stdout is not None and not proc.stdout.closed and proc.stdout.readable():
                        chunk = proc.stdout.readline()
                        if chunk:
                            stdout_chunks.append(chunk)
                    if proc.stderr is not None and not proc.stderr.closed and proc.stderr.readable():
                        err = proc.stderr.readline()
                        if err:
                            stderr_chunks.append(err)
                except Exception:
                    pass
        except KeyboardInterrupt:
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            raise
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        if proc is None or proc.returncode != 0:
            raise RuntimeError(f"Failed to extract playlist: {stderr}")

        urls = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not urls:
            return []
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        records: List[SongRecord] = []
        for url in unique_urls:
            safe_id = sub(r"[^a-zA-Z0-9]", "", url)[-32:]
            record = SongRecord(
                id=safe_id,
                title="",
                artists=[],
                album="",
                playlist_id="unknown",
                url=url,
            )
            records.append(record)
        return records
