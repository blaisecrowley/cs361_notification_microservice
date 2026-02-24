"""
Notification microservice
"""

import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = Path(__file__).parent / "notifications.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                notification_description TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                unread INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.commit()


@app.route("/notifications", methods=["POST"])
def create_notification():
    """Receive a notification from another microservice. Body: { "user_id": "...", "notification_description": "..." }. notification_id is generated automatically."""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    notification_description = data.get("notification_description")

    if not user_id or notification_description is None:
        return jsonify({"error": "user_id and notification_description are required"}), 400

    user_id = str(user_id).strip()
    notification_description = str(notification_description).strip()

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO notifications (user_id, notification_description, unread) VALUES (?, ?, 1)",
            (user_id, notification_description),
        )
        notification_id = cur.lastrowid
        conn.commit()

    return jsonify({
        "notification_id": notification_id,
        "user_id": user_id,
        "notification_description": notification_description,
        "unread": True,
        "message": "Notification received",
    }), 201


@app.route("/users/<user_id>/notifications", methods=["GET"])
def list_user_notifications(user_id):
    """Get all notifications for a given user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT notification_id, user_id, notification_description, created_at, unread FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return jsonify({
        "user_id": user_id,
        "notifications": [
            {
                "notification_id": r["notification_id"],
                "user_id": r["user_id"],
                "notification_description": r["notification_description"],
                "created_at": r["created_at"],
                "unread": bool(r["unread"]),
            }
            for r in rows
        ],
    }), 200


@app.route("/users/<user_id>/unread-count", methods=["GET"])
def get_unread_count(user_id):
    """Get unread notification count for a given user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS unread_count FROM notifications WHERE user_id = ? AND unread = 1",
            (user_id,),
        ).fetchone()

    return jsonify({
        "user_id": user_id,
        "unread_count": row["unread_count"],
    }), 200

@app.route("/notifications/<int:notification_id>", methods=["PATCH"])
def mark_read(notification_id):
    data = request.get_json()

    if "unread" not in data:
        return jsonify({"error": "Must include 'unread' true or false"}), 400

    unread_value = 1 if data["unread"] else 0

    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET unread = ? WHERE notification_id = ?",
            (unread_value, notification_id),
        )
        conn.commit()

    return jsonify({"message": "Notification updated"}), 200

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8001, debug=True)
