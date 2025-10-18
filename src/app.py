from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, session
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
from werkzeug.utils import secure_filename
import sys
import os

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application modules
from src.data_manager import SimpleDataManager
from tools.autostart import WindowsAutostart
from src.update_manager import UpdateManager
from src.security_manager import security_manager
from src.user_manager import user_manager

# Flask app configuration
app = Flask(__name__)
# Use persistent secret key from environment or generate once and store
# Use application directory instead of current working directory to avoid permission issues
app_dir = os.path.dirname(os.path.abspath(__file__))
secret_key_file = os.path.join(app_dir, '.flask_secret')
if os.path.exists(secret_key_file):
    with open(secret_key_file, 'rb') as f:
        app.secret_key = f.read()
else:
    app.secret_key = os.urandom(32)  # Use 32 bytes for better security
    with open(secret_key_file, 'wb') as f:
        f.write(app.secret_key)

# Set up static and template folders after app creation
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(root_dir, 'assets', 'static')
template_dir = os.path.join(root_dir, 'assets', 'templates')

# Configure Flask app paths
app.static_folder = static_dir
app.template_folder = template_dir


# Try to import system tray functionality
try:
    import pystray
    from PIL import Image, ImageDraw
    SYSTEM_TRAY_AVAILABLE = True
except ImportError:
    SYSTEM_TRAY_AVAILABLE = False
    print("Warning: pystray or PIL not available. System tray functionality disabled.")

# Setup logging
try:
    # Determine the correct path for logs based on execution mode
    if getattr(sys, 'frozen', False):
        # Running as bundled executable - use current working directory
        logs_dir = os.path.join(os.getcwd(), 'logs')
    else:
        # Running as development script - use project root
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    
    # Try to create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, 'shakshuka.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
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

# Try to import bcrypt for proper password hashing
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    logger.warning("bcrypt not available. Password hashing will be less secure.")

# Application context class to replace global variables
class AppContext:
    """Centralized application context to replace global variables"""

    def __init__(self):
        self._data_manager = None
        self._autostart_manager = WindowsAutostart()
        self._password_set = False
        self._update_manager = None
        self._auto_save_enabled = True
        self._auto_save_thread = None
        self._session_secrets = {}
        self._csrf_tokens = {}  # Store CSRF tokens with expiration

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
    def password_set(self):
        return self._password_set

    @password_set.setter
    def password_set(self, value):
        self._password_set = value

    @property
    def update_manager(self):
        return self._update_manager

    @update_manager.setter
    def update_manager(self, value):
        self._update_manager = value

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
        """Generate CSRF token for forms with expiration"""
        token = secrets.token_urlsafe(32)
        # Store token with 1 hour expiration
        self._csrf_tokens[token] = {
            'created': time.time(),
            'expires': time.time() + 3600  # 1 hour
        }
        return token

    def validate_csrf_token(self, token):
        """Validate CSRF token with proper expiration check"""
        if not token or len(token) < 10:
            return False
        
        if token not in self._csrf_tokens:
            return False
            
        token_data = self._csrf_tokens[token]
        current_time = time.time()
        
        # Check if token has expired
        if current_time > token_data['expires']:
            # Remove expired token
            del self._csrf_tokens[token]
            return False
            
        return True

    # Password hashing functions removed - were unused dead code

# Initialize application context
app_context = AppContext()

CORS(app, supports_credentials=True)

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
        'version': '1.0.0'
    })

@app.route('/api/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with system information"""
    try:
        health_info = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
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

# Helper function to get user ID safely
def get_user_id():
    """Get user ID from authenticated user or request headers"""
    # First try to get from authenticated user
    if hasattr(request, 'user') and request.user:
        user_id = request.user.get('user_id', 'default_user')
        logger.info(f"Using authenticated user ID: {user_id}")
        return user_id
    
    # If no authenticated user, try to get from request headers (for simple user identification)
    user_id = request.headers.get('X-User-ID')
    if user_id:
        logger.info(f"Using header user ID: {user_id}")
        return user_id
    
    # Fallback to default user
    logger.info("Using default user ID")
    return 'default_user'

# Authentication enabled
def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        # Check for session cookie
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Validate session and get user data
        user_info = user_manager.validate_session(session_id)
        if not user_info:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        # Set user information on request object
        request.user = user_info
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_csrf(f):
    """Decorator to require CSRF token validation"""
    def decorated_function(*args, **kwargs):
        # Skip CSRF validation for GET requests
        if request.method == 'GET':
            return f(*args, **kwargs)

        # Get CSRF token from headers or form data
        csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')

        if not csrf_token or not app_context.validate_csrf_token(csrf_token):
            return jsonify({'error': 'CSRF token validation failed'}), 403

        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def rate_limit(f):
    """Decorator to implement rate limiting"""
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr or 'unknown'
        if not security_manager.check_rate_limit(client_ip):
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def sanitize_input(data):
    """Sanitize input data to prevent XSS"""
    if isinstance(data, dict):
        return {key: security_manager.sanitize_input(str(value)) if isinstance(value, str) else value 
                for key, value in data.items()}
    elif isinstance(data, str):
        return security_manager.sanitize_input(data)
    return data

def initialize_data_manager():
    """Initialize data manager without password"""
    try:
        logger.info(f"Initializing data manager...")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Handle PyInstaller bundle path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
            data_dir = os.path.join(base_path, "data")
        else:
            # Running as script
            data_dir = "data"

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
            app_context.data_manager = SimpleDataManager(data_dir=data_dir)
            logger.info(f"Data manager initialized successfully with data directory: {data_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize data manager: {e}")
            return False

        app_context.password_set = True
        
        # Initialize update manager
        try:
            app_context.update_manager = UpdateManager(app_dir=os.getcwd(), data_dir=data_dir)
            app_context.update_manager.start_auto_update_check()
            app_context.update_manager.schedule_weekly_backup()
            print("Update manager initialized successfully")
        except Exception as update_error:
            print(f"Warning: Update manager initialization failed: {update_error}")
            # Don't fail the entire setup for update manager issues
        
        return True
    except Exception as e:
        print(f"Error initializing data manager: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def auto_save_worker():
    """Background thread for auto-saving"""
    while app_context.auto_save_enabled:
        try:
            # Auto-save every 30 seconds by default
            settings = app_context.data_manager.load_settings() if app_context.data_manager else {}
            interval = settings.get('autosave_interval', 30)
            time.sleep(interval)
            
            if app_context.auto_save_enabled and app_context.data_manager:
                # Actually save data
                tasks = app_context.data_manager.load_tasks()
                app_context.data_manager.save_tasks(tasks)
                print("Auto-saved data successfully")
        except Exception as e:
            print(f"Auto-save error: {e}")

def start_auto_save():
    """Start the auto-save background thread"""
    app_context.auto_save_enabled = True
    app_context.auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
    app_context.auto_save_thread.start()

def stop_auto_save():
    """Stop the auto-save background thread"""
    app_context.auto_save_enabled = False

def scheduler_worker():
    """Background thread for scheduled tasks"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def setup_daily_reset():
    """Setup daily reset schedule"""
    if app_context.data_manager:
        settings = app_context.data_manager.load_settings()
        reset_time = settings.get('daily_reset_time', '09:00')
        schedule.every().day.at(reset_time).do(reset_daily_strikes_job)
        print(f"Daily reset scheduled for {reset_time}")

def reset_daily_strikes_job():
    """Job to reset daily strikes"""
    try:
        if app_context.data_manager:
            tasks = app_context.data_manager.load_tasks()
            today = datetime.now().strftime('%Y-%m-%d')
            
            for i, task in enumerate(tasks):
                if task.get('struck_today') and task.get('struck_date') != today:
                    tasks[i]['struck_today'] = False
                    tasks[i]['struck_date'] = None
            
            app_context.data_manager.save_tasks(tasks)
            print("Daily strikes reset completed")
    except Exception as e:
        print(f"Error in daily reset: {e}")

def start_scheduler():
    """Start the scheduler background thread"""
    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()
    setup_daily_reset()

@app.route('/')
def index():
    """Serve the main application page"""
    # Check if user is already authenticated using user_manager
    session_id = request.cookies.get('session_id')
    if not session_id or not user_manager.validate_session(session_id):
        return redirect(url_for('login'))

    # Load version information
    try:
        import json
        # Get the root directory (parent of src/)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        version_path = os.path.join(root_dir, 'config', 'version.json')
        with open(version_path, 'r') as f:
            version_data = json.load(f)
        version = f"{version_data['version']}.{version_data['build']}"
    except:
        version = '1.0.0'

    return render_template('index.html', version=version)

@app.route('/api/changelog')
def get_changelog():
    """Serve the changelog file"""
    try:
        # Get the root directory (parent of src/)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        changelog_path = os.path.join(root_dir, 'config', 'changelog.txt')
        with open(changelog_path, 'r', encoding='utf-8') as f:
            changelog_content = f.read()
        return changelog_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except FileNotFoundError:
        return 'Changelog file not found.', 404
    except Exception as e:
        logger.error(f"Error reading changelog: {e}")
        return 'Error reading changelog.', 500


# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with proper authentication"""
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Authenticate user
        auth_result = user_manager.authenticate_user(username, password)
        
        if auth_result['success']:
            # Set session cookie using user_manager
            response = jsonify({
                'success': True,
                'message': 'Login successful',
                'user': auth_result['user']
            })

            # Set HTTP-only cookie for session management
            response.set_cookie(
                'session_id',
                auth_result['session_id'],
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                max_age=24*60*60,  # 24 hours
                samesite='Lax'
            )

            return response
        else:
            return jsonify({'error': auth_result['error']}), 401
    
    # Return login form HTML for GET requests
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shakshuka Login</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #FF8C42; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; margin-bottom: 10px; }
            button:hover { background: #e67e22; }
            .error { color: red; margin-top: 10px; text-align: center; }
            .info { background: #e8f4fd; padding: 15px; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #2196F3; }
            .signup-link { text-align: center; margin-top: 20px; }
            .signup-link a { color: #FF8C42; text-decoration: none; }
            .signup-link a:hover { text-decoration: underline; }
            .form-toggle { text-align: center; margin-bottom: 20px; }
            .form-toggle button { background: none; color: #FF8C42; border: none; cursor: pointer; text-decoration: underline; width: auto; padding: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2 style="text-align: center; color: #333;">Shakshuka Login</h2>
            
            <div class="info">
                <strong>Welcome to Shakshuka!</strong><br>
                Secure task management application. Login or create a new account.
            </div>
            
            <div class="form-toggle">
                <button onclick="toggleForm()" id="toggleBtn">Don't have an account? Sign up</button>
            </div>
            
            <!-- Login Form -->
            <form id="loginForm">
                <div class="form-group">
                    <label for="login-username">Username:</label>
                    <input type="text" id="login-username" name="username" required placeholder="Enter your username">
                </div>
                <div class="form-group">
                    <label for="login-password">Password:</label>
                    <input type="password" id="login-password" name="password" required placeholder="Enter your password">
                </div>
                <button type="submit">Login</button>
                <div id="login-error" class="error" style="display: none;"></div>
            </form>
            
            <!-- Signup Form -->
            <form id="signupForm" style="display: none;">
                <div class="form-group">
                    <label for="signup-username">Username:</label>
                    <input type="text" id="signup-username" name="username" required placeholder="Choose a username (min 3 chars)">
                </div>
                <div class="form-group">
                    <label for="signup-password">Password:</label>
                    <input type="password" id="signup-password" name="password" required placeholder="Choose a password (min 6 chars)">
                </div>
                <div class="form-group">
                    <label for="signup-confirm">Confirm Password:</label>
                    <input type="password" id="signup-confirm" name="confirm_password" required placeholder="Confirm your password">
                </div>
                <button type="submit">Sign Up</button>
                <div id="signup-error" class="error" style="display: none;"></div>
            </form>
        </div>
        
        <script>
            function toggleForm() {
                const loginForm = document.getElementById('loginForm');
                const signupForm = document.getElementById('signupForm');
                const toggleBtn = document.getElementById('toggleBtn');
                
                if (loginForm.style.display === 'none') {
                    loginForm.style.display = 'block';
                    signupForm.style.display = 'none';
                    toggleBtn.textContent = "Don't have an account? Sign up";
                } else {
                    loginForm.style.display = 'none';
                    signupForm.style.display = 'block';
                    toggleBtn.textContent = "Already have an account? Login";
                }
            }
            
            // Login form handler
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;
                const errorDiv = document.getElementById('login-error');
                
                try {
                    const response = await fetch('/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: username, password: password})
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        window.location.href = '/';
                    } else {
                        errorDiv.textContent = data.error || 'Login failed';
                        errorDiv.style.display = 'block';
                    }
                } catch (error) {
                    errorDiv.textContent = 'Network error. Please try again.';
                    errorDiv.style.display = 'block';
                }
            });
            
            // Signup form handler
            document.getElementById('signupForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('signup-username').value;
                const password = document.getElementById('signup-password').value;
                const confirmPassword = document.getElementById('signup-confirm').value;
                const errorDiv = document.getElementById('signup-error');
                
                if (password !== confirmPassword) {
                    errorDiv.textContent = 'Passwords do not match';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                try {
                    const response = await fetch('/register', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: username, password: password})
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        errorDiv.textContent = 'Registration successful! Please login.';
                        errorDiv.style.display = 'block';
                        errorDiv.style.color = 'green';
                        toggleForm(); // Switch to login form
                    } else {
                        errorDiv.textContent = data.error || 'Registration failed';
                        errorDiv.style.display = 'block';
                    }
                } catch (error) {
                    errorDiv.textContent = 'Network error. Please try again.';
                    errorDiv.style.display = 'block';
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/register', methods=['POST'])
def register():
    """User registration endpoint - username and password only"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    # Register user
    result = user_manager.register_user(username, password)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': 'Registration successful! Please login with your credentials.'
        })
    else:
        return jsonify({'error': result['error']}), 400

@app.route('/api/auth/setup', methods=['POST'])
def api_auth_setup():
    """API endpoint for user setup"""
    data = request.json
    password = data.get('password', '').strip()
    
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Create user account
    auth_result = user_manager.create_user('admin', password)
    
    if auth_result['success']:
        # Set session cookie
        response = jsonify({
            'success': True,
            'message': 'Account setup successful'
        })
        
        # Set HTTP-only cookie for session management
        response.set_cookie(
            'session_id',
            auth_result['session_id'],
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite='Lax',
            max_age=86400  # 24 hours
        )
        
        return response
    else:
        return jsonify({'error': auth_result['error']}), 400

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """API endpoint for user login"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Authenticate user
    auth_result = user_manager.authenticate_user(username, password)
    
    if auth_result['success']:
        # Set session cookie
        response = jsonify({
            'success': True,
            'message': 'Login successful',
            'user': auth_result['user']
        })
        
        # Set HTTP-only cookie for session management
        response.set_cookie(
            'session_id',
            auth_result['session_id'],
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite='Lax',
            max_age=86400  # 24 hours
        )
        
        return response
    else:
        return jsonify({'error': auth_result['error']}), 401

@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    """API endpoint to check authentication status"""
    session_id = request.cookies.get('session_id')
    
    if not session_id:
        return jsonify({'authenticated': False}), 401
    
    # Validate session
    user_info = user_manager.validate_session(session_id)
    if not user_info:
        return jsonify({'authenticated': False}), 401
    
    return jsonify({
        'authenticated': True,
        'user': user_info
    })

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for forms"""
    # Authentication temporarily disabled - no auth modal in HTML
    token = app_context.generate_csrf_token()
    return jsonify({'csrf_token': token})

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint"""
    return jsonify({'status': 'ok', 'message': 'API is working'})

@app.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    session_id = session.get('session_id')
    if session_id:
        user_manager.logout_user(session_id)
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def api_logout():
    """API logout endpoint"""
    session_id = session.get('session_id')
    if session_id:
        user_manager.logout_user(session_id)
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    data = request.json
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters long'}), 400
    
    session_id = session.get('session_id')
    user_data = user_manager.validate_session(session_id)
    
    if not user_data:
        return jsonify({'error': 'Invalid session'}), 401
    
    # Verify current password
    if not user_manager.verify_password(current_password, user_data['password_hash']):
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    # Update password
    result = user_manager.update_password(user_data['user_id'], new_password)
    
    if result['success']:
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
        return jsonify({'error': result['error']}), 400

@app.route('/api/tasks', methods=['GET'])
@require_auth
def get_tasks():
    """Get all tasks for the authenticated user"""
    # Use default user ID when authentication is disabled
    user_id = get_user_id()
    
    # For now, return empty tasks to test if the endpoint works
    try:
        tasks = app_context.data_manager.load_tasks(user_id)
        return jsonify(tasks)
    except Exception as e:
        # If data manager fails, return empty tasks
        return jsonify([])

@app.route('/api/tasks/import', methods=['POST'])
@require_auth
def import_tasks():
    """Import tasks from CSV or TXT file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file:
        return jsonify({'error': 'Invalid file'}), 400
    
    try:
        # Read file content
        file_content = file.read().decode('utf-8')
        file_extension = file.filename.lower().split('.')[-1]
        
        imported_tasks = []
        errors = []
        
        if file_extension == 'csv':
            imported_tasks, errors = parse_csv_tasks(file_content)
        elif file_extension == 'txt':
            imported_tasks, errors = parse_txt_tasks(file_content)
        else:
            return jsonify({'error': 'Unsupported file format. Please use CSV or TXT.'}), 400
        
        if not imported_tasks:
            return jsonify({'error': 'No valid tasks found in file', 'details': errors}), 400
        
        # Load existing tasks for the user
        user_id = get_user_id()
        existing_tasks = app_context.data_manager.load_tasks(user_id)
        
        # Add imported tasks
        for task in imported_tasks:
            task['id'] = str(uuid.uuid4())
            task['created_at'] = datetime.now().isoformat()
            task['completed'] = False
            task['strike_count'] = 0
            task['struck_today'] = False
            existing_tasks.append(task)
        
        # Save all tasks for the user
        if app_context.data_manager.save_tasks(user_id, existing_tasks):
            return jsonify({
                'success': True,
                'message': f'Successfully imported {len(imported_tasks)} tasks',
                'imported_count': len(imported_tasks),
                'errors': errors
            })
        else:
            return jsonify({'error': 'Failed to save imported tasks'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

def parse_csv_tasks(content):
    """Parse CSV content and return tasks and errors"""
    tasks = []
    errors = []
    
    try:
        # Use StringIO to read CSV content
        csv_file = io.StringIO(content)
        reader = csv.DictReader(csv_file)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 because header is row 1
            try:
                # Sanitize input
                row = sanitize_input(row)
                
                # Extract task data
                title = row.get('title', '').strip()
                if not title:
                    errors.append(f"Row {row_num}: Title is required")
                    continue
                
                description = row.get('description', '').strip()
                project = row.get('project', '').strip()
                
                # Parse duration
                duration_str = row.get('duration', '60').strip()
                try:
                    duration = int(duration_str) if duration_str else 60
                except ValueError:
                    duration = 60
                
                # Parse due date
                due_date = row.get('due_date', '').strip()
                if due_date:
                    try:
                        # Try to parse various date formats
                        datetime.fromisoformat(due_date)
                    except ValueError:
                        try:
                            datetime.strptime(due_date, '%Y-%m-%d')
                        except ValueError:
                            try:
                                datetime.strptime(due_date, '%m/%d/%Y')
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid date format for '{due_date}'")
                                due_date = None
                
                # Parse priority
                priority = row.get('priority', 'medium').strip().lower()
                if priority not in ['low', 'medium', 'high']:
                    priority = 'medium'
                
                task = {
                    'title': title,
                    'description': description,
                    'project': project,
                    'estimated_duration': duration,
                    'due_date': due_date,
                    'priority': priority
                }
                
                tasks.append(task)
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                
    except Exception as e:
        errors.append(f"CSV parsing error: {str(e)}")
    
    return tasks, errors

def parse_txt_tasks(content):
    """Parse TXT content and return tasks and errors"""
    tasks = []
    errors = []
    
    try:
        lines = content.strip().split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith('#'):  # Skip empty lines and comments
                continue
            
            try:
                # Sanitize input
                line = sanitize_input(line)
                
                # Simple format: Title | Description | Project | Duration | Due Date
                parts = [part.strip() for part in line.split('|')]
                
                if len(parts) < 1:
                    errors.append(f"Line {line_num}: At least title is required")
                    continue
                
                title = parts[0]
                if not title:
                    errors.append(f"Line {line_num}: Title is required")
                    continue
                
                description = parts[1] if len(parts) > 1 else ''
                project = parts[2] if len(parts) > 2 else ''
                
                # Parse duration
                duration = 60
                if len(parts) > 3 and parts[3]:
                    try:
                        duration = int(parts[3])
                    except ValueError:
                        errors.append(f"Line {line_num}: Invalid duration '{parts[3]}'")
                
                # Parse due date
                due_date = None
                if len(parts) > 4 and parts[4]:
                    try:
                        datetime.fromisoformat(parts[4])
                        due_date = parts[4]
                    except ValueError:
                        try:
                            datetime.strptime(parts[4], '%Y-%m-%d')
                            due_date = parts[4]
                        except ValueError:
                            try:
                                datetime.strptime(parts[4], '%m/%d/%Y')
                                due_date = parts[4]
                            except ValueError:
                                errors.append(f"Line {line_num}: Invalid date format '{parts[4]}'")
                
                task = {
                    'title': title,
                    'description': description,
                    'project': project,
                    'estimated_duration': duration,
                    'due_date': due_date,
                    'priority': 'medium'
                }
                
                tasks.append(task)
                
            except Exception as e:
                errors.append(f"Line {line_num}: {str(e)}")
                
    except Exception as e:
        errors.append(f"TXT parsing error: {str(e)}")
    
    return tasks, errors

@app.route('/api/tasks', methods=['POST'])
@require_auth
@require_csrf
@rate_limit
def create_task():
    """Create a new task for the authenticated user"""
    user_id = get_user_id()
    task_data = request.json
    tasks = app_context.data_manager.load_tasks(user_id)
    
    # Sanitize input data
    task_data = sanitize_input(task_data)
    
    # Input validation
    title = task_data.get('title', '').strip()
    if not title or len(title) > 200:
        return jsonify({'error': 'Title is required and must be less than 200 characters'}), 400
    
    description = task_data.get('description', '').strip()
    if len(description) > 1000:
        return jsonify({'error': 'Description must be less than 1000 characters'}), 400
    
    project = task_data.get('project', '').strip()
    if len(project) > 100:
        return jsonify({'error': 'Project name must be less than 100 characters'}), 400
    
    estimated_duration = task_data.get('estimated_duration', 60)
    if not isinstance(estimated_duration, int) or estimated_duration < 5 or estimated_duration > 480:
        return jsonify({'error': 'Duration must be between 5 and 480 minutes'}), 400
    
    due_date = task_data.get('due_date')
    if due_date:
        try:
            datetime.fromisoformat(due_date)
        except ValueError:
            return jsonify({'error': 'Invalid due date format'}), 400
    
    # Generate unique ID
    task_id = str(uuid.uuid4())
    
    new_task = {
        'id': task_id,
        'title': title,
        'description': description,
        'completed': False,
        'created_at': datetime.now().isoformat(),
        'due_date': due_date,
        'project': project,
        'scheduled_hour': task_data.get('scheduled_hour'),
        'estimated_duration': estimated_duration,
        'struck_today': False,
        'struck_date': None
    }
    
    tasks.append(new_task)
    
    if app_context.data_manager.save_tasks(tasks, user_id):
        return jsonify(new_task), 201
    else:
        return jsonify({'error': 'Failed to save task'}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@require_auth
@require_csrf
def update_task(task_id):
    """Update an existing task for the authenticated user"""
    user_id = get_user_id()
    task_data = request.json
    tasks = app_context.data_manager.load_tasks(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i].update(task_data)
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@require_auth
@require_csrf
def delete_task(task_id):
    """Delete a task for the authenticated user"""
    user_id = get_user_id()
    tasks = app_context.data_manager.load_tasks(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            deleted_task = tasks.pop(i)
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(deleted_task)
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
@require_auth
def complete_task(task_id):
    """Mark a task as completed for the authenticated user"""
    user_id = get_user_id()
    tasks = app_context.data_manager.load_tasks(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['completed'] = True
            tasks[i]['completed_at'] = datetime.now().isoformat()
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/strike', methods=['POST'])
@require_auth
def strike_task(task_id):
    """Unified strike endpoint for both today and forever"""
    user_id = get_user_id()
    strike_data = request.json
    strike_type = strike_data.get('type')
    report = strike_data.get('report', '')
    
    if not strike_type or strike_type not in ['today', 'forever']:
        return jsonify({'error': 'Invalid strike type'}), 400
    
    tasks = app_context.data_manager.load_tasks(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if strike_type == 'today':
                # Check if task has already been struck twice today
                daily_strikes = task.get('daily_strikes', {})
                strikes_today = daily_strikes.get(today, 0)
                
                if strikes_today >= 2:
                    return jsonify({'error': 'Maximum strikes reached for today'}), 400
                
                # Update daily strikes
                daily_strikes[today] = strikes_today + 1
                tasks[i]['daily_strikes'] = daily_strikes
                tasks[i]['struck_today'] = True
                tasks[i]['struck_date'] = today
                tasks[i]['strike_report'] = report
                tasks[i]['strike_count'] = tasks[i].get('strike_count', 0) + 1
            elif strike_type == 'forever':
                tasks[i]['completed'] = True
                tasks[i]['completed_at'] = datetime.now().isoformat()
                tasks[i]['struck_today'] = False
                tasks[i]['struck_date'] = None
                tasks[i]['strike_report'] = report
                tasks[i]['strike_count'] = tasks[i].get('strike_count', 0) + 1
            
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/undo-strike', methods=['POST'])
@require_auth
def undo_strike(task_id):
    """Undo a strike for today for the authenticated user"""
    user_id = get_user_id()
    tasks = app_context.data_manager.load_tasks(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if task.get('struck_today'):
                # Update daily strikes
                daily_strikes = task.get('daily_strikes', {})
                strikes_today = daily_strikes.get(today, 0)
                if strikes_today > 0:
                    daily_strikes[today] = strikes_today - 1
                    tasks[i]['daily_strikes'] = daily_strikes
                
                # If no more strikes today, mark as not struck
                if daily_strikes.get(today, 0) == 0:
                    tasks[i]["struck_today"] = False
                    tasks[i]["struck_date"] = None
                    tasks[i]["strike_report"] = None
                # Don't decrease strike_count as it tracks total strikes
                
                if app_context.data_manager.save_tasks(tasks, user_id):
                    return jsonify(tasks[i])
                else:
                    return jsonify({'error': 'Failed to save tasks'}), 500
            else:
                return jsonify({'error': 'Task is not struck for today'}), 400
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/unschedule', methods=['POST'])
@require_auth
def unschedule_task(task_id):
    """Remove a task from the daily planner for the authenticated user"""
    user_id = get_user_id()
    tasks = app_context.data_manager.load_tasks(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            # Remove scheduling information
            tasks[i]['scheduled_hour'] = None
            tasks[i]['scheduled_date'] = None
            tasks[i]['duration'] = None
            
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/schedule', methods=['POST'])
@require_auth
def schedule_task(task_id):
    """Schedule a task for a specific hour and duration for the authenticated user"""
    user_id = get_user_id()
    schedule_data = request.json
    hour = schedule_data.get('hour')
    duration = schedule_data.get('duration', 30)  # Default 30 minutes
    date = schedule_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not hour:
        return jsonify({'error': 'Hour is required'}), 400
    
    tasks = app_context.data_manager.load_tasks(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['scheduled_hour'] = hour
            tasks[i]['scheduled_date'] = date
            tasks[i]['duration'] = duration
            
            if app_context.data_manager.save_tasks(tasks, user_id):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/reset-daily-strikes', methods=['POST'])
@require_auth
def reset_daily_strikes():
    """Reset all daily strikes for the authenticated user (called by daily reset timer)"""
    user_id = get_user_id()
    tasks = app_context.data_manager.load_tasks(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        # Reset daily strikes for all tasks
        if 'daily_strikes' in task:
            # Keep only today's strikes, clear older ones
            daily_strikes = task.get('daily_strikes', {})
            if today in daily_strikes:
                daily_strikes = {today: daily_strikes[today]}
            else:
                daily_strikes = {}
            tasks[i]['daily_strikes'] = daily_strikes
        
        # Reset struck_today if it's from a previous day
        if task.get('struck_today') and task.get('struck_date') != today:
            tasks[i]['struck_today'] = False
            tasks[i]['struck_date'] = None
    
    if app_context.data_manager.save_tasks(tasks, user_id):
        return jsonify({'success': True, 'message': 'Daily strikes reset'})
    else:
        return jsonify({'error': 'Failed to reset daily strikes'}), 500

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """Get application settings for the authenticated user"""
    user_id = get_user_id()
    
    # Check if data manager is initialized
    if not ensure_data_manager():
        return jsonify({'error': 'Failed to initialize data manager'}), 500
    
    settings = app_context.data_manager.load_settings(user_id)
    settings['autostart_enabled'] = app_context.autostart_manager.is_autostart_enabled()
    # Ensure default values for new settings
    if 'theme' not in settings:
        settings['theme'] = 'orange'
    if 'dpi_scale' not in settings:
        settings['dpi_scale'] = 100
    if 'daily_reset_time' not in settings:
        settings['daily_reset_time'] = '09:00'
    return jsonify(settings)

@app.route('/api/settings', methods=['PUT'])
@require_auth
def update_settings():
    """Update application settings for the authenticated user"""
    user_id = get_user_id()
    settings_data = request.json
    current_settings = app_context.data_manager.load_settings(user_id)
    current_settings.update(settings_data)
    
    # Handle autostart setting
    if 'autostart' in settings_data:
        if settings_data['autostart']:
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
    
    if app_context.data_manager.save_settings(user_id, current_settings):
        return jsonify(current_settings)
    else:
        return jsonify({'error': 'Failed to save settings'}), 500

# Password change endpoint removed - no password authentication

@app.route('/api/planner/schedule', methods=['GET'])
@require_auth
def get_schedule():
    """Get daily schedule for the authenticated user"""
    user_id = get_user_id()
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    tasks = app_context.data_manager.load_tasks(user_id)
    
    # Filter tasks for the specific date
    scheduled_tasks = []
    for task in tasks:
        if task.get('scheduled_hour') and task.get('scheduled_date') == date:
            scheduled_tasks.append(task)
    
    return jsonify(scheduled_tasks)

@app.route('/api/planner/schedule', methods=['POST'])
@require_auth
def update_schedule():
    """Update daily schedule"""
    schedule_data = request.json
    tasks = app_context.data_manager.load_tasks()
    
    # Update task scheduling
    for task_update in schedule_data:
        task_id = task_update.get('task_id')
        scheduled_hour = task_update.get('scheduled_hour')
        scheduled_date = task_update.get('scheduled_date')
        
        for task in tasks:
            if task['id'] == task_id:
                task['scheduled_hour'] = scheduled_hour
                task['scheduled_date'] = scheduled_date
                break
    
    if app_context.data_manager.save_tasks(tasks):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save schedule'}), 500

# Update Management Endpoints
@app.route('/api/updates/status', methods=['GET'])
@require_auth
def get_update_status():
    """Get current update status"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(app_context.update_manager.get_update_status())

@app.route('/api/updates/check', methods=['POST'])
@require_auth
def check_for_updates():
    """Check for available updates"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_context.update_manager = UpdateManager(app_dir=os.getcwd(), data_dir="data")

        update_info = app_context.update_manager.check_for_updates()
        if update_info:
            return jsonify({'update_available': True, 'update_info': update_info})
        else:
            return jsonify({'update_available': False})
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return jsonify({'error': 'Failed to check for updates'}), 500

@app.route('/api/updates/download', methods=['POST'])
@require_auth
def download_update():
    """Download available update"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_info = request.json
    if not update_info:
        return jsonify({'error': 'Update info required'}), 400
    
    def progress_callback(progress):
        # Could implement WebSocket or Server-Sent Events for real-time progress
        pass
    
    success = app_context.update_manager.download_update(update_info, progress_callback)
    if success:
        return jsonify({'success': True, 'message': 'Update downloaded successfully'})
    else:
        return jsonify({'error': 'Failed to download update'}), 500

@app.route('/api/updates/install', methods=['POST'])
@require_auth
def install_update():
    """Install downloaded update"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_data = request.json
    update_file = update_data.get('update_file')
    backup_data = update_data.get('backup_before_update', True)
    
    if not update_file:
        return jsonify({'error': 'Update file required'}), 400
    
    success = app_context.update_manager.install_update(update_file, backup_data)
    if success:
        return jsonify({'success': True, 'message': 'Update installed successfully. Please restart the application.'})
    else:
        return jsonify({'error': 'Failed to install update'}), 500

@app.route('/api/updates/config', methods=['GET'])
@require_auth
def get_update_config():
    """Get update configuration"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(app_context.update_manager.update_config)

@app.route('/api/updates/config', methods=['PUT'])
@require_auth
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
@require_auth
def get_backups():
    """Get list of available backups"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_context.update_manager = UpdateManager(app_dir=os.getcwd(), data_dir="data")

        backups = app_context.update_manager.get_backup_list()
        return jsonify({'backups': backups})
    except Exception as e:
        print(f"Error getting backups: {e}")
        return jsonify({'error': 'Failed to get backups'}), 500

@app.route('/api/backups/create', methods=['POST'])
@require_auth
def create_backup():
    """Create manual backup"""
    try:
        if not app_context.update_manager:
            # Initialize update manager if not already done
            app_context.update_manager = UpdateManager(app_dir=os.getcwd(), data_dir="data")
    
        backup_data = request.json or {}
        backup_type = backup_data.get('type', 'manual')
        
        success = app_context.update_manager.create_backup(backup_type)
        if success:
            return jsonify({'success': True, 'message': 'Backup created successfully'})
        else:
            return jsonify({'error': 'Failed to create backup'}), 500
    except Exception as e:
        print(f"Error creating backup: {e}")
        return jsonify({'error': 'Failed to create backup'}), 500

@app.route('/api/backups/restore', methods=['POST'])
@require_auth
def restore_backup():
    """Restore from backup"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    backup_data = request.json
    backup_name = backup_data.get('backup_name')
    
    if not backup_name:
        return jsonify({'error': 'Backup name required'}), 400
    
    success = app_context.update_manager.restore_backup(backup_name)
    if success:
        return jsonify({'success': True, 'message': 'Backup restored successfully'})
    else:
        return jsonify({'error': 'Failed to restore backup'}), 500

if __name__ == '__main__':
    try:
        print("Starting Shakshuka application...")
        
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

def create_system_tray_icon() -> Optional[Any]:
    """Create and show system tray icon"""
    if not SYSTEM_TRAY_AVAILABLE:
        logger.warning("System tray not available - skipping icon creation")
        return None

    try:
        # Create a simple icon (you can replace this with a proper icon file)
        icon = create_icon_image()

        # Create system tray menu
        def show_app():
            """Show the main application window"""
            logger.info("Opening application from system tray")

        def hide_app():
            """Hide the main application window"""
            logger.info("Hiding application from system tray")

        def quit_app():
            """Quit the application"""
            logger.info("Quitting application from system tray")
            if system_tray_icon:
                system_tray_icon.stop()
            shutdown_application()

        menu = pystray.Menu(
            pystray.MenuItem("Show Shakshuka", show_app),
            pystray.MenuItem("Hide Shakshuka", hide_app),
            pystray.MenuItem("Quit Shakshuka", quit_app)
        )

        # Create and show icon
        tray_icon = pystray.Icon("shakshuka", icon, "Shakshuka Task Manager", menu)
        return tray_icon

    except Exception as e:
        logger.error(f"Failed to create system tray icon: {e}")
        return None

def create_icon_image() -> Any:
    """Create a simple icon image for the system tray"""
    try:
        # Create a 64x64 image
        image = Image.new('RGB', (64, 64), color='#FF8C42')

        # Draw a simple leaf icon (matching the app logo)
        draw = ImageDraw.Draw(image)
        # Draw a simple leaf shape (circle with stem)
        draw.ellipse([16, 16, 48, 48], fill='white')  # Main leaf body
        draw.rectangle([30, 10, 34, 20], fill='#FF8C42')  # Stem

        return image
    except Exception as e:
        logger.error(f"Failed to create icon image: {e}")
        # Return a simple colored square as fallback
        return Image.new('RGB', (64, 64), color='#FF8C42')

def start_system_tray() -> None:
    """Start the system tray icon"""
    global system_tray_icon

    if not SYSTEM_TRAY_AVAILABLE:
        logger.warning("System tray not available")
        return

    try:
        system_tray_icon = create_system_tray_icon()
        if system_tray_icon:
            # Run in a separate thread to avoid blocking
            import threading
            tray_thread = threading.Thread(target=system_tray_icon.run, daemon=True)
            tray_thread.start()
            logger.info("System tray icon started")
        else:
            logger.warning("Failed to create system tray icon")
    except Exception as e:
        logger.error(f"Error starting system tray: {e}")

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

    # Stop any background threads
    try:
        if 'scheduler_thread' in globals():
            scheduler_thread.join(timeout=5)
    except:
        pass

    logger.info("Application shutdown complete")
    sys.exit(0)
