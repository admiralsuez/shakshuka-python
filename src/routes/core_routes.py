from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Any, Optional

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError, ValidationError
from src.routes.api_utils import get_json_object, register_api_error_handlers
from src.utils.paths import get_logs_dir

logger = logging.getLogger(__name__)

core_bp = Blueprint('core', __name__)

register_api_error_handlers(core_bp)

_app_context = None
_get_user_id_func = None
_ensure_data_manager_func = None
_root_dir = None
_config = None
_get_app_version_func = None
_setup_daily_reset_func = None
_stop_system_tray_func = None


def init_core_routes(
    app_context,
    get_user_id_func,
    ensure_data_manager_func,
    root_dir: str,
    config,
    get_app_version_func,
    setup_daily_reset_func,
    stop_system_tray_func,
):
    global _app_context, _get_user_id_func, _ensure_data_manager_func
    global _root_dir, _config, _get_app_version_func
    global _setup_daily_reset_func, _stop_system_tray_func

    _app_context = app_context
    _get_user_id_func = get_user_id_func
    _ensure_data_manager_func = ensure_data_manager_func
    _root_dir = root_dir
    _config = config
    _get_app_version_func = get_app_version_func
    _setup_daily_reset_func = setup_daily_reset_func
    _stop_system_tray_func = stop_system_tray_func


def _get_user_id() -> str:
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _validate_time_format(time_str: str) -> bool:
    try:
        if not isinstance(time_str, str):
            return False
        parts = time_str.split(':')
        if len(parts) != 2:
            return False
        hour, minute = int(parts[0]), int(parts[1])
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except (ValueError, IndexError):
        return False


@core_bp.route('/static/webfonts/<filename>')
def serve_font(filename):
    font_dir = os.path.join(current_app.static_folder, 'webfonts')
    font_path = os.path.join(font_dir, filename)

    if not os.path.exists(font_path):
        return 'Font file not found', 404

    if filename.endswith('.woff2'):
        mimetype = 'font/woff2'
    elif filename.endswith('.woff'):
        mimetype = 'font/woff'
    elif filename.endswith('.ttf'):
        mimetype = 'font/ttf'
    elif filename.endswith('.otf'):
        mimetype = 'font/otf'
    else:
        mimetype = 'application/octet-stream'

    return send_file(font_path, mimetype=mimetype)


@core_bp.route('/health', methods=['GET'])
def health_check():
    version = '1.0.0'
    if _get_app_version_func:
        try:
            version = _get_app_version_func()
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            logger.exception('Health check: failed to read app version')
            version = '1.0.0'

    ctx = _app_context
    if ctx is None:
        try:
            ctx = current_app.extensions.get('app_context')
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            logger.exception('Health check: failed to resolve app_context from app.extensions')
            ctx = None

    ready = bool(ctx and getattr(ctx, 'data_manager', None))
    if _ensure_data_manager_func:
        try:
            ready = ready and bool(_ensure_data_manager_func())
        except Exception:  # noqa: broad-except
            logger.exception('Health check: ensure_data_manager failed')
            ready = False

    if not ready:
        return (
            jsonify({'status': 'starting', 'timestamp': datetime.now().isoformat(), 'version': version}),
            503,
        )

    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'version': version})


@core_bp.route('/api/health/detailed', methods=['GET'])
def detailed_health_check():
    version = '1.0.0'
    if _get_app_version_func:
        try:
            version = _get_app_version_func()
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            version = '1.0.0'

    try:
        health_info = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': version,
            'components': {},
        }

        try:
            if _app_context and getattr(_app_context, 'data_manager', None):
                health_info['components']['data_manager'] = 'healthy'
            else:
                health_info['components']['data_manager'] = 'not_initialized'
        except Exception as e:
            health_info['components']['data_manager'] = f'error: {str(e)}'

        try:
            if _app_context and getattr(_app_context, 'update_manager', None):
                health_info['components']['update_manager'] = 'healthy'
            else:
                health_info['components']['update_manager'] = 'not_initialized'
        except Exception as e:
            health_info['components']['update_manager'] = f'error: {str(e)}'

        try:
            data_dir = 'data'
            if os.path.exists(data_dir):
                health_info['components']['filesystem'] = 'healthy'
            else:
                health_info['components']['filesystem'] = 'directory_missing'
        except Exception as e:
            health_info['components']['filesystem'] = f'error: {str(e)}'

        return jsonify(health_info)

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e), 'timestamp': datetime.now().isoformat()}), 500


@core_bp.route('/')
def index():
    try:
        version = _get_app_version_func() if _get_app_version_func else '1.0.0'
    except Exception as e:
        logger.warning(f'Failed to read version.json via _get_app_version, falling back to 1.0.0: {e}')
        version = '1.0.0'

    return render_template('index_modular.html', version=version, config=_config)


@core_bp.route('/companion')
def companion():
    return render_template('companion.html')


@core_bp.route('/companion/manifest.webmanifest')
def companion_manifest():
    companion_dir = os.path.join(_root_dir or '', 'assets', 'static', 'companion')
    return send_from_directory(companion_dir, 'manifest.webmanifest', mimetype='application/manifest+json')


@core_bp.route('/companion/sw.js')
def companion_sw():
    companion_dir = os.path.join(_root_dir or '', 'assets', 'static', 'companion')
    return send_from_directory(companion_dir, 'sw.js', mimetype='application/javascript')


@core_bp.route('/favicon.ico')
def favicon():
    try:
        favicon_path = os.path.join(_root_dir or '', 'assets', 'static', 'images', 'icon.ico')
        logger.info(f'Looking for favicon at: {favicon_path}')

        if os.path.exists(favicon_path):
            return send_from_directory(os.path.dirname(favicon_path), 'icon.ico', mimetype='image/x-icon')

        logger.warning(f'Favicon not found at: {favicon_path}')
        return '', 404
    except Exception as e:
        logger.error(f'Error serving favicon: {e}')
        return '', 404


@core_bp.route('/api/changelog')
def get_changelog():
    try:
        changelog_path = os.path.join(_root_dir or '', 'config', 'changelog.txt')
        logger.info(f'Looking for changelog at: {changelog_path}')

        with open(changelog_path, 'r', encoding='utf-8') as f:
            changelog_content = f.read()
        return changelog_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except FileNotFoundError:
        logger.error(f'Changelog file not found at: {changelog_path}')
        return 'Changelog file not found.', 404
    except Exception as e:
        logger.error(f'Error reading changelog: {e}')
        return 'Error reading changelog.', 500


@core_bp.route('/api/logs/open-folder', methods=['POST'])
def open_logs_folder():
    """Open the logs directory on the host machine (desktop-only helper)."""
    try:
        logs_dir = get_logs_dir()

        # Ensure directory exists
        if not os.path.isdir(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)

        if sys.platform.startswith('win'):
            # Windows explorer
            os.startfile(logs_dir)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            # macOS Finder
            subprocess.Popen(['open', logs_dir])
        else:
            # Linux / other
            subprocess.Popen(['xdg-open', logs_dir])

        return jsonify({'success': True, 'path': logs_dir}), 200
    except Exception as e:  # noqa: broad-except - must not crash app if shell open fails
        logger.exception('Failed to open logs folder')
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/analytics')
def get_analytics():
    try:
        from src.analytics_manager import get_analytics_counters

        data = get_analytics_counters()
        return jsonify({'success': True, **data})
    except Exception as e:
        logger.exception('Analytics read error')
        raise DatabaseError(message='Analytics read error', cause=e)


@core_bp.route('/api/analytics/strike-calendar', methods=['GET'])
def get_strike_calendar():
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not available')

    try:
        month = request.args.get('month')
        if not month:
            month = datetime.now().strftime('%Y-%m')
        data = _app_context.data_manager.get_strike_contributions_for_month(user_id, month)
        months = _app_context.data_manager.list_strike_contribution_months(user_id, limit=36)
        return jsonify({'success': True, **data, 'months': months})
    except ValidationError as e:
        logger.exception('Invalid strike calendar request')
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception('Database error building strike calendar')
        return jsonify({'success': False, 'error': 'Database error building strike calendar'}), 503
    except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
        logger.exception('Strike calendar error')
        return jsonify({'success': False, 'error': 'Strike calendar error'}), 500


@core_bp.route('/api/analytics/daily-recap', methods=['GET'])
def get_daily_recap():
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not available')

    try:
        day = request.args.get('day')
        if not day:
            day = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        recap = _app_context.data_manager.get_daily_recap(user_id, day)
        seen = _app_context.data_manager.was_recap_seen(user_id, day)
        return jsonify({'success': True, 'seen': bool(seen), **recap})
    except ValidationError as e:
        logger.exception('Invalid daily recap request')
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception('Database error building daily recap')
        return jsonify({'success': False, 'error': 'Database error building daily recap'}), 503
    except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
        logger.exception('Daily recap error')
        return jsonify({'success': False, 'error': 'Daily recap error'}), 500


@core_bp.route('/api/analytics/daily-recap/seen', methods=['POST'])
def mark_daily_recap_seen():
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not available')

    try:
        payload = get_json_object(required=False)
        day = payload.get('day') or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        ok = _app_context.data_manager.mark_recap_seen(user_id, day)
        return jsonify({'success': bool(ok), 'day': day}), 200
    except ValidationError as e:
        logger.exception('Invalid mark recap seen request')
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception('Database error marking recap seen')
        return jsonify({'success': False, 'error': 'Database error marking recap seen'}), 503
    except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
        logger.exception('Mark recap seen error')
        return jsonify({'success': False, 'error': 'Mark recap seen error'}), 500


@core_bp.route('/api/analytics/daily-recap/feedback', methods=['GET'])
def get_daily_recap_feedback():
    """Return saved feedback answers for a given recap day."""
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not available')

    day = request.args.get('day', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    try:
        feedback = _app_context.data_manager.load_recap_feedback(user_id, day)
        return jsonify({'success': True, 'day': day, 'feedback': feedback}), 200
    except DatabaseError:
        logger.exception('Database error loading recap feedback')
        return jsonify({'success': False, 'error': 'Database error loading recap feedback'}), 503
    except Exception:  # noqa: broad-except
        logger.exception('Error loading recap feedback')
        return jsonify({'success': False, 'error': 'Error loading recap feedback'}), 500


@core_bp.route('/api/analytics/daily-recap/feedback', methods=['POST'])
def save_daily_recap_feedback():
    """Persist feedback answers for a given recap day."""
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        raise DatabaseError(message='Data manager not available')

    payload = get_json_object(required=True)
    day = payload.get('day') or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    answers_raw = payload.get('answers')
    if not isinstance(answers_raw, dict):
        return jsonify({'success': False, 'error': 'answers must be an object'}), 400

    allowed_keys = {'went_well', 'improve_tomorrow', 'mood_rating'}
    answers = {k: v for k, v in answers_raw.items() if k in allowed_keys}
    if not answers:
        return jsonify({'success': False, 'error': 'No valid answer keys provided'}), 400

    try:
        _app_context.data_manager.save_recap_feedback(user_id, day, answers)
        return jsonify({'success': True, 'day': day}), 200
    except DatabaseError:
        logger.exception('Database error saving recap feedback')
        return jsonify({'success': False, 'error': 'Database error saving recap feedback'}), 503
    except Exception:  # noqa: broad-except
        logger.exception('Error saving recap feedback')
        return jsonify({'success': False, 'error': 'Error saving recap feedback'}), 500


@core_bp.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    user_id = _get_user_id()
    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({'success': False, 'error': 'Failed to initialize data manager'}), 500

    try:
        from src.analytics_manager import get_analytics_counters

        analytics = get_analytics_counters()

        try:
            tasks = _app_context.data_manager.load_tasks_for_user(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for analytics summary (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading tasks'}), 503
        tasks = tasks or []
        try:
            tasks = [t for t in tasks if isinstance(t, dict)]
        except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
            tasks = []

        total_tasks = len(tasks)
        active_tasks = 0
        expired_tasks = 0
        completed_tasks = 0
        completion_days = set()
        tasks_with_dates_count = 0
        tasks_with_time_count = 0
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        for t in tasks:
            if not isinstance(t, dict):
                continue
            
            is_completed = t.get('completed') or t.get('struck_forever')
            is_struck_today = t.get('struck_today')
            
            if is_completed:
                completed_tasks += 1
            elif not is_struck_today:
                active_tasks += 1
            
            if t.get('due_date') and not is_completed and not t.get('struck_forever') and t.get('due_date') < today_str:
                expired_tasks += 1
            
            if t.get('due_date'):
                tasks_with_dates_count += 1
            if t.get('estimated_duration') or t.get('duration'):
                tasks_with_time_count += 1
            
            if is_completed:
                completed_at = t.get('completed_at')
                if completed_at:
                    s = str(completed_at)
                    d = s.split('T')[0] if 'T' in s else s
                    try:
                        completion_days.add(datetime.strptime(d, '%Y-%m-%d').date())
                    except Exception:  # noqa: broad-except
                        pass

        def _longest_consecutive_run(days_sorted):
            if not days_sorted:
                return 0
            run = 1
            best = 1
            for i in range(1, len(days_sorted)):
                if (days_sorted[i] - days_sorted[i - 1]).days == 1:
                    run += 1
                else:
                    if run > best:
                        best = run
                    run = 1
            if run > best:
                best = run
            return best

        try:
            user_settings = _app_context.data_manager.load_settings(user_id) or {}
        except DatabaseError:
            logger.exception("Database error loading settings for analytics summary (user %s)", user_id)
            return jsonify({'success': False, 'error': 'Database error loading settings'}), 503
        streak_skip_weekends = bool(user_settings.get('streak_skip_weekends', False))
        streak_count_new_tasks = bool(user_settings.get('streak_count_new_tasks', False))
        streak_count_settings = bool(user_settings.get('streak_count_settings', False))

        completion_current = 0
        completion_best = 0
        try:
            from src.db.analytics_queries import get_productivity_streak

            with _app_context.data_manager.pooled_connection() as conn:
                completion_current = get_productivity_streak(
                    conn,
                    user_id,
                    skip_weekends=streak_skip_weekends,
                    count_new_tasks=streak_count_new_tasks,
                    count_settings=streak_count_settings,
                )
        except DatabaseError:
            logger.exception('Database error calculating completion streak')
            return jsonify({'success': False, 'error': 'Database error calculating streak'}), 503
        except Exception:  # noqa: broad-except
            logger.exception('Error calculating completion streak')
            return jsonify({'success': False, 'error': 'Error calculating streak'}), 500

        try:
            completion_best = _longest_consecutive_run(sorted(completion_days))
        except Exception:  # noqa: broad-except
            completion_best = 0

        strike_current = 0
        strike_best = 0
        try:
            with _app_context.data_manager.pooled_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    '''
                    SELECT DISTINCT day
                    FROM strike_events
                    WHERE user_id = ?
                    ''',
                    (user_id,),
                )
                rows = cur.fetchall() or []
            days_set = set()
            for r in rows:
                if not r:
                    continue
                day_val = r[0]
                if not day_val:
                    continue
                try:
                    days_set.add(datetime.strptime(str(day_val), '%Y-%m-%d').date())
                except Exception:  # noqa: broad-except
                    continue

            if days_set:
                strike_best = _longest_consecutive_run(sorted(days_set))
                today_dt = datetime.now().date()
                if today_dt in days_set:
                    anchor = today_dt
                elif (today_dt - timedelta(days=1)) in days_set:
                    anchor = today_dt - timedelta(days=1)
                else:
                    anchor = None

                if anchor is not None:
                    s = 0
                    while (anchor - timedelta(days=s)) in days_set:
                        s += 1
                    strike_current = s
        except DatabaseError:
            logger.exception('Database error calculating strike streak')
            return jsonify({'success': False, 'error': 'Database error calculating strike streak'}), 503
        except Exception:  # noqa: broad-except
            logger.exception('Error calculating strike streak')
            return jsonify({'success': False, 'error': 'Error calculating strike streak'}), 500

        completed_forever = len([t for t in tasks if t.get('struck_forever')])

        try:
            with _app_context.data_manager.pooled_connection() as conn:
                cur = conn.cursor()

                cur.execute('SELECT COUNT(*) FROM settings_change_events WHERE user_id = ?', (user_id,))
                settings_changes = cur.fetchone()[0]

                cur.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ?', (user_id,))
                tasks_added = cur.fetchone()[0]

                tasks_retried = 0
        except DatabaseError:
            logger.exception('Database error fetching additional metrics')
            return jsonify({'success': False, 'error': 'Database error fetching metrics'}), 503
        except Exception:  # noqa: broad-except
            logger.exception('Error fetching additional metrics')
            return jsonify({'success': False, 'error': 'Error fetching metrics'}), 500

        tasks_planned_all_time = analytics.get('tasks_planned', 0)

        daily_reset_count = user_settings.get('daily_reset_count', 0)
        
        return jsonify(
            {
                'success': True,
                'tasks': {'total': total_tasks, 'active': active_tasks, 'expired': expired_tasks, 'completed': completed_tasks},
                'strikes': {'today': analytics.get('today_strikes', 0), 'total': analytics.get('total_strikes', 0)},
                'streak': {'current': completion_current, 'best': completion_best},
                'completion_streak': {'current': completion_current, 'best': completion_best},
                'strike_streak': {'current': strike_current, 'best': strike_best},
                'completed_forever': completed_forever,
                'settings_changes': settings_changes,
                'tasks_added': tasks_added,
                'tasks_retried': tasks_retried,
                'tasks_deleted': analytics.get('tasks_deleted', 0),
                'tasks_edited': analytics.get('tasks_edited', 0),
                'tasks_with_dates': tasks_with_dates_count,
                'tasks_with_time': tasks_with_time_count,
                'tasks_planned': tasks_planned_all_time,
                'daily_reset_count': daily_reset_count,
            }
        )

    except Exception as e:
        logger.exception('Analytics summary error')
        raise DatabaseError(message='Analytics summary error', cause=e)


# DISABLED: Heartbeat and installed users analytics endpoints
# @core_bp.route('/api/analytics/heartbeat', methods=['POST'])
# def record_user_activity():
#     """Record user heartbeat to track active users. Call every 1 minute."""
#     user_id = _get_user_id()
#     if _ensure_data_manager_func and not _ensure_data_manager_func():
#         return jsonify({'success': False, 'error': 'Data manager not available'}), 500
#     try:
#         _app_context.data_manager.record_user_heartbeat(user_id)
#         return jsonify({'success': True}), 200
#     except DatabaseError:
#         logger.exception('Database error recording heartbeat for user %s', user_id)
#         return jsonify({'success': False, 'error': 'Database error'}), 503
#     except Exception:  # noqa: broad-except
#         logger.exception('Error recording heartbeat for user %s', user_id)
#         return jsonify({'success': False, 'error': 'Heartbeat error'}), 500
#
#
# @core_bp.route('/api/analytics/active-users', methods=['GET'])
# def get_active_users():
#     """Get count of users active in the last 2 minutes."""
#     if _ensure_data_manager_func and not _ensure_data_manager_func():
#         return jsonify({'success': False, 'error': 'Data manager not available', 'active_users': 0}), 500
#     try:
#         active_count = _app_context.data_manager.count_active_users(minutes=2)
#         return jsonify({'success': True, 'active_users': active_count}), 200
#     except DatabaseError:
#         logger.exception('Database error counting active users')
#         return jsonify({'success': False, 'error': 'Database error', 'active_users': 0}), 503
#     except Exception:  # noqa: broad-except
#         logger.exception('Error counting active users')
#         return jsonify({'success': False, 'error': 'Error', 'active_users': 0}), 500
#
#
# @core_bp.route('/api/analytics/installed-users', methods=['GET'])
# def get_installed_users():
#     """Get total count of all users who have installed/accessed the app."""
#     if _ensure_data_manager_func and not _ensure_data_manager_func():
#         return jsonify({'success': False, 'error': 'Data manager not available', 'installed_users': 0}), 500
#     try:
#         installed_count = _app_context.data_manager.count_installed_users()
#         return jsonify({'success': True, 'installed_users': installed_count}), 200
#     except DatabaseError:
#         logger.exception('Database error counting installed users')
#         return jsonify({'success': False, 'error': 'Database error', 'installed_users': 0}), 503
#     except Exception:  # noqa: broad-except
#         logger.exception('Error counting installed users')
#         return jsonify({'success': False, 'error': 'Error', 'installed_users': 0}), 500


@core_bp.route('/api/account', methods=['GET'])
def get_account_info():
    try:
        pin = _app_context.pin_manager if _app_context else None
        return jsonify(
            {
                'username': DEFAULT_USER_ID,
                'authenticated': bool(pin.is_session_valid()) if pin else False,
                'created_at': None,
                'last_login': pin.get_last_login() if pin else None,
            }
        )
    except Exception as e:
        logger.exception('/api/account error')
        raise DatabaseError(message='Account info error', cause=e)


@core_bp.route('/login', methods=['GET', 'POST'])
def login():
    return redirect(url_for('.index'))


@core_bp.route('/api/settings/autostart', methods=['GET', 'POST'])
def get_autostart_status():
    if not _app_context or not _app_context.autostart_manager:
        raise DatabaseError(message='Autostart manager not available')

    if request.method == 'POST':
        payload = get_json_object(required=True)
        enabled = payload.get('enabled')
        if not isinstance(enabled, bool):
            raise ValidationError(message='enabled must be boolean')

        if enabled:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.join(_root_dir or '', 'main.py')
            _app_context.autostart_manager.enable_autostart(exe_path)
        else:
            _app_context.autostart_manager.disable_autostart()

    enabled_now = _app_context.autostart_manager.is_autostart_enabled()
    cmd = _app_context.autostart_manager.get_autostart_command()
    return jsonify({'enabled': bool(enabled_now), 'command': cmd}), 200


@core_bp.route('/api/settings', methods=['GET'])
def get_settings():
    user_id = _get_user_id()

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({'error': 'Failed to initialize data manager'}), 500

    try:
        settings = _app_context.data_manager.load_settings(user_id)

        try:
            settings['autostart_enabled'] = _app_context.autostart_manager.is_autostart_enabled()
        except Exception as e:
            logger.warning(f'Failed to get autostart status: {e}')
            settings['autostart_enabled'] = False

        validated_settings = {
            'theme': settings.get('theme', 'orange'),
            'dpi_scale': max(50, min(200, settings.get('dpi_scale', 100))),
            'autosave_interval': max(5, min(300, settings.get('autosave_interval', 30))),
            'notifications': bool(settings.get('notifications', True)),
            'daily_reset_time': settings.get('daily_reset_time', '06:00'),
            'timezone': settings.get('timezone', 'UTC'),
            'language': settings.get('language', 'en'),
            'mini_analytics_interval': settings.get('mini_analytics_interval', 5),
            'settings_layout': settings.get('settings_layout', 'scroll'),
            'autostart_enabled': bool(settings.get('autostart_enabled', False)),
            'quick_project_from_title': bool(settings.get('quick_project_from_title', False)),
            'casual_dates': bool(settings.get('casual_dates', False)),
            'streak_skip_weekends': bool(settings.get('streak_skip_weekends', False)),
            'streak_count_new_tasks': bool(settings.get('streak_count_new_tasks', False)),
            'streak_count_settings': bool(settings.get('streak_count_settings', False)),
            # Perf Max flags (persisted via SQLiteDataManager)
            'perf_disable_blur': bool(settings.get('perf_disable_blur', False)),
            'perf_disable_shadows': bool(settings.get('perf_disable_shadows', False)),
            'perf_disable_animations': bool(settings.get('perf_disable_animations', False)),
            'perf_disable_glow': bool(settings.get('perf_disable_glow', False)),
            'finish': settings.get('finish', 'glossy'),
            'intensity': settings.get('intensity', '5'),
            'compact_mode': bool(settings.get('compact_mode', False)),
        }

        if validated_settings.get('settings_layout') not in ['scroll', 'tabs']:
            validated_settings['settings_layout'] = 'scroll'

        logger.info(f'Successfully loaded settings for user {user_id}')
        return jsonify(validated_settings)

    except DatabaseError:
        logger.exception("Database error loading settings for user %s", user_id)
        return jsonify({'error': 'Database error loading settings'}), 503
    except Exception:  # noqa: broad-except
        logger.exception("Error loading settings for user %s", user_id)
        return jsonify({'error': 'Internal server error'}), 500


@core_bp.route('/api/settings', methods=['PUT'])
def update_settings():
    user_id = _get_user_id()

    if _ensure_data_manager_func and not _ensure_data_manager_func():
        return jsonify({'error': 'Failed to initialize data manager'}), 500

    if not _app_context or not getattr(_app_context, 'data_manager', None):
        return jsonify({'error': 'Data manager not initialized'}), 500

    if not request.json:
        return jsonify({'error': 'No settings data provided'}), 400

    settings_data = request.json

    if not isinstance(settings_data, dict):
        return jsonify({'error': 'Settings data must be a dictionary'}), 400

    try:
        max_retries = 3
        current_settings = _app_context.data_manager.load_settings(user_id)

        validated_updates = {}

        if 'theme' in settings_data:
            theme = settings_data['theme']
            # Must stay in sync with frontend theme selector and SQLite validation.
            # "speedy" is a performance-focused theme that is always matte in the
            # frontend; it must be whitelisted here or the selection will not
            # persist across sessions.
            valid_themes = [
                'orange', 'blue', 'green', 'purple',
                'dark', 'light', 'self-esteem', 'anxiety',
                'yellow', 'speedy', 'auto',
            ]
            if isinstance(theme, str) and theme in valid_themes:
                validated_updates['theme'] = theme

        if 'dpi_scale' in settings_data:
            dpi_scale = settings_data['dpi_scale']
            if isinstance(dpi_scale, int) and 50 <= dpi_scale <= 200:
                validated_updates['dpi_scale'] = dpi_scale

        if 'autosave_interval' in settings_data:
            interval = settings_data['autosave_interval']
            if isinstance(interval, int) and 5 <= interval <= 300:
                validated_updates['autosave_interval'] = interval

        if 'mini_analytics_interval' in settings_data:
            mai = settings_data['mini_analytics_interval']
            try:
                mai = int(mai)
            except Exception:  # noqa: broad-except
                mai = None
            if mai in [0, 5, 10, 20, 30, 60]:
                validated_updates['mini_analytics_interval'] = mai

        if 'settings_layout' in settings_data:
            layout = settings_data['settings_layout']
            if isinstance(layout, str) and layout in ['scroll', 'tabs']:
                validated_updates['settings_layout'] = layout

        if 'notifications' in settings_data:
            notifications = settings_data['notifications']
            if isinstance(notifications, bool):
                validated_updates['notifications'] = notifications

        if 'daily_reset_time' in settings_data:
            reset_time = settings_data['daily_reset_time']
            if isinstance(reset_time, str) and _validate_time_format(reset_time):
                validated_updates['daily_reset_time'] = reset_time
                daily_reset_time_changed = True
            else:
                daily_reset_time_changed = False
        else:
            daily_reset_time_changed = False

        if 'quick_project_from_title' in settings_data:
            qp = settings_data['quick_project_from_title']
            if isinstance(qp, bool):
                validated_updates['quick_project_from_title'] = qp

        if 'casual_dates' in settings_data:
            cd = settings_data['casual_dates']
            if isinstance(cd, bool):
                validated_updates['casual_dates'] = cd

        if 'streak_skip_weekends' in settings_data:
            val = settings_data['streak_skip_weekends']
            if isinstance(val, bool):
                validated_updates['streak_skip_weekends'] = val

        if 'streak_count_new_tasks' in settings_data:
            val = settings_data['streak_count_new_tasks']
            if isinstance(val, bool):
                validated_updates['streak_count_new_tasks'] = val

        if 'streak_count_settings' in settings_data:
            val = settings_data['streak_count_settings']
            if isinstance(val, bool):
                validated_updates['streak_count_settings'] = val
 
        # Perf Max flags (simple booleans)
        perf_fields = [
            'perf_disable_blur',
            'perf_disable_shadows',
            'perf_disable_animations',
            'perf_disable_glow',
        ]
        for field in perf_fields:
            if field in settings_data and isinstance(settings_data[field], bool):
                validated_updates[field] = settings_data[field]
 
        if 'finish' in settings_data:
            finish = settings_data['finish']
            if isinstance(finish, str) and finish in ['glossy', 'matte']:
                validated_updates['finish'] = finish
 
        if 'intensity' in settings_data:
            intensity = settings_data['intensity']
            if isinstance(intensity, str) and intensity in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                validated_updates['intensity'] = intensity

        if 'compact_mode' in settings_data:
            compact_mode = settings_data['compact_mode']
            if isinstance(compact_mode, bool):
                validated_updates['compact_mode'] = compact_mode

        if 'default_task_duration' in settings_data:
            try:
                dtd = int(settings_data['default_task_duration'])
                if 5 <= dtd <= 480:
                    validated_updates['default_task_duration'] = dtd
            except (TypeError, ValueError) as e:
                logger.debug("Invalid default_task_duration value: %s", e)

        if 'start_page' in settings_data:
            sp = settings_data['start_page']
            if isinstance(sp, str) and sp in ('tasks', 'planner', 'notes', 'analytics'):
                validated_updates['start_page'] = sp

        if 'notification_sound' in settings_data:
            if isinstance(settings_data['notification_sound'], bool):
                validated_updates['notification_sound'] = settings_data['notification_sound']

        if 'week_start_day' in settings_data:
            try:
                wsd = int(settings_data['week_start_day'])
                if wsd in (0, 1):
                    validated_updates['week_start_day'] = wsd
            except (TypeError, ValueError) as e:
                logger.debug("Invalid week_start_day value: %s", e)

        if 'timezone' in settings_data:
            timezone = settings_data['timezone']
            if isinstance(timezone, str) and len(timezone) <= 50:
                validated_updates['timezone'] = timezone

        if 'language' in settings_data:
            language = settings_data['language']
            if isinstance(language, str) and len(language) <= 10:
                validated_updates['language'] = language

        current_settings.update(validated_updates)

        autostart_updated = False
        if 'autostart' in settings_data:
            autostart_value = settings_data['autostart']
            if isinstance(autostart_value, bool):
                try:
                    if autostart_value:
                        if getattr(sys, 'frozen', False):
                            exe_path = sys.executable
                        else:
                            exe_path = os.path.join(_root_dir or '', 'main.py')
                        _app_context.autostart_manager.enable_autostart(exe_path)
                    else:
                        _app_context.autostart_manager.disable_autostart()
                    autostart_updated = True
                except Exception as e:
                    logger.error(f'Failed to update autostart setting: {e}')
                    return jsonify({'error': 'Failed to update autostart setting'}), 500

        save_success = False
        for attempt in range(max_retries):
            try:
                save_success = _app_context.data_manager.save_settings(user_id, current_settings)
                if save_success:
                    break
            except DatabaseError:
                logger.exception("Database error saving settings for user %s", user_id)
                return jsonify({'error': 'Database error saving settings'}), 503
            except Exception as e:
                logger.warning(f'Settings save attempt {attempt + 1} failed for user {user_id}: {e}')
                if attempt == max_retries - 1:
                    logger.error(f'Failed to save settings for user {user_id} after {max_retries} attempts')

        if save_success:
            try:
                _app_context.data_manager.add_settings_change_event(user_id)
            except DatabaseError:
                logger.exception("Database error recording settings change event")
            except Exception:  # noqa: broad-except
                logger.exception("Error recording settings change event")

            if daily_reset_time_changed:
                try:
                    if _setup_daily_reset_func:
                        _setup_daily_reset_func()
                    logger.info(f"Daily reset rescheduled to {validated_updates.get('daily_reset_time')}")
                except Exception as e:
                    logger.error(f'Failed to reschedule daily reset: {e}')

            current_settings['autostart_enabled'] = _app_context.autostart_manager.is_autostart_enabled()
            logger.info(f'Successfully updated settings for user {user_id}')
            return jsonify(current_settings)

        return jsonify({'error': 'Failed to save settings after multiple attempts'}), 500

    except DatabaseError:
        logger.exception("Database error updating settings for user %s", user_id)
        return jsonify({'error': 'Database error updating settings'}), 503
    except Exception:  # noqa: broad-except
        logger.exception("Error updating settings for user %s", user_id)
        return jsonify({'error': 'Failed to update settings'}), 500


@core_bp.route('/api/export', methods=['GET'])
def export_data():
    user_id = _get_user_id()
    try:
        if _ensure_data_manager_func and not _ensure_data_manager_func():
            return jsonify({'error': 'Failed to initialize data manager'}), 500

        dm = getattr(_app_context, 'data_manager', None) if _app_context else None
        if not dm:
            return jsonify({'error': 'Data manager not initialized'}), 500

        try:
            tasks = dm.load_tasks_for_user(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for export (user %s)", user_id)
            return jsonify({'error': 'Database error loading tasks'}), 503
        notes = dm.load_notes_for_user(user_id)
        try:
            settings = dm.load_settings(user_id)
        except DatabaseError:
            logger.exception("Database error loading settings for export (user %s)", user_id)
            return jsonify({'error': 'Database error loading settings'}), 503
        try:
            planner_v2_schedule = dm.load_planner_v2_schedule(user_id)
            days = dm.load_planner_history_days(user_id, limit=30)
            planner_history = {}
            for day in days:
                planner_history[day] = dm.load_planner_history_for_day(user_id, day)
        except DatabaseError:
            logger.exception('Database error exporting planner data')
            return jsonify({'error': 'Database error exporting planner data'}), 503

        return jsonify(
            {
                'exported_at': datetime.now().isoformat(),
                'user_id': user_id,
                'tasks': tasks,
                'notes': notes,
                'settings': settings,
                'planner_v2_schedule': planner_v2_schedule,
                'planner_history': planner_history,
            }
        )
    except Exception:  # noqa: broad-except
        logger.exception('Failed to export data for user %s', user_id)
        return jsonify({'error': 'Failed to export data'}), 500


@core_bp.route('/api/clear', methods=['POST'])
def clear_data():
    user_id = _get_user_id()
    try:
        if _ensure_data_manager_func and not _ensure_data_manager_func():
            return jsonify({'success': False, 'error': 'Failed to initialize data manager'}), 500

        dm = getattr(_app_context, 'data_manager', None) if _app_context else None
        db_path = getattr(dm, 'db_path', None) if dm else None
        if not db_path:
            return jsonify({'success': False, 'error': 'Data manager not initialized'}), 500

        def _safe_delete(conn, sql: str, params: tuple) -> None:
            try:
                conn.execute(sql, params)
            except sqlite3.OperationalError:
                return

        with sqlite3.connect(db_path) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('BEGIN IMMEDIATE TRANSACTION')

            _safe_delete(conn, 'DELETE FROM tasks WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM notes WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM planner_v2_schedule WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM planner_task_history WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM strike_today_report_history WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM deleted_tasks WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM sessions WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
            _safe_delete(conn, 'DELETE FROM settings WHERE user_id = ?', (user_id,))

            conn.commit()

        try:
            from src.analytics_manager import reset_analytics_counters

            reset_analytics_counters()
        except Exception:  # noqa: broad-except
            logger.exception("Failed to reset analytics counters during clear-data")

        return jsonify({'success': True})
    except Exception:  # noqa: broad-except
        logger.exception('Failed to clear data for user %s', user_id)
        return jsonify({'success': False, 'error': 'Failed to clear data'}), 500


@core_bp.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    logger.info('Shutdown requested via API')

    try:
        if _stop_system_tray_func:
            _stop_system_tray_func()
    except Exception:  # noqa: broad-except - API route error handler must catch all exceptions
        logger.exception("Failed to stop system tray during shutdown")

    def delayed_shutdown():
        import time

        time.sleep(0.5)
        os._exit(0)

    shutdown_thread = threading.Thread(target=delayed_shutdown)
    shutdown_thread.daemon = True
    shutdown_thread.start()

    return jsonify({'success': True, 'message': 'Shutting down...'})
