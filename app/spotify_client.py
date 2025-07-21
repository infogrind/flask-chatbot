import logging
import urllib.parse

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
        logger.info(f"Creating playlist '{name}'")
        user_id = self.client.me()["id"]
        playlist = self.client.user_playlist_create(
            user_id, name, public=True, description=description
        )
        logger.info(f"Adding items to playlist: {track_uris}")
        self.client.playlist_add_items(playlist["id"], track_uris)
        return playlist["id"]

    def search_songs(
        self, title: str, artist: str, limit: int = 5
    ) -> list[dict[str, str]]:
        """Searches for songs on Spotify.

        Args:
            title: The title of the song.
            artist: The artist of the song.
            limit: The maximum number of songs to return.

        Returns:
            A list of songs, each a dictionary with song details.
        """
        encoded_title = urllib.parse.quote(title)
        encoded_artist = urllib.parse.quote(artist)
        query = f"track:{encoded_title} {encoded_artist}"
        logger.info(f"Searching songs with query '{query}'.")
        results = self.client.search(q=query, type="track", limit=limit)
        if results:
            logger.info(f"Found {len(results)} results.")
            print("%s" % results)
        else:
            logger.info("Results was empty")
        songs = []
        if results and results["tracks"]["items"]:
            for item in results["tracks"]["items"]:
                songs.append(
                    {
                        "name": item["name"],
                        "artist": ", ".join(
                            artist["name"] for artist in item["artists"]
                        ),
                        "album": item["album"]["name"],
                        "track_id": item["id"],
                    }
                )
        logger.info(f"Returning songs: {songs}.")
        return songs
