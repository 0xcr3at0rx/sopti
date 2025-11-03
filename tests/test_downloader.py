from __future__ import annotations
from pathlib import Path
from typing import List

import sopti.downloader as dl
from sopti.models import SongRecord


class CapturePopen:
    last_cmd: List[str] | None = None

    def __init__(self, cmd, stdout=None, stderr=None, text=False):
        CapturePopen.last_cmd = cmd
        self._ret = 0
        self._out = ""
        self._err = ""

    def poll(self):
        # Immediately finish
        return self._ret

    def communicate(self, timeout=1):
        return self._out, self._err

    @property
    def stdout(self):
        return Dummy()

    @property
    def stderr(self):
        return Dummy()


class Dummy:
    closed = False

    def readable(self):
        return False

    def readline(self):
        return ""


def test_downloader_includes_archive(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dl, "Popen", CapturePopen)
    w = dl.SpotDLWrapper(dest=tmp_path, preferred_format="flac", bitrate="320k")
    song = SongRecord(id="1", title="t", artists=["a"], album="", playlist_id="p", url="https://open.spotify.com/track/1")
    ok = w.download(song)
    assert ok is True
    cmd = CapturePopen.last_cmd
    assert cmd is not None
    assert "--archive" in cmd
    # Ensure archive path points under dest
    idx = cmd.index("--archive")
    assert Path(cmd[idx + 1]).parent == tmp_path
