from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Optional

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError

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
        except Exception:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
            logger.exception("Failed to get user id for auto-save")
            return DEFAULT_USER_ID
    return DEFAULT_USER_ID


def auto_save_worker() -> None:
    """Robust background thread for auto-saving with race condition prevention and error handling"""
    if _app_context is None:
        logger.error("Auto-save worker started without app context")
        return

    logger.info("Auto-save worker started")
    consecutive_errors = 0
    max_consecutive_errors = 5

    while _app_context.auto_save_enabled:
        user_id = None
        try:
            settings = {}
            if _app_context.data_manager:
                try:
                    user_id = _get_user_id()
                    settings = _app_context.data_manager.load_settings(user_id) or {}
                except DatabaseError as db_err:
                    logger.exception("Failed to load settings for auto-save (DB error)")
                    consecutive_errors += 1
                    settings = {}
                except Exception as e:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                    logger.exception("Failed to load settings for auto-save: %s", e)
                    consecutive_errors += 1
                    settings = {}
            else:
                consecutive_errors += 1

            # Backoff if too many consecutive errors
            if consecutive_errors >= max_consecutive_errors:
                logger.error(
                    "Auto-save encountered %d consecutive errors, backing off for 30 seconds",
                    consecutive_errors,
                )
                time.sleep(30)
                consecutive_errors = 0
                continue

            interval = settings.get("autosave_interval", 30)

            if _app_context.wait_for_auto_save_stop(interval):
                logger.info("Auto-save worker stopped by event")
                break

            if not _app_context.auto_save_enabled:
                logger.info("Auto-save disabled, stopping worker")
                break

            with _app_context._auto_save_lock:
                if _app_context._save_in_progress:
                    logger.debug("Save already in progress, skipping auto-save")
                    continue
                _app_context._save_in_progress = True

            if not _app_context.data_manager:
                with _app_context._auto_save_lock:
                    _app_context._save_in_progress = False
                logger.warning("Data manager not available for auto-save")
                consecutive_errors += 1
                continue

            try:
                user_id = _get_user_id()
                if not user_id:
                    logger.warning("No user ID available for auto-save")
                    consecutive_errors += 1
                    continue

                try:
                    # Load only active (non-completed) tasks
                    # Completed tasks are archived and saved separately
                    tasks = _app_context.data_manager.load_active_tasks_for_user(
                        user_id
                    )
                except DatabaseError as db_err:
                    logger.exception(
                        "Auto-save could not load tasks (DB error) for user %s", user_id
                    )
                    consecutive_errors += 1
                    continue
                except Exception as e:
                    logger.exception(
                        "Auto-save failed to load tasks for user %s: %s", user_id, e
                    )
                    consecutive_errors += 1
                    continue

                current_time = time.time()
                last_save_time = _app_context.get_last_save_time()
                last_signature = _app_context.get_last_saved_tasks_signature()

                snapshot = json.dumps(tasks, sort_keys=True, separators=(",", ":"))
                signature = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

                if last_signature == signature:
                    logger.debug(
                        "No task changes detected since last auto-save; skipping save"
                    )
                    _app_context.set_last_save_time(current_time)
                    consecutive_errors = 0  # Reset on successful check
                    continue

                if last_save_time and current_time - last_save_time < max(
                    5, interval * 0.25
                ):
                    logger.debug("Auto-save interval guard prevented redundant save")
                    consecutive_errors = 0  # Reset on successful check
                    continue

                try:
                    success = _app_context.data_manager.save_tasks_for_user(
                        user_id, tasks
                    )

                    if success:
                        _app_context.set_last_save_time(current_time)
                        _app_context.set_last_saved_tasks_signature(signature)
                        logger.info(f"Auto-saved {len(tasks)} tasks for user {user_id}")
                        consecutive_errors = 0  # Reset on successful save
                    else:
                        logger.error(f"Auto-save failed for user {user_id}")
                        consecutive_errors += 1
                except DatabaseError as db_err:
                    logger.exception("Auto-save database error for user %s", user_id)
                    consecutive_errors += 1
                except Exception as e:
                    logger.exception("Auto-save save error for user %s: %s", user_id, e)
                    consecutive_errors += 1

            except Exception as e:  # noqa: broad-except - Background job must handle all exceptions to prevent crash
                logger.exception(
                    "Auto-save error for user %s: %s", user_id or "unknown", e
                )
                consecutive_errors += 1
            finally:
                try:
                    _app_context.set_save_in_progress(False)
                except Exception as e:
                    logger.exception("Failed to reset save_in_progress flag: %s", e)

        except Exception as e:
            logger.exception("Auto-save worker error: %s", e)
            consecutive_errors += 1
            time.sleep(5)

    logger.info("Auto-save worker stopped")
    try:
        _app_context.set_auto_save_running(False)
    except Exception as e:
        logger.exception("Failed to reset auto_save_running flag: %s", e)


def start_auto_save() -> None:
    global _thread
    if _app_context is None:
        raise RuntimeError("Auto-save requires app context")

    if _app_context.is_auto_save_running():
        logger.warning("Auto-save is already running")
        return

    _app_context.clear_auto_save_stop_event()
    _app_context.auto_save_enabled = True

    _thread = threading.Thread(
        target=auto_save_worker, daemon=True, name="AutoSaveWorker"
    )
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
