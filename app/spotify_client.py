import spotipy


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
                    }
                )
            if results["next"]:
                results = self.client.next(results)
            else:
                results = None
        return liked_songs

    def get_playlist_contents(self, playlist_id: str):
        """Gets the tracks in a specific playlist."""
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
                        }
                    )
            if results["next"]:
                results = self.client.next(results)
            else:
                results = None
        return tracks
