"""
Enhanced logging and error handling for Shakshuka application
"""
import logging
import logging.handlers
import os
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
import json

class ShakshukaLogger:
    """Enhanced logger with structured logging and error tracking"""
    
    def __init__(self, name: str, log_file: str = 'logs/shakshuka.log', 
                 max_size: int = 10 * 1024 * 1024, backup_count: int = 10):
        self.name = name
        self.log_file = log_file
        
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.INFO)
        
        # Error file handler
        error_file = log_file.replace('.log', '_errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=max_size,
            backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
        )
        
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message"""
        if extra:
            self.logger.info(f"{message} | Extra: {json.dumps(extra)}")
        else:
            self.logger.info(message)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        if extra:
            self.logger.warning(f"{message} | Extra: {json.dumps(extra)}")
        else:
            self.logger.warning(message)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log error message"""
        if extra:
            self.logger.error(f"{message} | Extra: {json.dumps(extra)}", exc_info=exc_info)
        else:
            self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log critical message"""
        if extra:
            self.logger.critical(f"{message} | Extra: {json.dumps(extra)}", exc_info=exc_info)
        else:
            self.logger.critical(message, exc_info=exc_info)
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        if extra:
            self.logger.debug(f"{message} | Extra: {json.dumps(extra)}")
        else:
            self.logger.debug(message)

class ErrorHandler:
    """Centralized error handling"""
    
    def __init__(self, logger: ShakshukaLogger):
        self.logger = logger
        self.error_count = 0
        self.last_error_time = None
    
    def handle_exception(self, exception: Exception, context: str = "", 
                        extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an exception with proper logging and context"""
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        error_id = f"ERR_{self.error_count}_{int(datetime.now().timestamp())}"
        
        error_info = {
            'error_id': error_id,
            'type': type(exception).__name__,
            'message': str(exception),
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'traceback': traceback.format_exc()
        }
        
        if extra:
            error_info['extra'] = extra
        
        # Log the error
        self.logger.error(
            f"Exception in {context}: {str(exception)}",
            extra={'error_id': error_id, 'error_type': type(exception).__name__},
            exc_info=True
        )
        
        return error_info
    
    def handle_validation_error(self, field: str, value: Any, 
                              expected_type: str, context: str = "") -> Dict[str, Any]:
        """Handle validation errors"""
        error_info = {
            'type': 'ValidationError',
            'field': field,
            'value': str(value),
            'expected_type': expected_type,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.warning(
            f"Validation error in {context}: {field} = {value} (expected {expected_type})",
            extra=error_info
        )
        
        return error_info
    
    def handle_data_error(self, operation: str, file_path: str, 
                         error: Exception) -> Dict[str, Any]:
        """Handle data-related errors"""
        error_info = {
            'type': 'DataError',
            'operation': operation,
            'file_path': file_path,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.error(
            f"Data error during {operation} on {file_path}: {str(error)}",
            extra=error_info,
            exc_info=True
        )
        
        return error_info

# Global logger instance
app_logger = ShakshukaLogger('shakshuka')
error_handler = ErrorHandler(app_logger)

def setup_logging(app):
    """Setup logging for Flask app"""
    # Disable Flask's default logging
    app.logger.disabled = True
    
    # Set up our custom logger
    app.logger = app_logger.logger
    
    # Log app startup
    app_logger.info("Shakshuka application started", extra={
        'version': '1.0.0',
        'environment': os.getenv('FLASK_ENV', 'production'),
        'debug': app.debug
    })

def log_request_info(request, response=None):
    """Log request information"""
    extra = {
        'method': request.method,
        'url': request.url,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'content_length': request.content_length or 0
    }
    
    if response:
        extra['status_code'] = response.status_code
        extra['response_size'] = response.content_length or 0
    
    app_logger.info(f"Request: {request.method} {request.url}", extra=extra)

def log_security_event(event_type: str, details: Dict[str, Any]):
    """Log security-related events"""
    app_logger.warning(f"Security event: {event_type}", extra={
        'event_type': event_type,
        'timestamp': datetime.now().isoformat(),
        **details
    })

