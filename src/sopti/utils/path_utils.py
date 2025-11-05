from __future__ import annotations
from pathlib import Path
from re import sub as _re_sub


def safe_folder_name(name: str, base_path: Path) -> Path:
    safe = _re_sub(r"[^\w\-\. ]+", "_", name).strip("._ ")
    if not safe:
        safe = "playlist"
    # Truncate to avoid OS path length issues
    if len(safe) > 80:
        safe = safe[:80]
    return base_path / safe
