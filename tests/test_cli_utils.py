from __future__ import annotations
from pathlib import Path
import builtins
import io
import os
import pytest

import sopti.__main__ as cli


def test_looks_like_spotify_url():
    assert cli.looks_like_spotify_url("https://open.spotify.com/playlist/abc")
    assert not cli.looks_like_spotify_url("https://example.com/")


def test_validate_bitrate_accepts_valid(monkeypatch):
    assert cli.validate_bitrate("auto")
    assert cli.validate_bitrate("disable")
    assert cli.validate_bitrate("320k")
    assert cli.validate_bitrate("128k")


def test_validate_bitrate_rejects_invalid():
    assert cli.validate_bitrate("320") is False
    assert cli.validate_bitrate("foo") is False


def test_ensure_writable_dir(tmp_path: Path):
    cli.ensure_writable_dir(tmp_path)
    # Should not raise and should be writable
    p = tmp_path / "x.txt"
    p.write_text("ok", encoding="utf-8")
    assert p.exists()
