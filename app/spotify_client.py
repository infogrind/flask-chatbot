import logging

import spotipy

logger = logging.getLogger(__name__)


class SpotifyClient:
    """A wrapper for the Spotipy library."""

    def __init__(self, auth_manager):
        self.client = spotipy.Spotify(auth_manager=auth_manager)

    def get_user_playlists(self):
        """Gets the current user's playlists."""
        playlists = []
        results = self.client.current_user_playlists()
        while results:
            for item in results["items"]:
                # Only include playlists owned by the user
                if item["owner"]["id"] == self.client.me()["id"]:
                    playlists.append(
                        {
                            "name": item["name"],
                            "playlist_id": item["id"],
                            "description": item["description"],
                            "tracks": item["tracks"]["total"],
                        }
                    )
            if results["next"]:
                results = self.client.next(results)
            else:
                results = None
        return playlists

    def get_liked_songs(self):
        """Gets the current user's liked songs."""
        liked_songs = []
        results = self.client.current_user_saved_tracks()
        while results:
            for item in results["items"]:
                track = item["track"]
                liked_songs.append(
                    {
                        "name": track["name"],
                        "artist": ", ".join(
                            artist["name"] for artist in track["artists"]
                        ),
                        "album": track["album"]["name"],
                        "track_id": track["id"],
                    }
                )
            if results["next"]:
                results = self.client.next(results)
            else:
                results = None
        return liked_songs

    def get_playlist_contents(self, playlist_id: str):
        """Gets the tracks in a specific playlist."""
        logger.info(f"Getting contents for playlist: {playlist_id}")
        tracks = []
        results = self.client.playlist_items(playlist_id)
        while results:
            for item in results["items"]:
                track = item["track"]
                if track:
                    tracks.append(
                        {
                            "name": track["name"],
                            "artist": ", ".join(
                                artist["name"] for artist in track["artists"]
                            ),
                            "album": track["album"]["name"],
                            "track_id": track["id"],
                        }
                    )
            if results["next"]:
                results = self.client.next(results)
            else:
                results = None
        return tracks

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
        user_id = self.client.me()["id"]
        playlist = self.client.user_playlist_create(
            user_id, name, public=True, description=description
        )
        self.client.playlist_add_items(playlist["id"], track_uris)
        return playlist["id"]
