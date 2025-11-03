from __future__ import annotations
from pathlib import Path
from json import load, dump


class CacheManager:
    def __init__(self) -> None:
        self.cache_dir = Path.home() / ".cache" / "sopti"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "downloads.json"
        if not self.cache_file.exists():
            self.save({})

    def load(self) -> dict:
        with open(self.cache_file, "r", encoding="utf-8") as f:
            return load(f)

    def save(self, data: dict) -> None:
        with open(self.cache_file, "w", encoding="utf-8") as f:
            dump(data, f, indent=4)
