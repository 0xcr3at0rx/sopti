from __future__ import annotations
from pathlib import Path
from json import load, dump
from os import getenv


class Config:
    def __init__(self) -> None:
        self.config_dir = Path.home() / ".config" / "sopti"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.default_config = {
            "music_dir": str(Path.home() / "Music"),
            "workers": 3,
            "profiles": [],  # List of playlist/profile URLs for sync-all
            "preferred_format": "flac",  # spotdl formats: mp3, flac, ogg, opus, m4a, wav
            "bitrate": "auto",  # spotdl bitrates: auto|disable|128k|320k|...
            "spotify_client_id": getenv("SPOTIFY_CLIENT_ID", ""),
            "spotify_client_secret": getenv("SPOTIFY_CLIENT_SECRET", ""),
        }
        self.data = self.load()

    def load(self) -> dict:
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                return load(f)
        else:
            self.save(self.default_config)
            return self.default_config

    def save(self, data: dict) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            dump(data, f, indent=4)
