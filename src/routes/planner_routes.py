from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError
from src.routes.api_utils import get_json_object, register_api_error_handlers

logger = logging.getLogger(__name__)

planner_bp = Blueprint("planner_v2", __name__, url_prefix="/api/planner-v2")

register_api_error_handlers(planner_bp)

_app_context = None
_get_user_id_func = None
_ensure_data_manager_func = None


def init_planner_routes(app_context, get_user_id_func, ensure_data_manager_func=None):
    global _app_context, _get_user_id_func, _ensure_data_manager_func
    _app_context = app_context
    _get_user_id_func = get_user_id_func
    _ensure_data_manager_func = ensure_data_manager_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _get_data_manager():
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return None
    return _app_context.data_manager if _app_context else None


@planner_bp.route("/schedule", methods=["GET"])
def get_planner_v2_schedule():
    """Get scheduled tasks for Daily Planner v2"""
    logger.info("GET /api/planner-v2/schedule called")
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            raise DatabaseError(message='Data manager not available')

        try:
            tasks = dm.load_tasks(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for planner v2 schedule (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading tasks'}), 503
        
        logger.info(f"[DEBUG] Loaded {len(tasks)} total tasks for user {user_id}")
        scheduled_tasks = {}
        scheduled_count = 0

        for task in tasks:
            task_id = task.get('id', 'unknown')
            scheduled_hour = task.get('scheduled_hour')
            scheduled_date = task.get('scheduled_date')
            logger.info(f"[DEBUG] Task {task_id}: scheduled_hour={scheduled_hour}, scheduled_date={scheduled_date}")
            
            if scheduled_hour is not None and scheduled_date:
                scheduled_count += 1
                logger.info(f"[DEBUG] Task {task_id} is SCHEDULED for {scheduled_date} at {scheduled_hour}")

                if scheduled_date not in scheduled_tasks:
                    scheduled_tasks[scheduled_date] = {}

                if scheduled_hour not in scheduled_tasks[scheduled_date]:
                    scheduled_tasks[scheduled_date][scheduled_hour] = []

                scheduled_tasks[scheduled_date][scheduled_hour].append(task)
        
        logger.info(f"[DEBUG] Found {scheduled_count} scheduled tasks out of {len(tasks)} total")
        logger.info(f"[DEBUG] Scheduled tasks dict: {scheduled_tasks.keys()}")

        response = jsonify({'success': True, 'scheduled_tasks': scheduled_tasks})
        # Disable caching to ensure fresh data
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    except Exception as e:
        logger.exception("Error loading planner v2 schedule")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/schedule", methods=["POST"])
def save_planner_v2_schedule():
    """Save scheduled tasks for Daily Planner v2"""
    user_id = _get_user_id()
    try:
        data = get_json_object(required=True)

        scheduled_tasks = data.get('scheduled_tasks', {})
        if scheduled_tasks is None:
            scheduled_tasks = {}
        if not isinstance(scheduled_tasks, dict):
            return jsonify({'success': False, 'error': 'scheduled_tasks must be an object'}), 400

        for date_key, by_hour in scheduled_tasks.items():
            if not isinstance(date_key, str):
                return jsonify({'success': False, 'error': 'scheduled_tasks keys must be date strings'}), 400
            try:
                datetime.strptime(date_key, '%Y-%m-%d')
            except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
                return jsonify({'success': False, 'error': f"Invalid scheduled date: {date_key}"}), 400

            if not isinstance(by_hour, dict):
                return jsonify({'success': False, 'error': f"scheduled_tasks[{date_key}] must be an object"}), 400

            for hour_key, tasks_list in by_hour.items():
                try:
                    hour_int = int(hour_key)
                except Exception:  # noqa: broad-except
                    return jsonify({'success': False, 'error': f"Invalid hour key: {hour_key}"}), 400
                if hour_int < 0 or hour_int > 23:
                    return jsonify({'success': False, 'error': f"Invalid hour: {hour_int}"}), 400

                if not isinstance(tasks_list, list):
                    return jsonify({'success': False, 'error': f"scheduled_tasks[{date_key}][{hour_key}] must be a list"}), 400

                for idx, t in enumerate(tasks_list):
                    if not isinstance(t, dict):
                        return jsonify({'success': False, 'error': f"Task at {date_key}/{hour_key}[{idx}] must be an object"}), 400
                    tid = t.get('id')
                    if not tid or not isinstance(tid, str):
                        return jsonify({'success': False, 'error': f"Task at {date_key}/{hour_key}[{idx}] missing valid id"}), 400

        dm = _get_data_manager()
        if not dm:
            raise DatabaseError(message='Data manager not available')

        try:
            success = dm.save_planner_v2_schedule(user_id, scheduled_tasks)
        except DatabaseError:
            logger.exception("Database error saving planner v2 schedule (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error saving schedule'}), 503
        if success:
            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Failed to save schedule'}), 500

    except Exception as e:
        logger.exception("Error saving planner v2 schedule")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/tasks", methods=["GET"])
def get_planner_v2_available_tasks():
    """Get available tasks for Daily Planner v2"""
    logger.info("GET /api/planner-v2/tasks called")
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        try:
            tasks = dm.load_tasks(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for planner v2 available tasks (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading tasks'}), 503

        today_str = datetime.now().strftime('%Y-%m-%d')

        available_tasks = []
        for task in tasks:
            is_completed = task.get('completed', False)
            is_struck_today = task.get('struck_today', False)
            is_scheduled = task.get('scheduled_hour') is not None and task.get('scheduled_date') is not None

            # Exclude snoozed tasks ("hide for X days") from available pool until
            # their snoozed_until date is today or earlier.
            snoozed_until = task.get('snoozed_until')
            is_snoozed = False
            if isinstance(snoozed_until, str) and snoozed_until.strip():
                try:
                    is_snoozed = snoozed_until.strip() > today_str
                except Exception:  # noqa: broad-except - defensive, string compare only
                    is_snoozed = False

            if not is_completed and not is_struck_today and not is_scheduled and not is_snoozed:
                available_tasks.append({
                    'id': task.get('id'),
                    'title': task.get('title', ''),
                    'description': task.get('description', ''),
                    'priority': task.get('priority', 'medium'),
                    'due_date': task.get('due_date'),
                    'created_at': task.get('created_at'),
                    'estimated_duration': task.get('estimated_duration', 30)
                })

        return jsonify({'success': True, 'available_tasks': available_tasks})

    except Exception as e:
        logger.exception("Error loading planner v2 available tasks")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/cleanup-overdue", methods=["POST"])
def cleanup_overdue_scheduled_tasks():
    """Unschedule any tasks scheduled for previous days if not completed."""
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        today_str = datetime.now().strftime('%Y-%m-%d')

        try:
            tasks = dm.load_tasks(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for cleanup_overdue_scheduled_tasks (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading tasks'}), 503
        unscheduled = 0
        for t in tasks:
            scheduled_date = t.get('scheduled_date')
            if scheduled_date and scheduled_date < today_str:
                t['scheduled_hour'] = None
                t['scheduled_minute'] = None
                t['scheduled_date'] = None
                t['scheduled_duration'] = None
                unscheduled += 1

        if unscheduled > 0:
            if not dm.save_tasks(tasks, user_id):
                return jsonify({'success': False, 'error': 'Failed to save tasks after cleanup'}), 500

        return jsonify({'success': True, 'unscheduled': unscheduled})

    except Exception as e:
        logger.exception("Error cleaning up overdue scheduled tasks")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/history", methods=["GET"])
def get_planner_history_days():
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        limit_raw = request.args.get('limit', '7')
        try:
            limit = int(limit_raw)
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            limit = 7
        if limit <= 0:
            limit = 7
        if limit > 30:
            limit = 30

        try:
            days = dm.load_planner_history_days(user_id, limit=limit)
        except DatabaseError:
            logger.exception("Database error loading planner history days (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading history'}), 503
        return jsonify({'success': True, 'days': days})
    except Exception as e:
        logger.exception("Error loading planner history days")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/history/<day>", methods=["GET"])
def get_planner_history_for_day(day: str):
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        try:
            datetime.strptime(day, '%Y-%m-%d')
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            return jsonify({'success': False, 'error': 'Invalid day'}), 400

        try:
            entries = dm.load_planner_history_for_day(user_id, day)
        except DatabaseError:
            logger.exception("Database error loading planner history for day %s (user %s)", day, user_id)
            return jsonify({'success': False, 'error': 'Database error loading history'}), 503
        return jsonify({'success': True, 'day': day, 'entries': entries})
    except Exception as e:
        logger.exception("Error loading planner history for day %s", day)
        return jsonify({'success': False, 'error': str(e)}), 500
