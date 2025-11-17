"""
Task Routes - All task management endpoints

This module handles:
- Task CRUD operations (GET, POST, PUT, DELETE)
- Task actions (complete, strike, undo-strike, schedule, unschedule)
- Task imports from CSV/TXT files
- Daily strike resets
"""

from flask import Blueprint, request, jsonify
import logging
import uuid
import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple

# Import app context and utilities (will be injected)
from src.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# Blueprint definition
task_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

# These will be injected at runtime
_app_context = None
_get_user_id_func = None
_ensure_data_manager_func = None
_sanitize_input_func = None
_validate_task_data_func = None
_rate_limit_decorator = None


def init_task_routes(app_context, get_user_id_func, ensure_data_manager_func, 
                     sanitize_input_func, validate_task_data_func, rate_limit_decorator):
    """Initialize task routes with dependency injection"""
    global _app_context, _get_user_id_func, _ensure_data_manager_func
    global _sanitize_input_func, _validate_task_data_func, _rate_limit_decorator
    
    _app_context = app_context
    _get_user_id_func = get_user_id_func
    _ensure_data_manager_func = ensure_data_manager_func
    _sanitize_input_func = sanitize_input_func
    _validate_task_data_func = validate_task_data_func
    _rate_limit_decorator = rate_limit_decorator


def _get_user_id():
    """Get current user ID"""
    if _get_user_id_func:
        return _get_user_id_func()
    return DEFAULT_USER_ID


def _get_data_manager():
    """Get data manager instance"""
    return _app_context.data_manager if _app_context else None


@task_bp.route('', methods=['GET'])
def get_tasks():
    """Get all tasks for the current user"""
    user_id = _get_user_id()
    logger.info(f"API get_tasks called with user_id: {user_id}")
    
    try:
        # Ensure data manager is initialized
        if _ensure_data_manager_func and not _ensure_data_manager_func():
            logger.error("Data manager not initialized")
            return jsonify([])
        
        data_manager = _get_data_manager()
        if not data_manager:
            return jsonify([])
        
        tasks = data_manager.load_tasks(user_id)
        logger.info(f"Loaded {len(tasks)} tasks for user {user_id}")
        return jsonify(tasks)
    except Exception as e:
        logger.error(f"Error loading tasks for user {user_id}: {e}")
        return jsonify([])


@task_bp.route('/import', methods=['POST'])
def import_tasks():
    """Import tasks from CSV or TXT file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '' or not file:
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read file content
        file_content = file.read().decode('utf-8')
        file_extension = file.filename.lower().split('.')[-1]
        
        imported_tasks = []
        errors = []
        
        if file_extension == 'csv':
            imported_tasks, errors = _parse_csv_tasks(file_content)
        elif file_extension == 'txt':
            imported_tasks, errors = _parse_txt_tasks(file_content)
        else:
            return jsonify({'error': 'Unsupported file format. Please use CSV or TXT.'}), 400
        
        if not imported_tasks:
            return jsonify({'error': 'No valid tasks found in file', 'details': errors}), 400
        
        # Load existing tasks for the user
        user_id = _get_user_id()
        data_manager = _get_data_manager()
        if not data_manager:
            return jsonify({'error': 'Data manager not available'}), 500
        
        existing_tasks = data_manager.load_tasks(user_id)
        
        # Add imported tasks
        for task in imported_tasks:
            task['id'] = str(uuid.uuid4())
            task['created_at'] = datetime.now().isoformat()
            task['completed'] = False
            task['strike_count'] = 0
            task['struck_today'] = False
            existing_tasks.append(task)
        
        # Save all tasks for the user
        if data_manager.save_tasks(user_id, existing_tasks):
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


def _parse_csv_tasks(content: str) -> Tuple[List[Dict], List[str]]:
    """Parse CSV content and return tasks and errors"""
    tasks = []
    errors = []
    
    try:
        csv_file = io.StringIO(content)
        reader = csv.DictReader(csv_file)
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # Sanitize input
                if _sanitize_input_func:
                    row = _sanitize_input_func(row)
                
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


def _parse_txt_tasks(content: str) -> Tuple[List[Dict], List[str]]:
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
                if _sanitize_input_func:
                    line = _sanitize_input_func(line)
                
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


@task_bp.route('', methods=['POST'])
def create_task():
    """Create a new task with comprehensive validation and error handling"""
    user_id = _get_user_id()
    logger.info(f"API create_task called with user_id: {user_id}")
    
    try:
        if not request.json:
            return jsonify({'error': 'Request must contain JSON data'}), 400
        
        task_data = request.json
        
        # Sanitize input data
        if _sanitize_input_func:
            task_data = _sanitize_input_func(task_data)
        
        # Comprehensive validation
        if _validate_task_data_func:
            is_valid, error_message = _validate_task_data_func(task_data)
            if not is_valid:
                logger.warning(f"Task validation failed for user {user_id}: {error_message}")
                return jsonify({'error': error_message}), 400
        
        # Ensure data manager is available
        data_manager = _get_data_manager()
        if not data_manager:
            logger.error(f"Data manager not available for user {user_id}")
            return jsonify({'error': 'Data manager not available'}), 500
        
        # Create task using data manager
        created_task = data_manager.create_task_for_user(user_id, task_data)
        
        if created_task:
            logger.info(f"Successfully created task {created_task['id']} for user {user_id}")
            return jsonify(created_task), 201
        else:
            logger.error(f"Failed to create task for user {user_id}")
            return jsonify({'error': 'Failed to create task'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in create_task for user {user_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@task_bp.route('/<task_id>', methods=['PUT'])
def update_task(task_id):
    """Update an existing task with comprehensive validation and error handling"""
    user_id = _get_user_id()
    logger.info(f"API update_task called for task {task_id} with user_id: {user_id}")
    
    try:
        if not request.json:
            return jsonify({'error': 'Request must contain JSON data'}), 400
        
        task_data = request.json
        
        # Sanitize input data
        if _sanitize_input_func:
            task_data = _sanitize_input_func(task_data)
        
        # Comprehensive validation
        if _validate_task_data_func:
            is_valid, error_message = _validate_task_data_func(task_data)
            if not is_valid:
                logger.warning(f"Task validation failed for user {user_id}: {error_message}")
                return jsonify({'error': error_message}), 400
        
        # Ensure data manager is available
        data_manager = _get_data_manager()
        if not data_manager:
            logger.error(f"Data manager not available for user {user_id}")
            return jsonify({'error': 'Data manager not available'}), 500
        
        # Update task using data manager
        success = data_manager.update_task_for_user(user_id, task_id, task_data)
        
        if success:
            # Return updated task directly from database
            updated_task = data_manager.get_task_by_id(user_id, task_id)
            if updated_task:
                logger.info(f"Successfully updated task {task_id} for user {user_id}")
                return jsonify(updated_task)
            
            logger.error(f"Task {task_id} not found after update for user {user_id}")
            return jsonify({'error': 'Task not found after update'}), 500
        else:
            logger.error(f"Failed to update task {task_id} for user {user_id}")
            return jsonify({'error': 'Failed to update task'}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in update_task for user {user_id}, task {task_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@task_bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task with comprehensive error handling"""
    user_id = _get_user_id()
    logger.info(f"API delete_task called for task {task_id} with user_id: {user_id}")
    
    try:
        if not task_id or not isinstance(task_id, str):
            return jsonify({'error': 'Invalid task ID'}), 400
        
        # Ensure data manager is available
        data_manager = _get_data_manager()
        if not data_manager:
            logger.error(f"Data manager not available for user {user_id}")
            return jsonify({'error': 'Data manager not available'}), 500
        
        # Get task before deletion for response
        task_to_delete = data_manager.get_task_by_id(user_id, task_id)
        
        if not task_to_delete:
            logger.warning(f"Task {task_id} not found for user {user_id}")
            return jsonify({'error': 'Task not found'}), 404
        
        # Delete task using data manager
        success = data_manager.delete_task_for_user(user_id, task_id)
        
        if success:
            logger.info(f"Successfully deleted task {task_id} for user {user_id}")
            return jsonify(task_to_delete)
        else:
            logger.error(f"Failed to delete task {task_id} for user {user_id}")
            return jsonify({'error': 'Failed to delete task'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in delete_task for user {user_id}, task {task_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@task_bp.route('/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """Mark a task as completed for the authenticated user"""
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    tasks = data_manager.load_tasks_for_user(user_id)
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['completed'] = True
            tasks[i]['completed_at'] = datetime.utcnow().isoformat()
            if data_manager.save_tasks_for_user(user_id, tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save task'}), 500
    
    return jsonify({'error': 'Task not found'}), 404


@task_bp.route('/<task_id>/strike', methods=['POST'])
def strike_task(task_id):
    """Unified strike endpoint for both today and forever"""
    user_id = _get_user_id()
    strike_data = request.json or {}
    strike_type = strike_data.get('type')
    report = strike_data.get('report', '')
    
    if not strike_type or strike_type not in ['today', 'forever']:
        return jsonify({'error': 'Invalid strike type'}), 400
    
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    tasks = data_manager.load_tasks_for_user(user_id)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
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
                tasks[i]['completed_at'] = datetime.utcnow().isoformat()
                tasks[i]['struck_today'] = True
                tasks[i]['struck_date'] = today
                tasks[i]['strike_report'] = report
                tasks[i]['strike_count'] = tasks[i].get('strike_count', 0) + 1
            
            if data_manager.save_tasks_for_user(user_id, tasks):
                # Increment analytics counters (decoupled from daily reset)
                try:
                    from src.utils.paths import get_user_data_dir
                    import json, os
                    analytics_path = os.path.join(get_user_data_dir(), 'analytics.json')
                    analytics = {'today_date': today, 'today_strikes': 0, 'total_strikes': 0}
                    if os.path.exists(analytics_path):
                        try:
                            with open(analytics_path, 'r', encoding='utf-8') as f:
                                analytics = json.load(f) or analytics
                        except Exception:
                            pass
                    # Roll over if stored date != today
                    if analytics.get('today_date') != today:
                        analytics['today_date'] = today
                        analytics['today_strikes'] = 0
                    analytics['today_strikes'] = int(analytics.get('today_strikes', 0)) + 1
                    analytics['total_strikes'] = int(analytics.get('total_strikes', 0)) + 1
                    os.makedirs(os.path.dirname(analytics_path), exist_ok=True)
                    with open(analytics_path, 'w', encoding='utf-8') as f:
                        json.dump(analytics, f)
                except Exception as _e:
                    # Non-fatal; analytics are best-effort
                    pass
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404


@task_bp.route('/<task_id>/undo-strike', methods=['POST'])
def undo_strike(task_id):
    """Undo a strike for today for the authenticated user"""
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    tasks = data_manager.load_tasks_for_user(user_id)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if task.get('struck_today'):
                # Check if this was a "strike forever" (completed task)
                was_completed = task.get('completed', False)
                
                if was_completed:
                    # Undo strike forever - revert to incomplete state
                    tasks[i]['completed'] = False
                    tasks[i]['completed_at'] = None
                    tasks[i]['struck_today'] = False
                    tasks[i]['struck_date'] = None
                    tasks[i]['strike_report'] = None
                    tasks[i]['strike_count'] = max(0, tasks[i].get('strike_count', 0) - 1)
                else:
                    # Undo regular strike today
                    daily_strikes = task.get("daily_strikes", {})
                    strikes_today = daily_strikes.get(today, 0)
                    if strikes_today > 0:
                        daily_strikes[today] = strikes_today - 1
                        tasks[i]["daily_strikes"] = daily_strikes
                    
                    # If no more strikes today, mark as not struck
                    if daily_strikes.get(today, 0) == 0:
                        tasks[i]["struck_today"] = False
                        tasks[i]["struck_date"] = None
                        tasks[i]["strike_report"] = None
                
                if data_manager.save_tasks_for_user(user_id, tasks):
                    return jsonify(tasks[i])
                else:
                    return jsonify({'error': 'Failed to save tasks'}), 500
            else:
                return jsonify({'error': 'Task is not struck for today'}), 400
    
    return jsonify({'error': 'Task not found'}), 404


@task_bp.route('/<task_id>/unschedule', methods=['POST'])
def unschedule_task(task_id):
    """Remove a task from the daily planner for the authenticated user"""
    user_id = _get_user_id()
    
    # Validate task_id format
    if not task_id or not isinstance(task_id, str) or len(task_id.strip()) == 0:
        return jsonify({'error': 'Invalid task ID'}), 400
    
    try:
        data_manager = _get_data_manager()
        if not data_manager:
            return jsonify({'error': 'Data manager not available'}), 500
        
        tasks = data_manager.load_tasks(user_id)
        
        for i, task in enumerate(tasks):
            if task['id'] == task_id:
                # Remove scheduling information
                tasks[i]['scheduled_hour'] = None
                tasks[i]['scheduled_minute'] = None
                tasks[i]['scheduled_date'] = None
                tasks[i]['scheduled_duration'] = None
                
                if data_manager.save_tasks_for_user(user_id, tasks):
                    return jsonify(tasks[i])
                else:
                    return jsonify({'error': 'Failed to save tasks'}), 500
        
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"Error unscheduling task {task_id} for user {user_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@task_bp.route('/<task_id>/schedule', methods=['POST'])
def schedule_task(task_id):
    """Schedule a task for a specific hour and duration for the authenticated user"""
    user_id = _get_user_id()
    schedule_data = request.json or {}
    logger.info(f"RAW schedule_data received: {schedule_data}")
    
    hour_input = schedule_data.get('hour')
    minute = schedule_data.get('minute', 0)
    duration = schedule_data.get('duration', 30)
    date = schedule_data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    logger.info(f"Extracted: hour_input={hour_input} (type={type(hour_input).__name__}), minute={minute}, duration={duration}, date={date}")
    
    if hour_input is None:
        return jsonify({'error': 'Hour is required'}), 400
    
    # Parse hour - can be either "HH:MM" string or numeric hour
    if isinstance(hour_input, str) and ':' in hour_input:
        logger.info(f"Parsing HH:MM format: {hour_input}")
        parts = hour_input.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        logger.info(f"Parsed to hour={hour}, minute={minute}")
    else:
        logger.info(f"Using numeric hour: {hour_input}")
        hour = int(hour_input)
    
    logger.info(f"FINAL: Scheduling task {task_id} at {hour}:{minute} on {date} for {duration} minutes")
    
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    tasks = data_manager.load_tasks(user_id)
    
    # Check for conflicts with existing scheduled tasks
    start_minutes = hour * 60 + minute
    end_minutes = start_minutes + duration
    
    for task in tasks:
        # Skip the task being scheduled and unscheduled tasks
        if task['id'] == task_id or not task.get('scheduled_date'):
            continue
        
        # Only check tasks on the same date
        if task.get('scheduled_date') != date:
            continue
        
        task_start_minutes = task.get('scheduled_hour', 0) * 60 + task.get('scheduled_minute', 0)
        task_duration = task.get('scheduled_duration', 30)
        task_end_minutes = task_start_minutes + task_duration
        
        # Check if there's an overlap
        if (start_minutes < task_end_minutes and end_minutes > task_start_minutes):
            conflict_hour = task.get('scheduled_hour')
            conflict_minute = task.get('scheduled_minute', 0)
            conflict_time = f"{conflict_hour}:{conflict_minute:02d}"
            
            logger.warning(f"Schedule conflict: Task {task_id} conflicts with {task['id']} at {conflict_time}")
            return jsonify({
                'error': 'Time slot conflict',
                'message': f"Conflicts with '{task['title']}' at {conflict_time}",
                'conflict_task': task['title'],
                'conflict_time': conflict_time
            }), 409
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['scheduled_hour'] = hour
            tasks[i]['scheduled_minute'] = minute
            tasks[i]['scheduled_date'] = date
            tasks[i]['scheduled_duration'] = duration
            
            logger.info(f"Task {task_id} scheduled: hour={hour}, minute={minute}, date={date}, duration={duration}")
            
            if data_manager.save_tasks_for_user(user_id, tasks):
                return jsonify(tasks[i])
            else:
                return jsonify({'error': 'Failed to save tasks'}), 500
    
    return jsonify({'error': 'Task not found'}), 404


@task_bp.route('/reset-daily-strikes', methods=['POST'])
def reset_daily_strikes():
    """Reset all daily strikes and clean overdue schedule for the authenticated user (local time)."""
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    tasks = data_manager.load_tasks(user_id)
    now = datetime.now()
    today_local = now.strftime('%Y-%m-%d')
    
    reset_count = 0
    unscheduled = 0
    
    for i, task in enumerate(tasks):
        # Clean the rolling daily_strikes dict (keep recent 7 days) if present
        if 'daily_strikes' in task:
            daily_strikes = task.get('daily_strikes', {})
            cleaned_strikes = {}
            for strike_date in list(daily_strikes.keys()):
                try:
                    strike_datetime = datetime.strptime(strike_date, '%Y-%m-%d')
                    today_datetime = datetime.strptime(today_local, '%Y-%m-%d')
                    days_diff = (today_datetime - strike_datetime).days
                    if days_diff <= 7:
                        cleaned_strikes[strike_date] = daily_strikes[strike_date]
                except ValueError:
                    pass
            tasks[i]['daily_strikes'] = cleaned_strikes
        
        # Clear today's strike flags unconditionally for new day
        if task.get('struck_today'):
            tasks[i]['struck_today'] = False
            tasks[i]['struck_date'] = None
            tasks[i]['strike_report'] = None
            reset_count += 1
    
    # Unschedule previous-day tasks that aren't completed
    for i, t in enumerate(tasks):
        sd = t.get('scheduled_date')
        if sd and sd < today_local:
            tasks[i]['scheduled_hour'] = None
            tasks[i]['scheduled_minute'] = None
            tasks[i]['scheduled_date'] = None
            tasks[i]['scheduled_duration'] = None
            unscheduled += 1
    
    if data_manager.save_tasks_for_user(user_id, tasks):
        return jsonify({'success': True, 'message': 'Daily reset completed', 'strikes_cleared': reset_count, 'unscheduled': unscheduled})
    else:
        return jsonify({'error': 'Failed to reset daily strikes'}), 500
