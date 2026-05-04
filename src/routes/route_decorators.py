"""
Route Decorators - Reusable decorators for route handlers
"""

from functools import wraps
from src.routes.api_response_helpers import error_response


def require_data_manager(func):
    """Decorator to ensure data manager is available and inject it
    
    Injects user_id and data_manager into the decorated function's kwargs.
    Returns 500 error if data manager is not available.
    
    Usage:
        @task_bp.route('/<task_id>/complete', methods=['POST'])
        @require_data_manager
        def complete_task(task_id, user_id, data_manager):
            # user_id and data_manager are already injected
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Import here to avoid circular imports
        from src.routes.task_routes import _get_user_id, _get_data_manager
        
        user_id = _get_user_id()
        data_manager = _get_data_manager()
        
        if not data_manager:
            return error_response('Data manager not available', 500)
        
        kwargs['user_id'] = user_id
        kwargs['data_manager'] = data_manager
        return func(*args, **kwargs)
    
    return wrapper


def require_json_body(func):
    """Decorator to ensure request has JSON body
    
    Returns 400 error if request body is not JSON.
    
    Usage:
        @task_bp.route('', methods=['POST'])
        @require_json_body
        def create_task():
            # request.json is guaranteed to be a dict
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request
        
        if not request.json or not isinstance(request.json, dict):
            return error_response('Request must contain JSON object', 400)
        
        return func(*args, **kwargs)
    
    return wrapper


def require_file_upload(field_name: str = 'file'):
    """Decorator to ensure file is uploaded
    
    Args:
        field_name: Name of the file field (default 'file')
    
    Returns 400 error if file is not provided.
    
    Usage:
        @task_bp.route('/import', methods=['POST'])
        @require_file_upload('file')
        def import_tasks():
            # request.files['file'] is guaranteed to exist
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            if field_name not in request.files:
                return error_response(f'No {field_name} provided', 400)
            
            file = request.files[field_name]
            if not file or file.filename == '':
                return error_response(f'No {field_name} selected', 400)
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def validate_input(validator_func):
    """Decorator to validate request input
    
    Args:
        validator_func: Function that takes request.json and returns (is_valid, error_message)
    
    Returns 400 error if validation fails.
    
    Usage:
        def validate_schedule(data):
            hour = data.get('hour')
            minute = data.get('minute', 0)
            return validate_schedule_input(hour, minute)
        
        @task_bp.route('/<task_id>/schedule', methods=['POST'])
        @validate_input(validate_schedule)
        def schedule_task(task_id):
            # request.json is guaranteed to be valid
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            if not request.json:
                return error_response('Request must contain JSON', 400)
            
            is_valid, error_message = validator_func(request.json)
            if not is_valid:
                return error_response(error_message, 400)
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def rate_limit(max_requests: int, window_seconds: int = 60):
    """Decorator to rate limit requests
    
    Args:
        max_requests: Maximum requests allowed
        window_seconds: Time window in seconds (default 60)
    
    Returns 429 error if rate limit exceeded.
    
    Usage:
        @task_bp.route('/import', methods=['POST'])
        @rate_limit(max_requests=10, window_seconds=60)
        def import_tasks():
            # Limited to 10 requests per 60 seconds
            ...
    """
    def decorator(func):
        # Simple in-memory rate limiting (not suitable for distributed systems)
        request_times = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            from datetime import datetime, timedelta
            
            # Get client IP
            client_ip = request.remote_addr
            key = f"{client_ip}:{func.__name__}"
            
            now = datetime.now()
            
            # Clean old requests
            if key in request_times:
                request_times[key] = [
                    t for t in request_times[key]
                    if (now - t).total_seconds() < window_seconds
                ]
            else:
                request_times[key] = []
            
            # Check rate limit
            if len(request_times[key]) >= max_requests:
                return error_response(
                    f'Rate limit exceeded: {max_requests} requests per {window_seconds} seconds',
                    429
                )
            
            # Record request
            request_times[key].append(now)
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def handle_database_error(func):
    """Decorator to handle database errors
    
    Catches DatabaseError and returns 503 response.
    
    Usage:
        @task_bp.route('/<task_id>', methods=['GET'])
        @handle_database_error
        def get_task(task_id):
            # DatabaseError is automatically caught and converted to 503
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from src.exceptions import DatabaseError
        
        try:
            return func(*args, **kwargs)
        except DatabaseError as e:
            return error_response(str(e), 503, {'error_type': 'DatabaseError'})
    
    return wrapper
