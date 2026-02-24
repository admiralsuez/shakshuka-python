"""Notes Routes - CRUD API for notes, stored in SQLite via SQLiteDataManager.

This mirrors the style of task_routes but with a much narrower surface:
- GET /api/notes           -> list notes for current user
- POST /api/notes          -> create note (title, content)
- PUT /api/notes/<note_id> -> update title/content
- DELETE /api/notes/<id>   -> delete note
"""

from flask import Blueprint, request, jsonify, current_app
import logging
from typing import Any, Dict

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError
from src.routes.api_utils import get_json_object, register_api_error_handlers

logger = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

register_api_error_handlers(notes_bp)

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
    ctx = _app_context
    if ctx is None:
        try:
            ctx = current_app.extensions.get('app_context')
        except Exception:  # noqa: broad-except
            ctx = None
    return ctx.data_manager if ctx else None


@notes_bp.route("", methods=["GET"])
def get_notes():
    """Return all notes for the current user."""
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not initialized')
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    notes = dm.load_notes(user_id)
    # Ensure JSON doesn't HTML-escape strings
    from flask import make_response
    import json
    response = make_response(json.dumps(notes, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response, 200


@notes_bp.route("", methods=["POST"])
def create_note():
    """Create a new note for the current user."""
    user_id = _get_user_id()
    note_data: Dict[str, Any] = get_json_object(required=True)
    if _sanitize_input_func:
        note_data = _sanitize_input_func(note_data)

    title = (note_data.get("title") or "").strip() or "Untitled"
    content = note_data.get("content", "")
    folder_raw = note_data.get("folder")
    folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
    if folder == "":
        folder = None

    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')

    created = dm.create_note_for_user(user_id, {"title": title, "content": content, "folder": folder})
    if not created:
        raise DatabaseError(message='Failed to create note')
    return jsonify(created), 201


@notes_bp.route("/<note_id>", methods=["PUT"])
def update_note(note_id: str):
    """Update title/content/folder of a note."""
    user_id = _get_user_id()
    note_data: Dict[str, Any] = get_json_object(required=True)
    if _sanitize_input_func:
        note_data = _sanitize_input_func(note_data)
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')

    updated = dm.update_note_for_user(user_id, note_id, note_data)
    if not updated:
        return jsonify({"error": "Note not found"}), 404
    return jsonify(updated), 200


@notes_bp.route("/<note_id>", methods=["DELETE"])
def delete_note(note_id: str):
    """Delete a note for the current user."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    success = dm.delete_note_for_user(user_id, note_id)
    if not success:
        return jsonify({"error": "Note not found"}), 404
    return jsonify({"success": True}), 200
