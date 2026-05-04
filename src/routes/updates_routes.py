from flask import Blueprint, jsonify, request
import logging
import os
import sys

from src.exceptions import ValidationError
from src.update_manager import UpdateIOError, UpdateIntegrityError

# Import decorators
from src.routes.route_decorators import (
    require_json_body,
    handle_database_error
)

logger = logging.getLogger(__name__)

updates_bp = Blueprint("updates", __name__, url_prefix="/api/updates")

_app_context = None
_update_manager_cls = None
_get_user_data_dir_func = None


def init_updates_routes(app_context, update_manager_cls, get_user_data_dir_func):
    global _app_context, _update_manager_cls, _get_user_data_dir_func
    _app_context = app_context
    _update_manager_cls = update_manager_cls
    _get_user_data_dir_func = get_user_data_dir_func


def _ensure_update_manager():
    if not _app_context:
        return False

    if _app_context.update_manager:
        return True

    try:
        app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = _get_user_data_dir_func() if _get_user_data_dir_func else None
        _app_context.update_manager = _update_manager_cls(app_dir=app_root, data_dir=data_dir)
        return True
    except Exception as e:
        logger.exception("Failed to initialize update manager")
        return False


@updates_bp.route('/status', methods=['GET'])
@handle_database_error
def get_update_status():
    """Get current update status"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    return jsonify(_app_context.update_manager.get_update_status())


@updates_bp.route('/check', methods=['POST'])
@handle_database_error
def check_for_updates():
    """Check for available updates"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    update_info = _app_context.update_manager.check_for_updates()
    if update_info:
        return jsonify({'update_available': True, 'update_info': update_info})

    return jsonify({'update_available': False})


@updates_bp.route('/download', methods=['POST'])
@require_json_body
@handle_database_error
def download_update():
    """Start downloading the available update in background"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    update_info = request.json
    download_url = update_info.get('download_url')
    version = update_info.get('version')
    if not isinstance(download_url, str) or not download_url.strip():
        return jsonify({'error': 'download_url required'}), 400
    if not isinstance(version, str) or not version.strip():
        return jsonify({'error': 'version required'}), 400

    status = _app_context.update_manager.get_download_status()
    if (status.get('status') or '').lower() == 'downloading':
        return jsonify({'error': 'Download already in progress', 'status': status}), 409

    _app_context.update_manager.start_download(update_info)
    return jsonify({'started': True}), 202


@updates_bp.route('/install', methods=['POST'])
@require_json_body
@handle_database_error
def install_update():
    """Install downloaded update"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    update_data = request.json
    if update_data is None:
        update_data = {}

    update_file = update_data.get('update_file')
    backup_data = update_data.get('backup_before_update', True)

    if not isinstance(backup_data, bool):
        return jsonify({'error': 'backup_before_update must be boolean'}), 400

    if not update_file:
        status = _app_context.update_manager.get_download_status()
        update_file = status.get('update_file')
        if not update_file:
            return jsonify({'error': 'Update file required'}), 400

    if not isinstance(update_file, str):
        return jsonify({'error': 'update_file must be a string'}), 400

    # Do not allow arbitrary absolute paths from clients.
    update_file = os.path.basename(update_file)

    update_file = str(_app_context.update_manager.update_dir / update_file)

    success = _app_context.update_manager.install_update(update_file, backup_data)

    if success:
        return jsonify({'success': True, 'message': 'Update installed successfully. Please restart the application.'})

    status = _app_context.update_manager.get_download_status()
    return jsonify({'error': status.get('error') or 'Failed to install update', 'status': status}), 500


@updates_bp.route('/progress', methods=['GET'])
@handle_database_error
def get_download_progress():
    """Get current download/install progress."""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    return jsonify(_app_context.update_manager.get_download_status())


@updates_bp.route('/cancel', methods=['POST'])
@handle_database_error
def cancel_update_download():
    """Cancel current update download if in progress."""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    _app_context.update_manager.cancel_download()
    return jsonify({'success': True, 'status': _app_context.update_manager.get_download_status()})


@updates_bp.route('/config', methods=['GET'])
@handle_database_error
def get_update_config():
    """Get update configuration"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    return jsonify(_app_context.update_manager.update_config)


@updates_bp.route('/config', methods=['PUT'])
@require_json_body
@handle_database_error
def update_update_config():
    """Update update configuration"""
    if not _ensure_update_manager():
        return jsonify({'error': 'Update manager not initialized'}), 500

    config_data = request.json
    if config_data is None or not isinstance(config_data, dict) or not config_data:
        return jsonify({'error': 'Configuration data required'}), 400

    _app_context.update_manager.update_config.update(config_data)
    _app_context.update_manager._save_update_config(_app_context.update_manager.update_config)
    return jsonify({'success': True, 'message': 'Configuration updated successfully'})
