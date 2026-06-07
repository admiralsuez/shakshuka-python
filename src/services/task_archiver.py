"""
Auto-archive service for completed tasks older than specified days.

This module provides functionality to automatically archive completed tasks that
are older than a configurable threshold (default: 40 days). Archived tasks are
moved to a separate database table and are not included in active task count.

Features:
- Configurable archival age threshold
- Database-backed archival (archived_tasks table)
- Atomic transaction-based archival
- User can view and restore archived tasks
- Comprehensive error handling and logging
- Can be run on a schedule or manually
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.constants import AUTO_ARCHIVE_COMPLETED_DAYS, DEFAULT_USER_ID
from src.exceptions import DatabaseError

logger = logging.getLogger(__name__)

_app_context = None
_archiver_thread: threading.Thread = None


def set_app_context(app_context) -> None:
    """Set the app context for accessing the data manager."""
    global _app_context
    _app_context = app_context


def auto_archive_completed_tasks_for_user(
    user_id: str, days_old: int = AUTO_ARCHIVE_COMPLETED_DAYS, data_manager=None
) -> Dict[str, Any]:
    """
    Auto-archive completed tasks older than specified days for a user.

    This moves completed tasks from the active tasks table to the archived_tasks
    table, reducing the active task count for validation purposes.

    Args:
        user_id: User ID to archive tasks for
        days_old: Number of days old a completed task must be to archive (default: 40)
        data_manager: Data manager instance (if not using app_context)

    Returns:
        Dict with 'archived_count', 'failed_count', and 'errors' keys
    """
    if data_manager is None:
        if _app_context is None:
            logger.error("No app context or data manager available for archival")
            return {
                "archived_count": 0,
                "failed_count": 0,
                "errors": ["No data manager"],
            }
        data_manager = _app_context.data_manager

    if data_manager is None:
        logger.error("Data manager not available for task archival")
        return {
            "archived_count": 0,
            "failed_count": 0,
            "errors": ["Data manager unavailable"],
        }

    try:
        # Validate inputs
        if not user_id or not isinstance(user_id, str):
            logger.error("Invalid user_id for task archival: %s", user_id)
            return {
                "archived_count": 0,
                "failed_count": 0,
                "errors": ["Invalid user_id"],
            }

        if not isinstance(days_old, int) or days_old < 1 or days_old > 365:
            logger.warning(
                "Invalid days_old value %s, using default %d",
                days_old,
                AUTO_ARCHIVE_COMPLETED_DAYS,
            )
            days_old = AUTO_ARCHIVE_COMPLETED_DAYS

        logger.info(
            "Starting auto-archival for user %s: archiving completed tasks older than %d days",
            user_id,
            days_old,
        )

        # Use data manager's auto-archive method which handles the database operations
        try:
            archived_count = data_manager.auto_archive_old_completed_tasks(
                user_id, days_old
            )

            if archived_count > 0:
                logger.info(
                    "Successfully auto-archived %d completed tasks for user %s",
                    archived_count,
                    user_id,
                )

            return {"archived_count": archived_count, "failed_count": 0, "errors": []}

        except DatabaseError as e:
            logger.exception("Database error during task archival for user %s", user_id)
            return {
                "archived_count": 0,
                "failed_count": 0,
                "errors": [f"Database error: {str(e)}"],
            }
        except Exception as e:
            logger.exception(
                "Unexpected error during task archival for user %s: %s", user_id, e
            )
            return {
                "archived_count": 0,
                "failed_count": 0,
                "errors": [f"Unexpected error: {str(e)}"],
            }

    except Exception as e:
        logger.exception(
            "Unexpected error in auto_archive_completed_tasks_for_user: %s", e
        )
        return {
            "archived_count": 0,
            "failed_count": 0,
            "errors": [f"Critical error: {str(e)}"],
        }


def auto_archive_all_users_completed_tasks(
    days_old: int = AUTO_ARCHIVE_COMPLETED_DAYS, data_manager=None
) -> Dict[str, Any]:
    """
    Auto-archive completed tasks for all users.

    Args:
        days_old: Number of days old a completed task must be to archive
        data_manager: Data manager instance (if not using app_context)

    Returns:
        Dict with summary of archival results for all users
    """
    if data_manager is None:
        if _app_context is None:
            logger.error("No app context or data manager available for archival")
            return {"total_archived": 0, "total_errors": 0, "by_user": {}}
        data_manager = _app_context.data_manager

    if data_manager is None:
        logger.error("Data manager not available")
        return {"total_archived": 0, "total_errors": 0, "by_user": {}}

    try:
        # Get list of all users (for now, just use default user if available)
        # In a full implementation, you would query all users from the database
        users_to_process = [DEFAULT_USER_ID]

        total_archived = 0
        total_errors = 0
        by_user = {}

        for user_id in users_to_process:
            try:
                result = auto_archive_completed_tasks_for_user(
                    user_id, days_old, data_manager
                )
                by_user[user_id] = result
                total_archived += result.get("archived_count", 0)
                total_errors += result.get("failed_count", 0) + len(
                    result.get("errors", [])
                )
            except Exception as e:
                logger.exception("Error archiving tasks for user %s: %s", user_id, e)
                by_user[user_id] = {
                    "archived_count": 0,
                    "failed_count": 0,
                    "errors": [str(e)],
                }
                total_errors += 1

        logger.info(
            "Task archival complete: archived %d tasks, %d errors across %d users",
            total_archived,
            total_errors,
            len(users_to_process),
        )

        return {
            "total_archived": total_archived,
            "total_errors": total_errors,
            "by_user": by_user,
        }

    except Exception as e:
        logger.exception(
            "Critical error in auto_archive_all_users_completed_tasks: %s", e
        )
        return {"total_archived": 0, "total_errors": 1, "by_user": {}}


def archiver_worker() -> None:
    """
    Background worker for periodic task archival.

    Runs every 24 hours to archive completed tasks older than the threshold.
    Archived tasks are moved to the archived_tasks table and no longer count
    towards the active task limit for validation.
    """
    if _app_context is None:
        logger.error("Archiver worker started without app context")
        return

    logger.info("Task archiver worker started")

    while True:
        try:
            # Run archival every 24 hours
            run_interval = 24 * 60 * 60  # 24 hours in seconds

            # Wait for the interval
            logger.debug("Task archiver sleeping for %d seconds", run_interval)
            time.sleep(run_interval)

            # Check if archiver is still enabled
            if (
                not hasattr(_app_context, "archiver_enabled")
                or not _app_context.archiver_enabled
            ):
                logger.info("Task archiver disabled, stopping worker")
                break

            logger.info("Running scheduled task archival")
            result = auto_archive_all_users_completed_tasks(
                days_old=AUTO_ARCHIVE_COMPLETED_DAYS,
                data_manager=_app_context.data_manager,
            )

            if result.get("total_archived", 0) > 0:
                logger.info(
                    "Scheduled archival completed: archived %d tasks",
                    result.get("total_archived", 0),
                )

        except Exception as e:
            logger.exception("Error in archiver worker: %s", e)
            # Continue running despite errors
            time.sleep(60)

    logger.info("Task archiver worker stopped")


def start_archiver() -> None:
    """
    Start the background task archiver worker thread.

    The archiver will run every 24 hours to move completed tasks older than
    AUTO_ARCHIVE_COMPLETED_DAYS to the archived_tasks table.
    """
    global _archiver_thread

    if _app_context is None:
        logger.error("Cannot start archiver: no app context")
        return

    if hasattr(_app_context, "archiver_enabled") and _app_context.archiver_enabled:
        logger.warning("Task archiver already running")
        return

    try:
        _app_context.archiver_enabled = True
        _archiver_thread = threading.Thread(
            target=archiver_worker, daemon=True, name="TaskArchiverWorker"
        )
        _archiver_thread.start()
        logger.info("Task archiver thread started successfully")
    except Exception as e:
        logger.exception("Failed to start task archiver: %s", e)
        _app_context.archiver_enabled = False


def stop_archiver(timeout: float = 10.0) -> None:
    """
    Stop the background task archiver worker thread.

    Args:
        timeout: Maximum seconds to wait for thread to stop gracefully
    """
    if _app_context is None:
        return

    logger.info("Stopping task archiver...")

    _app_context.archiver_enabled = False

    if _archiver_thread and _archiver_thread.is_alive():
        _archiver_thread.join(timeout=timeout)

        if _archiver_thread.is_alive():
            logger.warning("Task archiver thread did not stop gracefully")
        else:
            logger.info("Task archiver thread stopped successfully")
