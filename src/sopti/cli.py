from __future__ import annotations
from argparse import (
    ArgumentParser,
    ArgumentDefaultsHelpFormatter,
    RawTextHelpFormatter,
)
from pathlib import Path
from .config import Config
from .orchestrator import Orchestrator
from .utils.logging import setup_logging
from .utils.cli import positive_int, ensure_dependencies, looks_like_spotify_url

logger = setup_logging(__name__)


class HelpFormatter(ArgumentDefaultsHelpFormatter, RawTextHelpFormatter):
    pass


def get_parser() -> ArgumentParser:
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
        help="Spotify client ID (used with --login).",
    )
    parser.add_argument(
        "--crid",
        dest="client_secret",
        help="Spotify client secret (used with --login).",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Destination folder for music downloads. Defaults to the configured music directory.",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        help="Number of parallel downloads to run.",
    )
    parser.add_argument(
        "--format",
        dest="preferred_format",
        choices=["mp3", "flac", "ogg", "opus", "m4a", "wav"],
        help="Audio format for downloads.",
    )
    parser.add_argument(
        "--bitrate",
        dest="bitrate",
        help="Bitrate (e.g., auto, 128k, 320k).",
    )
    return parser


def main() -> None:
    parser = get_parser()
    args = parser.parse_args()

    ensure_dependencies()

    config = Config()

    if args.login:
        handle_login(args, config)
        return

    dest, workers, preferred_format, bitrate = get_download_settings(args, config)
    profiles = get_profiles(args, config)

    bad_urls = [p for p in profiles if not looks_like_spotify_url(p)]
    if bad_urls:
        logger.error("Invalid profile URLs: " + ", ".join(bad_urls))
        raise SystemExit(1)

    quiet = bool(args.quiet or args.sync)
    user_auth = bool(args.user_auth or args.my)

    process_profiles(
        profiles,
        dest,
        workers,
        preferred_format,
        bitrate,
        quiet,
        user_auth,
        config,
    )


def get_download_settings(args, config: Config) -> tuple[Path, int, str, str]:
    dest = args.dest or Path(config.data["music_dir"])
    workers = args.workers or config.data.get("workers", 3)
    preferred_format = args.preferred_format or config.data.get(
        "preferred_format", "flac"
    )
    bitrate = args.bitrate or config.data.get("bitrate", "auto")
    return dest, workers, preferred_format, bitrate


def handle_login(args, config: Config) -> None:
    if not args.client_id or not args.client_secret:
        logger.error("--login requires both --id and --crid")
        raise SystemExit(1)
    config.data["spotify_client_id"] = args.client_id
    config.data["spotify_client_secret"] = args.client_secret
    config.save(config.data)
    logger.info("Credentials saved to config.")
    print("Credentials saved to config.")


def get_profiles(args, config: Config) -> list[str]:
    if args.my:
        profiles = list(config.data.get("profiles", []))
        if not profiles:
            logger.error("No configured profiles found for --my option.")
            raise SystemExit(1)
    else:
        profiles = (
            args.profile if args.profile else list(config.data.get("profiles", []))
        )

    if not profiles:
        logger.error(
            "No profiles provided via --profile and no configured profiles in config. Use --profile or add profiles to config."
        )
        raise SystemExit(1)
    return profiles


def process_profiles(
    profiles: list[str],
    dest: Path,
    workers: int,
    preferred_format: str,
    bitrate: str,
    quiet: bool,
    user_auth: bool,
    config: Config,
) -> None:
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
            logger.info(f"Processing of {p} cancelled by user.")
            break
        except SystemExit:
            # Allow SystemExit to propagate for controlled exits
            raise
        except Exception as e:
            msg = f"Failed processing {p}: {e}"
            logger.error(msg, exc_info=True)
            if not quiet:
                print(msg)
            continue
