from __future__ import annotations
from sqlite3 import connect
from pathlib import Path
from .models import SongRecord


class DBManager:
    def __init__(self) -> None:
        self.db_path = Path.home() / ".cache" / "sopti" / "downloads.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = connect(self.db_path)
        self._init_tables()

    def _init_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS downloads (
        id TEXT PRIMARY KEY,
        title TEXT,
        artists TEXT,
        album TEXT,
        playlist_id TEXT,
        url TEXT
        )"""
            )

    def exists(self, song_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM downloads WHERE id= ?", (song_id,))
        return cur.fetchone() is not None

    def add(self, record: SongRecord) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO downloads VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.title,
                    ",".join(record.artists),
                    record.album,
                    record.playlist_id,
                    record.url,
                ),
            )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
