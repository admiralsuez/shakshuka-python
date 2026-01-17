from flask import Blueprint, jsonify, request
import logging
import os
import json
from datetime import datetime

from src.exceptions import ValidationError
from src.update_manager import UpdateIOError, UpdateIntegrityError

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
        logger.exception("Failed to initialize update manager")
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


def _validate_backup_name(backup_name: str) -> str:
    if not backup_name or not isinstance(backup_name, str):
        raise ValidationError(message='backup_name is required')
    if os.path.basename(backup_name) != backup_name:
        raise ValidationError(message='Invalid backup_name')
    return backup_name


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

        backup_name = _app_context.update_manager.create_backup(backup_type)
        logger.info("Backup created successfully: %s", backup_name)
        return jsonify({'success': True, 'message': 'Backup created successfully', 'backup_name': backup_name}), 201

    except ValidationError as e:
        logger.exception("Validation error creating backup")
        return jsonify({'error': str(e)}), 400
    except UpdateIOError as e:
        logger.exception("IO error creating backup")
        return jsonify({'error': str(e)}), 500
    except UpdateIntegrityError as e:
        logger.exception("Integrity error creating backup")
        return jsonify({'error': str(e)}), 500
    except Exception:  # noqa: broad-except
        logger.exception("Error creating backup")
        return jsonify({'error': 'Failed to create backup'}), 500


def restore_backup_with_validation():
    """Restore backup with integrity validation"""
    try:
        if not _ensure_update_manager():
            return jsonify({'error': 'Update manager not initialized'}), 500

        backup_data = request.json
        if backup_data is None or not isinstance(backup_data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        backup_name = _validate_backup_name(backup_data.get('backup_name'))

        try:
            safety_backup_name = f"safety_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            _app_context.update_manager.create_backup(safety_backup_name)
        except Exception:  # noqa: broad-except
            logger.exception("Failed to create safety backup")

        success = _app_context.update_manager.restore_backup(backup_name)
        if success:
            logger.info("Backup restored successfully: %s", backup_name)
            return jsonify({'success': True, 'message': 'Backup restored successfully'}), 200

        return jsonify({'error': 'Failed to restore backup'}), 500

    except ValidationError as e:
        logger.exception("Validation error restoring backup")
        return jsonify({'error': str(e)}), 400
    except UpdateIntegrityError as e:
        logger.exception("Integrity error restoring backup")
        return jsonify({'error': str(e)}), 409
    except UpdateIOError as e:
        logger.exception("IO error restoring backup")
        return jsonify({'error': str(e)}), 500
    except Exception:  # noqa: broad-except
        logger.exception("Error restoring backup")
        return jsonify({'error': 'Failed to restore backup'}), 500


@backups_bp.route('', methods=['GET'])
def get_backups():
    """Get list of available backups"""
    try:
        if not _ensure_update_manager():
            return jsonify({'error': 'Update manager not initialized'}), 500

        backups = _app_context.update_manager.get_backup_list()
        return jsonify({'backups': backups}), 200

    except UpdateIOError as e:
        logger.exception("IO error getting backups")
        return jsonify({'error': str(e)}), 500
    except UpdateIntegrityError as e:
        logger.exception("Integrity error getting backups")
        return jsonify({'error': str(e)}), 500
    except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
        logger.exception("Error getting backups")
        return jsonify({'error': 'Failed to get backups'}), 500


@backups_bp.route('/create', methods=['POST'])
def create_backup():
    """Create manual backup with validation"""
    return create_backup_with_validation()


@backups_bp.route('/restore', methods=['POST'])
def restore_backup():
    """Restore from backup with validation"""
    return restore_backup_with_validation()
