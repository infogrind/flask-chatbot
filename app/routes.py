from flask import Blueprint, jsonify

bp = Blueprint("routes", __name__)


@bp.route("/", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})
