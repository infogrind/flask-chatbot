import urllib.parse
from unittest.mock import MagicMock, patch

from app.spotify_client import SpotifyClient


def test_get_user_playlists():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.me.return_value = {"id": "test_user"}
        mock_spotify_instance.current_user_playlists.return_value = {
            "items": [
                {
                    "id": "test_playlist_id",
                    "owner": {"id": "test_user"},
                    "name": "Test Playlist",
                    "description": "A test playlist",
                    "tracks": {"total": 10},
                }
            ],
            "next": None,
        }
        client = SpotifyClient(auth_manager=mock_auth_manager)

        # Act
        playlists = client.get_user_playlists()

        # Assert
        assert len(playlists) == 1
        assert playlists[0]["name"] == "Test Playlist"
        mock_spotify_instance.current_user_playlists.assert_called_once()


def test_get_liked_songs():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.current_user_saved_tracks.return_value = {
            "items": [
                {
                    "track": {
                        "id": "test_song_id",
                        "name": "Test Song",
                        "artists": [{"name": "Test Artist"}],
                        "album": {"name": "Test Album"},
                    }
                }
            ],
            "next": None,
        }
        client = SpotifyClient(auth_manager=mock_auth_manager)

        # Act
        liked_songs = client.get_liked_songs()

        # Assert
        assert len(liked_songs) == 1
        assert liked_songs[0]["name"] == "Test Song"
        assert liked_songs[0]["artist"] == "Test Artist"
        assert liked_songs[0]["album"] == "Test Album"
        mock_spotify_instance.current_user_saved_tracks.assert_called_once()


def test_get_playlist_contents():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.playlist_items.return_value = {
            "items": [
                {
                    "track": {
                        "id": "test_song_id",
                        "name": "Test Song",
                        "artists": [{"name": "Test Artist"}],
                        "album": {"name": "Test Album"},
                    }
                }
            ],
            "next": None,
        }
        client = SpotifyClient(auth_manager=mock_auth_manager)

        # Act
        tracks = client.get_playlist_contents("test_playlist_id")

        # Assert
        assert len(tracks) == 1
        assert tracks[0]["name"] == "Test Song"
        mock_spotify_instance.playlist_items.assert_called_once_with("test_playlist_id")


def test_create_playlist():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.me.return_value = {"id": "test_user"}
        mock_spotify_instance.user_playlist_create.return_value = {
            "id": "new_playlist_id"
        }
        client = SpotifyClient(auth_manager=mock_auth_manager)

        # Act
        playlist_id = client.create_playlist(
            "New Playlist", "A new playlist", ["spotify:track:123"]
        )

        # Assert
        assert playlist_id == "new_playlist_id"
        mock_spotify_instance.user_playlist_create.assert_called_once_with(
            "test_user", "New Playlist", public=True, description="A new playlist"
        )
        mock_spotify_instance.playlist_add_items.assert_called_once_with(
            "new_playlist_id", ["spotify:track:123"]
        )


def test_search_songs():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "test_id_1",
                        "name": "Test Song",
                        "artists": [{"name": "Test Artist"}],
                        "album": {"name": "Test Album"},
                    },
                    {
                        "id": "test_id_2",
                        "name": "Another Song",
                        "artists": [{"name": "Another Artist"}],
                        "album": {"name": "Another Album"},
                    },
                ]
            }
        }
        client = SpotifyClient(auth_manager=mock_auth_manager)

        # Act
        songs = client.search_songs("Test", "Artist", limit=2)

        # Assert
        assert len(songs) == 2
        assert songs[0]["name"] == "Test Song"
        assert songs[1]["name"] == "Another Song"
        mock_spotify_instance.search.assert_called_once_with(
            q="track:Test artist:Artist", type="track", limit=2
        )


def test_search_songs_with_special_characters():
    # Arrange
    mock_auth_manager = MagicMock()
    with patch("spotipy.Spotify") as mock_spotify:
        mock_spotify_instance = mock_spotify.return_value
        mock_spotify_instance.search.return_value = {"tracks": {"items": []}}
        client = SpotifyClient(auth_manager=mock_auth_manager)
        title = "Song with / and spaces"
        artist = "Artist with & and ="

        # Act
        client.search_songs(title, artist)

        # Assert
        encoded_title = urllib.parse.quote(title)
        encoded_artist = urllib.parse.quote(artist)
        expected_query = f"track:{encoded_title} artist:{encoded_artist}"
        mock_spotify_instance.search.assert_called_once_with(
            q=expected_query, type="track", limit=5
        )
