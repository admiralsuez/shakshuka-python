from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

from src.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

planner_bp = Blueprint("planner_v2", __name__, url_prefix="/api/planner-v2")

_app_context = None
_get_user_id_func = None


def init_planner_routes(app_context, get_user_id_func):
    global _app_context, _get_user_id_func
    _app_context = app_context
    _get_user_id_func = get_user_id_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _get_data_manager():
    return _app_context.data_manager if _app_context else None


@planner_bp.route("/schedule", methods=["GET"])
def get_planner_v2_schedule():
    """Get scheduled tasks for Daily Planner v2"""
    logger.info("GET /api/planner-v2/schedule called")
    user_id = _get_user_id()
    try:
        dm = _get_data_manager()
        if not dm:
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        tasks = dm.load_tasks(user_id)
        scheduled_tasks = {}

        for task in tasks:
            if task.get('scheduled_hour') is not None and task.get('scheduled_date'):
                scheduled_date = task['scheduled_date']
                scheduled_hour = task['scheduled_hour']

                if scheduled_date not in scheduled_tasks:
                    scheduled_tasks[scheduled_date] = {}

                if scheduled_hour not in scheduled_tasks[scheduled_date]:
                    scheduled_tasks[scheduled_date][scheduled_hour] = []

                scheduled_tasks[scheduled_date][scheduled_hour].append(task)

        return jsonify({'success': True, 'scheduled_tasks': scheduled_tasks})

    except Exception as e:
        logger.error(f"Error loading planner v2 schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@planner_bp.route("/schedule", methods=["POST"])
def save_planner_v2_schedule():
    """Save scheduled tasks for Daily Planner v2"""
    user_id = _get_user_id()
    try:
        data = request.json
        if data is None or not isinstance(data, dict):
            return jsonify({'success': False, 'error': 'Request must contain JSON object'}), 400

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
            except Exception:
                return jsonify({'success': False, 'error': f"Invalid scheduled date: {date_key}"}), 400

            if not isinstance(by_hour, dict):
                return jsonify({'success': False, 'error': f"scheduled_tasks[{date_key}] must be an object"}), 400

            for hour_key, tasks_list in by_hour.items():
                try:
                    hour_int = int(hour_key)
                except Exception:
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
            return jsonify({'success': False, 'error': 'Data manager not available'}), 500

        success = dm.save_planner_v2_schedule(user_id, scheduled_tasks)
        if success:
            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Failed to save schedule'}), 500

    except Exception as e:
        logger.error(f"Error saving planner v2 schedule: {e}")
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

        tasks = dm.load_tasks(user_id)

        available_tasks = []
        for task in tasks:
            is_completed = task.get('completed', False)
            is_struck_today = task.get('struck_today', False)
            is_scheduled = task.get('scheduled_hour') is not None and task.get('scheduled_date') is not None

            if not is_completed and not is_struck_today and not is_scheduled:
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
        logger.error(f"Error loading planner v2 available tasks: {e}")
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

        tasks = dm.load_tasks(user_id)
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
        logger.error(f"Error cleaning up overdue scheduled tasks: {e}")
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
        except Exception:
            limit = 7
        if limit <= 0:
            limit = 7
        if limit > 30:
            limit = 30

        days = dm.load_planner_history_days(user_id, limit=limit)
        return jsonify({'success': True, 'days': days})
    except Exception as e:
        logger.error(f"Error loading planner history days: {e}")
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
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid day'}), 400

        entries = dm.load_planner_history_for_day(user_id, day)
        return jsonify({'success': True, 'day': day, 'entries': entries})
    except Exception as e:
        logger.error(f"Error loading planner history for day {day}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
