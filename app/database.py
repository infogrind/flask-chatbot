import json
import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


@click.command("init-db")
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


def create_conversation(conversation_id, history):
    db = get_db()
    db.execute(
        "INSERT INTO conversation (id, history) VALUES (?, ?)",
        (conversation_id, json.dumps(history)),
    )
    db.commit()


def get_conversation(conversation_id):
    db = get_db()
    row = db.execute(
        "SELECT history FROM conversation WHERE id = ?", (conversation_id,)
    ).fetchone()
    return json.loads(row["history"]) if row else None


def update_conversation(conversation_id, history):
    db = get_db()
    db.execute(
        "UPDATE conversation SET history = ? WHERE id = ?",
        (json.dumps(history), conversation_id),
    )
    db.commit()


def delete_conversation(conversation_id):
    db = get_db()
    db.execute("DELETE FROM conversation WHERE id = ?", (conversation_id,))
    db.commit()
