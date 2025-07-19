import os
import uuid
import json
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    redirect,
    url_for,
)
from spotipy.oauth2 import SpotifyOAuth
from app.chat_client import ChatClient
from app.spotify_client import SpotifyClient

bp = Blueprint("routes", __name__)
chat_client = ChatClient()

SCOPE = "playlist-read-private"


def get_spotify_auth_manager():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=url_for("routes.spotify_callback", _external=True),
        scope=SCOPE,
        cache_path=session.get("spotify_cache_path"),
    )


@bp.route("/", methods=["GET"])
def index():
    """Main chat page."""
    if "conversation" not in session:
        session["conversation"] = []

    auth_manager = get_spotify_auth_manager()
    is_spotify_connected = auth_manager.get_cached_token() is not None

    return render_template(
        "index.html",
        conversation=session["conversation"],
        is_spotify_connected=is_spotify_connected,
    )


@bp.route("/spotify/login")
def spotify_login():
    """Redirects to Spotify for authentication."""
    if "spotify_cache_id" not in session:
        session["spotify_cache_id"] = str(uuid.uuid4())
    # Use a unique cache path for each user's session
    session["spotify_cache_path"] = f".spotify_cache/{session['spotify_cache_id']}"
    auth_manager = get_spotify_auth_manager()
    return redirect(auth_manager.get_authorize_url())


@bp.route("/spotify/callback")
def spotify_callback():
    """Handles the callback from Spotify."""
    auth_manager = get_spotify_auth_manager()
    auth_manager.get_access_token(request.args.get("code"))
    return redirect(url_for("routes.index"))


@bp.route("/chat", methods=["POST"])
def chat():
    """Handles chat submissions, including tool calls."""
    query = request.json.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    # Add user query to conversation
    session["conversation"].append({"role": "user", "content": query})
    session.modified = True

    auth_manager = get_spotify_auth_manager()
    spotify_client = SpotifyClient(auth_manager=auth_manager)
    available_tools = {"get_my_playlists": spotify_client.get_user_playlists}

    # Get bot response, potentially with tool calls
    response_message = chat_client.get_chat_completion(session["conversation"])

    if hasattr(response_message, "tool_calls") and response_message.tool_calls:
        # The model wants to call tools.
        session["conversation"].append(response_message)

        # Execute the tool calls and add the results to the history
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            if function_name in available_tools:
                function_to_call = available_tools[function_name]
                function_args = json.loads(tool_call.function.arguments)
                function_response = function_to_call(**function_args)
                session["conversation"].append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(function_response),
                    }
                )

        # Now, get the final response from the model
        final_response = chat_client.get_chat_completion(session["conversation"])
        session["conversation"].append({"role": "assistant", "content": final_response})
        bot_response = final_response
    else:
        # This is a direct response
        session["conversation"].append(
            {"role": "assistant", "content": response_message}
        )
        bot_response = response_message

    session.modified = True
    return jsonify({"response": bot_response})
