from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class SongRecord:
    id: str
    title: str
    artists: List[str]
    album: str
    playlist_id: str
    url: str
