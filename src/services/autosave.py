from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Optional

from src.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

_app_context = None
_get_user_id_func = None

_thread: Optional[threading.Thread] = None


def set_app_context(app_context) -> None:
    global _app_context
    _app_context = app_context


def set_get_user_id(get_user_id_func) -> None:
    global _get_user_id_func
    _get_user_id_func = get_user_id_func


def _get_user_id() -> str:
    if _get_user_id_func:
        try:
            uid = _get_user_id_func()
            return uid or DEFAULT_USER_ID
        except Exception:
            return DEFAULT_USER_ID
    return DEFAULT_USER_ID


def auto_save_worker() -> None:
    """Robust background thread for auto-saving with race condition prevention"""
    if _app_context is None:
        logger.error("Auto-save worker started without app context")
        return

    logger.info("Auto-save worker started")

    while _app_context.auto_save_enabled:
        user_id = None
        try:
            settings = {}
            if _app_context.data_manager:
                try:
                    user_id = _get_user_id()
                    settings = _app_context.data_manager.load_settings(user_id) or {}
                except Exception as e:
                    logger.warning(f"Failed to load settings for auto-save: {e}")

            interval = settings.get('autosave_interval', 30)

            if _app_context.wait_for_auto_save_stop(interval):
                logger.info("Auto-save worker stopped by event")
                break

            if not _app_context.auto_save_enabled:
                logger.info("Auto-save disabled, stopping worker")
                break

            with _app_context._auto_save_lock:
                if _app_context._save_in_progress:
                    logger.info("Save already in progress, skipping auto-save")
                    continue
                _app_context._save_in_progress = True

            if not _app_context.data_manager:
                with _app_context._auto_save_lock:
                    _app_context._save_in_progress = False
                logger.warning("Data manager not available for auto-save")
                continue

            try:
                user_id = _get_user_id()
                if not user_id:
                    logger.warning("No user ID available for auto-save")
                    continue

                tasks = _app_context.data_manager.load_tasks_for_user(user_id)

                current_time = time.time()
                last_save_time = _app_context.get_last_save_time()
                last_signature = _app_context.get_last_saved_tasks_signature()

                snapshot = json.dumps(tasks, sort_keys=True, separators=(",", ":"))
                signature = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

                if last_signature == signature:
                    logger.debug("No task changes detected since last auto-save; skipping save")
                    _app_context.set_last_save_time(current_time)
                    continue

                if last_save_time and current_time - last_save_time < max(5, interval * 0.25):
                    logger.debug("Auto-save interval guard prevented redundant save")
                    continue

                success = _app_context.data_manager.save_tasks_for_user(user_id, tasks)

                if success:
                    _app_context.set_last_save_time(current_time)
                    _app_context.set_last_saved_tasks_signature(signature)
                    logger.info(f"Auto-saved {len(tasks)} tasks for user {user_id}")
                else:
                    logger.error(f"Auto-save failed for user {user_id}")

            except Exception as save_error:
                logger.error(f"Auto-save error for user {user_id or 'unknown'}: {save_error}")
            finally:
                _app_context.set_save_in_progress(False)

        except Exception as e:
            logger.error(f"Auto-save worker error: {e}")
            time.sleep(5)

    logger.info("Auto-save worker stopped")
    _app_context.set_auto_save_running(False)


def start_auto_save() -> None:
    global _thread
    if _app_context is None:
        raise RuntimeError("Auto-save requires app context")

    if _app_context.is_auto_save_running():
        logger.warning("Auto-save is already running")
        return

    _app_context.clear_auto_save_stop_event()
    _app_context.auto_save_enabled = True

    _thread = threading.Thread(target=auto_save_worker, daemon=True, name="AutoSaveWorker")
    _app_context.auto_save_thread = _thread
    _app_context.set_auto_save_running(True)
    _thread.start()

    logger.info("Auto-save thread started successfully")


def stop_auto_save(timeout: float = 10.0) -> None:
    if _app_context is None:
        return

    logger.info("Stopping auto-save...")

    _app_context.auto_save_enabled = False
    _app_context.stop_auto_save_event()

    t = _app_context.auto_save_thread
    if t and t.is_alive():
        t.join(timeout=timeout)

        if t.is_alive():
            logger.warning("Auto-save thread did not stop gracefully")
        else:
            logger.info("Auto-save thread stopped successfully")

    _app_context.set_auto_save_running(False)
