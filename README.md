# Sopti

Sopti is a resilient, production-ready orchestrator for downloading Spotify playlists and profiles using spotdl. It focuses on reliability, high-quality output, clear progress, quiet background sync, and safe shutdown.

## Features
- Parallel downloads with bounded worker pool
- Robust cancellation (Ctrl-C) with clean shutdown
- Two-pass download with recheck to recover transient failures
- Quiet sync mode (no console output; errors logged to a file)
- Per-playlist folder naming (derived from metadata), sanitized and truncated
- High-quality output: configurable format and bitrate
- Duplicate-safe via a local SQLite database
- User-auth support for private/self playlists

## Requirements
- Python 3.13+
- `spotdl` v4+
- `ffmpeg`
- `tqdm`

## Installation
Using uv (recommended):
```bash
# From repo root
uv venv
uv sync

# Editable install
uv pip install -e .

# Verify
sopti --help
```

Alternative (wheel/sdist):
```bash
uv build
uv pip install dist/*.whl
```

## Quick Start
Download a specific playlist or profile:
```bash
sopti --profile "https://open.spotify.com/playlist/..." --workers 6
```

Quiet sync of all configured profiles (background-like; errors go to log):
```bash
sopti --sync
# Log file: ~/.cache/sopti/sopti.log
```

Save Spotify API credentials (optional, used by spotdl):
```bash
sopti --login --id "<CLIENT_ID>" --crid "<CLIENT_SECRET>"
```

High-quality settings (override config):
```bash
sopti --profile "<url>" --format flac --bitrate 320k
```

Self/private playlists (requires user auth):
```bash
# Use your configured profiles from config
sopti --my

# Or a specific URL with user auth
sopti --profile "<url>" --user-auth
```

## CLI Overview
- `--profile <url>` (repeatable): run for the provided URLs
- `--sync`: process all `profiles` from config (quiet by default)
- `--my`: process your configured profiles and imply `--user-auth`
- `--user-auth`: use user authentication (required for private/self playlists)
- `--quiet`: suppress progress/summary; errors are logged to file
- `--dest <path>`: destination directory (defaults to config `music_dir`)
- `--workers <n>`: max parallel downloads (must be > 0; clamped to 64)
- `--format <fmt>`: one of `mp3|flac|ogg|opus|m4a|wav`
- `--bitrate <val>`: `auto|disable|<number>k` (e.g. `320k`)
- `--login --id <CLIENT_ID> --crid <CLIENT_SECRET>`: store credentials
- `-v / --version`: show version and exit

Run `sopti --help` for examples and default values.

## Configuration
Config file: `~/.config/sopti/config.json`

Created on first run with defaults:
```json
{
  "music_dir": "<HOME>/Music",
  "workers": 3,
  "profiles": [],
  "preferred_format": "flac",
  "bitrate": "auto",
  "spotify_client_id": "",
  "spotify_client_secret": ""
}
```

- `music_dir`: destination when `--dest` is not provided
- `workers`: default concurrency when `--workers` is not provided
- `profiles`: used by `--sync` and `--my`
- `preferred_format` and `bitrate`: quality defaults
- `spotify_client_id` / `spotify_client_secret`: saved via `--login`

## Behavior & Folder Structure
- Tracks are downloaded under the destination directory.
- For playlist URLs, Sopti creates a sanitized subfolder using playlist metadata (truncates long names).
- Already-downloaded tracks are skipped using both the SQLite DB and `--overwrite skip` to avoid duplicates.

## Logging
- Quiet mode (`--quiet` or `--sync`) writes errors to: `~/.cache/sopti/sopti.log`
- In verbose mode, errors are also appended to the same log for auditing.

## Reliability Notes
- Preflight checks ensure `spotdl` and `ffmpeg` are installed before running.
- Destination directories are created and write-checked.
- Bitrate is validated: only `auto|disable|<num>k` are accepted.
- A second download pass retries any tracks still missing from the DB.
- Ctrl-C cleanly cancels downloads, closes resources, and exits.

## Troubleshooting
- "Missing dependencies: spotdl, ffmpeg": install them and ensure they are on PATH.
- Permission errors: choose a writable `--dest` or set a writable `music_dir` in config.
- Nothing downloaded:
  - Verify the URL and that it is public/accessible
  - Reduce `--workers`
  - Use `--user-auth` for private/self playlists
  - Check `~/.cache/sopti/sopti.log` for errors
- Playlist folder name looks odd:
  - Sopti prefers metadata name; if not available, it falls back to the URL tail (with query stripped). Use `--user-auth` if the playlist is private.

## Uninstall
```bash
uv pip uninstall sopti
```

## License
MIT — see [LICENSE](LICENSE).
