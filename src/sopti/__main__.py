from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, RawTextHelpFormatter
from typing import Type
from argparse import ArgumentTypeError
from shutil import which
from pathlib import Path
from datetime import datetime
from .config import Config
from .orchestrator import Orchestrator


class HelpFormatter(ArgumentDefaultsHelpFormatter, RawTextHelpFormatter):
    pass


def positive_int(value: str) -> Type[int]:
    try:
        iv = int(value)
        if iv <= 0:
            raise ArgumentTypeError("workers must be a positive integer")
        return int(iv)
    except ValueError:
        raise ArgumentTypeError("workers must be a positive integer")


def ensure_dependencies() -> None:
    missing: list[str] = []
    if which("spotdl") is None:
        missing.append("spotdl")
    if which("ffmpeg") is None:
        missing.append("ffmpeg")
    if missing:
        raise SystemExit(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". Install them and try again."
        )


def looks_like_spotify_url(url: str) -> bool:
    return url.startswith("https://open.spotify.com/")


def append_log(message: str) -> None:
    log_file = Path.home() / ".cache" / "sopti" / "sopti.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass


def main() -> None:
    parser = ArgumentParser(
        description=(
            "Sopti - Advanced Spotify Playlist Downloader\n\n"
            "Examples:\n"
            "  sopti --profile 'https://open.spotify.com/playlist/... '\n"
            "  sopti --sync\n"
            "  sopti --login --id '<client_id>' --crid '<client_secret>'\n"
            "  sopti --profile '<url>' --format flac --bitrate 320k --workers 6\n"
            "  sopti --my --format flac\n"
        ),
        formatter_class=HelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="Sopti 0.1.2",
        help="Show version and exit.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        help="Spotify profile or playlist URL. Repeatable. If omitted, all configured profiles are synced.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Enable sync mode. With --quiet (default in sync), runs without console output and logs errors.",
    )
    parser.add_argument(
        "--my",
        action="store_true",
        help="Download your own configured playlists (uses profiles from config). Implies --user-auth.",
    )
    parser.add_argument(
        "--user-auth",
        action="store_true",
        help="Use user authentication with spotdl (required for private/self playlists).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output (progress and summary). Errors are written to the log file.",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Store Spotify API client credentials (use with --id and --crid).",
    )
    parser.add_argument(
        "--id",
        dest="client_id",
        default=None,
        help="Spotify client ID (used with --login).",
    )
    parser.add_argument(
        "--crid",
        dest="client_secret",
        default=None,
        help="Spotify client secret (used with --login).",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Destination folder for music downloads. Defaults to the configured music directory.",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="Number of parallel downloads to run.",
    )
    parser.add_argument(
        "--format",
        dest="preferred_format",
        default=None,
        choices=["mp3", "flac", "ogg", "opus", "m4a", "wav"],
        help="Audio format for downloads.",
    )
    parser.add_argument(
        "--bitrate",
        dest="bitrate",
        default=None,
        help="Bitrate (e.g., auto, 128k, 320k).",
    )

    args = parser.parse_args()

    ensure_dependencies()

    config = Config()

    if args.login:
        if not args.client_id or not args.client_secret:
            raise SystemExit("--login requires both --id and --crid")
        config.data["spotify_client_id"] = args.client_id
        config.data["spotify_client_secret"] = args.client_secret
        config.save(config.data)
        print("Credentials saved to config.")
        return

    dest = Path(args.dest or config.data["music_dir"])
    workers = args.workers or int(config.data.get("workers", 3))
    preferred_format = args.preferred_format or config.data.get(
        "preferred_format", "flac"
    )
    bitrate = args.bitrate or config.data.get("bitrate", "auto")

    if args.my:
        profiles = list(config.data.get("profiles", []))
    else:
        profiles = args.profile if args.profile else list(config.data.get("profiles", []))

    if not profiles:
        raise SystemExit(
            "No profiles provided and no configured profiles in config. Use --profile or add profiles to config."
        )

    def looks_like_spotify_url(url: str) -> bool:
        return url.startswith("https://open.spotify.com/")

    bad_urls = [p for p in profiles if not looks_like_spotify_url(p)]
    if bad_urls:
        raise SystemExit(
            "Invalid profile URLs: " + ", ".join(bad_urls)
        )

    quiet = bool(args.quiet or args.sync)
    user_auth = bool(args.user_auth or args.my)

    for p in profiles:
        try:
            orchestrator = Orchestrator(profile_url=p, dest=dest, max_workers=workers)
            orchestrator.preferred_format = preferred_format
            orchestrator.bitrate = bitrate
            orchestrator.client_id = config.data.get("spotify_client_id")
            orchestrator.client_secret = config.data.get("spotify_client_secret")
            orchestrator.verbose = not quiet
            orchestrator.user_auth = user_auth
            orchestrator.run()
        except KeyboardInterrupt:
            if not quiet:
                print("\nCancelled by user.")
            break
        except Exception as e:
            msg = f"Failed processing {p}: {e}"
            if quiet:
                append_log(msg)
            else:
                print(msg)
            continue


if __name__ == "__main__":
    main()
