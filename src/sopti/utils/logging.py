from __future__ import annotations
import logging
from pathlib import Path


def setup_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Ensure the cache directory exists for the log file
    log_dir = Path.home() / ".cache" / "sopti"
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_dir / "sopti.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
