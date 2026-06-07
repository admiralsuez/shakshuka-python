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
from src.exceptions import ValidationError

# Import decorators
from src.routes.route_decorators import (
    require_data_manager,
    require_json_body,
    handle_database_error
)

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
@require_data_manager
@handle_database_error
def get_notes(user_id, data_manager):
    """Return all notes for the current user."""
    notes = data_manager.load_notes(user_id)
    # Ensure JSON doesn't HTML-escape strings
    from flask import make_response
    import json
    response = make_response(json.dumps(notes, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response, 200


@notes_bp.route("", methods=["POST"])
@require_data_manager
@require_json_body
@handle_database_error
def create_note(user_id, data_manager):
    """Create a new note for the current user."""
    note_data: Dict[str, Any] = request.json
    if _sanitize_input_func:
        note_data = _sanitize_input_func(note_data)

    title = (note_data.get("title") or "").strip() or "Untitled"
    content = note_data.get("content", "")
    folder_raw = note_data.get("folder")
    folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
    if folder == "":
        folder = None
    pinned = bool(note_data.get("pinned", False))
    archived = bool(note_data.get("archived", False))

    created = data_manager.create_note_for_user(
        user_id,
        {"title": title, "content": content, "folder": folder, "pinned": pinned, "archived": archived},
    )
    if not created:
        raise DatabaseError(message='Failed to create note')
    return jsonify(created), 201


@notes_bp.route("/<note_id>", methods=["PUT"])
@require_data_manager
@require_json_body
@handle_database_error
def update_note(note_id: str, user_id, data_manager):
    """Update title/content/folder of a note."""
    note_data: Dict[str, Any] = request.json
    if _sanitize_input_func:
        note_data = _sanitize_input_func(note_data)

    updated = data_manager.update_note_for_user(user_id, note_id, note_data)
    if not updated:
        return jsonify({"error": "Note not found"}), 404
    return jsonify(updated), 200


@notes_bp.route("/<note_id>", methods=["PATCH"])
@require_data_manager
@handle_database_error
def patch_note(note_id: str, user_id, data_manager):
    """Partially update a note (supports parent_id for nesting)."""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    note_data: Dict[str, Any] = request.json
    if not note_data:
        return jsonify({"error": "No data provided"}), 400
    
    if _sanitize_input_func:
        note_data = _sanitize_input_func(note_data)
    
    # Validate parent_id if provided (must be a valid note or None)
    if 'parent_id' in note_data:
        parent_id = note_data.get('parent_id')
        if parent_id is not None:
            parent_note = data_manager.get_note_by_id(user_id, parent_id)
            if not parent_note:
                return jsonify({"error": f"Parent note {parent_id} not found"}), 404
            # Prevent circular references (note cannot be its own parent)
            if parent_id == note_id:
                return jsonify({"error": "A note cannot be its own parent"}), 400
    
    updated = data_manager.update_note_for_user(user_id, note_id, note_data)
    if not updated:
        return jsonify({"error": "Note not found"}), 404
    return jsonify(updated), 200


@notes_bp.route("/<note_id>", methods=["DELETE"])
@require_data_manager
@handle_database_error
def delete_note(note_id: str, user_id, data_manager):
    """Delete a note for the current user."""
    success = data_manager.delete_note_for_user(user_id, note_id)
    if not success:
        return jsonify({"error": "Note not found"}), 404
    return jsonify({"success": True}), 200


@notes_bp.route("/trash", methods=["GET"])
def get_trashed_notes():
    """Return soft-deleted notes for the current user."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    try:
        trashed = dm.load_trashed_notes_for_user(user_id)
        from flask import make_response
        import json as _json
        resp = make_response(_json.dumps(trashed, ensure_ascii=False))
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp, 200
    except DatabaseError:
        raise
    except Exception as e:
        logger.exception("Error loading trashed notes")
        raise DatabaseError(message='Error loading trashed notes', cause=e)


@notes_bp.route("/<note_id>/restore", methods=["POST"])
def restore_note(note_id: str):
    """Restore a trashed note."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    ok = dm.restore_note_for_user(user_id, note_id)
    if not ok:
        return jsonify({"error": "Note not found in trash"}), 404
    return jsonify({"success": True}), 200


@notes_bp.route("/<note_id>/permanent", methods=["DELETE"])
def permanent_delete_note(note_id: str):
    """Permanently delete a note and its version history."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    ok = dm.hard_delete_note_for_user(user_id, note_id)
    if not ok:
        return jsonify({"error": "Note not found"}), 404
    return jsonify({"success": True}), 200


@notes_bp.route("/<note_id>/history", methods=["GET"])
def get_note_history(note_id: str):
    """Return version history for a note."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    versions = dm.load_note_versions(user_id, note_id)
    return jsonify({"success": True, "versions": versions}), 200


@notes_bp.route("/<note_id>/restore-version", methods=["POST"])
def restore_note_version(note_id: str):
    """Restore a note to a previous version."""
    user_id = _get_user_id()
    payload = get_json_object(required=True)
    version_id = payload.get("version_id")
    if version_id is None:
        return jsonify({"error": "version_id is required"}), 400
    try:
        version_id = int(version_id)
    except (TypeError, ValueError):
        return jsonify({"error": "version_id must be an integer"}), 400
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    result = dm.restore_note_version(user_id, note_id, version_id)
    if not result:
        return jsonify({"error": "Version not found"}), 404
    return jsonify(result), 200


@notes_bp.route("/<note_id>/duplicate", methods=["POST"])
def duplicate_note(note_id: str):
    """Duplicate an existing note."""
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')
    dup = dm.duplicate_note_for_user(user_id, note_id)
    if not dup:
        return jsonify({"error": "Note not found"}), 404
    return jsonify(dup), 201


@notes_bp.route("/export-all", methods=["POST"])
def export_all_notes_now():
    """Trigger an immediate export of all notes as .md files and return a zip download."""
    import io
    import zipfile
    from flask import send_file as _send_file

    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        raise DatabaseError(message='Data manager not available')

    try:
        all_notes = dm.load_notes_for_user(user_id) or []
    except DatabaseError:
        raise
    except Exception as e:  # noqa: broad-except
        raise DatabaseError(message='Error loading notes for export', cause=e)

    if not all_notes:
        return jsonify({"error": "No notes to export"}), 404

    buf = io.BytesIO()
    used_names = set()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for note in all_notes:
            title = (note.get('title') or 'Untitled').strip()
            safe = ''.join(c if (c.isalnum() or c in (' ', '-', '_')) else '_' for c in title).strip() or 'note'
            fname = f"{safe}.md"
            counter = 1
            while fname in used_names:
                fname = f"{safe}_{counter}.md"
                counter += 1
            used_names.add(fname)
            content = note.get('content') or ''
            zf.writestr(fname, f"# {title}\n\n{content}")

    buf.seek(0)
    from datetime import datetime as _dt
    ts = _dt.now().strftime('%Y%m%d_%H%M%S')
    return _send_file(buf, mimetype='application/zip', as_attachment=True,
                      download_name=f'shakshuka_notes_{ts}.zip')


@notes_bp.route("/export-status", methods=["GET"])
def get_notes_export_status():
    """Return info about auto-export history (folder path, count, latest)."""
    import os as _os
    from src.services.scheduler import get_notes_export_dir
    export_root = get_notes_export_dir()
    folders = []
    try:
        if _os.path.isdir(export_root):
            for name in sorted(_os.listdir(export_root)):
                full = _os.path.join(export_root, name)
                if _os.path.isdir(full):
                    count = len([f for f in _os.listdir(full) if f.endswith('.md')])
                    folders.append({"name": name, "note_count": count})
    except Exception:  # noqa: broad-except
        pass
    return jsonify({
        "success": True,
        "export_path": export_root,
        "exports": folders,
        "total": len(folders),
        "max": 14,
    }), 200


@notes_bp.route("/cleaner-status", methods=["GET"])
def get_notes_cleaner_status():
    """Expose the latest note-cleaner run summary for the notifications indicator.

    Response format (when available):
        {"success": True, "status": {"ran_at": iso_str, "cleaned_count": int}}
    """
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    try:
        status = dm.get_latest_notes_cleaner_status(user_id)
        return jsonify({"success": True, "status": status}), 200
    except DatabaseError:
        logger.exception("Database error loading notes cleaner status for user %s", user_id)
        return jsonify({"success": False, "error": "Database error loading notes cleaner status"}), 503
    except Exception as e:  # noqa: broad-except
        logger.exception("Unexpected error loading notes cleaner status for user %s", user_id)
        return jsonify({"success": False, "error": str(e)}), 500
