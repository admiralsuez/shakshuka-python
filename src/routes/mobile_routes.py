from flask import Blueprint, request, jsonify
import logging
import secrets
import hashlib
import json
import uuid
import socket
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.constants import DEFAULT_USER_ID
from src.utils.validators import validate_task_data

logger = logging.getLogger(__name__)

mobile_bp = Blueprint("mobile", __name__, url_prefix="/api/mobile")

_app_context = None
_get_user_id_func = None
_ensure_data_manager_func = None


def init_mobile_routes(app_context, get_user_id_func, ensure_data_manager_func):
    global _app_context, _get_user_id_func, _ensure_data_manager_func
    _app_context = app_context
    _get_user_id_func = get_user_id_func
    _ensure_data_manager_func = ensure_data_manager_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _get_data_manager():
    return _app_context.data_manager if _app_context else None


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_local_request() -> bool:
    addr = request.remote_addr or ""
    return addr == "127.0.0.1" or addr == "::1"


def _get_local_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and ip != "127.0.0.1":
            return ip
    except Exception:
        return None
    return None


def _require_mobile_token() -> Tuple[bool, Optional[Dict[str, Any]], str]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False, None, "Missing Authorization header"

    token = auth[len("Bearer ") :].strip()
    if not token:
        return False, None, "Missing token"

    token_hash = _sha256_hex(token)

    dm = _get_data_manager()
    if not dm:
        return False, None, "Data manager not available"

    user_id = _get_user_id()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            cur = conn.execute(
                "SELECT device_id, device_name FROM mobile_devices WHERE user_id = ? AND token_hash = ?",
                (user_id, token_hash),
            )
            row = cur.fetchone()
            if not row:
                return False, None, "Invalid token"

            device = {
                "device_id": row[0],
                "device_name": row[1],
                "user_id": user_id,
            }
            return True, device, ""
    except Exception as e:
        logger.error("Error validating mobile token: %s", e)
        return False, None, "Token validation failed"


@mobile_bp.route("/pairing", methods=["GET"])
def get_pairing_code():
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    if not _app_context:
        return jsonify({"success": False, "error": "App context not available"}), 500

    code = str(secrets.randbelow(1000000)).zfill(6)
    try:
        pairing_cache = getattr(_app_context, "_mobile_pairing_codes", None)
        if pairing_cache is not None:
            pairing_cache[code] = datetime.now().isoformat()
    except Exception:
        pass

    ip = _get_local_ip()
    port = request.host.split(":")[-1] if request.host else "8989"
    lan_url = f"http://{ip}:{port}" if ip else None

    return jsonify(
        {
            "success": True,
            "code": code,
            "expires_in": 300,
            "lan_url": lan_url,
        }
    )


@mobile_bp.route("/pair", methods=["POST"])
def pair_device():
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    if not _app_context:
        return jsonify({"success": False, "error": "App context not available"}), 500

    data = request.json
    if data is None or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request must contain JSON object"}), 400

    code = str(data.get("code") or "").strip()
    device_id = str(data.get("device_id") or "").strip() or str(uuid.uuid4())
    device_name = str(data.get("device_name") or "").strip() or "Phone"

    pairing_cache = getattr(_app_context, "_mobile_pairing_codes", None)
    if not code or pairing_cache is None or code not in pairing_cache:
        return jsonify({"success": False, "error": "Invalid or expired code"}), 400

    try:
        del pairing_cache[code]
    except Exception:
        pass

    token = secrets.token_urlsafe(32)
    token_hash = _sha256_hex(token)
    user_id = _get_user_id()
    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    now = datetime.now().isoformat()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            conn.execute(
                "INSERT OR REPLACE INTO mobile_devices (user_id, device_id, device_name, token_hash, created_at, last_seen_at) VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM mobile_devices WHERE user_id = ? AND device_id = ?), ?), ?)",
                (user_id, device_id, device_name, token_hash, user_id, device_id, now, now),
            )
            conn.commit()
    except Exception as e:
        logger.error("Failed to save paired device: %s", e)
        return jsonify({"success": False, "error": "Failed to save device"}), 500

    return jsonify({"success": True, "token": token, "device_id": device_id, "device_name": device_name})


@mobile_bp.route("/inbox", methods=["POST"])
def submit_inbox():
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    ok, device, err = _require_mobile_token()
    if not ok or not device:
        return jsonify({"success": False, "error": err}), 401

    data = request.json
    if data is None or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request must contain JSON object"}), 400

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return jsonify({"success": False, "error": "tasks must be a list"}), 400

    submission_id = str(data.get("submission_id") or "").strip() or str(uuid.uuid4())

    payload = {
        "device_id": device.get("device_id"),
        "device_name": device.get("device_name"),
        "tasks": tasks,
    }

    dm = _get_data_manager()
    user_id = device.get("user_id")
    now = datetime.now().isoformat()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            conn.execute(
                "INSERT OR REPLACE INTO mobile_inbox (id, user_id, device_id, device_name, payload_json, status, created_at, processed_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)",
                (submission_id, user_id, device.get("device_id"), device.get("device_name"), json.dumps(payload), now),
            )
            conn.execute(
                "UPDATE mobile_devices SET last_seen_at = ? WHERE user_id = ? AND device_id = ?",
                (now, user_id, device.get("device_id")),
            )
            conn.commit()
    except Exception as e:
        logger.error("Failed to save inbox submission: %s", e)
        return jsonify({"success": False, "error": "Failed to save submission"}), 500

    return jsonify({"success": True, "submission_id": submission_id, "received": len(tasks)})


@mobile_bp.route("/inbox/pending", methods=["GET"])
def get_pending_inbox():
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    user_id = _get_user_id()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            cur = conn.execute(
                "SELECT id, device_id, device_name, payload_json, created_at FROM mobile_inbox WHERE user_id = ? AND status = 'pending' ORDER BY created_at ASC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"success": True, "pending": None})

            payload = None
            try:
                payload = json.loads(row[3]) if row[3] else None
            except Exception:
                payload = None

            return jsonify(
                {
                    "success": True,
                    "pending": {
                        "id": row[0],
                        "device_id": row[1],
                        "device_name": row[2],
                        "payload": payload,
                        "created_at": row[4],
                    },
                }
            )
    except Exception as e:
        logger.error("Failed to load pending inbox: %s", e)
        return jsonify({"success": False, "error": "Failed to load inbox"}), 500


def _map_mobile_task_to_task_payload(mobile_task: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    title = (mobile_task.get("title") or mobile_task.get("name") or "").strip()
    if not title:
        return False, {}, "Missing title"

    project = (mobile_task.get("project") or "").strip()
    due_date = mobile_task.get("due_date") or mobile_task.get("date")
    if isinstance(due_date, str):
        due_date = due_date.strip() or None
    else:
        due_date = None

    duration = mobile_task.get("estimated_duration")
    if duration is None:
        duration = mobile_task.get("duration")

    try:
        duration_int = int(duration) if duration is not None else 60
    except Exception:
        duration_int = 60

    if duration_int < 5:
        duration_int = 5
    if duration_int > 480:
        duration_int = 480

    task_payload: Dict[str, Any] = {
        "title": title,
        "description": (mobile_task.get("description") or mobile_task.get("notes") or ""),
        "project": project,
        "estimated_duration": duration_int,
    }
    if due_date is not None:
        task_payload["due_date"] = due_date

    is_valid, msg = validate_task_data(task_payload)
    if not is_valid:
        return False, {}, msg

    return True, task_payload, ""


@mobile_bp.route("/inbox/<submission_id>/approve", methods=["POST"])
def approve_inbox(submission_id: str):
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    data = request.json
    if data is None or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request must contain JSON object"}), 400

    selected_ids = data.get("selected_task_ids")
    if not isinstance(selected_ids, list):
        return jsonify({"success": False, "error": "selected_task_ids must be a list"}), 400

    user_id = _get_user_id()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            cur = conn.execute(
                "SELECT payload_json FROM mobile_inbox WHERE id = ? AND user_id = ? AND status = 'pending'",
                (submission_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"success": False, "error": "Submission not found"}), 404

            payload = json.loads(row[0]) if row[0] else {}
            tasks = payload.get("tasks") if isinstance(payload, dict) else None
            if not isinstance(tasks, list):
                tasks = []

        created_tasks = []
        created_count = 0
        skipped = []

        selected_set = set(str(x) for x in selected_ids)

        for t in tasks:
            if not isinstance(t, dict):
                continue
            client_task_id = str(t.get("client_task_id") or t.get("id") or "").strip()
            if not client_task_id:
                skipped.append({"client_task_id": client_task_id, "error": "Missing client_task_id"})
                continue
            if client_task_id not in selected_set:
                continue

            ok_map, task_payload, msg = _map_mobile_task_to_task_payload(t)
            if not ok_map:
                skipped.append({"client_task_id": client_task_id, "error": msg})
                continue

            created = dm.create_task_for_user(user_id, task_payload)
            if created:
                created_tasks.append(created)
                created_count += 1
            else:
                skipped.append({"client_task_id": client_task_id, "error": "Create failed"})

        now = datetime.now().isoformat()
        result_json = json.dumps({"created": created_count, "skipped": skipped})

        with dm._get_connection() as conn:  # pylint: disable=protected-access
            conn.execute(
                "UPDATE mobile_inbox SET status = 'approved', processed_at = ?, result_json = ? WHERE id = ? AND user_id = ?",
                (now, result_json, submission_id, user_id),
            )
            conn.commit()

        return jsonify({"success": True, "created": created_count, "tasks": created_tasks, "skipped": skipped})

    except Exception as e:
        logger.error("Failed to approve inbox submission %s: %s", submission_id, e)
        return jsonify({"success": False, "error": "Failed to approve submission"}), 500


@mobile_bp.route("/inbox/<submission_id>/status", methods=["GET"])
def get_submission_status(submission_id: str):
    """Allow mobile app to check the status of a submission."""
    ok, device, err = _require_mobile_token()
    if not ok or not device:
        return jsonify({"success": False, "error": err}), 401

    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    user_id = device.get("user_id")

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            cur = conn.execute(
                "SELECT status, processed_at, result_json FROM mobile_inbox WHERE id = ? AND user_id = ?",
                (submission_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"success": False, "error": "Submission not found"}), 404

            status = row[0]
            processed_at = row[1]
            result_json = row[2]
            
            result = None
            if result_json:
                try:
                    result = json.loads(result_json)
                except Exception:
                    pass

            return jsonify({
                "success": True,
                "submission_id": submission_id,
                "status": status,
                "processed_at": processed_at,
                "result": result,
            })
    except Exception as e:
        logger.error("Failed to get submission status %s: %s", submission_id, e)
        return jsonify({"success": False, "error": "Failed to get status"}), 500


@mobile_bp.route("/inbox/<submission_id>/reject", methods=["POST"])
def reject_inbox(submission_id: str):
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({"success": False, "error": "Data manager not initialized"}), 503

    dm = _get_data_manager()
    if not dm:
        return jsonify({"success": False, "error": "Data manager not available"}), 500

    user_id = _get_user_id()
    now = datetime.now().isoformat()

    try:
        with dm._get_connection() as conn:  # pylint: disable=protected-access
            conn.execute(
                "UPDATE mobile_inbox SET status = 'rejected', processed_at = ? WHERE id = ? AND user_id = ? AND status = 'pending'",
                (now, submission_id, user_id),
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Failed to reject inbox submission %s: %s", submission_id, e)
        return jsonify({"success": False, "error": "Failed to reject submission"}), 500
