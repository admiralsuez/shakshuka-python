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
from src.utils.validators import validate_task_data
from src.routes.task_routes import task_bp, init_task_routes
from src.routes.notes_routes import notes_bp, init_notes_routes

# Flask app configuration
app = Flask(__name__)
# Enable debug mode for better error messages (disable in production)
app.config['DEBUG'] = True
app.debug = True

# Issue #30: Set request size limit
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

# Set up user data directory and secret key immediately to avoid permission issues
# Use centralized path helper so all components agree on the same location
from src.utils.paths import get_user_data_dir

user_data_dir = get_user_data_dir()
os.makedirs(user_data_dir, exist_ok=True)
secret_key_file = os.path.join(user_data_dir, '.flask_secret')

# Issue #7: Secret key management with proper fallback
try:
    if os.path.exists(secret_key_file):
        with open(secret_key_file, 'rb') as f:
            secret_key_data = f.read()
            if len(secret_key_data) >= 32:
                app.secret_key = secret_key_data
            else:
                raise ValueError("Invalid secret key size")
    else:
        app.secret_key = os.urandom(32)
        with open(secret_key_file, 'wb') as f:
            f.write(app.secret_key)
except Exception as e:
    # Logging not yet initialized — use a temporary logger
    import logging as _logging
    _init_logger = _logging.getLogger(__name__)
    _init_logger.warning("Could not create Flask secret key file: %s. Using environment or generated key", e)
    # Try environment variable first, then generate persistent key
    env_key = os.getenv('FLASK_SECRET_KEY')
    if env_key:
        app.secret_key = env_key.encode()
    else:
        # Generate and persist even on failure
        app.secret_key = os.urandom(32)

# Use persistent secret key from environment or generate once and store
# Use user AppData directory to avoid permission issues when installed in Program Files
import tempfile

# Set up static and template folders after app creation
# Handle both development, PyInstaller executable, and installed package modes
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = os.path.dirname(sys.executable)
    root_dir = base_path
else:
    # Check if running as installed package
    import pkg_resources
    try:
        # Try to get package location
        dist = pkg_resources.get_distribution('shakshuka')
        if dist:
            # Running as installed package
            # Look for assets in package data or share directory
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Check if assets exist in package location
            package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not os.path.exists(os.path.join(package_root, 'assets')):
                # Try share directory
                share_dir = '/usr/share/shakshuka'
                if os.path.exists(share_dir):
                    root_dir = share_dir
                else:
                    # Fall back to development mode
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except (pkg_resources.DistributionNotFound, Exception):
        # Running as development script
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

static_dir = os.path.join(root_dir, 'assets', 'static')
template_dir = os.path.join(root_dir, 'assets', 'templates')

# Configure Flask app paths
app.static_folder = static_dir
app.template_folder = template_dir

# Try to set working directory to app root to avoid system32 when launched from shortcuts
try:
    os.chdir(root_dir)
    # Logger not initialized yet; defer logging until logger is set
except Exception:
    # Ignore failures; code uses absolute paths
    pass


# System tray availability - will be checked when needed
# Don't import pystray at module level to avoid GTK errors on Linux
SYSTEM_TRAY_AVAILABLE = None  # Will be determined when needed
scheduler_thread = None
scheduler_stop_event = None
def _check_system_tray_available():
    """Check if system tray is available (lazy check)"""
    global SYSTEM_TRAY_AVAILABLE
    if SYSTEM_TRAY_AVAILABLE is not None:
        return SYSTEM_TRAY_AVAILABLE
    
    try:
        import pystray
        from PIL import Image, ImageDraw
        # Just importing pystray doesn't test GTK/AppIndicator availability
        # We'll catch errors when actually creating the icon
        SYSTEM_TRAY_AVAILABLE = True
        return True
    except ImportError:
        SYSTEM_TRAY_AVAILABLE = False
        return False
    except Exception as e:
        # GTK, AppIndicator, or other dependencies not available (Linux)
        # Don't fail here - let it fail when creating icon
        SYSTEM_TRAY_AVAILABLE = True  # Allow it to try, will fail gracefully
        return True

# Setup logging
try:
    # Always use user data directory for logs to avoid permission issues
    logs_dir = os.path.join(user_data_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Create a new log file on each launch with format: date-time-log#number.txt
    # Example: 2025-11-24_21-06-18-log#1.txt
    from datetime import datetime as _dt

    timestamp = _dt.now().strftime('%Y-%m-%d_%H-%M-%S')
    existing_txt_logs = [f for f in os.listdir(logs_dir) if f.lower().endswith('.txt')]

    # Determine next sequence number for this launch
    next_index = 1
    if existing_txt_logs:
        import re as _re
        pattern = _re.compile(rf"^{timestamp}-log#(\d+)\.txt$", _re.IGNORECASE)
        for name in existing_txt_logs:
            m = pattern.match(name)
            if m:
                try:
                    idx = int(m.group(1))
                    if idx >= next_index:
                        next_index = idx + 1
                except ValueError:
                    continue

    log_filename = f"{timestamp}-log#{next_index}.txt"
    log_file = os.path.join(logs_dir, log_filename)

    # Configure logging to use the per-launch file plus console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Enforce a maximum of 10 txt log files; when we reach/exceed 10, delete the oldest 5
    try:
        txt_paths = [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.lower().endswith('.txt')]
        if len(txt_paths) >= 10:
            txt_paths.sort(key=lambda p: os.path.getmtime(p))
            for old_path in txt_paths[:5]:
                try:
                    os.remove(old_path)
                except Exception:
                    # Best-effort cleanup; ignore failures
                    pass
    except Exception:
        # Never let rotation failures break app startup
        pass

except Exception as e:
    # Fallback to console-only logging if file logging fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not set up file logging: {e}. Using console logging only.")
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

def _is_newer_version(new_version: str, current_version: str) -> bool:
    try:
        new_parts = [int(x) for x in str(new_version).split('.')]
        cur_parts = [int(x) for x in str(current_version).split('.')]
        max_len = max(len(new_parts), len(cur_parts))
        new_parts += [0] * (max_len - len(new_parts))
        cur_parts += [0] * (max_len - len(cur_parts))
        return new_parts > cur_parts
    except Exception:
        return False

# Now that logging is ready, record the working directory
try:
    logger.info(f"Working directory set to: {os.getcwd()}")
except Exception:
    pass

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
app_context = AppContext()

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

# Font file serving with correct MIME types
@app.route('/static/webfonts/<filename>')
def serve_font(filename):
    """Serve font files with correct MIME types"""
    font_dir = os.path.join(app.static_folder, 'webfonts')
    font_path = os.path.join(font_dir, filename)
    
    if not os.path.exists(font_path):
        return "Font file not found", 404
    
    # Determine MIME type based on file extension
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

# Health check endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': _get_app_version()
    })

@app.route('/api/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with system information"""
    try:
        health_info = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': _get_app_version(),
            'components': {}
        }

        # Check data manager
        try:
            if app_context.data_manager:
                health_info['components']['data_manager'] = 'healthy'
            else:
                health_info['components']['data_manager'] = 'not_initialized'
        except Exception as e:
            health_info['components']['data_manager'] = f'error: {str(e)}'

        # Check update manager
        try:
            if app_context.update_manager:
                health_info['components']['update_manager'] = 'healthy'
            else:
                health_info['components']['update_manager'] = 'not_initialized'
        except Exception as e:
            health_info['components']['update_manager'] = f'error: {str(e)}'

        # Check file system
        try:
            data_dir = "data"
            if os.path.exists(data_dir):
                health_info['components']['filesystem'] = 'healthy'
            else:
                health_info['components']['filesystem'] = 'directory_missing'
        except Exception as e:
            health_info['components']['filesystem'] = f'error: {str(e)}'

        return jsonify(health_info)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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
    """Enhanced decorator to implement rate limiting with monitoring"""
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        client_ip = request.remote_addr or 'unknown'
        
        try:
            if not security_manager.check_rate_limit(client_ip):
                monitor.record_error('rate_limit_exceeded', f'Rate limit exceeded for IP: {client_ip}')
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
            
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
                except Exception:
                    status_code = 200
            elif isinstance(result, tuple) and len(result) >= 2:
                possible_status = result[1]
                try:
                    status_code = int(getattr(possible_status, 'value', possible_status))
                except Exception:
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
            return jsonify({'error': 'Internal server error'}), 500
    
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


# Initialize and register task + notes routes blueprints after helper functions
init_task_routes(
    app_context=app_context,
    get_user_id_func=get_user_id,
    ensure_data_manager_func=ensure_data_manager,
    sanitize_input_func=sanitize_input,
    validate_task_data_func=validate_task_data,
    rate_limit_decorator=rate_limit,
)
app.register_blueprint(task_bp)

init_notes_routes(
    app_context=app_context,
    get_user_id_func=get_user_id,
    ensure_data_manager_func=ensure_data_manager,
    sanitize_input_func=sanitize_input,
)
app.register_blueprint(notes_bp)


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
            app_context.update_manager.start_auto_update_check()
            app_context.update_manager.schedule_weekly_backup()
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


def auto_save_worker():
    """Robust background thread for auto-saving with race condition prevention"""
    logger.info("Auto-save worker started")
    
    while app_context.auto_save_enabled:
        user_id = None
        try:
            # Get auto-save interval from settings
            settings = {}
            if app_context.data_manager:
                try:
                    user_id = get_user_id()
                    settings = app_context.data_manager.load_settings(user_id) or {}
                except Exception as e:
                    logger.warning(f"Failed to load settings for auto-save: {e}")
            
            interval = settings.get('autosave_interval', 30)
            
            # Wait for interval or stop event
            if app_context.wait_for_auto_save_stop(interval):
                logger.info("Auto-save worker stopped by event")
                break
            
            # Check if auto-save is still enabled
            if not app_context.auto_save_enabled:
                logger.info("Auto-save disabled, stopping worker")
                break
            
            # Issue #4: Atomic check-and-set to prevent race conditions
            with app_context._auto_save_lock:
                if app_context._save_in_progress:
                    logger.info("Save already in progress, skipping auto-save")
                    continue
                app_context._save_in_progress = True
            
            # Check if data manager is available
            if not app_context.data_manager:
                with app_context._auto_save_lock:
                    app_context._save_in_progress = False
                logger.warning("Data manager not available for auto-save")
                continue
            
            try:
                # Get current user ID
                user_id = get_user_id()
                if not user_id:
                    logger.warning("No user ID available for auto-save")
                    continue
                
                # Load current tasks
                tasks = app_context.data_manager.load_tasks_for_user(user_id)
                
                # Only save if there are changes since last save
                current_time = time.time()
                last_save_time = app_context.get_last_save_time()
                last_signature = app_context.get_last_saved_tasks_signature()

                # Build deterministic snapshot signature
                snapshot = json.dumps(tasks, sort_keys=True, separators=(",", ":"))
                signature = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

                if last_signature == signature:
                    logger.debug("No task changes detected since last auto-save; skipping save")
                    app_context.set_last_save_time(current_time)
                    continue

                # Skip save if interval hasn't elapsed (fallback guard)
                if last_save_time and current_time - last_save_time < max(5, interval * 0.25):
                    logger.debug("Auto-save interval guard prevented redundant save")
                    continue

                # Save tasks with the robust save method
                success = app_context.data_manager.save_tasks_for_user(user_id, tasks)
                
                if success:
                    app_context.set_last_save_time(current_time)
                    app_context.set_last_saved_tasks_signature(signature)
                    logger.info(f"Auto-saved {len(tasks)} tasks for user {user_id}")
                else:
                    logger.error(f"Auto-save failed for user {user_id}")
                
            except Exception as save_error:
                logger.error(f"Auto-save error for user {user_id or 'unknown'}: {save_error}")
            finally:
                # Always clear the save in progress flag
                app_context.set_save_in_progress(False)
                
        except Exception as e:
            logger.error(f"Auto-save worker error: {e}")
            # Wait a bit before retrying to prevent rapid error loops
            time.sleep(5)
    
    logger.info("Auto-save worker stopped")
    app_context.set_auto_save_running(False)

def start_auto_save():
    """Start the auto-save background thread with proper state management"""
    try:
        # Check if auto-save is already running
        if app_context.is_auto_save_running():
            logger.warning("Auto-save is already running")
            return
        
        # Clear any previous stop event
        app_context.clear_auto_save_stop_event()
        
        # Enable auto-save
        app_context.auto_save_enabled = True
        
        # Start the thread
        app_context.auto_save_thread = threading.Thread(
            target=auto_save_worker, 
            daemon=True,
            name="AutoSaveWorker"
        )
        app_context.set_auto_save_running(True)
        app_context.auto_save_thread.start()
        
        logger.info("Auto-save thread started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start auto-save: {e}")
        app_context.set_auto_save_running(False)

def stop_auto_save():
    """Stop the auto-save background thread with proper cleanup"""
    try:
        logger.info("Stopping auto-save...")
        
        # Disable auto-save
        app_context.auto_save_enabled = False
        
        # Signal the worker to stop
        app_context.stop_auto_save_event()
        
        # Wait for the thread to finish (with timeout)
        if app_context.auto_save_thread and app_context.auto_save_thread.is_alive():
            app_context.auto_save_thread.join(timeout=10)
            
            if app_context.auto_save_thread.is_alive():
                logger.warning("Auto-save thread did not stop gracefully")
            else:
                logger.info("Auto-save thread stopped successfully")
        
        # Clear the running state
        app_context.set_auto_save_running(False)
        
    except Exception as e:
        logger.error(f"Error stopping auto-save: {e}")

def scheduler_worker(stop_event: threading.Event):
    """Robust background thread for scheduled tasks with timezone awareness"""
    logger.info("Scheduler worker started")
    last_missed_check = datetime.utcnow()
    
    while not stop_event.is_set():
        try:
            # Run pending scheduled jobs
            schedule.run_pending()
            
            # Periodically check for missed resets (every 15 minutes)
            now = datetime.utcnow()
            if (now - last_missed_check).total_seconds() >= 900:  # 15 minutes
                if app_context.data_manager:
                    user_id = get_user_id()
                    settings = app_context.data_manager.load_settings(user_id) or {}
                    reset_time = settings.get('daily_reset_time', '08:00')
                    check_and_run_missed_reset(reset_time, verbose=False)  # Quiet mode for intervals
                last_missed_check = now
            
            # Issue #5: TTL cache handles CSRF cleanup automatically, no need to call manually
            
            # Sleep for 60 seconds or until stop requested
            stop_event.wait(timeout=60)
            
        except Exception as e:
            logger.error(f"Scheduler worker error: {e}")
            # Wait a bit before retrying to prevent rapid error loops
            stop_event.wait(timeout=30)
def check_and_run_missed_reset(reset_time_str, verbose=True):
    """Check if today's reset was missed and run it if needed (uses local time)."""
    try:
        # Validate and normalize reset time
        reset_time_str = _validate_and_normalize_reset_time(reset_time_str)
        reset_hour, reset_minute = map(int, reset_time_str.split(':'))
        
        # Use local time so it matches how the scheduler runs
        now = datetime.now()
        
        # Create datetime for today's reset time (local)
        today_reset_time = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)
        
        # If current time is past today's reset time and any task is still flagged struck_today, run reset
        if now > today_reset_time:
            user_id = get_user_id()
            if not user_id or not app_context.data_manager:
                return
            
            tasks = app_context.data_manager.load_tasks_for_user(user_id)
            if not tasks:
                return
            
            needs_reset = any(task.get('struck_today') for task in tasks)
            if needs_reset:
                logger.info(f"⏰ Missed reset detected! Current time {now.strftime('%H:%M')} is past reset time {reset_time_str}. Running reset now...")
                reset_daily_strikes_job()
            elif verbose:
                logger.debug("👍 No tasks flagged for today; reset not needed")
        elif verbose:
            logger.info(f"⏳ Reset time {reset_time_str} is still upcoming today (current: {now.strftime('%H:%M')})")
            
    except Exception as e:
        logger.error(f"Error checking for missed reset: {e}")

def setup_daily_reset():
    """Setup daily reset schedule with timezone awareness"""
    try:
        if not app_context.data_manager:
            logger.warning("Data manager not available for daily reset setup")
            return
        
        # Get user ID for proper settings loading
        user_id = get_user_id()
        settings = app_context.data_manager.load_settings(user_id) or {}
        reset_time = settings.get('daily_reset_time', '08:00')
        
        # Validate and normalize reset time
        reset_time = _validate_and_normalize_reset_time(reset_time)
        
        # Check if we've already passed today's reset time
        check_and_run_missed_reset(reset_time)
        
        # Clear any existing daily reset jobs
        schedule.clear('daily_reset')
        
        # Schedule the daily reset with proper timezone handling
        schedule.every().day.at(reset_time).do(reset_daily_strikes_job).tag('daily_reset')
        
        logger.info(f"✅ Daily reset scheduled for {reset_time} (user: {user_id})")
        
    except Exception as e:
        logger.error(f"Error setting up daily reset: {e}")

def reset_daily_strikes_job():
    """Job to reset daily strikes and clean all scheduled tasks (local time).
    
    Behavior:
    - Tasks struck TODAY: Clear strike flag AND all scheduling -> move to available tasks
    - Tasks struck FOREVER (completed): Don't show in available tasks
    - All other scheduled tasks: Clear scheduling to return to available pool
    """
    try:
        logger.info("Starting daily strikes reset job")
        
        if not app_context.data_manager:
            logger.error("Data manager not available for daily reset")
            return
        
        # Use local time to align with user expectation and scheduler
        now = datetime.now()
        today_str_local = now.strftime('%Y-%m-%d')
        
        # Get user
        user_id = get_user_id()
        if not user_id:
            logger.warning("No user ID available for daily reset")
            return
        
        # Load tasks for the user
        tasks = app_context.data_manager.load_tasks_for_user(user_id)
        if not tasks:
            logger.info("No tasks found for daily reset")
            return
        
        # 1) Clear today's strike flags and ALL scheduling for struck-today tasks
        reset_count = 0
        for task in tasks:
            if task.get('struck_today'):
                # Check if task was struck forever
                is_struck_forever = task.get('struck_forever', False)
                
                # Clear the today's strike flag
                task['struck_today'] = False
                task['struck_date'] = None
                task['strike_report'] = None
                reset_count += 1
                
                # ALWAYS clear scheduling during reset - all tasks should return to pool
                # (struck_forever tasks won't appear anyway, but clearing keeps data consistent)
                task['scheduled_hour'] = None
                task['scheduled_minute'] = None
                task['scheduled_date'] = None
                task['scheduled_duration'] = None
                logger.debug(f"Task '{task.get('title', 'Unknown')}' unscheduled after today's strike reset")
        
        # 2) Clear ALL remaining scheduled tasks (from any day, not just previous days)
        # This ensures the planner is clean at the start of each day
        unscheduled = 0
        for t in tasks:
            # Unschedule all scheduled tasks except those struck forever (those are hidden anyway)
            is_struck_forever = t.get('struck_forever', False)
            has_schedule = t.get('scheduled_date') is not None
            
            if has_schedule and not is_struck_forever:
                t['scheduled_hour'] = None
                t['scheduled_minute'] = None
                t['scheduled_date'] = None
                t['scheduled_duration'] = None
                unscheduled += 1
                logger.debug(f"Task '{t.get('title', 'Unknown')}' unscheduled during daily reset")
        
        if reset_count > 0 or unscheduled > 0:
            success = app_context.data_manager.save_tasks_for_user(user_id, tasks)
            if success:
                logger.info(f"Daily reset done: {reset_count} strikes cleared, {unscheduled} tasks unscheduled")
            else:
                logger.error("Failed to save tasks after daily reset")
        else:
            logger.info("Daily reset: no changes needed")
            
    except Exception as e:
        logger.error(f"Error in daily reset job: {e}")
        import traceback
        logger.error(f"Daily reset traceback: {traceback.format_exc()}")

def start_scheduler():
    """Start the scheduler background thread with proper error handling"""
    global scheduler_thread, scheduler_stop_event
    try:
        # Setup daily reset schedule
        setup_daily_reset()
        
        # Start scheduler thread
        if scheduler_thread and scheduler_thread.is_alive():
            logger.warning("Scheduler thread already running")
        else:
            scheduler_stop_event = threading.Event()
            scheduler_thread = threading.Thread(
                target=scheduler_worker,
                args=(scheduler_stop_event,),
                daemon=True,
                name="SchedulerWorker",
            )
            scheduler_thread.start()
        
        logger.info("Scheduler thread started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


def stop_scheduler(timeout: float = 10.0):
    """Stop the scheduler background thread gracefully if it is running."""
    global scheduler_thread, scheduler_stop_event
    try:
        if not scheduler_thread or not scheduler_thread.is_alive():
            logger.info("Scheduler thread is not running; nothing to stop")
            return

        if scheduler_stop_event is None:
            logger.warning("Scheduler stop event is not initialized; cannot signal stop cleanly")
            return

        logger.info("Stopping scheduler thread...")
        scheduler_stop_event.set()
        scheduler_thread.join(timeout=timeout)

        if scheduler_thread.is_alive():
            logger.warning("Scheduler thread did not stop within timeout")
        else:
            logger.info("Scheduler thread stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

# Removed: get_timezone_aware_time() - unused function.
# App uses local time (datetime.now()) exclusively for consistency.

def _validate_and_normalize_reset_time(reset_time_str):
    """Validate and normalize reset time format - used centrally for all reset time operations"""
    try:
        # Parse the time string
        hour, minute = map(int, reset_time_str.split(':'))
        
        # Validate hour and minute ranges
        if not (0 <= hour <= 23):
            logger.warning(f"Invalid hour in reset time: {hour}, using default")
            return "08:00"
        
        if not (0 <= minute <= 59):
            logger.warning(f"Invalid minute in reset time: {minute}, using default")
            return "08:00"
        
        return f"{hour:02d}:{minute:02d}"
        
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid reset time format '{reset_time_str}': {e}, using default")
        return "08:00"

# Deprecated: kept for backward compatibility (all calls should use _validate_and_normalize_reset_time)
def validate_reset_time(reset_time_str):
    return _validate_and_normalize_reset_time(reset_time_str)

@app.route('/')
def index():
    """Serve the main application page - authentication disabled"""
    # Authentication disabled - serve dashboard directly

    # Load version information (works both in dev and when frozen)
    try:
        version = _get_app_version()
    except Exception as e:
        logger.warning(f"Failed to read version.json via _get_app_version, falling back to 1.0.0: {e}")
        version = '1.0.0'

    return render_template(
        'index.html',
        version=version,
        config=config
    )

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon"""
    try:
        # Handle both development and PyInstaller executable modes
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
            root_dir = base_path
        else:
            # Running as Python script
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        favicon_path = os.path.join(root_dir, 'assets', 'static', 'images', 'icon.ico')
        logger.info(f"Looking for favicon at: {favicon_path}")
        
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.dirname(favicon_path), 'icon.ico', mimetype='image/x-icon')
        else:
            logger.warning(f"Favicon not found at: {favicon_path}")
            return '', 404
    except Exception as e:
        logger.error(f"Error serving favicon: {e}")
        return '', 404

@app.route('/api/changelog')
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

@app.route('/api/analytics')
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
            'today_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'today_strikes': 0,
            'total_strikes': 0,
        }), 200


@app.route('/api/check-updates')
def check_updates():
    """Check for available updates"""
    try:
        # Get current version
        current_version = _get_app_version()
        
        # For now, return current version info
        # In a real implementation, this would check a remote server
        return jsonify({
            'current_version': current_version,
            'latest_version': current_version,
            'update_available': False,
            'download_url': None,
            'release_notes': 'No updates available'
        })
    except Exception as e:
        logger.error(f"Error checking updates: {e}")
        return jsonify({
            'error': 'Failed to check for updates',
            'current_version': 'unknown',
            'latest_version': 'unknown',
            'update_available': False
        }), 500

@app.route('/api/updates/check', methods=['POST'])
def check_updates_legacy():
    """Check for available updates (legacy endpoint)"""
    try:
        # Get current version
        current_version = _get_app_version()
        
        # For now, return current version info
        # In a real implementation, this would check a remote server
        return jsonify({
            'update_available': False,
            'current_version': current_version,
            'latest_version': current_version,
            'update_info': {
                'version': current_version,
                'release_notes': 'No updates available',
                'download_url': None,
                'file_size': 0
            }
        })
    except Exception as e:
        logger.error(f"Error checking updates: {e}")
        return jsonify({
            'error': 'Failed to check for updates',
            'update_available': False,
            'current_version': 'unknown',
            'latest_version': 'unknown'
        }), 500

@app.route('/api/github/check-update', methods=['POST'])
def check_github_update():
    """Check for updates from GitHub releases"""
    try:
        import requests
        import json
        
        # Get request data
        data = request.get_json() or {}
        branch = data.get('branch', 'main')
        
        # GitHub repository info
        repo_owner = GITHUB_REPO_OWNER
        repo_name = GITHUB_REPO_NAME
        
        # Get latest release from GitHub API
        if branch == 'main':
            # For main branch, get the latest stable release
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        else:
            # For other branches, get the latest release with prerelease tag
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            params = {'per_page': 1}
            if branch == 'testing':
                params['prerelease'] = True
            elif branch == 'development':
                params['prerelease'] = True
        
        response = requests.get(url, params=params if branch != 'main' else None, timeout=10)
        response.raise_for_status()
        
        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({
                    'update_available': False,
                    'message': 'No releases found for this branch'
                })
            release_data = releases[0]
        
        # Get current version
        current_version = _get_app_version()
        
        # Compare versions (semver aware)
        latest_version = str(release_data['tag_name']).lstrip('v')
        update_available = _is_newer_version(latest_version, current_version)
        
        # Try to pick a Windows installer asset for GitHub modal convenience
        asset_url = None
        asset_size = 0
        for asset in release_data.get('assets', []):
            name = asset.get('name', '').lower()
            if name.endswith('.exe') and ('setup' in name or 'installer' in name):
                asset_url = asset.get('browser_download_url')
                asset_size = int(asset.get('size', 0))
                break
        if not asset_url:
            # fallback to any asset
            assets = release_data.get('assets', [])
            if assets:
                asset_url = assets[0].get('browser_download_url')
                asset_size = int(assets[0].get('size', 0))
        
        return jsonify({
            'update_available': update_available,
            'current_version': current_version,
            'latest_version': latest_version,
            'release_info': {
                'tag_name': release_data.get('tag_name'),
                'name': release_data.get('name'),
                'body': release_data.get('body'),
                'published_at': release_data.get('published_at'),
                'download_url': asset_url,
                'file_size': asset_size
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API error: {e}")
        return jsonify({
            'error': 'Failed to connect to GitHub',
            'update_available': False
        }), 500
    except Exception as e:
        logger.error(f"Error checking GitHub update: {e}")
        return jsonify({
            'error': 'Failed to check for updates',
            'update_available': False
        }), 500

@app.route('/api/github/download-update', methods=['POST'])
def download_github_update():
    """Download and prepare update from GitHub.

    Note: For security reasons this endpoint only downloads the installer to a
    temporary directory and returns its path/size. Actual execution of the
    installer must be handled by the user or a trusted local component.
    """
    try:
        import requests
        import json
        import tempfile
        import shutil
        
        # Get request data
        data = request.get_json() or {}
        branch = data.get('branch', 'main')
        
        # GitHub repository info
        repo_owner = GITHUB_REPO_OWNER
        repo_name = GITHUB_REPO_NAME
        
        # Get latest release
        if branch == 'main':
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        else:
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            params = {'per_page': 1}
            if branch in ('testing', 'development'):
                params['prerelease'] = True

        response = requests.get(url, params=params if branch != 'main' else None, timeout=10)
        response.raise_for_status()
        
        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({'error': 'No releases found for this branch'}), 404
            release_data = releases[0]
        
        # Find the Windows installer asset
        installer_url = None
        installer_size = 0
        installer_name = None
        for asset in release_data.get('assets', []):
            name = asset.get('name', '')
            if name.lower().endswith('.exe') and 'setup' in name.lower():
                installer_url = asset.get('browser_download_url')
                installer_size = int(asset.get('size', 0) or 0)
                installer_name = name
                break
        
        if not installer_url:
            return jsonify({'error': 'No Windows installer found in release'}), 404
        
        # Choose a Downloads folder as the destination when possible
        try:
            home_dir = os.path.expanduser('~')
            downloads_dir = os.path.join(home_dir, 'Downloads')
            if not os.path.isdir(downloads_dir):
                downloads_dir = tempfile.gettempdir()
        except Exception:
            downloads_dir = tempfile.gettempdir()
        os.makedirs(downloads_dir, exist_ok=True)
        
        if not installer_name:
            # Fallback file name if the asset name isn't available
            tag = str(release_data.get('tag_name') or 'latest').lstrip('v')
            installer_name = f'Shakshuka-Setup-{tag}.exe'
        
        installer_path = os.path.join(downloads_dir, installer_name)
        
        # Download the installer
        logger.info(f"Downloading update from: {installer_url} to {installer_path}")
        download_response = requests.get(installer_url, stream=True, timeout=30)
        download_response.raise_for_status()
        
        # Save to chosen path
        with open(installer_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
        
        logger.info(f"Downloaded installer to: {installer_path}")
        
        return jsonify({
            'success': True,
            'message': 'Update downloaded successfully',
            'installer_size': installer_size,
            'installer_path': installer_path,
            'release_info': {
                'tag_name': release_data.get('tag_name'),
                'name': release_data.get('name'),
                'body': release_data.get('body'),
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub download error: {e}")
        return jsonify({'error': 'Failed to download update from GitHub'}), 500
    except Exception as e:
        logger.error(f"Error downloading GitHub update: {e}")
        return jsonify({'error': 'Failed to download update'}), 500

# Basic account endpoint to prevent 404s from frontend probes
@app.route('/api/account', methods=['GET'])
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

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - authentication disabled, redirect to dashboard"""
    # Authentication disabled - redirect to dashboard
    return redirect(url_for('index'))








# ============================================
# PIN Authentication Endpoints
# ============================================

@app.route('/api/pin/status', methods=['GET'])
def get_pin_status():
    """Check if PIN is setup and get cooldown status"""
    try:
        if not app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500
        
        is_setup = app_context.pin_manager.is_setup_complete()
        in_cooldown, seconds_remaining = app_context.pin_manager.is_in_cooldown()
        
        response = {
            'setup_complete': is_setup,
            'in_cooldown': in_cooldown,
            'seconds_remaining': seconds_remaining,
            'session_valid': app_context.pin_manager.is_session_valid() if is_setup else False
        }
        
        if is_setup:
            response['last_login'] = app_context.pin_manager.get_last_login()
            response['failed_attempts'] = app_context.pin_manager.get_failed_attempts()
            response['remembered'] = app_context.pin_manager.is_remembered()
            response['session_expires'] = app_context.pin_manager.get_session_expiry()
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error checking PIN status: {e}")
        return jsonify({'error': 'Failed to check PIN status'}), 500

@app.route('/api/pin/setup', methods=['POST'])
def setup_pin():
    """Setup new PIN"""
    try:
        if not app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        pin = data.get('pin', '')
        confirm_pin = data.get('confirm_pin', '')
        recovery_questions = data.get('recovery_questions', [])
        
        success, message = app_context.pin_manager.setup_pin(pin, confirm_pin, recovery_questions)
        
        if success:
            # Create session token
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token
            })
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        logger.error(f"Error setting up PIN: {e}")
        return jsonify({'error': 'Failed to setup PIN'}), 500

@app.route('/api/pin/verify', methods=['POST'])
def verify_pin():
    """Verify PIN and login"""
    try:
        if not app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        pin = data.get('pin', '')
        remember = data.get('remember', False)
        
        success, message, attempts_remaining = app_context.pin_manager.verify_pin(pin, remember)
        
        if success:
            # Create session token
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token,
                'remembered': remember
            })
        else:
            return jsonify({
                'error': message,
                'attempts_remaining': attempts_remaining
            }), 401
    except Exception as e:
        logger.error(f"Error verifying PIN: {e}")
        return jsonify({'error': 'Failed to verify PIN'}), 500

@app.route('/api/pin/reset', methods=['POST'])
def reset_pin():
    """Reset PIN (forgot PIN recovery)"""
    try:
        if not app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        new_pin = data.get('new_pin', '')
        confirm_pin = data.get('confirm_pin', '')
        
        success, message = app_context.pin_manager.reset_pin(new_pin, confirm_pin)
        
        if success:
            # Create session token
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token
            })
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        logger.error(f"Error resetting PIN: {e}")
        return jsonify({'error': 'Failed to reset PIN'}), 500

@app.route('/api/pin/logout', methods=['POST'])
def logout():
    """Logout and clear session"""
    try:
        # Clear remember session in PIN manager
        if app_context.pin_manager:
            app_context.pin_manager.logout()
        
        # Clear Flask session
        session.clear()
        
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({'error': 'Logout failed'}), 500

# ============================================
# Task Management Endpoints
# ============================================
# NOTE: Task endpoints are now provided by the tasks blueprint in
# src.routes.task_routes and registered above. The legacy inline
# route implementations have been removed from this module.

@app.route('/api/settings/autostart', methods=['GET'])
def get_autostart_status():
    try:
        enabled = app_context.autostart_manager.is_autostart_enabled() if app_context.autostart_manager else False
        cmd = app_context.autostart_manager.get_autostart_command() if app_context.autostart_manager else None
        return jsonify({ 'enabled': bool(enabled), 'command': cmd })
    except Exception:
        return jsonify({ 'enabled': False }), 200

@app.route('/api/settings', methods=['GET'])
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
                        'language': 'en'
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
                'language': 'en'
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
            'autostart_enabled': bool(settings.get('autostart_enabled', False)),
            'quick_project_from_title': bool(settings.get('quick_project_from_title', False)),
            'casual_dates': bool(settings.get('casual_dates', False)),
        }
        
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
            'autostart_enabled': False
        })

@app.route('/api/settings', methods=['PUT'])
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
            valid_themes = ['orange', 'blue', 'green', 'purple', 'dark', 'light', 'self-esteem', 'anxiety', 'auto']
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
            # If daily reset time was changed, reschedule the reset job
            if daily_reset_time_changed:
                try:
                    setup_daily_reset()
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

# Monitoring endpoints
@app.route('/api/monitoring/health', methods=['GET'])
def get_health_status():
    """Get system health status"""
    try:
        health_status = monitor.get_health_status()
        return jsonify(health_status)
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return jsonify({'error': 'Failed to get health status'}), 500

@app.route('/api/monitoring/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics"""
    try:
        metrics = monitor.get_metrics_summary()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': 'Failed to get metrics'}), 500

@app.route('/api/monitoring/export', methods=['POST'])
def export_metrics():
    """Export metrics to file in the user data directory"""
    try:
        user_id = get_user_id()
        # Keep exports alongside other user data to avoid permission issues
        export_dir = os.path.join(get_user_data_dir(), 'metrics')
        os.makedirs(export_dir, exist_ok=True)
        export_path = os.path.join(export_dir, f"metrics_export_{user_id}_{int(time.time())}.json")
        
        if monitor.export_metrics(export_path):
            return jsonify({'success': True, 'file_path': export_path})
        else:
            return jsonify({'error': 'Failed to export metrics'}), 500
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        return jsonify({'error': 'Failed to export metrics'}), 500

@app.route('/api/monitoring/rate-limit-stats', methods=['GET'])
def get_rate_limit_stats():
    """Get rate limiting statistics"""
    try:
        stats = security_manager.get_rate_limit_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        return jsonify({'error': 'Failed to get rate limit stats'}), 500

# Password change endpoint removed - no password authentication

# Daily Planner Version 2 Endpoints
@app.route('/api/planner-v2/schedule', methods=['GET'])
def get_planner_v2_schedule():
    """Get scheduled tasks for Daily Planner v2"""
    logger.info("GET /api/planner-v2/schedule called")
    user_id = get_user_id()
    try:
        # Load all tasks and filter for scheduled ones
        tasks = app_context.data_manager.load_tasks(user_id)
        scheduled_tasks = {}
        
        for task in tasks:
            logger.info(f"Checking task: {task.get('title', 'Unknown')} - scheduled_hour: {task.get('scheduled_hour')}, scheduled_date: {task.get('scheduled_date')}")
            if task.get('scheduled_hour') is not None and task.get('scheduled_date'):
                scheduled_date = task['scheduled_date']
                scheduled_hour = task['scheduled_hour']
                
                logger.info(f"Found scheduled task: {task.get('title', 'Unknown')} at {scheduled_hour}:{task.get('scheduled_minute', 0)} on {scheduled_date}")
                
                if scheduled_date not in scheduled_tasks:
                    scheduled_tasks[scheduled_date] = {}
                
                if scheduled_hour not in scheduled_tasks[scheduled_date]:
                    scheduled_tasks[scheduled_date][scheduled_hour] = []
                
                scheduled_tasks[scheduled_date][scheduled_hour].append(task)
        
        logger.info(f"Found {len(scheduled_tasks)} scheduled dates")
        return jsonify({
            'success': True,
            'scheduled_tasks': scheduled_tasks
        })
    except Exception as e:
        logger.error(f"Error loading planner v2 schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/planner-v2/schedule', methods=['POST'])
def save_planner_v2_schedule():
    """Save scheduled tasks for Daily Planner v2"""
    user_id = get_user_id()
    try:
        data = request.json
        scheduled_tasks = data.get('scheduled_tasks', {})
        
        # Save scheduled tasks to database
        success = app_context.data_manager.save_planner_v2_schedule(user_id, scheduled_tasks)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save schedule'}), 500
            
    except Exception as e:
        logger.error(f"Error saving planner v2 schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/planner-v2/tasks', methods=['GET'])
def get_planner_v2_available_tasks():
    """Get available tasks for Daily Planner v2"""
    logger.info("GET /api/planner-v2/tasks called")
    user_id = get_user_id()
    try:
        tasks = app_context.data_manager.load_tasks(user_id)
        
        # Filter available tasks (not completed, not struck today, not scheduled)
        available_tasks = []
        for task in tasks:
            # Task is available if:
            # 1. Not completed
            # 2. Not struck today
            # 3. Not scheduled (no scheduled_hour or no scheduled_date)
            is_completed = task.get('completed', False)
            is_struck_today = task.get('struck_today', False)
            is_scheduled = task.get('scheduled_hour') is not None and task.get('scheduled_date') is not None
            
            if not is_completed and not is_struck_today and not is_scheduled:
                available_tasks.append({
                    'id': task.get('id'),
                    'title': task.get('title', ''),
                    'description': task.get('description', ''),
                    'priority': task.get('priority', 'medium'),
                    'due_date': task.get('due_date'),
                    'created_at': task.get('created_at'),
                    'estimated_duration': task.get('estimated_duration', 30)
                })
        
        logger.info(f"Returning {len(available_tasks)} available tasks (filtered out scheduled tasks)")
        return jsonify({
            'success': True,
            'available_tasks': available_tasks
        })
        
    except Exception as e:
        logger.error(f"Error loading planner v2 available tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/planner-v2/cleanup-overdue', methods=['POST'])
def cleanup_overdue_scheduled_tasks():
    """Unschedule any tasks scheduled for previous days if not completed."""
    user_id = get_user_id()
    try:
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        
        tasks = app_context.data_manager.load_tasks(user_id)
        unscheduled = 0
        for t in tasks:
            scheduled_date = t.get('scheduled_date')
            if scheduled_date and scheduled_date < today_str:
                # Remove scheduling to move back to available
                t['scheduled_hour'] = None
                t['scheduled_minute'] = None
                t['scheduled_date'] = None
                t['scheduled_duration'] = None
                unscheduled += 1
        
        # Save only if changes were made
        if unscheduled > 0:
            if not app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify({'success': False, 'error': 'Failed to save tasks after cleanup'}), 500
        
        return jsonify({'success': True, 'unscheduled': unscheduled})
    except Exception as e:
        logger.error(f"Error cleaning up overdue scheduled tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Update Management Endpoints
@app.route('/api/updates/status', methods=['GET'])
def get_update_status():
    """Get current update status"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(app_context.update_manager.get_update_status())

@app.route('/api/updates/check', methods=['POST'])
def check_for_updates():
    """Check for available updates"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=get_user_data_dir())

        update_info = app_context.update_manager.check_for_updates()
        if update_info:
            return jsonify({'update_available': True, 'update_info': update_info})
        else:
            return jsonify({'update_available': False})
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return jsonify({'error': 'Failed to check for updates'}), 500

@app.route('/api/updates/download', methods=['POST'])
def download_update():
    """Start downloading the available update in background"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=get_user_data_dir())
        
        update_info = request.json or {}
        if not update_info:
            return jsonify({'error': 'Update info required'}), 400
        
        # Kick off background download
        app_context.update_manager.start_download(update_info)
        return jsonify({'started': True}), 202
    except Exception as e:
        logger.error(f"Error starting update download: {e}")
        return jsonify({'error': 'Failed to start download'}), 500

@app.route('/api/updates/install', methods=['POST'])
def install_update():
    """Install downloaded update"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_data = request.json or {}
    update_file = update_data.get('update_file')
    backup_data = update_data.get('backup_before_update', True)
    
    # If not provided, try to use the last downloaded file
    if not update_file:
        status = app_context.update_manager.get_download_status()
        update_file = status.get('update_file')
        if not update_file:
            return jsonify({'error': 'Update file required'}), 400
    
    # Resolve to absolute path inside updates directory when relative
    if not os.path.isabs(update_file):
        update_file = str(app_context.update_manager.update_dir / update_file)
    
    success = app_context.update_manager.install_update(update_file, backup_data)
    if success:
        return jsonify({'success': True, 'message': 'Update installed successfully. Please restart the application.'})
    else:
        return jsonify({'error': 'Failed to install update'}), 500

@app.route('/api/updates/progress', methods=['GET'])
def get_download_progress():
    """Get current download/install progress."""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    return jsonify(app_context.update_manager.get_download_status())

@app.route('/api/updates/cancel', methods=['POST'])
def cancel_update_download():
    """Cancel current update download if in progress."""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    app_context.update_manager.cancel_download()
    return jsonify({'success': True, 'status': app_context.update_manager.get_download_status()})
@app.route('/api/updates/config', methods=['GET'])
def get_update_config():
    """Get update configuration"""
    if not app_context.update_manager:
        try:
            # Initialize with app root and user data dir
            app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=get_user_data_dir())
        except Exception as e:
            logger.error(f"Failed to initialize update manager for config: {e}")
            return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(app_context.update_manager.update_config)

@app.route('/api/updates/config', methods=['PUT'])
def update_update_config():
    """Update update configuration"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    config_data = request.json
    if not config_data:
        return jsonify({'error': 'Configuration data required'}), 400
    
    # Update configuration
    app_context.update_manager.update_config.update(config_data)
    app_context.update_manager._save_update_config(app_context.update_manager.update_config)
    
    return jsonify({'success': True, 'message': 'Configuration updated successfully'})

# Kill App Endpoint - REMOVED FOR SECURITY
# This endpoint was a critical security vulnerability
# Use proper process management instead

# Backup Management Endpoints
@app.route('/api/backups', methods=['GET'])
def get_backups():
    """Get list of available backups"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=get_user_data_dir())

        backups = app_context.update_manager.get_backup_list()
        return jsonify({'backups': backups})
    except Exception as e:
        print(f"Error getting backups: {e}")
        return jsonify({'error': 'Failed to get backups'}), 500

def validate_backup_integrity(backup_path):
    """Validate backup file integrity and detect corruption"""
    try:
        if not os.path.exists(backup_path):
            return False, "Backup file does not exist"
        
        # Check file size
        file_size = os.path.getsize(backup_path)
        if file_size == 0:
            return False, "Backup file is empty"
        
        if file_size > 100 * 1024 * 1024:  # 100MB limit
            return False, "Backup file too large (>100MB)"
        
        # Check file permissions
        if not os.access(backup_path, os.R_OK):
            return False, "Backup file not readable"
        
        # Try to read and parse the backup file
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Basic JSON validation if it's a JSON backup
            if backup_path.endswith('.json'):
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON in backup: {e}"
            
            # Check for suspicious content
            if len(content) < 10:
                return False, "Backup content too short"
            
            # Check for common corruption patterns
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
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_root = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            app_context.update_manager = UpdateManager(app_dir=app_root, data_dir=get_user_data_dir())
    
        backup_data = request.json or {}
        backup_type = backup_data.get('type', 'manual')
        
        # Create backup
        success = app_context.update_manager.create_backup(backup_type)
        if not success:
            return jsonify({'error': 'Failed to create backup'}), 500
        
        # Get the latest backup file for validation
        backup_dir = os.path.join(os.getcwd(), "backups")
        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith(('.json', '.zip', '.tar.gz'))]
            if backup_files:
                latest_backup = max(backup_files, key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)))
                backup_path = os.path.join(backup_dir, latest_backup)
                
                # Validate backup integrity
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
        if not app_context.update_manager:
            return jsonify({'error': 'Update manager not initialized'}), 500
        
        backup_data = request.json
        backup_name = backup_data.get('backup_name')
        
        if not backup_name:
            return jsonify({'error': 'Backup name is required'}), 400
        
        # Validate backup file before restoration
        backup_dir = os.path.join(os.getcwd(), "backups")
        backup_path = os.path.join(backup_dir, backup_name)
        
        is_valid, message = validate_backup_integrity(backup_path)
        if not is_valid:
            logger.error(f"Backup validation failed before restore: {message}")
            return jsonify({'error': f'Backup validation failed: {message}'}), 400
        
        # Create a safety backup before restoration
        try:
            safety_backup_name = f"safety_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            safety_success = app_context.update_manager.create_backup(safety_backup_name)
            if not safety_success:
                logger.warning("Failed to create safety backup before restore")
        except Exception as e:
            logger.warning(f"Failed to create safety backup: {e}")
        
        # Restore backup
        success = app_context.update_manager.restore_backup(backup_name)
        if success:
            logger.info(f"Backup restored successfully: {backup_name}")
            return jsonify({'success': True, 'message': 'Backup restored successfully'})
        else:
            logger.error(f"Failed to restore backup: {backup_name}")
            return jsonify({'error': 'Failed to restore backup'}), 500
            
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({'error': 'Failed to restore backup'}), 500

@app.route('/api/backups/create', methods=['POST'])
def create_backup():
    """Create manual backup with validation"""
    return create_backup_with_validation()

@app.route('/api/backups/restore', methods=['POST'])
def restore_backup():
    """Restore from backup with validation"""
    return restore_backup_with_validation()

@app.route('/api/shutdown', methods=['POST'])
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
        
        # Check for existing instance and kill it if found
        import psutil
        import time
        
        def kill_existing_instances():
            """Kill any existing Shakshuka instances with enhanced detection"""
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
                        elif proc.info['exe'] and 'shakshuka' in proc.info['exe'].lower():
                            print(f"Found existing Shakshuka instance by path (PID: {proc.info['pid']}), terminating...")
                            proc.terminate()
                            killed_count += 1
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
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
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                    
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
                            except:
                                pass
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
                        except:
                            pass
                        time.sleep(1)
                
                print("Failed to acquire lock after 3 attempts. Another instance may be running.")
                return False
        
        # Check single instance with file lock
        if not check_single_instance():
            sys.exit(1)
        
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
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open('http://127.0.0.1:8989')
        
        # Start browser in a separate thread
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Run the Flask app
        print("Starting Shakshuka...")
        print("Opening browser at http://127.0.0.1:8989")
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
            except:
                pass
        
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
            print("Server starting on http://127.0.0.1:8989")
            run_simple('127.0.0.1', 8989, app, use_reloader=False, use_debugger=False)
        except Exception as e:
            print(f"Error starting server: {e}")
            # Fallback to standard Flask run
            app.run(host='127.0.0.1', port=8989, debug=False, use_reloader=False)
            
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
    if not _check_system_tray_available():
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
            webbrowser.open('http://127.0.0.1:8989')

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
                requests.post('http://127.0.0.1:8989/api/shutdown', timeout=1)
            except:
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
        except Exception:
            return None

def start_system_tray() -> None:
    """Start the system tray icon"""
    global system_tray_icon

    # Check availability lazily
    if not _check_system_tray_available():
        logger.warning("System tray not available")
        return

    try:
        system_tray_icon = create_system_tray_icon()
        if system_tray_icon:
            # Run in a separate thread to avoid blocking the main Flask thread
            import threading
            tray_thread = threading.Thread(target=system_tray_icon.run, daemon=True)
            tray_thread.start()
            logger.info("System tray icon started successfully")
            print("System tray icon created and started")
        else:
            logger.warning("Failed to create system tray icon")
            print("Failed to create system tray icon")
    except Exception as e:
        # System tray is optional - don't fail the app
        error_msg = str(e)
        if 'Gtk' in error_msg or 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
            logger.warning(f"System tray not available (GTK/AppIndicator not installed): {e}")
            logger.info("App will continue without system tray icon")
            print(f"Warning: System tray not available. App will work without tray icon.")
        elif 'g-io-error' in error_msg.lower() or 'Could not connect' in error_msg or 'D-Bus' in error_msg or 'dbus' in error_msg.lower():
            logger.warning(f"System tray not available (D-Bus connection error): {e}")
            logger.info("App will continue without system tray icon")
            print(f"Warning: System tray not available (D-Bus error). App will work without tray icon.")
        else:
            logger.warning(f"Error starting system tray: {e}")
            print(f"Warning: System tray not available: {e}")

def stop_system_tray() -> None:
    """Stop the system tray icon"""
    global system_tray_icon

    if system_tray_icon and SYSTEM_TRAY_AVAILABLE:
        try:
            system_tray_icon.stop()
            logger.info("System tray icon stopped")
        except Exception as e:
            logger.error(f"Error stopping system tray: {e}")

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
            except:
                pass
        else:  # Unix-like systems
            import tempfile
            lock_file = os.path.join(tempfile.gettempdir(), 'shakshuka.lock')
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info("Single instance lock file cleaned up")
            except:
                pass
    except Exception as e:
        logger.warning(f"Error cleaning up single instance resources: {e}")

    # Stop any background threads
    try:
        if 'scheduler_thread' in globals():
            scheduler_thread.join(timeout=5)
    except:
        pass

    logger.info("Application shutdown complete")
    sys.exit(0)
