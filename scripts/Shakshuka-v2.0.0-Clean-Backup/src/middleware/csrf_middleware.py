"""
CSRF Protection Middleware
"""
from functools import wraps
from flask import request, jsonify
import secrets
import time
import logging

from src.core import app_context, config

logger = logging.getLogger(__name__)

# CSRF token store (in-memory, could be moved to Redis for production)
csrf_tokens = {}
CSRF_TOKEN_EXPIRY = 3600  # 1 hour


def generate_csrf_token():
    """Generate a new CSRF token"""
    token = secrets.token_urlsafe(32)
    csrf_tokens[token] = time.time()
    
    # Clean up expired tokens
    current_time = time.time()
    expired_tokens = [t for t, created in csrf_tokens.items() 
                     if current_time - created > CSRF_TOKEN_EXPIRY]
    for token in expired_tokens:
        del csrf_tokens[token]
    
    return token


def validate_csrf_token(token):
    """Validate a CSRF token"""
    if not token:
        return False
    
    if token not in csrf_tokens:
        return False
    
    # Check if token is expired
    created_time = csrf_tokens[token]
    if time.time() - created_time > CSRF_TOKEN_EXPIRY:
        del csrf_tokens[token]
        return False
    
    return True


def require_csrf(f):
    """
    Decorator to require CSRF token for state-changing operations.
    Checks for token in X-CSRF-Token header or csrf_token form field.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.CSRF_ENABLED:
            return f(*args, **kwargs)
        
        # GET requests don't need CSRF protection
        if request.method == 'GET':
            return f(*args, **kwargs)
        
        # Get token from header or form data
        token = request.headers.get('X-CSRF-Token')
        if not token and request.is_json:
            token = request.json.get('csrf_token')
        elif not token:
            token = request.form.get('csrf_token')
        
        if not validate_csrf_token(token):
            logger.warning(f"CSRF token validation failed for {request.path}")
            return jsonify({'error': 'Invalid or expired CSRF token'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

