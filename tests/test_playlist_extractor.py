from __future__ import annotations
from typing import Any
from subprocess import Popen
import types
import builtins

import sopti.playlist as pl


class FakePopen:
    def __init__(self, cmd, stdout=None, stderr=None, text=False):
        self.cmd = cmd
        self._stdout = []
        self._stderr = []
        self._ret = 0
        self._polled = False
        if "meta" in cmd:
            self._out = '{"name": "My Playlist"}'
        else:
            self._out = "\n".join([
                "https://open.spotify.com/track/1",
                "https://open.spotify.com/track/2",
                "https://open.spotify.com/track/1",  # duplicate
            ])
        self._err = ""

    def poll(self):
        if not self._polled:
            self._polled = True
            return None
        return self._ret

    def communicate(self, timeout=1):
        return self._out, self._err

    @property
    def stdout(self):
        return DummyStream(self._out)

    @property
    def stderr(self):
        return DummyStream(self._err)


class DummyStream:
    def __init__(self, data: str):
        self._lines = data.splitlines(keepends=True)
        self._idx = 0
        self.closed = False

    def readable(self):
        return True

    def readline(self):
        if self._idx >= len(self._lines):
            return ""
        v = self._lines[self._idx]
        self._idx += 1
        return v


def test_get_playlist_name(monkeypatch):
    monkeypatch.setattr(pl, "Popen", FakePopen)
    ex = pl.PlaylistExtractor("https://open.spotify.com/playlist/abc")
    assert ex.get_playlist_name() == "My Playlist"


def test_extract_dedup(monkeypatch):
    monkeypatch.setattr(pl, "Popen", FakePopen)
    ex = pl.PlaylistExtractor("https://open.spotify.com/playlist/abc")
    recs = ex.extract()
    urls = [r.url for r in recs]
    assert urls == [
        "https://open.spotify.com/track/1",
        "https://open.spotify.com/track/2",
    ]
