import json
import logging
import os
import uuid

from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    stream_with_context,
    url_for,
)
from openai.types.responses import (
    ResponseInputParam,
)
from spotipy.oauth2 import SpotifyOAuth

from app.chat_client import ChatClient, ChatResponse, ToolCallResponse
from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

bp = Blueprint("routes", __name__)
chat_client = ChatClient()

SCOPE = "playlist-read-private user-library-read playlist-modify-public"


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
    token_info = auth_manager.cache_handler.get_cached_token()
    is_spotify_connected = auth_manager.validate_token(token_info) is not None

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


@bp.route("/chat")
def chat():
    logger.info("Called /chat")
    """Handles chat submissions, including tool calls."""
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    conversation_history: ResponseInputParam = session["conversation"]
    conversation_history.append(
        {
            "role": "user",
            "content": query,
        }
    )

    auth_manager = get_spotify_auth_manager()
    spotify_client = SpotifyClient(auth_manager=auth_manager)

    def stream():
        logger.info("Starting chat response stream")

        for response in chat_client.get_chat_completion(
            conversation_history, spotify_client
        ):
            logger.info("Got completion response")
            match response:
                case ChatResponse(history, response):
                    session["conversation"] = history
                    session.modified = True

                    data = {"response": response}
                    json_data = json.dumps(data)
                    yield f"data: {json_data}\n\n"
                case ToolCallResponse(function_name, arguments):
                    tool_code = f"{function_name}({arguments})"
                    data = {"tool_code": tool_code}
                    json_data = json.dumps(data)
                    yield f"data: {json_data}\n\n"

        json_end = json.dumps({"status": "end"})
        yield f"data: {json_end}\n\n"

    return Response(stream_with_context(stream()), mimetype="text/event-stream")


@bp.route("/clear", methods=["POST"])
def clear_chat():
    """Clears the conversation history from the session."""
    session.pop("conversation", None)
    return jsonify({"status": "ok"})
