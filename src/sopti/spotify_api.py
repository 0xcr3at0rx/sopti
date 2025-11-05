from __future__ import annotations
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from sopti.utils.logging import setup_logging

logger = setup_logging(__name__)


class SpotifyAPIClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._sp_client = None

    def _get_spotify_client(self) -> spotipy.Spotify | None:
        if not self.client_id or not self.client_secret:
            logger.warning(
                "Spotify client ID or secret not provided. Cannot use Spotify API. "
                "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."
            )
            return None

        if self._sp_client is None:
            try:
                if not self.client_id or not self.client_secret:
                    logger.error(
                        "Spotify client ID or secret is empty. Cannot initialize Spotify API client."
                    )
                    return None

                self._sp_client = spotipy.Spotify(
                    client_credentials_manager=SpotifyClientCredentials(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                    )
                )
                logger.info(
                    f"Spotify API client initialized successfully with client ID: {self.client_id[:4]}...{self.client_id[-4:]}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Spotify API client: {e}")
                self._sp_client = None
        return self._sp_client

    def _extract_playlist_id(self, playlist_url: str) -> str | None:
        # Regex to match Spotify playlist URLs and extract the ID
        # Handles formats like:
        # https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
        # spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
        # 37i9dQZF1DXcBWIGoYBM5M (direct ID)
        import re

        match = re.search(r"(?:playlist[/:])?([a-zA-Z0-9]{22})", playlist_url)
        if match:
            return match.group(1)
        return None

    def get_playlist_name(self, playlist_url: str) -> str | None:
        sp = self._get_spotify_client()
        if sp is None:
            logger.warning("Spotify client not available. Cannot fetch playlist name.")
            return None

        playlist_id = self._extract_playlist_id(playlist_url)
        if not playlist_id:
            logger.warning(f"Could not extract playlist ID from URL: {playlist_url}")
            return None

        try:
            playlist = sp.playlist(playlist_id)
            if playlist and "name" in playlist:
                logger.info(
                    f"Fetched playlist name '{playlist['name']}' for ID {playlist_id} from Spotify API."
                )
                return playlist["name"]
            else:
                logger.warning(
                    f"Could not fetch playlist name for ID {playlist_id} from Spotify API. Response: {playlist}"
                )
                return None
        except spotipy.exceptions.SpotifyException as se:
            logger.error(
                f"Spotify API error fetching playlist name for {playlist_url} (ID: {playlist_id}): {se}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error fetching playlist name from Spotify API for {playlist_url} (ID: {playlist_id}): {e}",
                exc_info=True,
            )
            return None
