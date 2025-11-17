"""
Authentication Middleware - Handles authentication requirements
"""
from functools import wraps
from flask import request, jsonify, session
from datetime import datetime, timedelta
import logging

from src.core import config

logger = logging.getLogger(__name__)


def get_user_id():
    """
    Get the current user ID from session or return default user.
    Handles both authenticated and non-authenticated modes.
    """
    if config.AUTH_ENABLED:
        user_id = session.get('user_id')
        if not user_id:
            logger.warning("No user_id in session despite auth being enabled")
            return None
        return user_id
    else:
        # Authentication disabled - use default user
        return config.DEFAULT_USER


def require_auth(f):
    """
    Decorator to require authentication for routes.
    Returns 401 if user is not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if config.AUTH_ENABLED:
            user_id = session.get('user_id')
            if not user_id:
                logger.warning(f"Unauthorized access attempt to {request.path}")
                return jsonify({'error': 'Unauthorized. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function


def optional_auth(f):
    """
    Decorator for routes that work with or without authentication.
    Sets user_id in kwargs if available.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        kwargs['user_id'] = get_user_id()
        return f(*args, **kwargs)
    return decorated_function


def check_session_valid():
    """
    Check if the current session is valid.
    Returns True if valid, False otherwise.
    """
    if not config.AUTH_ENABLED:
        return True
    
    user_id = session.get('user_id')
    if not user_id:
        return False
    
    # Check session expiry
    session_created = session.get('created_at')
    if session_created:
        try:
            created_dt = datetime.fromisoformat(session_created)
            expiry = created_dt + timedelta(hours=config.SESSION_LIFETIME_HOURS)
            if datetime.now() > expiry:
                logger.info(f"Session expired for user {user_id}")
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"Error checking session expiry: {e}")
            return False
    
    return True


def extend_session():
    """
    Extend the current session by updating the last activity time.
    """
    if config.AUTH_ENABLED and session.get('user_id'):
        session['last_activity'] = datetime.now().isoformat()
        session.modified = True

