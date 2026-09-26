import json
import logging
import uuid
from collections.abc import Iterator

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    stream_with_context,
    url_for,
)
from openai.types.responses import ResponseInputParam
from werkzeug.wrappers import Response as BaseResponse
from spotipy.oauth2 import CacheFileHandler, SpotifyOAuth

from app.chat_client import ChatClient, ChatResponse, ToolCallResponse
from app.database import (
    create_conversation,
    delete_conversation,
    get_conversation,
    update_conversation,
)
from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

bp = Blueprint("routes", __name__)

SCOPE = "playlist-read-private user-library-read playlist-modify-public"
SPOTIFY_CACHE_DIR = ".spotify_cache"


def get_chat_client() -> ChatClient:
    """Returns the app's `ChatClient`, created on first use.

    Created lazily so that importing this module (e.g. for `flask init-db`) does
    not require `OPENAI_API_KEY`.
    """
    if "chat_client" not in current_app.extensions:
        current_app.extensions["chat_client"] = ChatClient(
            current_app.config["OPENAI_API_KEY"]
        )
    return current_app.extensions["chat_client"]


def get_spotify_auth_manager() -> SpotifyOAuth:
    # Always use a per-session token cache: with `cache_path=None`, spotipy falls
    # back to a single `.cache` file shared by every session.
    cache_id = session.setdefault("spotify_cache_id", str(uuid.uuid4()))
    return SpotifyOAuth(
        client_id=current_app.config["SPOTIFY_CLIENT_ID"],
        client_secret=current_app.config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=url_for("routes.spotify_callback", _external=True),
        scope=SCOPE,
        cache_handler=CacheFileHandler(cache_path=f"{SPOTIFY_CACHE_DIR}/{cache_id}"),
    )


def load_or_create_conversation() -> tuple[str, ResponseInputParam]:
    """Returns the session's conversation, creating it if it doesn't exist.

    Handles both a missing session entry and a stale ID whose database row is
    gone (e.g. after `flask init-db`).
    """
    conversation_id = session.setdefault("conversation_id", str(uuid.uuid4()))
    conversation_history = get_conversation(conversation_id)
    if conversation_history is None:
        conversation_history = []
        create_conversation(conversation_id, conversation_history)
    return conversation_id, conversation_history


@bp.route("/", methods=["GET"])
def index() -> str:
    """Main chat page."""
    _, conversation_history = load_or_create_conversation()

    auth_manager = get_spotify_auth_manager()
    token_info = auth_manager.cache_handler.get_cached_token()
    is_spotify_connected = auth_manager.validate_token(token_info) is not None

    return render_template(
        "index.html",
        conversation=conversation_history,
        is_spotify_connected=is_spotify_connected,
    )


@bp.route("/spotify/login")
def spotify_login() -> BaseResponse:
    """Redirects to Spotify for authentication."""
    auth_manager = get_spotify_auth_manager()
    return redirect(auth_manager.get_authorize_url())


@bp.route("/spotify/callback")
def spotify_callback() -> BaseResponse:
    """Handles the callback from Spotify."""
    # Without a code (e.g. `?error=access_denied`), there is nothing to exchange
    if code := request.args.get("code"):
        get_spotify_auth_manager().get_access_token(code)
    return redirect(url_for("routes.index"))


@bp.route("/chat")
def chat() -> Response | tuple[Response, int]:
    """Handles chat submissions, including tool calls."""
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    conversation_id, conversation_history = load_or_create_conversation()
    conversation_history.append(
        {
            "role": "user",
            "content": query,
        }
    )
    update_conversation(conversation_id, conversation_history)

    auth_manager = get_spotify_auth_manager()
    spotify_client = SpotifyClient(auth_manager=auth_manager)
    chat_client = get_chat_client()

    def stream() -> Iterator[str]:
        logger.info("Starting chat response stream")

        for response in chat_client.get_chat_completion(
            conversation_history, spotify_client
        ):
            logger.info("Got completion response")
            match response:
                case ChatResponse(history, response):
                    update_conversation(conversation_id, history)
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
def clear_chat() -> Response:
    """Clears the conversation history from the database and session."""
    conversation_id = session.pop("conversation_id", None)
    if conversation_id:
        delete_conversation(conversation_id)
    return jsonify({"status": "ok"})
