from flask import Blueprint, jsonify
import logging
import os
import time

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError
from src.routes.api_utils import register_api_error_handlers, require_dependency

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/monitoring")

register_api_error_handlers(monitoring_bp)

_monitor = None
_security_manager = None
_get_user_id_func = None
_get_user_data_dir_func = None


def init_monitoring_routes(monitor, security_manager, get_user_id_func, get_user_data_dir_func):
    global _monitor, _security_manager, _get_user_id_func, _get_user_data_dir_func
    _monitor = monitor
    _security_manager = security_manager
    _get_user_id_func = get_user_id_func
    _get_user_data_dir_func = get_user_data_dir_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


@monitoring_bp.route('/health', methods=['GET'])
def get_health_status():
    """Get system health status"""
    monitor = require_dependency(_monitor, 'monitor')
    return jsonify(monitor.get_health_status()), 200


@monitoring_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics"""
    monitor = require_dependency(_monitor, 'monitor')
    return jsonify(monitor.get_metrics_summary()), 200


@monitoring_bp.route('/export', methods=['POST'])
def export_metrics():
    """Export metrics to file in the user data directory"""
    monitor = require_dependency(_monitor, 'monitor')
    user_id = _get_user_id()
    if not _get_user_data_dir_func:
        raise DatabaseError(message='User data dir resolver not available')

    export_dir = os.path.join(_get_user_data_dir_func(), 'metrics')
    os.makedirs(export_dir, exist_ok=True)
    export_path = os.path.join(export_dir, f"metrics_export_{user_id}_{int(time.time())}.json")

    if monitor.export_metrics(export_path):
        return jsonify({'success': True, 'file_path': export_path}), 200

    raise DatabaseError(message='Failed to export metrics')


@monitoring_bp.route('/rate-limit-stats', methods=['GET'])
def get_rate_limit_stats():
    """Get rate limiting statistics"""
    security_manager = require_dependency(_security_manager, 'security_manager')
    return jsonify(security_manager.get_rate_limit_stats()), 200
