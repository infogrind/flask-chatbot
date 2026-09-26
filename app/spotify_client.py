import logging
from collections.abc import Iterator
from itertools import batched
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

# Spotify API limits.
MAX_SEARCH_LIMIT = 50
MAX_TRACKS_PER_ADD = 100


def summarize_track(track: dict[str, Any]) -> dict[str, str]:
    """Reduces a Spotify track object to the fields the model needs."""
    return {
        "name": track["name"],
        "artist": ", ".join(artist["name"] for artist in track["artists"]),
        "album": track["album"]["name"],
        "track_id": track["id"],
    }


class SpotifyClient:
    """A wrapper for the Spotipy library."""

    def __init__(self, auth_manager: SpotifyOAuth) -> None:
        self.client = spotipy.Spotify(auth_manager=auth_manager)

    def _paginate(self, results: dict[str, Any] | None) -> Iterator[dict[str, Any]]:
        """Yields the items of a paged Spotify result, following `next` links."""
        while results:
            yield from results["items"]
            results = self.client.next(results) if results["next"] else None

    def get_user_playlists(self) -> list[dict[str, Any]]:
        """Gets the playlists owned by the current user."""
        user_id = self.client.me()["id"]
        return [
            {
                "name": item["name"],
                "playlist_id": item["id"],
                "description": item["description"],
                "tracks": item["tracks"]["total"],
            }
            for item in self._paginate(self.client.current_user_playlists())
            if item["owner"]["id"] == user_id
        ]

    def get_liked_songs(self) -> list[dict[str, str]]:
        """Gets the current user's liked songs."""
        return [
            summarize_track(item["track"])
            for item in self._paginate(self.client.current_user_saved_tracks())
        ]

    def get_playlist_contents(self, playlist_id: str) -> list[dict[str, str]]:
        """Gets the tracks in a specific playlist."""
        logger.info("Getting contents for playlist: %s", playlist_id)
        return [
            summarize_track(item["track"])
            for item in self._paginate(self.client.playlist_items(playlist_id))
            # Removed or local tracks have no track object
            if item["track"]
        ]

    def create_playlist(
        self, name: str, description: str, track_uris: list[str]
    ) -> str:
        """Creates a new playlist and adds tracks to it.

        Args:
            name: The name of the playlist.
            description: The description of the playlist.
            track_uris: A list of Spotify track URIs to add to the playlist.

        Returns:
            The ID of the newly created playlist.
        """
        logger.info("Creating playlist '%s' with %d tracks", name, len(track_uris))
        user_id = self.client.me()["id"]
        playlist = self.client.user_playlist_create(
            user_id, name, public=True, description=description
        )
        for batch in batched(track_uris, MAX_TRACKS_PER_ADD):
            self.client.playlist_add_items(playlist["id"], list(batch))
        return playlist["id"]

    def search_songs(
        self, title: str, artist: str, limit: int = 5
    ) -> list[dict[str, str]]:
        """Searches for songs on Spotify.

        Args:
            title: The title of the song.
            artist: The artist of the song.
            limit: The maximum number of songs to return, clamped to 1-50.

        Returns:
            A list of songs, each a dictionary with song details.
        """
        query = f'track:"{title}" "{artist}"'
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))
        logger.info("Searching songs with query '%s'", query)
        results = self.client.search(q=query, type="track", limit=limit)
        items = results["tracks"]["items"] if results else []
        logger.info("Found %d songs", len(items))
        return [summarize_track(item) for item in items]
