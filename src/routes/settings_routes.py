"""
Settings Routes - User settings and autostart management

This module handles:
- Settings GET/PUT endpoints
- Autostart status endpoint
"""

from flask import Blueprint, request, jsonify, current_app
import logging
import sys
import os

from src.constants import DEFAULT_USER_ID
from src.exceptions import AutostartError, DatabaseError, SettingsError, ValidationError
from src.routes.api_utils import get_json_object, register_api_error_handlers

# Import decorators
from src.routes.route_decorators import (
    require_data_manager,
    require_json_body,
    handle_database_error
)

logger = logging.getLogger(__name__)

# Blueprint definition
settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')

register_api_error_handlers(settings_bp)

# These will be injected at runtime
_app_context = None
_get_user_id_func = None


def _get_app_context():
    ctx = _app_context
    if ctx is None:
        try:
            ctx = current_app.extensions.get('app_context')
        except Exception:  # noqa: broad-except
            ctx = None
    return ctx


def init_settings_routes(app_context, get_user_id_func):
    """Initialize settings routes with dependency injection"""
    global _app_context, _get_user_id_func
    _app_context = app_context
    _get_user_id_func = get_user_id_func


def _get_user_id():
    """Get current user ID"""
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _validate_time_format(time_str: str) -> bool:
    """Validate time format (HH:MM)"""
    if not isinstance(time_str, str):
        return False
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return False
        hour, minute = int(parts[0]), int(parts[1])
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except (ValueError, IndexError):
        return False


@settings_bp.route('/autostart', methods=['GET'])
@handle_database_error
def get_autostart_status():
    """Get autostart status"""
    ctx = _get_app_context()
    if not ctx or not ctx.autostart_manager:
        raise DatabaseError(message='Autostart manager not available')

    enabled = ctx.autostart_manager.is_autostart_enabled()
    cmd = ctx.autostart_manager.get_autostart_command()
    return jsonify({'enabled': bool(enabled), 'command': cmd}), 200


@settings_bp.route('', methods=['GET'])
@require_data_manager
@handle_database_error
def get_settings(user_id, data_manager):
    """Get application settings for the authenticated user"""
    settings = _load_settings_with_retry(user_id)

    # Add autostart status
    try:
        ctx = _get_app_context()
        if ctx and ctx.autostart_manager:
            settings['autostart_enabled'] = ctx.autostart_manager.is_autostart_enabled()
    except Exception as e:
        logger.warning(f"Failed to get autostart status: {e}")
        settings['autostart_enabled'] = False

    # Validate and sanitize settings
    validated_settings = _validate_settings(settings)

    logger.info(f"Successfully loaded settings for user {user_id}")
    return jsonify(validated_settings), 200


@settings_bp.route('', methods=['PUT'])
@require_data_manager
@require_json_body
@handle_database_error
def update_settings(user_id, data_manager):
    """Update application settings for the authenticated user"""
    settings_data = request.json
    if not settings_data:
        settings_data = {}
    
    # Load current settings
    current_settings = _load_settings_with_retry(user_id)
    
    # Validate and merge updates
    validated_updates, daily_reset_time_changed = _validate_and_merge_updates(
        settings_data, current_settings
    )
    
    # Handle autostart setting separately
    if 'autostart' in settings_data:
        _handle_autostart_update(settings_data['autostart'])
    
    # Save settings
    if not _save_settings_with_retry(user_id, current_settings):
        raise DatabaseError(message='Failed to save settings after multiple attempts')
    
    # Record settings change event
    try:
        ctx = _get_app_context()
        if ctx and ctx.data_manager:
            ctx.data_manager.add_settings_change_event(user_id)
    except DatabaseError:
        logger.exception("Database error recording settings change event")
    except Exception:  # noqa: broad-except
        logger.exception("Error recording settings change event")
    
    # Reschedule daily reset if time changed
    if daily_reset_time_changed:
        _reschedule_daily_reset(validated_updates.get('daily_reset_time'))
    
    # Add autostart status to response
    try:
        ctx = _get_app_context()
        if ctx and ctx.autostart_manager:
            current_settings['autostart_enabled'] = ctx.autostart_manager.is_autostart_enabled()
    except Exception:  # noqa: broad-except
        logger.exception("Failed to get autostart status")
        current_settings['autostart_enabled'] = False
    logger.info(f"Successfully updated settings for user {user_id}")
    return jsonify(current_settings), 200


def _get_default_settings():
    """Return default settings"""
    return {
        'theme': 'orange',
        'dpi_scale': 100,
        'autosave_interval': 30,
        'notifications': True,
        'daily_reset_time': '06:00',
        'timezone': 'UTC',
        'language': 'en',
        'mini_analytics_interval': 5,
        'settings_layout': 'scroll',
        'autostart_enabled': False
    }


def _load_settings_with_retry(user_id: str, max_retries: int = 3) -> dict:
    """Load settings with retry mechanism"""
    for attempt in range(max_retries):
        try:
            ctx = _get_app_context()
            settings = ctx.data_manager.load_settings(user_id) if (ctx and ctx.data_manager) else None
            if settings:
                return settings
        except DatabaseError:
            raise
        except Exception as e:
            logger.warning(f"Settings load attempt {attempt + 1} failed for user {user_id}: {e}")
            if attempt == max_retries - 1:
                raise SettingsError(f"Failed to load settings after {max_retries} attempts")
    
    return _get_default_settings()


def _save_settings_with_retry(user_id: str, settings: dict, max_retries: int = 3) -> bool:
    """Save settings with retry mechanism"""
    for attempt in range(max_retries):
        try:
            ctx = _get_app_context()
            if ctx and ctx.data_manager and ctx.data_manager.save_settings(user_id, settings):
                return True
        except DatabaseError:
            raise
        except Exception as e:
            logger.warning(f"Settings save attempt {attempt + 1} failed for user {user_id}: {e}")
    
    return False


def _validate_settings(settings: dict) -> dict:
    """Validate and sanitize settings"""
    return {
        'theme': settings.get('theme', 'orange'),
        'dpi_scale': max(50, min(200, settings.get('dpi_scale', 100))),
        'autosave_interval': max(5, min(300, settings.get('autosave_interval', 30))),
        'notifications': bool(settings.get('notifications', True)),
        'daily_reset_time': settings.get('daily_reset_time', '06:00'),
        'timezone': settings.get('timezone', 'UTC'),
        'language': settings.get('language', 'en'),
        'mini_analytics_interval': settings.get('mini_analytics_interval', 5),
        'settings_layout': settings.get('settings_layout', 'scroll') if settings.get('settings_layout') in ['scroll', 'tabs'] else 'scroll',
        'autostart_enabled': bool(settings.get('autostart_enabled', False)),
        'quick_project_from_title': bool(settings.get('quick_project_from_title', False)),
        'casual_dates': bool(settings.get('casual_dates', False)),
        'streak_skip_weekends': bool(settings.get('streak_skip_weekends', False)),
        'streak_count_new_tasks': bool(settings.get('streak_count_new_tasks', False)),
        'streak_count_settings': bool(settings.get('streak_count_settings', False)),
        'perf_disable_blur': bool(settings.get('perf_disable_blur', False)),
        'perf_disable_shadows': bool(settings.get('perf_disable_shadows', False)),
        'perf_disable_animations': bool(settings.get('perf_disable_animations', False)),
        'perf_disable_glow': bool(settings.get('perf_disable_glow', False)),
        'finish': settings.get('finish', 'glossy'),
        'intensity': settings.get('intensity', '5'),
    }


def _validate_and_merge_updates(settings_data: dict, current_settings: dict) -> tuple:
    """Validate incoming settings and merge with current"""
    validated_updates = {}
    daily_reset_time_changed = False
    
    # Theme validation
    if 'theme' in settings_data:
        theme = settings_data['theme']
        valid_themes = ['orange', 'blue', 'green', 'purple', 'dark', 'light', 'self-esteem', 'anxiety', 'yellow', 'speedy', 'auto']
        if isinstance(theme, str) and theme in valid_themes:
            validated_updates['theme'] = theme
    
    # DPI scale validation
    if 'dpi_scale' in settings_data:
        dpi_scale = settings_data['dpi_scale']
        if isinstance(dpi_scale, int) and 50 <= dpi_scale <= 200:
            validated_updates['dpi_scale'] = dpi_scale
    
    # Autosave interval validation
    if 'autosave_interval' in settings_data:
        interval = settings_data['autosave_interval']
        if isinstance(interval, int) and 5 <= interval <= 300:
            validated_updates['autosave_interval'] = interval
    
    # Mini analytics interval
    if 'mini_analytics_interval' in settings_data:
        mai = settings_data['mini_analytics_interval']
        try:
            mai = int(mai)
            if mai in [0, 5, 10, 20, 30, 60]:
                validated_updates['mini_analytics_interval'] = mai
        except (ValueError, TypeError) as e:
            logger.debug("Invalid mini_analytics_interval value: %s", e)
    
    # Settings layout
    if 'settings_layout' in settings_data:
        layout = settings_data['settings_layout']
        if isinstance(layout, str) and layout in ['scroll', 'tabs']:
            validated_updates['settings_layout'] = layout
    
    # Notifications
    if 'notifications' in settings_data:
        if isinstance(settings_data['notifications'], bool):
            validated_updates['notifications'] = settings_data['notifications']
    
    # Daily reset time
    if 'daily_reset_time' in settings_data:
        reset_time = settings_data['daily_reset_time']
        if isinstance(reset_time, str) and _validate_time_format(reset_time):
            validated_updates['daily_reset_time'] = reset_time
            daily_reset_time_changed = True
    
    # Boolean toggles
    bool_fields = [
        'quick_project_from_title', 'casual_dates', 'streak_skip_weekends',
        'streak_count_new_tasks', 'streak_count_settings',
        'perf_disable_blur', 'perf_disable_shadows', 'perf_disable_animations', 'perf_disable_glow'
    ]
    for field in bool_fields:
        if field in settings_data and isinstance(settings_data[field], bool):
            validated_updates[field] = settings_data[field]
    
    # Finish (glossy/matte)
    if 'finish' in settings_data:
        if settings_data['finish'] in ['glossy', 'matte']:
            validated_updates['finish'] = settings_data['finish']
    
    # Intensity (1-10)
    if 'intensity' in settings_data:
        if settings_data['intensity'] in [str(i) for i in range(1, 11)]:
            validated_updates['intensity'] = settings_data['intensity']
    
    # Timezone
    if 'timezone' in settings_data:
        tz = settings_data['timezone']
        if isinstance(tz, str) and len(tz) <= 50:
            validated_updates['timezone'] = tz
    
    # Language
    if 'language' in settings_data:
        lang = settings_data['language']
        if isinstance(lang, str) and len(lang) <= 10:
            validated_updates['language'] = lang
    
    # Merge updates
    current_settings.update(validated_updates)
    
    return validated_updates, daily_reset_time_changed


def _handle_autostart_update(enable_autostart: bool):
    """Handle autostart enable/disable"""
    if not isinstance(enable_autostart, bool):
        return
    
    try:
        ctx = _get_app_context()
        if not ctx:
            ctx = current_app.extensions.get('app_context')
            if not ctx:
                raise AutostartError('Autostart manager not available')
        
        if enable_autostart:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                exe_path = os.path.join(root_dir, "main.py")
            ctx = _get_app_context()
            if not ctx:
                raise AutostartError('Autostart manager not available')
            ctx.autostart_manager.enable_autostart(exe_path)
        else:
            ctx = _get_app_context()
            if not ctx:
                raise AutostartError('Autostart manager not available')
            ctx.autostart_manager.disable_autostart()
    except Exception as e:
        raise AutostartError(f"Failed to update autostart: {e}")


def _reschedule_daily_reset(new_time: str):
    """Reschedule daily reset job using the central scheduler service"""
    try:
        from src.services import scheduler as scheduler_service
        scheduler_service.set_app_context(_get_app_context())
        scheduler_service.set_data_manager_getter(lambda: _get_app_context().data_manager if _get_app_context() else None)
        scheduler_service.setup_daily_reset()
        logger.info(f"Daily reset rescheduled to {new_time}")
    except Exception as e:
        logger.error(f"Failed to reschedule daily reset: {e}")
