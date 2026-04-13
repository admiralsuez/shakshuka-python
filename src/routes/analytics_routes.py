"""Analytics routes blueprint.

Handles analytics-related API endpoints including:
- Basic analytics counters
- Strike calendar
- Daily recap
- Consolidated analytics summary
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from src.exceptions import DatabaseError, ValidationError
from src.routes.api_utils import get_json_object, register_api_error_handlers

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

register_api_error_handlers(analytics_bp)

# These will be set by the app during initialization
_app_context = None
_get_user_id = None


def init_analytics_routes(app_context, get_user_id_func):
    """Initialize the analytics routes with app context and user ID function."""
    global _app_context, _get_user_id
    _app_context = app_context
    _get_user_id = get_user_id_func


def ensure_data_manager():
    """Check if data manager is available."""
    if not _app_context or not _app_context.data_manager:
        raise DatabaseError(message='Data manager not available')
    return True


@analytics_bp.route('', methods=['GET'])
def get_analytics():
    """Return decoupled analytics counters backed by SQLite."""
    user_id = _get_user_id()
    ensure_data_manager()
    
    counters = _app_context.data_manager.load_counters(user_id)
    return jsonify({
        'tasks_added': counters.get('tasks_added', 0),
        'tasks_completed': counters.get('tasks_completed', 0),
        'tasks_retried': counters.get('tasks_retried', 0),
        'settings_changes': counters.get('settings_changes', 0),
    }), 200


@analytics_bp.route('/strike-calendar', methods=['GET'])
def get_strike_calendar():
    """Return strike contribution calendar counts for a given month."""
    user_id = _get_user_id()
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    ensure_data_manager()
    
    try:
        result = _app_context.data_manager.get_strike_contributions_for_month(user_id, month)
        result['success'] = True
        return jsonify(result), 200
    except ValidationError as e:
        logger.exception("Invalid strike calendar request")
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception("Database error fetching strike calendar")
        return jsonify({'success': False, 'error': 'Database error fetching strike calendar'}), 503
    except Exception as e:
        logger.error(f"Error fetching strike calendar for {month}: {e}")
        return jsonify({'success': False, 'error': 'Strike calendar error'}), 500


@analytics_bp.route('/daily-recap', methods=['GET'])
def get_daily_recap():
    """Return recap metrics for a given day (defaults to yesterday)."""
    user_id = _get_user_id()
    day = request.args.get('day', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    
    ensure_data_manager()
    
    try:
        result = _app_context.data_manager.get_daily_recap(user_id, day)
        result['success'] = True
        return jsonify(result), 200
    except ValidationError as e:
        logger.exception("Invalid daily recap request")
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception("Database error fetching daily recap")
        return jsonify({'success': False, 'error': 'Database error fetching daily recap'}), 503
    except Exception as e:
        logger.error(f"Error fetching daily recap for {day}: {e}")
        return jsonify({'success': False, 'error': 'Daily recap error'}), 500


@analytics_bp.route('/daily-recap/seen', methods=['POST'])
def mark_daily_recap_seen():
    """Mark daily recap as seen."""
    user_id = _get_user_id()
    ensure_data_manager()

    payload = get_json_object(required=False)
    day = payload.get('day')
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        _app_context.data_manager.mark_recap_seen(user_id, day)
        return jsonify({'success': True}), 200
    except ValidationError as e:
        logger.exception("Invalid mark recap seen request")
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception("Database error marking recap seen")
        return jsonify({'success': False, 'error': 'Database error marking recap seen'}), 503
    except Exception as e:
        logger.error(f"Error marking recap seen for {day}: {e}")
        return jsonify({'success': False, 'error': 'Mark recap seen error'}), 500


@analytics_bp.route('/daily-recap/feedback', methods=['GET'])
def get_daily_recap_feedback():
    """Return saved feedback answers for a given day.

    Query param: day=YYYY-MM-DD  (defaults to yesterday)
    Response: {success: true, day: str, feedback: {question_key: answer}}
    """
    user_id = _get_user_id()
    day = request.args.get('day', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))

    ensure_data_manager()

    try:
        feedback = _app_context.data_manager.load_recap_feedback(user_id, day)
        return jsonify({'success': True, 'day': day, 'feedback': feedback}), 200
    except DatabaseError:
        logger.exception("Database error loading recap feedback for day %s", day)
        return jsonify({'success': False, 'error': 'Database error loading recap feedback'}), 503
    except Exception as e:
        logger.error("Error loading recap feedback for %s: %s", day, e)
        return jsonify({'success': False, 'error': 'Error loading recap feedback'}), 500


@analytics_bp.route('/daily-recap/feedback', methods=['POST'])
def save_daily_recap_feedback():
    """Persist feedback answers for a given day.

    Body: {day: YYYY-MM-DD, answers: {question_key: answer_string}}
    Allowed question keys: went_well, improve_tomorrow, mood_rating
    """
    user_id = _get_user_id()
    ensure_data_manager()

    payload = get_json_object(required=True)
    day = payload.get('day')
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    answers_raw = payload.get('answers')
    if not isinstance(answers_raw, dict):
        return jsonify({'success': False, 'error': 'answers must be an object'}), 400

    # Allow only the three defined question keys.
    allowed_keys = {'went_well', 'improve_tomorrow', 'mood_rating'}
    answers = {k: v for k, v in answers_raw.items() if k in allowed_keys}
    if not answers:
        return jsonify({'success': False, 'error': 'No valid answer keys provided'}), 400

    try:
        _app_context.data_manager.save_recap_feedback(user_id, day, answers)
        return jsonify({'success': True, 'day': day}), 200
    except DatabaseError:
        logger.exception("Database error saving recap feedback for day %s", day)
        return jsonify({'success': False, 'error': 'Database error saving recap feedback'}), 503
    except Exception as e:
        logger.error("Error saving recap feedback for %s: %s", day, e)
        return jsonify({'success': False, 'error': 'Error saving recap feedback'}), 500


@analytics_bp.route('/heartbeat', methods=['POST'])
def record_user_activity():
    """Record user heartbeat to track active users. Call every 1 minute."""
    user_id = _get_user_id()
    ensure_data_manager()

    try:
        _app_context.data_manager.record_user_heartbeat(user_id)
        return jsonify({'success': True}), 200
    except DatabaseError:
        logger.exception("Database error recording user heartbeat for user %s", user_id)
        return jsonify({'success': False, 'error': 'Database error'}), 503
    except Exception as e:
        logger.error("Error recording heartbeat for user %s: %s", user_id, e)
        return jsonify({'success': False, 'error': 'Heartbeat error'}), 500


@analytics_bp.route('/active-users', methods=['GET'])
def get_active_users():
    """Get count of users active in the last 2 minutes."""
    ensure_data_manager()

    try:
        active_count = _app_context.data_manager.count_active_users(minutes=2)
        return jsonify({'success': True, 'active_users': active_count}), 200
    except DatabaseError:
        logger.exception("Database error counting active users")
        return jsonify({'success': False, 'error': 'Database error', 'active_users': 0}), 503
    except Exception as e:
        logger.error("Error counting active users: %s", e)
        return jsonify({'success': False, 'error': 'Error', 'active_users': 0}), 500


@analytics_bp.route('/installed-users', methods=['GET'])
def get_installed_users():
    """Get total count of all users who have installed/accessed the app."""
    ensure_data_manager()

    try:
        installed_count = _app_context.data_manager.count_installed_users()
        return jsonify({'success': True, 'installed_users': installed_count}), 200
    except DatabaseError:
        logger.exception("Database error counting installed users")
        return jsonify({'success': False, 'error': 'Database error', 'installed_users': 0}), 503
    except Exception as e:
        logger.error("Error counting installed users: %s", e)
        return jsonify({'success': False, 'error': 'Error', 'installed_users': 0}), 500
