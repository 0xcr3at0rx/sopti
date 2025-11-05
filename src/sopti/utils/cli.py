from __future__ import annotations
from argparse import ArgumentTypeError
from shutil import which
from .logging import setup_logging

logger = setup_logging(__name__)


def positive_int(value: str) -> int:
    try:
        iv = int(value)
        if iv <= 0:
            raise ArgumentTypeError("workers must be a positive integer")
        return iv
    except ValueError:
        raise ArgumentTypeError("workers must be a positive integer")


def ensure_dependencies() -> None:
    missing: list[str] = []
    if which("spotdl") is None:
        missing.append("spotdl")
    if which("ffmpeg") is None:
        missing.append("ffmpeg")
    if missing:
        logger.error(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". Install them and try again."
        )
        raise SystemExit(1)


def looks_like_spotify_url(url: str) -> bool:
    return url.startswith("https://open.spotify.com/")
