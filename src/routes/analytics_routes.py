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

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

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
    return _app_context and _app_context.data_manager


@analytics_bp.route('', methods=['GET'])
def get_analytics():
    """Return decoupled analytics counters backed by SQLite."""
    user_id = _get_user_id()
    if not ensure_data_manager():
        return jsonify({'error': 'Data manager not available'}), 500
    
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
    
    if not ensure_data_manager():
        return jsonify({'success': False, 'month': month, 'days': {}, 'added': {}, 'max': 0, 'months': []}), 200
    
    try:
        result = _app_context.data_manager.get_strike_contributions_for_month(user_id, month)
        result['success'] = True
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching strike calendar for {month}: {e}")
        return jsonify({'success': False, 'month': month, 'days': {}, 'added': {}, 'max': 0, 'months': []}), 200


@analytics_bp.route('/daily-recap', methods=['GET'])
def get_daily_recap():
    """Return recap metrics for a given day (defaults to yesterday)."""
    user_id = _get_user_id()
    day = request.args.get('day', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    
    if not ensure_data_manager():
        return jsonify({'success': False, 'seen': False, 'day': day}), 200
    
    try:
        result = _app_context.data_manager.get_daily_recap(user_id, day)
        result['success'] = True
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching daily recap for {day}: {e}")
        return jsonify({'success': False, 'seen': False, 'day': day}), 200


@analytics_bp.route('/daily-recap/seen', methods=['POST'])
def mark_daily_recap_seen():
    """Mark daily recap as seen."""
    user_id = _get_user_id()
    if not ensure_data_manager():
        return jsonify({'success': False}), 200
    
    day = request.json.get('day') if request.json else None
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        _app_context.data_manager.mark_daily_recap_seen(user_id, day)
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Error marking recap seen for {day}: {e}")
        return jsonify({'success': False}), 200
