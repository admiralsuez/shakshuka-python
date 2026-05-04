"""
API Response Helpers - Standardized error and success responses
"""

from flask import jsonify
from typing import Dict, Tuple, Optional, Any


def error_response(message: str, code: int = 400, details: Optional[Dict[str, Any]] = None) -> Tuple[Dict, int]:
    """Standardized error response format
    
    Args:
        message: Error message
        code: HTTP status code (default 400)
        details: Optional additional details
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return jsonify({
        'success': False,
        'error': message,
        'details': details or {}
    }), code


def success_response(data: Optional[Dict[str, Any]] = None, message: Optional[str] = None) -> Dict:
    """Standardized success response format
    
    Args:
        data: Response data
        message: Optional success message
    
    Returns:
        Response dictionary
    """
    response = {'success': True}
    if message:
        response['message'] = message
    if data:
        response.update(data)
    return jsonify(response)


def validation_error(field: str, message: str) -> Tuple[Dict, int]:
    """Validation error response
    
    Args:
        field: Field that failed validation
        message: Error message
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return error_response(
        f"Validation error: {message}",
        400,
        {'field': field}
    )


def not_found_error(resource: str, resource_id: str = None) -> Tuple[Dict, int]:
    """Not found error response
    
    Args:
        resource: Resource type (e.g., 'Task', 'Note')
        resource_id: Optional resource ID
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    message = f"{resource} not found"
    details = {}
    if resource_id:
        message += f": {resource_id}"
        details['resource_id'] = resource_id
    
    return error_response(message, 404, details)


def conflict_error(message: str, details: Optional[Dict] = None) -> Tuple[Dict, int]:
    """Conflict error response (409)
    
    Args:
        message: Conflict message
        details: Optional additional details
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return error_response(message, 409, details)


def server_error(message: str = "Internal server error", details: Optional[Dict] = None) -> Tuple[Dict, int]:
    """Server error response (500)
    
    Args:
        message: Error message
        details: Optional additional details
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return error_response(message, 500, details)


def database_error(message: str = "Database error", details: Optional[Dict] = None) -> Tuple[Dict, int]:
    """Database error response (503)
    
    Args:
        message: Error message
        details: Optional additional details
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return error_response(message, 503, details)
