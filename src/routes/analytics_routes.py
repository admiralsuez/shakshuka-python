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
