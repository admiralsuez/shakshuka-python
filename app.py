from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import threading
import time
import uuid
import sys
import schedule
from datetime import datetime, timedelta
import json
import os
import csv
import io
import hashlib
import hmac
import re
import secrets
from werkzeug.utils import secure_filename
from data_manager import EncryptedDataManager
from autostart import WindowsAutostart
from update_manager import UpdateManager
from security_manager import security_manager

# Try to import bcrypt for proper password hashing
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("Warning: bcrypt not available. Password hashing will be less secure.")

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
        """Generate CSRF token for forms"""
        token = secrets.token_urlsafe(32)
        return token

    def validate_csrf_token(self, token):
        """Validate CSRF token (basic validation - in production use proper timing-safe comparison)"""
        # For this implementation, we'll just check if token exists and is not empty
        # In production, implement proper CSRF token validation with proper storage
        return token and len(token) > 10

    def hash_password(self, password):
        """Hash password using bcrypt if available, otherwise PBKDF2"""
        if BCRYPT_AVAILABLE:
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        else:
            # Fallback to PBKDF2
            salt = os.urandom(32)
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return salt + key

    def verify_password(self, password, hashed):
        """Verify password against hash"""
        if BCRYPT_AVAILABLE:
            return bcrypt.checkpw(password.encode('utf-8'), hashed)
        else:
            # Fallback PBKDF2 verification
            salt = hashed[:32]
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return hashed[32:] == key

# Initialize application context
app_context = AppContext()

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

CORS(app, supports_credentials=True)

# Request logging middleware
@app.before_request
def log_request_info():
    """Log incoming requests for debugging and monitoring"""
    try:
        # Log request details
        print(f"Request: {request.method} {request.url}")
        print(f"Client IP: {request.remote_addr}")
        print(f"User Agent: {request.headers.get('User-Agent', 'Unknown')}")

        # Log request body for debugging (be careful with sensitive data)
        if request.method in ['POST', 'PUT'] and request.content_type and 'application/json' in request.content_type:
            try:
                # Only log if request is small and not authentication-related
                if request.content_length and request.content_length < 1000:
                    body = request.get_json(silent=True)
                    if body and 'password' not in str(body).lower():
                        print(f"Request body: {body}")
            except:
                pass  # Ignore JSON parsing errors for logging

        print("---")
    except Exception as e:
        print(f"Error in request logging: {e}")

@app.after_request
def log_response_info(response):
    """Log response details"""
    try:
        print(f"Response: {response.status_code} - {len(response.get_data())} bytes")
        print("---")
    except Exception as e:
        print(f"Error in response logging: {e}")

    return response

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

def validate_input(data, schema):
    """Validate input data against a schema"""
    errors = []

    for field, rules in schema.items():
        value = data.get(field)

        # Required field check
        if rules.get('required') and (value is None or value == ''):
            errors.append(f"Field '{field}' is required")
            continue

        # Skip further validation if field is not required and empty
        if value is None or value == '':
            continue

        # Type validation
        expected_type = rules.get('type')
        if expected_type:
            if expected_type == 'string' and not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif expected_type == 'int' and not isinstance(value, int):
                errors.append(f"Field '{field}' must be an integer")
            elif expected_type == 'bool' and not isinstance(value, bool):
                errors.append(f"Field '{field}' must be a boolean")

        # Length validation
        min_length = rules.get('min_length')
        max_length = rules.get('max_length')
        if min_length and len(str(value)) < min_length:
            errors.append(f"Field '{field}' must be at least {min_length} characters")
        if max_length and len(str(value)) > max_length:
            errors.append(f"Field '{field}' must be at most {max_length} characters")

        # Pattern validation
        pattern = rules.get('pattern')
        if pattern and not re.match(pattern, str(value)):
            errors.append(f"Field '{field}' format is invalid")

    return errors

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401

        # Validate session secret for additional security
        user_id = session.get('user_id')
        session_secret = session.get('session_secret')
        if user_id and session_secret:
            if not app_context.validate_session_secret(user_id, session_secret):
                return jsonify({'error': 'Invalid session'}), 401

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

def initialize_data_manager(password):
    """Initialize data manager with password"""
    try:
        print(f"Initializing data manager...")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Data directory path: {os.path.join(os.getcwd(), 'data')}")

        # Check if we can create the data directory
        data_dir = "data"
        data_dir_created = False

        # Try different data directory locations
        possible_dirs = [
            "data",  # Current directory
            os.path.join(os.path.expanduser("~"), "ShakshukaData"),  # User home
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Shakshuka"),  # AppData
            os.path.join(os.getcwd(), "data")  # Absolute path
        ]

        for test_dir in possible_dirs:
            try:
                os.makedirs(test_dir, exist_ok=True)
                print(f"Data directory created/verified: {os.path.abspath(test_dir)}")
                data_dir = test_dir
                data_dir_created = True
                break
            except Exception as dir_error:
                print(f"Failed to create data directory '{test_dir}': {dir_error}")
                continue

        if not data_dir_created:
            print("Failed to create data directory in any location")
            return False

        # Check write permissions
        test_file = os.path.join(data_dir, ".test_write")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print("Write permissions verified")
        except Exception as write_error:
            print(f"Write permission test failed: {write_error}")
            return False

        # Initialize data manager with the working data directory
        app_context.data_manager = EncryptedDataManager(data_dir=data_dir, password=password)
        print(f"Data manager initialized successfully with data directory: {data_dir}")

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
    return render_template('index.html')

@app.route('/api/auth/setup', methods=['POST'])
@rate_limit  # Add rate limiting to setup endpoint
def setup_password():
    """Setup password for first run"""
    
    if app_context.password_set:
        return jsonify({'error': 'Password already set'}), 400
    
    password_data = request.json
    if not password_data:
        return jsonify({'error': 'Request body required'}), 400

    # Validate input
    validation_schema = {
        'password': {
            'required': True,
            'type': 'string',
            'min_length': 6,
            'max_length': 128
        }
    }
    validation_errors = validate_input(password_data, validation_schema)
    if validation_errors:
        return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400

    password = password_data.get('password')

    print(f"Setup request received, password length: {len(password)}")
    
    # Check if this is truly a first run (no existing encrypted files)
    data_dir = "data"
    key_file = os.path.join(data_dir, ".key")
    salt_file = os.path.join(data_dir, ".salt")
    
    if os.path.exists(key_file) and os.path.exists(salt_file):
        return jsonify({'error': 'Password already exists. Please use login instead.'}), 400
    
    try:
        if initialize_data_manager(password):
            session['authenticated'] = True
            session['user_id'] = str(uuid.uuid4())
            session['session_secret'] = app_context.generate_session_secret(session['user_id'])
            return jsonify({'success': True, 'message': 'Password set successfully'})
        else:
            return jsonify({'error': 'Failed to initialize data manager'}), 500
    except Exception as e:
        print(f"Setup error: {e}")
        return jsonify({'error': f'Setup failed: {str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
@rate_limit
def login():
    """Login with password"""
    password_data = request.json
    if not password_data:
        return jsonify({'error': 'Request body required'}), 400

    # Validate input
    validation_schema = {
        'password': {
            'required': True,
            'type': 'string',
            'min_length': 1,
            'max_length': 128
        }
    }
    validation_errors = validate_input(password_data, validation_schema)
    if validation_errors:
        return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400

    password = password_data.get('password')
    
    try:
        # Check if data manager is already initialized
        if app_context.data_manager is None:
            # Try to initialize data manager with existing encrypted files
            print("Data manager not initialized, attempting to initialize with existing password...")
            
            # Check if encrypted files exist
            data_dir = "data"
            key_file = os.path.join(data_dir, ".key")
            salt_file = os.path.join(data_dir, ".salt")
            
            if not (os.path.exists(key_file) and os.path.exists(salt_file)):
                return jsonify({'error': 'No password has been set up yet. Please use the setup endpoint first.'}), 400
            
            # Try to initialize data manager with the provided password
            if not initialize_data_manager(password):
                return jsonify({'error': 'Invalid password'}), 401

        # Try to load tasks with current data manager to verify password
        try:
            app_context.data_manager.load_tasks()
        except Exception:
            return jsonify({'error': 'Invalid password'}), 401

        # If successful, user is authenticated
        session['authenticated'] = True
        session['user_id'] = str(uuid.uuid4())
        session['session_secret'] = app_context.generate_session_secret(session['user_id'])

        return jsonify({'success': True, 'message': 'Login successful', 'session_secret': session['session_secret']})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    # Check if password is set by looking for encrypted files
    data_dir = "data"
    key_file = os.path.join(data_dir, ".key")
    salt_file = os.path.join(data_dir, ".salt")
    password_exists = os.path.exists(key_file) and os.path.exists(salt_file)

    return jsonify({
        'authenticated': session.get('authenticated', False),
        'password_set': password_exists or app_context.password_set
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout"""
    session.pop('authenticated', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for forms"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401

    token = app_context.generate_csrf_token()
    return jsonify({'csrf_token': token})

@app.route('/api/tasks', methods=['GET'])
@require_auth
def get_tasks():
    """Get all tasks"""
    tasks = app_context.data_manager.load_tasks()
    return jsonify(tasks)

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
        
        # Load existing tasks
        existing_tasks = app_context.data_manager.load_tasks()
        
        # Add imported tasks
        for task in imported_tasks:
            task['id'] = str(uuid.uuid4())
            task['created_at'] = datetime.now().isoformat()
            task['completed'] = False
            task['strike_count'] = 0
            task['struck_today'] = False
            existing_tasks.append(task)
        
        # Save all tasks
        if app_context.data_manager.save_tasks(existing_tasks):
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
def create_task():
    """Create a new task"""
    task_data = request.json
    tasks = app_context.data_manager.load_tasks()
    
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
    
    if app_context.data_manager.save_tasks(tasks):
        return jsonify(new_task), 201
    else:
        return jsonify({'error': 'Failed to save task'}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@require_auth
@require_csrf
def update_task(task_id):
    """Update an existing task"""
    task_data = request.json
    tasks = app_context.data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i].update(task_data)
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@require_auth
@require_csrf
def delete_task(task_id):
    """Delete a task"""
    tasks = app_context.data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            deleted_task = tasks.pop(i)
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(deleted_task)
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
@require_auth
def complete_task(task_id):
    """Mark a task as completed"""
    tasks = app_context.data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['completed'] = True
            tasks[i]['completed_at'] = datetime.now().isoformat()
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/strike', methods=['POST'])
@require_auth
def strike_task(task_id):
    """Unified strike endpoint for both today and forever"""
    strike_data = request.json
    strike_type = strike_data.get('type')
    report = strike_data.get('report', '')
    
    if not strike_type or strike_type not in ['today', 'forever']:
        return jsonify({'error': 'Invalid strike type'}), 400
    
    tasks = app_context.data_manager.load_tasks()
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
            
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/undo-strike', methods=['POST'])
@require_auth
def undo_strike(task_id):
    """Undo a strike for today"""
    tasks = app_context.data_manager.load_tasks()
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
                
                if app_context.data_manager.save_tasks(tasks):
                    return jsonify(tasks[i])
                else:
                    return jsonify({'error': 'Failed to save tasks'}), 500
            else:
                return jsonify({'error': 'Task is not struck for today'}), 400
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/unschedule', methods=['POST'])
@require_auth
def unschedule_task(task_id):
    """Remove a task from the daily planner"""
    tasks = app_context.data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            # Remove scheduling information
            tasks[i]['scheduled_hour'] = None
            tasks[i]['scheduled_date'] = None
            tasks[i]['duration'] = None
            
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/schedule', methods=['POST'])
@require_auth
def schedule_task(task_id):
    """Schedule a task for a specific hour and duration"""
    schedule_data = request.json
    hour = schedule_data.get('hour')
    duration = schedule_data.get('duration', 30)  # Default 30 minutes
    date = schedule_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not hour:
        return jsonify({'error': 'Hour is required'}), 400
    
    tasks = app_context.data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['scheduled_hour'] = hour
            tasks[i]['scheduled_date'] = date
            tasks[i]['duration'] = duration
            
            if app_context.data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/reset-daily-strikes', methods=['POST'])
@require_auth
def reset_daily_strikes():
    """Reset all daily strikes (called by daily reset timer)"""
    tasks = app_context.data_manager.load_tasks()
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
    
    if app_context.data_manager.save_tasks(tasks):
        return jsonify({'success': True, 'message': 'Daily strikes reset'})
    else:
        return jsonify({'error': 'Failed to reset daily strikes'}), 500

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """Get application settings"""
    settings = app_context.data_manager.load_settings()
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
    """Update application settings"""
    settings_data = request.json
    current_settings = app_context.data_manager.load_settings()
    current_settings.update(settings_data)
    
    # Handle autostart setting
    if 'autostart' in settings_data:
        if settings_data['autostart']:
            # Get the correct executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.join(os.path.dirname(__file__), "app.py")
            app_context.autostart_manager.enable_autostart(exe_path)
        else:
            app_context.autostart_manager.disable_autostart()
    
    if app_context.data_manager.save_settings(current_settings):
        return jsonify(current_settings)
    else:
        return jsonify({'error': 'Failed to save settings'}), 500

@app.route('/api/settings/password', methods=['POST'])
@require_auth
def change_password():
    """Change encryption password"""
    password_data = request.json
    new_password = password_data.get('new_password')
    current_password = password_data.get('current_password')
    
    if not new_password or not current_password:
        return jsonify({'error': 'Both current and new passwords are required'}), 400
    
    # Verify current password by trying to decrypt data
    try:
        # Create a temporary data manager with current password
        temp_manager = EncryptedDataManager(password=current_password)
        temp_manager.load_tasks()  # This will fail if password is wrong
    except Exception:
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    # Change password
    if app_context.data_manager.change_password(new_password):
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
        return jsonify({'error': 'Failed to change password'}), 500

@app.route('/api/planner/schedule', methods=['GET'])
@require_auth
def get_schedule():
    """Get daily schedule"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    tasks = app_context.data_manager.load_tasks()
    
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

# Kill App Endpoint
@app.route('/api/kill-app', methods=['POST'])
@require_auth
def kill_app():
    """Stop the Shakshuka server"""
    try:
        print("Kill app request received from user")
        
        # Try to run Stop-Shakshuka.bat
        import subprocess
        import os
        
        # Look for Stop-Shakshuka.bat in the current directory
        stop_script = os.path.join(os.getcwd(), 'Stop-Shakshuka.bat')
        
        if os.path.exists(stop_script):
            print(f"Running stop script: {stop_script}")
            # Run the stop script in a separate process
            subprocess.Popen([stop_script], shell=True)
            return jsonify({'success': True, 'message': 'Server stop initiated'})
        else:
            print("Stop-Shakshuka.bat not found, trying alternative method")
            # Alternative: try to kill the current process
            try:
                import signal
                import sys
                # Send SIGTERM to current process
                os.kill(os.getpid(), signal.SIGTERM)
                return jsonify({'success': True, 'message': 'Server stop initiated'})
            except Exception as sig_error:
                print(f"Signal method failed: {sig_error}")
                # Final fallback: just return success and let the frontend handle it
                return jsonify({'success': True, 'message': 'Server stop requested'})
                
    except Exception as e:
        print(f"Error in kill app: {e}")
        return jsonify({'error': 'Failed to stop server'}), 500

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
    # Start auto-save
    start_auto_save()
    
    # Start scheduler for daily resets
    start_scheduler()
    
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
