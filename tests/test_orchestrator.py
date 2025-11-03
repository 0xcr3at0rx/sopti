from __future__ import annotations
from pathlib import Path
from typing import List

import types
import sopti.orchestrator as orch
from sopti.models import SongRecord


class FakeDB:
    def __init__(self):
        self._have: set[str] = set()

    def exists(self, song_id: str) -> bool:
        return song_id in self._have

    def add(self, record: SongRecord) -> None:
        self._have.add(record.id)

    def close(self) -> None:
        pass


class FakeWrapper:
    def __init__(self, dest: Path, **kwargs):
        self.dest = dest
        self.calls: int = 0

    def download(self, song: SongRecord, cancel_event=None) -> bool:
        # First pass: only some succeed, second pass: others succeed
        self.calls += 1
        return (self.calls % 2) == 0


def test_orchestrator_multipass(monkeypatch, tmp_path: Path):
    # Patch DBManager and SpotDLWrapper
    monkeypatch.setattr(orch, "DBManager", lambda: FakeDB())
    monkeypatch.setattr(orch, "SpotDLWrapper", FakeWrapper)

    # Prepare orchestrator instance with a fake songs list via extractor
    songs = [SongRecord(id=str(i), title="", artists=[], album="", playlist_id="", url=f"u{i}") for i in range(4)]

    class FakeExtractor:
        def __init__(self, *a, **k):
            pass
        def extract(self) -> List[SongRecord]:
            return songs
        def get_playlist_name(self) -> str:
            return "X"

    monkeypatch.setattr(orch, "PlaylistExtractor", FakeExtractor)

    o = orch.Orchestrator(profile_url="https://open.spotify.com/playlist/x", dest=tmp_path, max_workers=2)
    o.verbose = False
    o.run()
    # All should be added after two passes due to alternating success
    db = o.db
    assert isinstance(db, FakeDB)
    for s in songs:
        assert db.exists(s.id)
