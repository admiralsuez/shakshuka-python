"""Notes Routes - CRUD API for notes, stored in SQLite via SQLiteDataManager.

This mirrors the style of task_routes but with a much narrower surface:
- GET /api/notes           -> list notes for current user
- POST /api/notes          -> create note (title, content)
- PUT /api/notes/<note_id> -> update title/content
- DELETE /api/notes/<id>   -> delete note
"""

from flask import Blueprint, request, jsonify
import logging
from typing import Any, Dict

from src.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

_app_context = None
_get_user_id_func = None
_ensure_data_manager_func = None
_sanitize_input_func = None


def init_notes_routes(app_context, get_user_id_func, ensure_data_manager_func, sanitize_input_func):
    """Initialize notes routes with dependency injection.

    This keeps the same pattern as task_routes so we can share helpers
    like get_user_id and ensure_data_manager.
    """
    global _app_context, _get_user_id_func, _ensure_data_manager_func, _sanitize_input_func
    _app_context = app_context
    _get_user_id_func = get_user_id_func
    _ensure_data_manager_func = ensure_data_manager_func
    _sanitize_input_func = sanitize_input_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _get_data_manager():
    return _app_context.data_manager if _app_context else None


@notes_bp.route("", methods=["GET"])
def get_notes():
    """Return all notes for the current user."""
    user_id = _get_user_id()
    try:
        if _ensure_data_manager_func and not _ensure_data_manager_func():
            logger.error("Data manager not initialized for notes")
            return jsonify({"error": "Data manager not initialized"}), 503
        dm = _get_data_manager()
        if not dm:
            return jsonify({"error": "Data manager not available"}), 503
        notes = dm.load_notes(user_id)
        return jsonify(notes)
    except Exception as e:
        logger.error("Error loading notes for user %s: %s", user_id, e)
        return jsonify({"error": "Internal server error"}), 500


@notes_bp.route("", methods=["POST"])
def create_note():
    """Create a new note for the current user."""
    user_id = _get_user_id()
    try:
        if not request.json:
            return jsonify({"error": "Request must contain JSON"}), 400
        note_data: Dict[str, Any] = request.json
        if _sanitize_input_func:
            note_data = _sanitize_input_func(note_data)

        title = (note_data.get("title") or "").strip() or "Untitled"
        content = note_data.get("content", "")
        dm = _get_data_manager()
        if not dm:
            return jsonify({"error": "Data manager not available"}), 500

        created = dm.create_note_for_user(user_id, {"title": title, "content": content})
        if not created:
            return jsonify({"error": "Failed to create note"}), 500
        return jsonify(created), 201
    except Exception as e:
        logger.error("Unexpected error creating note for user %s: %s", user_id, e)
        return jsonify({"error": "Internal server error"}), 500


@notes_bp.route("/<note_id>", methods=["PUT"])
def update_note(note_id: str):
    """Update title/content of a note."""
    user_id = _get_user_id()
    try:
        if not request.json:
            return jsonify({"error": "Request must contain JSON"}), 400
        note_data: Dict[str, Any] = request.json
        if _sanitize_input_func:
            note_data = _sanitize_input_func(note_data)
        dm = _get_data_manager()
        if not dm:
            return jsonify({"error": "Data manager not available"}), 500

        updated = dm.update_note_for_user(user_id, note_id, note_data)
        if not updated:
            return jsonify({"error": "Note not found"}), 404
        return jsonify(updated)
    except Exception as e:
        logger.error("Unexpected error updating note %s for user %s: %s", note_id, user_id, e)
        return jsonify({"error": "Internal server error"}), 500


@notes_bp.route("/<note_id>", methods=["DELETE"])
def delete_note(note_id: str):
    """Delete a note for the current user."""
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({"error": "Data manager not available"}), 500
        success = dm.delete_note_for_user(user_id, note_id)
        if not success:
            return jsonify({"error": "Note not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Unexpected error deleting note %s for user %s: %s", note_id, user_id, e)
        return jsonify({"error": "Internal server error"}), 500
