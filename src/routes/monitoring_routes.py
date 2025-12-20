from flask import Blueprint, jsonify
import logging
import os
import time

from src.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/monitoring")

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
    try:
        return jsonify(_monitor.get_health_status())
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return jsonify({'error': 'Failed to get health status'}), 500


@monitoring_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics"""
    try:
        return jsonify(_monitor.get_metrics_summary())
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': 'Failed to get metrics'}), 500


@monitoring_bp.route('/export', methods=['POST'])
def export_metrics():
    """Export metrics to file in the user data directory"""
    try:
        user_id = _get_user_id()
        export_dir = os.path.join(_get_user_data_dir_func(), 'metrics') if _get_user_data_dir_func else os.path.join(os.getcwd(), 'metrics')
        os.makedirs(export_dir, exist_ok=True)
        export_path = os.path.join(export_dir, f"metrics_export_{user_id}_{int(time.time())}.json")

        if _monitor.export_metrics(export_path):
            return jsonify({'success': True, 'file_path': export_path})

        return jsonify({'error': 'Failed to export metrics'}), 500

    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        return jsonify({'error': 'Failed to export metrics'}), 500


@monitoring_bp.route('/rate-limit-stats', methods=['GET'])
def get_rate_limit_stats():
    """Get rate limiting statistics"""
    try:
        return jsonify(_security_manager.get_rate_limit_stats())
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        return jsonify({'error': 'Failed to get rate limit stats'}), 500
