from flask import Blueprint, render_template, request, session, redirect, url_for
from app.chat_client import ChatClient

bp = Blueprint("routes", __name__)
chat_client = ChatClient()


@bp.route("/", methods=["GET"])
def index():
    """Main chat page."""
    if "conversation" not in session:
        session["conversation"] = []
    return render_template("index.html", conversation=session["conversation"])


@bp.route("/chat", methods=["POST"])
def chat():
    """Handles chat submissions."""
    query = request.form.get("query")
    if query:
        # Add user query to conversation
        session["conversation"].append({"role": "user", "content": query})

        # Get bot response
        bot_response = chat_client.get_chat_completion(session["conversation"])
        session["conversation"].append({"role": "assistant", "content": bot_response})

        # Ensure session is saved
        session.modified = True

    return redirect(url_for("routes.index"))
