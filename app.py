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
from werkzeug.utils import secure_filename
from data_manager import EncryptedDataManager
from autostart import WindowsAutostart
from update_manager import UpdateManager
from security_manager import security_manager

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate random secret key
CORS(app, supports_credentials=True)

# Global variables
data_manager = None
autostart_manager = WindowsAutostart()
password_set = False
update_manager = None

# Global variables for auto-save
auto_save_enabled = True
auto_save_thread = None

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
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
    global data_manager, password_set, update_manager
    try:
        data_manager = EncryptedDataManager(password=password)
        password_set = True
        
        # Initialize update manager
        update_manager = UpdateManager(app_dir=os.getcwd(), data_dir="data")
        update_manager.start_auto_update_check()
        update_manager.schedule_weekly_backup()
        
        return True
    except Exception as e:
        print(f"Error initializing data manager: {e}")
        return False

def auto_save_worker():
    """Background thread for auto-saving"""
    while auto_save_enabled:
        try:
            # Auto-save every 30 seconds by default
            settings = data_manager.load_settings() if data_manager else {}
            interval = settings.get('autosave_interval', 30)
            time.sleep(interval)
            
            if auto_save_enabled and data_manager:
                # Actually save data
                tasks = data_manager.load_tasks()
                data_manager.save_tasks(tasks)
                print("Auto-saved data successfully")
        except Exception as e:
            print(f"Auto-save error: {e}")

def start_auto_save():
    """Start the auto-save background thread"""
    global auto_save_thread, auto_save_enabled
    auto_save_enabled = True
    auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
    auto_save_thread.start()

def stop_auto_save():
    """Stop the auto-save background thread"""
    global auto_save_enabled
    auto_save_enabled = False

def scheduler_worker():
    """Background thread for scheduled tasks"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def setup_daily_reset():
    """Setup daily reset schedule"""
    if data_manager:
        settings = data_manager.load_settings()
        reset_time = settings.get('daily_reset_time', '09:00')
        schedule.every().day.at(reset_time).do(reset_daily_strikes_job)
        print(f"Daily reset scheduled for {reset_time}")

def reset_daily_strikes_job():
    """Job to reset daily strikes"""
    try:
        if data_manager:
            tasks = data_manager.load_tasks()
            today = datetime.now().strftime('%Y-%m-%d')
            
            for i, task in enumerate(tasks):
                if task.get('struck_today') and task.get('struck_date') != today:
                    tasks[i]['struck_today'] = False
                    tasks[i]['struck_date'] = None
            
            data_manager.save_tasks(tasks)
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
def setup_password():
    """Setup password for first run"""
    global data_manager, password_set
    
    if password_set:
        return jsonify({'error': 'Password already set'}), 400
    
    password_data = request.json
    password = password_data.get('password')
    
    print(f"Setup request received, password length: {len(password) if password else 0}")
    
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if this is truly a first run (no existing encrypted files)
    data_dir = "data"
    key_file = os.path.join(data_dir, ".key")
    salt_file = os.path.join(data_dir, ".salt")
    
    if os.path.exists(key_file) and os.path.exists(salt_file):
        return jsonify({'error': 'Password already exists. Please use login instead.'}), 400
    
    try:
        if initialize_data_manager(password):
            session['authenticated'] = True
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
    password = password_data.get('password')
    
    if not password:
        return jsonify({'error': 'Password required'}), 400
    
    try:
        # Try to initialize with provided password
        temp_manager = EncryptedDataManager(password=password)
        temp_manager.load_tasks()  # This will fail if password is wrong
        
        # If successful, initialize main data manager
        global data_manager, password_set
        data_manager = temp_manager
        password_set = True
        session['authenticated'] = True
        session['user_id'] = str(uuid.uuid4())
        
        # Generate session secret
        session_secret = security_manager.generate_session_secret(session['user_id'])
        session['session_secret'] = session_secret
        
        return jsonify({'success': True, 'message': 'Login successful', 'session_secret': session_secret})
    except Exception:
        return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    return jsonify({
        'authenticated': session.get('authenticated', False),
        'password_set': password_set
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout"""
    session.pop('authenticated', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/tasks', methods=['GET'])
@require_auth
def get_tasks():
    """Get all tasks"""
    tasks = data_manager.load_tasks()
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
        existing_tasks = data_manager.load_tasks()
        
        # Add imported tasks
        for task in imported_tasks:
            task['id'] = str(uuid.uuid4())
            task['created_at'] = datetime.now().isoformat()
            task['completed'] = False
            task['strike_count'] = 0
            task['struck_today'] = False
            existing_tasks.append(task)
        
        # Save all tasks
        if data_manager.save_tasks(existing_tasks):
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
def create_task():
    """Create a new task"""
    task_data = request.json
    tasks = data_manager.load_tasks()
    
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
    
    if data_manager.save_tasks(tasks):
        return jsonify(new_task), 201
    else:
        return jsonify({'error': 'Failed to save task'}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@require_auth
def update_task(task_id):
    """Update an existing task"""
    task_data = request.json
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i].update(task_data)
            if data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    """Delete a task"""
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            deleted_task = tasks.pop(i)
            if data_manager.save_tasks(tasks):
                return jsonify(deleted_task)
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
@require_auth
def complete_task(task_id):
    """Mark a task as completed"""
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['completed'] = True
            tasks[i]['completed_at'] = datetime.now().isoformat()
            if data_manager.save_tasks(tasks):
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
    
    tasks = data_manager.load_tasks()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if strike_type == 'today':
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
            
            if data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>/undo-strike', methods=['POST'])
@require_auth
def undo_strike(task_id):
    """Undo a strike for today"""
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if task.get('struck_today'):
                tasks[i]['struck_today'] = False
                tasks[i]['struck_date'] = None
                tasks[i]['strike_report'] = None
                # Don't decrease strike_count as it tracks total strikes
                
                if data_manager.save_tasks(tasks):
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
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            # Remove scheduling information
            tasks[i]['scheduled_hour'] = None
            tasks[i]['scheduled_date'] = None
            tasks[i]['duration'] = None
            
            if data_manager.save_tasks(tasks):
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
    
    tasks = data_manager.load_tasks()
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['scheduled_hour'] = hour
            tasks[i]['scheduled_date'] = date
            tasks[i]['duration'] = duration
            
            if data_manager.save_tasks(tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/reset-daily-strikes', methods=['POST'])
@require_auth
def reset_daily_strikes():
    """Reset all daily strikes (called by daily reset timer)"""
    tasks = data_manager.load_tasks()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        if task.get('struck_today') and task.get('struck_date') != today:
            tasks[i]['struck_today'] = False
            tasks[i]['struck_date'] = None
    
    if data_manager.save_tasks(tasks):
        return jsonify({'success': True, 'message': 'Daily strikes reset'})
    else:
        return jsonify({'error': 'Failed to reset daily strikes'}), 500

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """Get application settings"""
    settings = data_manager.load_settings()
    settings['autostart_enabled'] = autostart_manager.is_autostart_enabled()
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
    current_settings = data_manager.load_settings()
    current_settings.update(settings_data)
    
    # Handle autostart setting
    if 'autostart' in settings_data:
        if settings_data['autostart']:
            # Get the correct executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.join(os.path.dirname(__file__), "app.py")
            autostart_manager.enable_autostart(exe_path)
        else:
            autostart_manager.disable_autostart()
    
    if data_manager.save_settings(current_settings):
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
    if data_manager.change_password(new_password):
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    else:
        return jsonify({'error': 'Failed to change password'}), 500

@app.route('/api/planner/schedule', methods=['GET'])
@require_auth
def get_schedule():
    """Get daily schedule"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    tasks = data_manager.load_tasks()
    
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
    tasks = data_manager.load_tasks()
    
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
    
    if data_manager.save_tasks(tasks):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save schedule'}), 500

# Update Management Endpoints
@app.route('/api/updates/status', methods=['GET'])
@require_auth
def get_update_status():
    """Get current update status"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(update_manager.get_update_status())

@app.route('/api/updates/check', methods=['POST'])
@require_auth
def check_for_updates():
    """Check for available updates"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_info = update_manager.check_for_updates()
    if update_info:
        return jsonify({'update_available': True, 'update_info': update_info})
    else:
        return jsonify({'update_available': False})

@app.route('/api/updates/download', methods=['POST'])
@require_auth
def download_update():
    """Download available update"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_info = request.json
    if not update_info:
        return jsonify({'error': 'Update info required'}), 400
    
    def progress_callback(progress):
        # Could implement WebSocket or Server-Sent Events for real-time progress
        pass
    
    success = update_manager.download_update(update_info, progress_callback)
    if success:
        return jsonify({'success': True, 'message': 'Update downloaded successfully'})
    else:
        return jsonify({'error': 'Failed to download update'}), 500

@app.route('/api/updates/install', methods=['POST'])
@require_auth
def install_update():
    """Install downloaded update"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    update_data = request.json
    update_file = update_data.get('update_file')
    backup_data = update_data.get('backup_before_update', True)
    
    if not update_file:
        return jsonify({'error': 'Update file required'}), 400
    
    success = update_manager.install_update(update_file, backup_data)
    if success:
        return jsonify({'success': True, 'message': 'Update installed successfully. Please restart the application.'})
    else:
        return jsonify({'error': 'Failed to install update'}), 500

@app.route('/api/updates/config', methods=['GET'])
@require_auth
def get_update_config():
    """Get update configuration"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(update_manager.update_config)

@app.route('/api/updates/config', methods=['PUT'])
@require_auth
def update_update_config():
    """Update update configuration"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    config_data = request.json
    if not config_data:
        return jsonify({'error': 'Configuration data required'}), 400
    
    # Update configuration
    update_manager.update_config.update(config_data)
    update_manager._save_update_config(update_manager.update_config)
    
    return jsonify({'success': True, 'message': 'Configuration updated successfully'})

# Backup Management Endpoints
@app.route('/api/backups', methods=['GET'])
@require_auth
def get_backups():
    """Get list of available backups"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    backups = update_manager.get_backup_list()
    return jsonify({'backups': backups})

@app.route('/api/backups/create', methods=['POST'])
@require_auth
def create_backup():
    """Create manual backup"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    backup_data = request.json or {}
    backup_type = backup_data.get('type', 'manual')
    
    success = update_manager.create_backup(backup_type)
    if success:
        return jsonify({'success': True, 'message': 'Backup created successfully'})
    else:
        return jsonify({'error': 'Failed to create backup'}), 500

@app.route('/api/backups/restore', methods=['POST'])
@require_auth
def restore_backup():
    """Restore from backup"""
    if not update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    backup_data = request.json
    backup_name = backup_data.get('backup_name')
    
    if not backup_name:
        return jsonify({'error': 'Backup name required'}), 400
    
    success = update_manager.restore_backup(backup_name)
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
    print("🚀 Starting Shakshuka...")
    print("📱 Opening browser at http://127.0.0.1:8989")
    print("⏹️  Press Ctrl+C to stop the application")
    print()
    
    app.run(host='127.0.0.1', port=8989, debug=False)
