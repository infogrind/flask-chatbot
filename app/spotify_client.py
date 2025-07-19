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
