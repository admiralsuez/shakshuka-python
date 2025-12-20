from flask import Blueprint, jsonify, request
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

backups_bp = Blueprint("backups", __name__, url_prefix="/api/backups")

_app_context = None
_update_manager_cls = None
_get_user_data_dir_func = None


def init_backups_routes(app_context, update_manager_cls, get_user_data_dir_func):
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
        import sys
        app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = _get_user_data_dir_func() if _get_user_data_dir_func else None
        _app_context.update_manager = _update_manager_cls(app_dir=app_root, data_dir=data_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize update manager: {e}")
        return False


def validate_backup_integrity(backup_path):
    """Validate backup file integrity and detect corruption"""
    try:
        if not os.path.exists(backup_path):
            return False, "Backup file does not exist"

        file_size = os.path.getsize(backup_path)
        if file_size == 0:
            return False, "Backup file is empty"

        if file_size > 100 * 1024 * 1024:
            return False, "Backup file too large (>100MB)"

        if not os.access(backup_path, os.R_OK):
            return False, "Backup file not readable"

        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if backup_path.endswith('.json'):
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON in backup: {e}"

            if len(content) < 10:
                return False, "Backup content too short"

            if '\x00' in content:
                return False, "Backup contains null bytes (possible corruption)"

            return True, "Backup integrity validated"

        except UnicodeDecodeError:
            return False, "Backup file encoding error"
        except Exception as e:
            return False, f"Error reading backup file: {e}"

    except Exception as e:
        return False, f"Backup validation error: {e}"


def create_backup_with_validation():
    """Create backup with integrity validation"""
    try:
        if not _ensure_update_manager():
            return jsonify({'error': 'Update manager not initialized'}), 500

        backup_data = request.json
        if backup_data is None:
            backup_data = {}
        if not isinstance(backup_data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        backup_type = backup_data.get('type', 'manual')
        if not isinstance(backup_type, str) or backup_type.strip() == "":
            return jsonify({'error': 'type must be a non-empty string'}), 400

        success = _app_context.update_manager.create_backup(backup_type)
        if not success:
            return jsonify({'error': 'Failed to create backup'}), 500

        backup_dir = os.path.join(os.getcwd(), "backups")
        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith(('.json', '.zip', '.tar.gz'))]
            if backup_files:
                latest_backup = max(backup_files, key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)))
                backup_path = os.path.join(backup_dir, latest_backup)

                is_valid, message = validate_backup_integrity(backup_path)
                if not is_valid:
                    logger.error(f"Backup validation failed: {message}")
                    return jsonify({'error': f'Backup created but validation failed: {message}'}), 500

                logger.info(f"Backup created and validated successfully: {latest_backup}")
                return jsonify({'success': True, 'message': 'Backup created and validated successfully', 'backup_file': latest_backup})

        return jsonify({'success': True, 'message': 'Backup created successfully'})

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'error': 'Failed to create backup'}), 500


def restore_backup_with_validation():
    """Restore backup with integrity validation"""
    try:
        if not _ensure_update_manager():
            return jsonify({'error': 'Update manager not initialized'}), 500

        backup_data = request.json
        if backup_data is None or not isinstance(backup_data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        backup_name = backup_data.get('backup_name')
        if not backup_name:
            return jsonify({'error': 'Backup name is required'}), 400

        backup_dir = os.path.join(os.getcwd(), "backups")
        backup_path = os.path.join(backup_dir, backup_name)

        is_valid, message = validate_backup_integrity(backup_path)
        if not is_valid:
            logger.error(f"Backup validation failed before restore: {message}")
            return jsonify({'error': f'Backup validation failed: {message}'}), 400

        try:
            safety_backup_name = f"safety_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            safety_success = _app_context.update_manager.create_backup(safety_backup_name)
            if not safety_success:
                logger.warning("Failed to create safety backup before restore")
        except Exception as e:
            logger.warning(f"Failed to create safety backup: {e}")

        success = _app_context.update_manager.restore_backup(backup_name)
        if success:
            logger.info(f"Backup restored successfully: {backup_name}")
            return jsonify({'success': True, 'message': 'Backup restored successfully'})

        logger.error(f"Failed to restore backup: {backup_name}")
        return jsonify({'error': 'Failed to restore backup'}), 500

    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({'error': 'Failed to restore backup'}), 500


@backups_bp.route('', methods=['GET'])
def get_backups():
    """Get list of available backups"""
    try:
        if not _ensure_update_manager():
            return jsonify({'error': 'Update manager not initialized'}), 500

        backups = _app_context.update_manager.get_backup_list()
        return jsonify({'backups': backups})

    except Exception as e:
        logger.error(f"Error getting backups: {e}")
        return jsonify({'error': 'Failed to get backups'}), 500


@backups_bp.route('/create', methods=['POST'])
def create_backup():
    """Create manual backup with validation"""
    return create_backup_with_validation()


@backups_bp.route('/restore', methods=['POST'])
def restore_backup():
    """Restore from backup with validation"""
    return restore_backup_with_validation()
