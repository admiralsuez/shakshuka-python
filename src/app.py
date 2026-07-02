from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, session, send_from_directory
from flask_cors import CORS
import threading
import time
import uuid
import sys
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import csv
import io
import hashlib
import hmac
import html
import re
import secrets
import logging
import subprocess
import sqlite3
from werkzeug.utils import secure_filename

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application modules
from src.sqlite_data_manager import SQLiteDataManager
from tools.autostart import WindowsAutostart
from src.update_manager import UpdateManager
from src.security_manager import security_manager
from src.monitoring import monitor
from src.pin_manager import PINManager
from src.constants import (
    MAX_CONTENT_LENGTH_BYTES, CSRF_TOKEN_EXPIRY_SECONDS,
    GITHUB_REPO_OWNER, GITHUB_REPO_NAME, ALLOWED_ORIGINS,
    DEFAULT_USER_ID
)
from src.core.config import config
from src.app_factory import create_app
from src.app_setup import resolve_root_dir, configure_assets, configure_working_dir, configure_logging
from src.utils.validators import validate_task_data
from src.routes.task_routes import task_bp, init_task_routes
from src.routes.notes_routes import notes_bp, init_notes_routes
from src.routes.pin_routes import pin_bp, init_pin_routes
from src.routes.planner_routes import planner_bp, init_planner_routes
from src.routes.monitoring_routes import monitoring_bp, init_monitoring_routes
from src.routes.updates_routes import updates_bp, init_updates_routes
from src.routes.backups_routes import backups_bp, init_backups_routes
from src.routes.github_update_routes import github_update_bp, init_github_update_routes
from src.routes.mobile_routes import mobile_bp, init_mobile_routes
from src.routes.core_routes import core_bp, init_core_routes
from src.services import scheduler as scheduler_service
from src.services import autosave as autosave_service
from src.services import tray as tray_service
from src.services.route_registration import register_blueprints
from src.services.scheduler_setup import (
    start_scheduler,
    stop_scheduler,
    is_scheduler_running,
    setup_daily_reset,
)
from src.services.tray_setup import (
    check_system_tray_available,
    start_system_tray,
    stop_system_tray,
    open_url_in_browser,
    open_folder,
)

from src.exceptions import DatabaseError, ValidationError

# Flask app configuration
app = create_app()
# Enable debug mode for better error messages (disable in production)
app.config['DEBUG'] = bool(config.DEBUG)
app.debug = bool(config.DEBUG)

# Issue #30: Set request size limit
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

from src.utils.paths import get_user_data_dir

user_data_dir = get_user_data_dir()
os.makedirs(user_data_dir, exist_ok=True)

root_dir = resolve_root_dir()
configure_assets(app, root_dir)
configure_working_dir(root_dir)


# System tray availability - moved to tray_setup.py
scheduler_thread = None
scheduler_stop_event = None

configure_logging(user_data_dir)
logger = logging.getLogger(__name__)

# Version compare helper

def _get_app_version():
    """Load application version from config file - works in both dev and frozen modes"""
    try:
        if getattr(sys, 'frozen', False):
            root_dir = os.path.dirname(sys.executable)
        else:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        version_path = os.path.join(root_dir, 'config', 'version.json')
        with open(version_path, 'r') as f:
            version_data = json.load(f)
        return str(version_data.get('version', '1.0'))
    except Exception as e:
        logger.warning(f"Failed to read version.json, falling back to 1.0.0: {e}")
        return '1.0.0'

# _is_newer_version moved to route_registration.py

# Now that logging is ready, record the working directory
try:
    logger.info(f"Working directory set to: {os.getcwd()}")
except Exception:  # noqa: broad-except
    logger.exception("Failed to log working directory")

# Issue #5: Import TTL cache for CSRF tokens
from cachetools import TTLCache

# Application context class to replace global variables
class AppContext:
    """Centralized application context to replace global variables with thread safety"""

    def __init__(self):
        self._data_manager = None
        self._autostart_manager = WindowsAutostart("Shakshuka")
        self._update_manager = None
        self._pin_manager = None
        self._auto_save_enabled = True
        self._auto_save_thread = None
        self._session_secrets = {}
        # Issue #5: Use TTL cache for CSRF tokens to prevent memory leaks
        self._csrf_tokens = TTLCache(maxsize=10000, ttl=CSRF_TOKEN_EXPIRY_SECONDS)
        
        # Thread safety locks
        self._lock = threading.RLock()
        self._auto_save_lock = threading.RLock()
        
        # Auto-save state management
        self._auto_save_running = False
        self._auto_save_stop_event = threading.Event()
        self._last_save_time = 0
        self._save_in_progress = False
        self._last_saved_tasks_signature = None

    @property
    def data_manager(self):
        return self._data_manager

    @data_manager.setter
    def data_manager(self, value):
        self._data_manager = value

    @property
    def autostart_manager(self):
        return self._autostart_manager

    @property
    def update_manager(self):
        return self._update_manager

    @update_manager.setter
    def update_manager(self, value):
        self._update_manager = value

    @property
    def pin_manager(self):
        return self._pin_manager

    @pin_manager.setter
    def pin_manager(self, value):
        self._pin_manager = value

    @property
    def auto_save_enabled(self):
        return self._auto_save_enabled

    @auto_save_enabled.setter
    def auto_save_enabled(self, value):
        self._auto_save_enabled = value

    @property
    def auto_save_thread(self):
        return self._auto_save_thread

    @auto_save_thread.setter
    def auto_save_thread(self, value):
        self._auto_save_thread = value

    def generate_session_secret(self, user_id):
        """Generate and store session secret"""
        secret = security_manager.generate_session_secret(user_id)
        self._session_secrets[user_id] = secret
        return secret

    def validate_session_secret(self, user_id, secret):
        """Validate session secret"""
        return self._session_secrets.get(user_id) == secret

    def generate_csrf_token(self):
        """Generate CSRF token - TTL cache handles expiration (Issue #5)"""
        token = secrets.token_urlsafe(32)
        self._csrf_tokens[token] = True  # TTL cache handles expiration
        return token

    def validate_csrf_token(self, token):
        """Validate CSRF token - TTL cache handles expiration (Issue #5)"""
        if not token or len(token) < 10:
            return False
        return token in self._csrf_tokens

    def is_auto_save_running(self):
        """Check if auto-save is currently running"""
        with self._auto_save_lock:
            return self._auto_save_running

    def set_auto_save_running(self, running):
        """Set auto-save running state"""
        with self._auto_save_lock:
            self._auto_save_running = running

    def is_save_in_progress(self):
        """Check if a save operation is in progress"""
        with self._auto_save_lock:
            return self._save_in_progress

    def set_save_in_progress(self, in_progress):
        """Set save in progress state"""
        with self._auto_save_lock:
            self._save_in_progress = in_progress

    def get_last_save_time(self):
        """Get the last save time"""
        with self._auto_save_lock:
            return self._last_save_time

    def set_last_save_time(self, save_time):
        """Set the last save time"""
        with self._auto_save_lock:
            self._last_save_time = save_time

    def get_last_saved_tasks_signature(self):
        """Get signature of the last saved tasks snapshot"""
        with self._auto_save_lock:
            return self._last_saved_tasks_signature

    def set_last_saved_tasks_signature(self, signature):
        """Cache signature of the last saved tasks snapshot"""
        with self._auto_save_lock:
            self._last_saved_tasks_signature = signature

    def stop_auto_save_event(self):
        """Signal auto-save to stop"""
        self._auto_save_stop_event.set()

    def wait_for_auto_save_stop(self, timeout=None):
        """Wait for auto-save stop event"""
        return self._auto_save_stop_event.wait(timeout)

    def clear_auto_save_stop_event(self):
        """Clear the auto-save stop event"""
        self._auto_save_stop_event.clear()

    # Password hashing functions removed - were unused dead code

# Initialize application context
from src.core.app_context import app_context
from src.core.di import set_extension

set_extension(app, 'app_context', app_context)

# Issue #29: Configure CORS with proper origins
if '*' in ALLOWED_ORIGINS:
    CORS(app, supports_credentials=True)
    logger.warning("CORS configured to allow all origins. Set ALLOWED_ORIGINS environment variable for production.")
else:
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
    logger.info("CORS configured with allowed origins: %s", ALLOWED_ORIGINS)

# Configure Content Security Policy to allow data: URIs for images (needed for Font Awesome icons)
@app.after_request
def after_request(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; script-src-elem 'self' 'unsafe-inline' https://cdnjs.cloudflare.com"
    return response

# Session management is handled by user_manager
# No Flask-Session configuration needed

# Request logging middleware - simplified for now
@app.before_request
def log_request_info():
    """Log incoming requests for debugging and monitoring"""
    if app.debug:
        logger.info(f"Request: {request.method} {request.url}")

@app.after_request
def log_response_info(response):
    """Log response details"""
    if app.debug:
        logger.info(f"Response: {response.status_code}")
    return response

# validate_input function removed - was unused dead code (40 lines)

# Helper function to ensure data manager is initialized
def ensure_data_manager():
    """Ensure data manager is initialized"""
    if not app_context.data_manager:
        logger.info("Data manager not initialized, attempting to initialize...")
        if not initialize_data_manager():
            logger.error("Failed to initialize data manager")
            return False
    return True

# Helper function to get user ID safely (Issue #13)
def get_user_id():
    """Get user ID - authentication disabled, always return default user"""
    # Always return valid user ID, never None
    return DEFAULT_USER_ID


set_extension(app, 'ensure_data_manager', ensure_data_manager)
set_extension(app, 'get_user_id', get_user_id)

# Old auth decorators removed - using PIN authentication now
# CSRF validation handled by security_manager for specific endpoints

def require_csrf(f):
    """Decorator to require CSRF token validation - DISABLED"""
    def decorated_function(*args, **kwargs):
        # CSRF validation disabled - bypass all checks
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def rate_limit(f):
    """Enhanced decorator to implement rate limiting with monitoring.

    On unexpected errors this returns a JSON payload with a stable
    `error_code` to make debugging easier in logs and on the frontend
    without leaking internal details.
    """
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        client_ip = request.remote_addr or 'unknown'
        
        try:
            if not security_manager.check_rate_limit(client_ip):
                monitor.record_error('rate_limit_exceeded', f'Rate limit exceeded for IP: {client_ip}')
                return jsonify({'error': 'Rate limit exceeded. Please try again later.', 'error_code': 'RATE_LIMIT_EXCEEDED'}), 429
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Record successful request
            response_time = time.time() - start_time
            endpoint = request.endpoint or 'unknown'
            method = request.method

            # Determine HTTP status code for monitoring
            status_code = 200
            if hasattr(result, 'status_code'):
                try:
                    status_code = int(result.status_code)
                except Exception:  # noqa: broad-except
                    status_code = 200
            elif isinstance(result, tuple) and len(result) >= 2:
                possible_status = result[1]
                try:
                    status_code = int(getattr(possible_status, 'value', possible_status))
                except Exception:  # noqa: broad-except
                    status_code = 200
            
            monitor.record_request(endpoint, method, response_time, status_code)
            
            return result
            
        except Exception as e:
            # Record error
            response_time = time.time() - start_time
            monitor.record_error('endpoint_error', str(e), {
                'endpoint': request.endpoint,
                'method': request.method,
                'client_ip': client_ip
            })
            
            logger.error(f"Error in rate-limited endpoint {request.endpoint}: {e}")
            return jsonify({'error': 'Internal server error', 'error_code': 'UNEXPECTED_ENDPOINT_ERROR'}), 500
    
    decorated_function.__name__ = f.__name__
    return decorated_function

def sanitize_input(data):
    """Sanitize input data to prevent XSS and validate data integrity"""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str) or len(key) > 100:
                logger.warning(f"Invalid key in input data: {key}")
                continue
            
            # Sanitize value based on type
            if isinstance(value, str):
                # Limit string length to prevent memory exhaustion
                if len(value) > 10000:
                    logger.warning(f"String value too long, truncating: {len(value)} chars")
                    value = value[:10000]
                sanitized[key] = security_manager.sanitize_input(value)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                # Recursively sanitize list items
                sanitized[key] = [sanitize_input(item) for item in value[:100]]  # Limit list size
            elif isinstance(value, dict):
                # Recursively sanitize nested dict
                sanitized[key] = sanitize_input(value)
            elif value is None:
                sanitized[key] = None
            else:
                logger.warning(f"Unsupported data type for key {key}: {type(value)}")
                sanitized[key] = str(value)[:1000]  # Convert to string and limit length
        
        return sanitized
    elif isinstance(data, str):
        # Limit string length
        if len(data) > 10000:
            logger.warning(f"String too long, truncating: {len(data)} chars")
            data = data[:10000]
        return security_manager.sanitize_input(data)
    elif isinstance(data, list):
        # Limit list size and sanitize items
        return [sanitize_input(item) for item in data[:100]]
    return data


# Register all blueprints using centralized service
register_blueprints(
    app=app,
    app_context=app_context,
    get_user_id_func=get_user_id,
    ensure_data_manager_func=ensure_data_manager,
    sanitize_input_func=sanitize_input,
    validate_task_data_func=validate_task_data,
    rate_limit_decorator=rate_limit,
    root_dir=root_dir,
    config=config,
    get_app_version_func=_get_app_version,
    setup_daily_reset_func=lambda: setup_daily_reset(),
    stop_system_tray_func=lambda: stop_system_tray(),
    UpdateManager=UpdateManager,
    get_user_data_dir_func=get_user_data_dir,
    monitor=monitor,
    security_manager=security_manager,
)


# Add cache-control headers to prevent browser caching of static files
@app.after_request
def add_cache_control_headers(response):
    """Add cache-control headers to prevent caching of static files"""
    # For static files with version query params, allow caching
    if request.path.startswith('/static/') and '?v=' in request.url:
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True
    else:
        # For everything else, no caching
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def initialize_data_manager():
    """Initialize data manager without password"""
    try:
        logger.info(f"Initializing data manager...")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Get user data directory to avoid permission issues
        # This ensures the app works when installed in Program Files
        data_dir = os.path.join(user_data_dir, "data")

        print(f"Data directory path: {data_dir}")

        # Create data directory if it doesn't exist
        try:
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Data directory created/verified: {os.path.abspath(data_dir)}")
        except Exception as dir_error:
            logger.error(f"Failed to create data directory '{data_dir}': {dir_error}")
            return False

        # Check write permissions
        test_file = os.path.join(data_dir, ".test_write")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info("Write permissions verified")
        except Exception as write_error:
            logger.error(f"Write permission test failed: {write_error}")
            return False

        # Initialize data manager with the working data directory
        try:
            app_context.data_manager = SQLiteDataManager(data_dir=data_dir)
            logger.info(f"SQLite data manager initialized successfully with data directory: {data_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite data manager: {e}")
            return False

        # Initialize PIN manager
        try:
            app_context.pin_manager = PINManager(data_dir=data_dir)
            logger.info("PIN manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PIN manager: {e}")
            return False
        
        # Initialize update manager
        try:
            # Determine app root directory (works in both dev and frozen modes)
            if getattr(sys, 'frozen', False):
                app_root = os.path.dirname(sys.executable)
            else:
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            # Use user data directory (AppData/Roaming/Shakshuka) for update config/backups
            os.makedirs(user_data_dir, exist_ok=True)

            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=user_data_dir)
            app_context.update_manager._setup_auto_update_scheduler()
            app_context.update_manager._setup_weekly_backup_scheduler()
            logger.info("Update manager initialized successfully")
        except Exception as update_error:
            logger.warning(f"Update manager initialization failed: {update_error}")
            # Don't fail the entire setup for update manager issues
        
        return True
    except Exception as e:
        print(f"Error initializing data manager: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False


def start_auto_save():
    """Start the auto-save background thread with proper state management"""
    try:
        autosave_service.set_app_context(app_context)
        autosave_service.set_get_user_id(get_user_id)
        autosave_service.start_auto_save()
        logger.info("Auto-save thread started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start auto-save: {e}")
        app_context.set_auto_save_running(False)

def stop_auto_save():
    """Stop the auto-save background thread with proper cleanup"""
    try:
        autosave_service.set_app_context(app_context)
        autosave_service.stop_auto_save(timeout=10)
        app_context.set_auto_save_running(False)
        
    except Exception as e:
        logger.error(f"Error stopping auto-save: {e}")

# Removed: get_timezone_aware_time() - unused function.
# App uses local time (datetime.now()) exclusively for consistency.
def get_changelog():
    """Serve the changelog file"""
    try:
        # Handle both development and PyInstaller executable modes
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            root_dir = os.path.dirname(sys.executable)
        else:
            # Running as Python script
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        changelog_path = os.path.join(root_dir, 'config', 'changelog.txt')
        logger.info(f"Looking for changelog at: {changelog_path}")
        
        with open(changelog_path, 'r', encoding='utf-8') as f:
            changelog_content = f.read()
        return changelog_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except FileNotFoundError:
        logger.error(f"Changelog file not found at: {changelog_path}")
        return 'Changelog file not found.', 404
    except Exception as e:
        logger.error(f"Error reading changelog: {e}")
        return 'Error reading changelog.', 500

def get_analytics():
    """Return decoupled analytics counters backed by SQLite, not JSON.

    Values are stored in a small analytics.db under the user data
    directory so they survive reinstalls and are independent of the
    main tasks database and daily reset logic.
    """
    try:
        from src.analytics_manager import get_analytics_counters

        data = get_analytics_counters()
        return jsonify({'success': True, **data})
    except Exception as e:
        logger.error(f"Analytics read error: {e}")
        return jsonify({
            'success': False,
            'today_date': datetime.now().strftime('%Y-%m-%d'),
            'today_strikes': 0,
           'total_strikes': 0,
       }), 200


def get_daily_recap():
    """Return recap metrics for a given day (defaults to yesterday).

    Includes a 'seen' boolean so the frontend can decide whether to show the modal.
    """
    user_id = get_user_id()
    if not ensure_data_manager():
        return jsonify({'success': False, 'error': 'Failed to initialize data manager'}), 500

    try:
        day = request.args.get('day')
        if not day:
            day = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        recap = app_context.data_manager.get_daily_recap(user_id, day)
        seen = app_context.data_manager.was_recap_seen(user_id, day)
        return jsonify({'success': True, 'seen': bool(seen), **recap})
    except ValidationError as e:
        logger.exception("Invalid daily recap request")
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception("Database error building daily recap")
        return jsonify({'success': False, 'error': 'Database error building daily recap'}), 503
    except Exception:  # noqa: broad-except
        logger.exception("Daily recap error")
        return jsonify({'success': False, 'error': 'Daily recap error'}), 500


def mark_daily_recap_seen():
    user_id = get_user_id()
    if not ensure_data_manager():
        return jsonify({'success': False, 'error': 'Failed to initialize data manager'}), 500

    try:
        payload = request.json if isinstance(request.json, dict) else {}
        day = payload.get('day') or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        ok = app_context.data_manager.mark_recap_seen(user_id, day)
        return jsonify({'success': bool(ok), 'day': day})
    except ValidationError as e:
        logger.exception("Invalid mark recap seen request")
        return jsonify(e.to_dict()), 400
    except DatabaseError:
        logger.exception("Database error marking recap seen")
        return jsonify({'success': False, 'error': 'Database error marking recap seen'}), 503
    except Exception:  # noqa: broad-except
        logger.exception("Mark recap seen error")
        return jsonify({'success': False, 'error': 'Mark recap seen error'}), 500


def get_analytics_summary():
    """Consolidated analytics endpoint - returns all dashboard data in one call.
    
    This reduces multiple API calls to a single request, improving performance.
    Returns: tasks stats, strikes, streak, completed_forever, settings_changes, tasks_added, tasks_retried
    """
    user_id = get_user_id()
    if not ensure_data_manager():
        return jsonify({'success': False, 'error': 'Failed to initialize data manager'}), 500
    
    try:
        from src.analytics_manager import get_analytics_counters
        
        # Get analytics counters (today_strikes, total_strikes)
        analytics = get_analytics_counters()
        
        # Get tasks for stats calculation
        try:
            tasks = app_context.data_manager.load_tasks_for_user(user_id)
        except DatabaseError:
            logger.exception("Database error loading tasks for analytics summary")
            return jsonify({'success': False, 'error': 'Database error loading tasks'}), 503
        tasks = tasks or []
        try:
            tasks = [t for t in tasks if isinstance(t, dict)]
        except Exception:  # noqa: broad-except
            tasks = []
        
        # Calculate task stats
        total_tasks = len(tasks)
        active_tasks = len([t for t in tasks if not t.get('completed') and not t.get('struck_forever') and not t.get('struck_today')])
        expired_tasks = len([t for t in tasks if t.get('due_date') and not t.get('completed') and not t.get('struck_forever') and t.get('due_date') < datetime.now().strftime('%Y-%m-%d')])
        completed_tasks = len([t for t in tasks if t.get('completed') or t.get('struck_forever')])
        
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

        # Load user settings for streak calculation
        try:
            user_settings = app_context.data_manager.load_settings(user_id) or {}
        except DatabaseError:
            logger.exception("Database error loading settings for analytics summary")
            return jsonify({'success': False, 'error': 'Database error loading settings'}), 503
        streak_skip_weekends = bool(user_settings.get('streak_skip_weekends', False))
        streak_count_new_tasks = bool(user_settings.get('streak_count_new_tasks', False))
        streak_count_settings = bool(user_settings.get('streak_count_settings', False))

        # Completion streak: consecutive days with at least one completion.
        today_str = datetime.now().strftime('%Y-%m-%d')
        completion_current = 0
        completion_best = 0
        try:
            from src.db.analytics_queries import get_productivity_streak

            with app_context.data_manager.pooled_connection() as conn:
                completion_current = get_productivity_streak(
                    conn,
                    user_id,
                    skip_weekends=streak_skip_weekends,
                    count_new_tasks=streak_count_new_tasks,
                    count_settings=streak_count_settings,
                )
        except DatabaseError:
            logger.exception("Database error calculating completion streak")
            return jsonify({'success': False, 'error': 'Database error calculating streak'}), 503
        except Exception:  # noqa: broad-except
            logger.exception("Error calculating completion streak")
            return jsonify({'success': False, 'error': 'Error calculating streak'}), 500

        try:
            completion_days = set()
            for t in tasks:
                if not t:
                    continue
                if not (t.get('completed') or t.get('struck_forever')):
                    continue
                completed_at = t.get('completed_at')
                if not completed_at:
                    continue
                s = str(completed_at)
                d = s.split('T')[0] if 'T' in s else s
                try:
                    completion_days.add(datetime.strptime(d, '%Y-%m-%d').date())
                except Exception:  # noqa: broad-except
                    continue
            completion_best = _longest_consecutive_run(sorted(completion_days))
        except Exception:  # noqa: broad-except
            completion_best = 0

        # Strike streak: consecutive days with at least one strike event.
        strike_current = 0
        strike_best = 0
        try:
            with app_context.data_manager.pooled_connection() as conn:
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
            logger.exception("Database error calculating strike streak")
            return jsonify({'success': False, 'error': 'Database error calculating strike streak'}), 503
        except Exception:  # noqa: broad-except
            logger.exception("Error calculating strike streak")
            return jsonify({'success': False, 'error': 'Error calculating strike streak'}), 500
        
        # Get completed forever count
        completed_forever = len([t for t in tasks if t.get('struck_forever')])
        
        # Get additional metrics from database
        try:
            with app_context.data_manager.pooled_connection() as conn:
                cur = conn.cursor()

                cur.execute('SELECT COUNT(*) FROM settings_change_events WHERE user_id = ?', (user_id,))
                settings_changes = cur.fetchone()[0]

                cur.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ?', (user_id,))
                tasks_added = cur.fetchone()[0]

                tasks_retried = 0
        except DatabaseError:
            logger.exception("Database error fetching additional metrics")
            return jsonify({'success': False, 'error': 'Database error fetching metrics'}), 503
        except Exception:  # noqa: broad-except
            logger.exception("Error fetching additional metrics")
            return jsonify({'success': False, 'error': 'Error fetching metrics'}), 500
        
        # Calculate tasks with dates and time from current tasks
        tasks_with_dates_live = len([t for t in tasks if t.get('due_date')])
        tasks_with_time_live = len([t for t in tasks if t.get('estimated_duration') or t.get('duration')])
        tasks_planned_all_time = analytics.get('tasks_planned', 0)
        
        return jsonify({
            'success': True,
            'tasks': {
                'total': total_tasks,
                'active': active_tasks,
                'expired': expired_tasks,
                'completed': completed_tasks
            },
            'strikes': {
                'today': analytics.get('today_strikes', 0),
                'total': analytics.get('total_strikes', 0)
            },
            # Backward compatibility
            'streak': {
                'current': completion_current,
                'best': completion_best
            },
            'completion_streak': {
                'current': completion_current,
                'best': completion_best
            },
            'strike_streak': {
                'current': strike_current,
                'best': strike_best
            },
            'completed_forever': completed_forever,
            'settings_changes': settings_changes,
            'tasks_added': tasks_added,
            'tasks_retried': tasks_retried,
            'tasks_deleted': analytics.get('tasks_deleted', 0),
            'tasks_edited': analytics.get('tasks_edited', 0),
            'tasks_with_dates': tasks_with_dates_live,
            'tasks_with_time': tasks_with_time_live,
            'tasks_planned': tasks_planned_all_time
        })
        
    except Exception:  # noqa: broad-except
        logger.exception("Analytics summary error")
        return jsonify({
            'success': False,
            'tasks': {'total': 0, 'active': 0, 'expired': 0, 'completed': 0},
            'strikes': {'today': 0, 'total': 0},
            'streak': {'current': 0, 'best': 0},
            'completion_streak': {'current': 0, 'best': 0},
            'strike_streak': {'current': 0, 'best': 0},
            'completed_forever': 0,
            'settings_changes': 0,
            'tasks_added': 0,
            'tasks_retried': 0,
            'tasks_deleted': 0,
            'tasks_edited': 0,
            'tasks_with_dates': 0,
            'tasks_with_time': 0,
            'tasks_planned': 0
        }), 200


def get_account_info():
    try:
        pin = app_context.pin_manager
        return jsonify({
            'username': DEFAULT_USER_ID,
            'authenticated': bool(pin.is_session_valid()) if pin else False,
            'created_at': None,
            'last_login': pin.get_last_login() if pin else None
        })
    except Exception as e:
        logger.error(f"/api/account error: {e}")
        return jsonify({'username': DEFAULT_USER_ID, 'authenticated': False}), 200

def login():
    """Login page - authentication disabled, redirect to dashboard"""
    # Authentication disabled - redirect to dashboard
    return redirect(url_for('core.index'))



# ============================================
# Task Management Endpoints
# ============================================

def get_autostart_status():
    try:
        enabled = app_context.autostart_manager.is_autostart_enabled() if app_context.autostart_manager else False
        cmd = app_context.autostart_manager.get_autostart_command() if app_context.autostart_manager else None
        return jsonify({ 'enabled': bool(enabled), 'command': cmd })
    except Exception:  # noqa: broad-except
        return jsonify({ 'enabled': False }), 200

def get_settings():
    """Get application settings for the authenticated user with race condition protection"""
    user_id = get_user_id()
    
    # Check if data manager is initialized
    if not ensure_data_manager():
        return jsonify({'error': 'Failed to initialize data manager'}), 500
    
    try:
        # Use thread-safe settings loading with retry mechanism
        max_retries = 3
        settings = None
        
        for attempt in range(max_retries):
            try:
                settings = app_context.data_manager.load_settings(user_id)
                if settings:
                    break
            except Exception as e:
                logger.warning(f"Settings load attempt {attempt + 1} failed for user {user_id}: {e}")
                if attempt == max_retries - 1:
                    # Return default settings as failsafe
                    settings = {
                        'theme': 'orange',
                        'dpi_scale': 100,
                        'autosave_interval': 30,
                        'notifications': True,
                        'daily_reset_time': '06:00',
                        'timezone': 'UTC',
                        'language': 'en',
                        'mini_analytics_interval': 5,
                        'settings_layout': 'scroll',
                    }
                    logger.warning(f"Using default settings for user {user_id} after {max_retries} failed attempts")
        
        if not settings:
            settings = {
                'theme': 'orange',
                'dpi_scale': 100,
                'autosave_interval': 30,
                'notifications': True,
                'daily_reset_time': '06:00',
                'timezone': 'UTC',
                'language': 'en',
                'mini_analytics_interval': 5,
                'settings_layout': 'scroll',
            }
        
        # Add autostart status (thread-safe)
        try:
            settings['autostart_enabled'] = app_context.autostart_manager.is_autostart_enabled()
        except Exception as e:
            logger.warning(f"Failed to get autostart status: {e}")
            settings['autostart_enabled'] = False
        
        # Validate and sanitize settings before returning
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
            'finish': settings.get('finish', 'glossy'),
            'intensity': settings.get('intensity', '5'),
        }

        if validated_settings.get('settings_layout') not in ['scroll', 'tabs']:
            validated_settings['settings_layout'] = 'scroll'
        
        logger.info(f"Successfully loaded settings for user {user_id}")
        return jsonify(validated_settings)
        
    except Exception as e:
        logger.error(f"Error loading settings for user {user_id}: {e}")
        # Return safe default settings
        return jsonify({
            'theme': 'orange',
            'dpi_scale': 100,
            'autosave_interval': 30,
            'notifications': True,
            'daily_reset_time': '06:00',
            'timezone': 'UTC',
            'language': 'en',
            'settings_layout': 'scroll',
            'autostart_enabled': False
        })

def update_settings():
    """Update application settings for the authenticated user with race condition protection"""
    user_id = get_user_id()
    
    # Validate request data
    if not request.json:
        return jsonify({'error': 'No settings data provided'}), 400
    
    settings_data = request.json
    
    # Validate settings data structure
    if not isinstance(settings_data, dict):
        return jsonify({'error': 'Settings data must be a dictionary'}), 400
    
    try:
        # Load current settings with retry mechanism
        max_retries = 3
        current_settings = None
        
        for attempt in range(max_retries):
            try:
                current_settings = app_context.data_manager.load_settings(user_id)
                if current_settings:
                    break
            except Exception as e:
                logger.warning(f"Settings load attempt {attempt + 1} failed for user {user_id}: {e}")
                if attempt == max_retries - 1:
                    # Use default settings as base
                    current_settings = {
                        'theme': 'orange',
                        'dpi_scale': 100,
                        'autosave_interval': 30,
                        'notifications': True,
                        'daily_reset_time': '06:00',
                        'timezone': 'UTC',
                        'language': 'en'
                    }
                    logger.warning(f"Using default settings as base for user {user_id}")
        
        if not current_settings:
            current_settings = {
                'theme': 'orange',
                'dpi_scale': 100,
                'autosave_interval': 30,
                'notifications': True,
                'daily_reset_time': '06:00',
                'timezone': 'UTC',
                'language': 'en'
            }
        
        # Validate and sanitize incoming settings data
        validated_updates = {}
        
        # Theme validation
        if 'theme' in settings_data:
            theme = settings_data['theme']
            # Keep in sync with the main settings handler in core_routes and the
            # theme selector in assets/static/js/features/settings.js.
            valid_themes = [
                'orange', 'blue', 'green', 'purple',
                'dark', 'light', 'self-esteem', 'anxiety',
                'yellow', 'speedy', 'auto',
            ]
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
        
        # Notifications validation
        if 'notifications' in settings_data:
            notifications = settings_data['notifications']
            if isinstance(notifications, bool):
                validated_updates['notifications'] = notifications
        
        # Daily reset time validation
        if 'daily_reset_time' in settings_data:
            reset_time = settings_data['daily_reset_time']
            if isinstance(reset_time, str) and _validate_time_format(reset_time):
                validated_updates['daily_reset_time'] = reset_time
                # Flag to reschedule daily reset
                daily_reset_time_changed = True
            else:
                daily_reset_time_changed = False
        else:
            daily_reset_time_changed = False
        
        # Quick project-from-title toggle (simple boolean)
        if 'quick_project_from_title' in settings_data:
            qp = settings_data['quick_project_from_title']
            if isinstance(qp, bool):
                validated_updates['quick_project_from_title'] = qp

        # Casual dates toggle (simple boolean)
        if 'casual_dates' in settings_data:
            cd = settings_data['casual_dates']
            if isinstance(cd, bool):
                validated_updates['casual_dates'] = cd
        
        # Streak settings (simple booleans)
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
        
        # Finish validation (glossy/matte)
        if 'finish' in settings_data:
            finish = settings_data['finish']
            if isinstance(finish, str) and finish in ['glossy', 'matte']:
                validated_updates['finish'] = finish
        
        # Intensity validation (1-10)
        if 'intensity' in settings_data:
            intensity = settings_data['intensity']
            if isinstance(intensity, str) and intensity in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                validated_updates['intensity'] = intensity
        
        # Timezone validation
        if 'timezone' in settings_data:
            timezone = settings_data['timezone']
            if isinstance(timezone, str) and len(timezone) <= 50:
                validated_updates['timezone'] = timezone
        
        # Language validation
        if 'language' in settings_data:
            language = settings_data['language']
            if isinstance(language, str) and len(language) <= 10:
                validated_updates['language'] = language
        
        # Merge validated updates with current settings
        current_settings.update(validated_updates)
        
        # Handle autostart setting separately (not stored in database)
        autostart_updated = False
        if 'autostart' in settings_data:
            autostart_value = settings_data['autostart']
            if isinstance(autostart_value, bool):
                try:
                    if autostart_value:
                        # Get the correct executable path
                        if getattr(sys, 'frozen', False):
                            exe_path = sys.executable
                        else:
                            # Get the root directory (parent of src/)
                            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            exe_path = os.path.join(root_dir, "main.py")
                        app_context.autostart_manager.enable_autostart(exe_path)
                    else:
                        app_context.autostart_manager.disable_autostart()
                    autostart_updated = True
                except Exception as e:
                    logger.error(f"Failed to update autostart setting: {e}")
                    return jsonify({'error': 'Failed to update autostart setting'}), 500
        
        # Save settings with retry mechanism
        save_success = False
        for attempt in range(max_retries):
            try:
                save_success = app_context.data_manager.save_settings(user_id, current_settings)
                if save_success:
                    break
            except Exception as e:
                logger.warning(f"Settings save attempt {attempt + 1} failed for user {user_id}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to save settings for user {user_id} after {max_retries} attempts")
        
        if save_success:
            # Record a settings-change event for daily recap/history (best effort)
            try:
                app_context.data_manager.add_settings_change_event(user_id)
            except DatabaseError:
                logger.exception("Database error recording settings change event")
            except Exception:  # noqa: broad-except
                logger.exception("Error recording settings change event")
            # If daily reset time was changed, reschedule the reset job
            if daily_reset_time_changed:
                try:
                    scheduler_service.setup_daily_reset()
                    logger.info(f"Daily reset rescheduled to {validated_updates.get('daily_reset_time')}")
                except Exception as e:
                    logger.error(f"Failed to reschedule daily reset: {e}")
            
            # Add autostart status to response
            current_settings['autostart_enabled'] = app_context.autostart_manager.is_autostart_enabled()
            logger.info(f"Successfully updated settings for user {user_id}")
            return jsonify(current_settings)
        else:
            return jsonify({'error': 'Failed to save settings after multiple attempts'}), 500
            
    except Exception as e:
        logger.error(f"Error updating settings for user {user_id}: {e}")
        return jsonify({'error': 'Failed to update settings'}), 500


def export_data():
    user_id = get_user_id()
    try:
        dm = getattr(app_context, 'data_manager', None)
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
            logger.exception("Database error exporting planner data (user %s)", user_id)
            return jsonify({'error': 'Database error exporting planner data'}), 503

        return jsonify({
            'exported_at': datetime.now().isoformat(),
            'user_id': user_id,
            'tasks': tasks,
            'notes': notes,
            'settings': settings,
            'planner_v2_schedule': planner_v2_schedule,
            'planner_history': planner_history,
        })
    except Exception:  # noqa: broad-except
        logger.exception("Failed to export data for user %s", user_id)
        return jsonify({'error': 'Failed to export data'}), 500


def clear_data():
    user_id = get_user_id()
    try:
        dm = getattr(app_context, 'data_manager', None)
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
    except Exception as e:
        logger.error(f"Failed to clear data for user {user_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to clear data'}), 500

def _validate_time_format(time_str: str) -> bool:
    """Validate time format (HH:MM)"""
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

def shutdown_server():
    """Shutdown the server (for system tray quit)"""
    global shutdown_requested
    shutdown_requested = True
    logger.info("Shutdown requested via API")
    
    # Stop system tray
    stop_system_tray()
    
    # Schedule shutdown after response is sent
    import threading
    def delayed_shutdown():
        import time
        time.sleep(0.5)  # Give time for response to be sent
        import os
        os._exit(0)
    
    shutdown_thread = threading.Thread(target=delayed_shutdown)
    shutdown_thread.daemon = True
    shutdown_thread.start()
    
    return jsonify({'success': True, 'message': 'Shutting down...'})

if __name__ == '__main__':
    try:
        print("Starting Shakshuka application...")
        
        # In frozen/packaged mode we enforce a single running instance using
        # process scanning + a mutex. In dev (non-frozen) mode this is
        # disabled so "python src/app.py" can be used freely alongside an
        # installed EXE for debugging.
        import time
        import psutil
        import sys as _sys_single
        
        def kill_existing_instances():
            """Kill any existing Shakshuka instances with enhanced detection.

            NOTE: This is only active when running as a frozen executable. In
            dev mode (python src/app.py) it is a no-op to avoid immediately
            killing the dev process itself.
            """
            if not getattr(_sys_single, 'frozen', False):
                # Dev mode: do not attempt aggressive single-instance killing.
                print("Dev mode detected; skipping existing-instance termination.")
                return

            killed_count = 0
            max_attempts = 3
            
            for attempt in range(max_attempts):
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
                    try:
                        # Check if it's Shakshuka.exe
                        if proc.info['name'] == 'Shakshuka.exe':
                            print(f"Found existing Shakshuka.exe instance (PID: {proc.info['pid']}), terminating...")
                            proc.terminate()
                            killed_count += 1
                        
                        # Check if it's python running Shakshuka-related scripts
                        elif proc.info['name'] == 'python.exe' and proc.info['cmdline']:
                            cmdline = ' '.join(proc.info['cmdline']).lower()
                            if any(keyword in cmdline for keyword in ['main.py', 'app.py', 'shakshuka']):
                                print(f"Found existing Python Shakshuka instance (PID: {proc.info['pid']}), terminating...")
                                proc.terminate()
                                killed_count += 1
                        
                        # Check if executable path contains Shakshuka
                        elif proc.info.get('exe') and 'shakshuka' in proc.info['exe'].lower():
                            print(f"Found existing Shakshuka instance by path (PID: {proc.info['pid']}), terminating...")
                            proc.terminate()
                            killed_count += 1
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                        logger.debug("Process iteration exception during termination attempt: %s", e)
                
                if killed_count > 0:
                    print(f"Terminated {killed_count} existing instance(s). Waiting 3 seconds...")
                    time.sleep(3)
                    
                    # Force kill any remaining processes
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if proc.info['name'] == 'Shakshuka.exe':
                                print(f"Force killing remaining Shakshuka.exe (PID: {proc.info['pid']})...")
                                proc.kill()
                            elif proc.info['name'] == 'python.exe' and proc.info['cmdline']:
                                cmdline = ' '.join(proc.info['cmdline']).lower()
                                if any(keyword in cmdline for keyword in ['main.py', 'app.py', 'shakshuka']):
                                    print(f"Force killing remaining Python Shakshuka (PID: {proc.info['pid']})...")
                                    proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                            logger.debug("Process iteration exception during force-kill attempt: %s", e)
                    
                    time.sleep(2)
                    break
                else:
                    print("No existing instances found.")
                    break
        
        # Kill existing instances before starting
        kill_existing_instances()
        
        # Additional single-instance check using Windows mutex
        import tempfile
        
        def check_single_instance():
            """Use Windows mutex to ensure only one instance runs with enhanced robustness"""
            if os.name == 'nt':  # Windows
                import win32event
                import win32api
                import win32con
                
                # Create a named mutex with multiple attempts
                mutex_name = "ShakshukaSingleInstanceMutex"
                mutex = None
                
                for attempt in range(3):
                    try:
                        mutex = win32event.CreateMutex(None, False, mutex_name)
                        last_error = win32api.GetLastError()
                        
                        if last_error == win32con.ERROR_ALREADY_EXISTS:
                            print(f"Another instance is already running (attempt {attempt + 1}). Exiting...")
                            if mutex:
                                win32event.CloseHandle(mutex)
                            return False
                        elif last_error == 0:
                            print("Single instance mutex acquired successfully.")
                            return True
                        else:
                            print(f"Mutex creation failed with error {last_error}, retrying...")
                            if mutex:
                                win32event.CloseHandle(mutex)
                            time.sleep(1)
                            
                    except Exception as e:
                        print(f"Error creating mutex (attempt {attempt + 1}): {e}")
                        if mutex:
                            try:
                                win32event.CloseHandle(mutex)
                            except Exception:  # noqa: broad-except
                                logger.exception("Failed to close mutex handle")
                        time.sleep(1)
                
                print("Failed to acquire mutex after 3 attempts. Exiting...")
                return False
                
            else:  # Unix-like systems
                import fcntl
                lock_file = os.path.join(tempfile.gettempdir(), 'shakshuka.lock')
                
                for attempt in range(3):
                    try:
                        # Try to create and lock the file
                        lock_fd = os.open(lock_file, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        
                        # Write current PID to lock file
                        os.write(lock_fd, str(os.getpid()).encode())
                        os.close(lock_fd)
                        
                        print("Single instance lock acquired successfully.")
                        return True
                        
                    except (OSError, IOError) as e:
                        print(f"Lock acquisition failed (attempt {attempt + 1}): {e}")
                        try:
                            os.close(lock_fd)
                        except OSError:
                            logger.exception("Failed to close lock file descriptor")
                        time.sleep(1)
                
                print("Failed to acquire lock after 3 attempts. Another instance may be running.")
                return False
        
        # Check single instance with file/OS-level lock. Only enforce this in
        # frozen/packaged mode; in dev (python src/app.py) we skip it so the
        # app can run without pywin32 mutex support.
        if getattr(sys, 'frozen', False):
            if not check_single_instance():
                sys.exit(1)
        else:
            print("Dev mode detected; skipping single-instance mutex check.")
        
        # Initialize data manager
        print("Initializing data manager...")
        if not initialize_data_manager():
            print("Failed to initialize data manager")
            sys.exit(1)
        print("Data manager initialized successfully")
        
        # Start auto-save
        print("Starting auto-save...")
        start_auto_save()
        print("Auto-save started")
        
        # Start scheduler for daily resets
        print("Starting scheduler...")
        start_scheduler()
        print("Scheduler started")
        
        # Open browser automatically
        import webbrowser
        import threading
        
        def open_browser():
            import time
            import urllib.request

            connect_host = '127.0.0.1'
            url = f"http://{connect_host}:{config.DEFAULT_PORT}"
            health_url = f"{url.rstrip('/')}/health"
            deadline = time.time() + 20
            last_error: Exception | None = None

            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(health_url, timeout=0.5) as resp:
                        if getattr(resp, 'status', None) == 200:
                            break
                except Exception as e:
                    last_error = e
                time.sleep(0.25)

            try:
                webbrowser.open(url)
            except Exception:  # noqa: broad-except
                logger.exception("Could not open browser")
                if last_error is not None:
                    logger.warning("Last /health check error before opening browser: %s", last_error)
        
        # Start browser in a separate thread
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Run the Flask app
        print("Starting Shakshuka...")
        print(f"Opening browser at http://{config.DEFAULT_HOST}:{config.DEFAULT_PORT}")
        print("System tray icon available for app management")
        print("Press Ctrl+C to stop the application")
        print()
        
        # Fix console encoding issues for PyInstaller
        import sys
        import os
        
        # Set console encoding to UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:  # noqa: broad-except
                logger.exception("Failed to configure console encoding")
        
        # Suppress Flask banner and CLI to avoid encoding issues
        os.environ['FLASK_SKIP_DOTENV'] = '1'
        os.environ['FLASK_CLI'] = '0'
        
        # Start system tray (runs in background thread)
        try:
            print("Attempting to start system tray...")
            tray_starter = globals().get('start_system_tray')
            if callable(tray_starter):
                tray_starter()
            else:
                logger.info("System tray support not available (start_system_tray missing)")
        except Exception as e:
            logger.warning(f"Could not start system tray: {e}")
            print(f"Could not start system tray: {e}")
        
        # Custom Flask runner to avoid click.echo issues
        try:
            from werkzeug.serving import run_simple
            print(f"Server starting on http://{config.DEFAULT_HOST}:{config.DEFAULT_PORT}")
            run_simple(config.DEFAULT_HOST, config.DEFAULT_PORT, app, use_reloader=False, use_debugger=False)
        except Exception as e:
            print(f"Error starting server: {e}")
            # Fallback to standard Flask run
            app.run(host=config.DEFAULT_HOST, port=config.DEFAULT_PORT, debug=False, use_reloader=False)
            
    except Exception as e:
        print(f"Fatal error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# System Tray Management
system_tray_icon = None
shutdown_requested = False

def create_system_tray_icon() -> Optional[Any]:
    """Create and show system tray icon"""
    # Check availability lazily
    if not check_system_tray_available(lazy_check=True):
        logger.warning("System tray not available - skipping icon creation")
        return None

    try:
        # Import pystray here to avoid import errors at module level
        import pystray
        from PIL import Image, ImageDraw
        # Create a simple icon (you can replace this with a proper icon file)
        icon = create_icon_image()

        # System tray menu actions
        def open_dashboard():
            import webbrowser
            webbrowser.open(f"http://{config.DEFAULT_HOST}:{config.DEFAULT_PORT}")

        def open_logs_folder():
            folder = os.path.join(user_data_dir, 'logs')
            try:
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', folder])
                else:
                    subprocess.Popen(['xdg-open', folder])
            except Exception as e:
                logger.error(f"Failed to open logs folder: {e}")

        def open_data_folder():
            folder = os.path.join(user_data_dir, 'data')
            try:
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', folder])
                else:
                    subprocess.Popen(['xdg-open', folder])
            except Exception as e:
                logger.error(f"Failed to open data folder: {e}")

        def quit_app():
            logger.info("Quitting application from system tray")
            if system_tray_icon:
                system_tray_icon.stop()
            
            # Call shutdown API endpoint to properly stop the server
            import requests
            try:
                requests.post(f"http://{config.DEFAULT_HOST}:{config.DEFAULT_PORT}/api/shutdown", timeout=1)
            except Exception:  # noqa: broad-except
                logger.exception("Shutdown API call failed; forcing process exit")
                # Fallback to direct exit if API call fails
                import os
                os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard", lambda: open_dashboard()),
            pystray.MenuItem("Open Logs Folder", lambda: open_logs_folder()),
            pystray.MenuItem("Open Data Folder", lambda: open_data_folder()),
            pystray.MenuItem("Quit Shakshuka", lambda: quit_app())
        )

        # Create and show icon
        # This is where pystray tries to initialize GTK/AppIndicator
        tray_icon = pystray.Icon("shakshuka", icon, "Shakshuka Task Manager", menu)
        return tray_icon

    except Exception as e:
        # Catch GTK errors and other system tray errors
        error_msg = str(e)
        if 'Gtk' in error_msg or 'gtk' in error_msg.lower():
            logger.warning(f"System tray not available (GTK not available): {e}")
            print(f"Warning: System tray requires GTK libraries on Linux. Install with: sudo apt-get install python3-gi gir1.2-gtk-3.0")
        elif 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
            logger.warning(f"System tray not available (AppIndicator not available): {e}")
            print(f"Warning: System tray requires AppIndicator libraries on Linux. Install with: sudo apt-get install gir1.2-ayatanaappindicator3-0.1")
        else:
            logger.warning(f"System tray not available: {e}")
            print(f"Warning: System tray not available. App will work without tray icon.")
        # Return None - app continues without system tray
        return None

def create_icon_image() -> Any:
    """Create icon image for the system tray.

    Prefers the real app icon file (icon.ico / icon.png) so the tray matches
    the EXE/installer icon. Falls back to the old drawn leaf if loading fails.
    """
    try:
        from PIL import Image, ImageDraw
        import sys
        import os

        # Determine app root both in dev and frozen (PyInstaller) modes
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_candidates = [
            os.path.join(base_dir, 'assets', 'static', 'images', 'icon.ico'),
            os.path.join(base_dir, 'assets', 'static', 'images', 'icon.png'),
        ]

        for path in icon_candidates:
            if os.path.exists(path):
                try:
                    logger.info(f"Loading system tray icon from {path}")
                    img = Image.open(path)
                    # Ensure it is in a mode pystray is happy with
                    return img.convert('RGBA')
                except Exception as load_err:
                    logger.warning(f"Failed to load tray icon from {path}: {load_err}")

        # Fallback: draw the original simple leaf icon
        image = Image.new('RGBA', (64, 64), color='#FF8C42')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white')  # Main leaf body
        draw.rectangle([30, 10, 34, 20], fill='#FF8C42')  # Stem
        return image

    except Exception as e:
        logger.error(f"Failed to create icon image: {e}")
        # Final fallback: simple colored square
        try:
            from PIL import Image as _Image
            return _Image.new('RGBA', (64, 64), color='#FF8C42')
        except Exception:  # noqa: broad-except
            return None

# Note: start_system_tray and stop_system_tray are now imported from tray_setup module
# These wrappers are no longer needed as the new module functions handle everything

# Shutdown function for graceful exit
def shutdown_application() -> None:
    """Gracefully shutdown the application"""
    logger.info("Shutting down Shakshuka application...")

    # Stop system tray
    stop_system_tray()

    # Clean up single instance mutex
    try:
        if os.name == 'nt':  # Windows
            import win32event
            mutex_name = "ShakshukaSingleInstanceMutex"
            try:
                mutex = win32event.OpenMutex(win32event.MUTEX_ALL_ACCESS, False, mutex_name)
                if mutex:
                    win32event.CloseHandle(mutex)
                    logger.info("Single instance mutex cleaned up")
            except Exception:  # noqa: broad-except
                logger.exception("Failed to clean up single instance mutex")
        else:  # Unix-like systems
            import tempfile
            lock_file = os.path.join(tempfile.gettempdir(), 'shakshuka.lock')
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info("Single instance lock file cleaned up")
            except Exception:  # noqa: broad-except
                logger.exception("Failed to remove single instance lock file")
    except Exception as e:
        logger.warning(f"Error cleaning up single instance resources: {e}")

    # Stop any background threads
    try:
        stop_scheduler(timeout=5)
    except Exception:  # noqa: broad-except
        logger.exception("Failed to stop scheduler during shutdown")

    logger.info("Application shutdown complete")
    sys.exit(0)
