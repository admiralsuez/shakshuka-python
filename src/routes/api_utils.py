from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional, Tuple, Type, Union

from flask import Blueprint, jsonify, request

from src.core.correlation import get_correlation_id
from src.exceptions import AppError, AuthError, DatabaseError, ValidationError


logger = logging.getLogger(__name__)


def get_json_object(*, required: bool = True) -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        if required:
            raise ValidationError(message='Request must contain JSON object')
        return {}
    if not isinstance(data, dict):
        raise ValidationError(message='Request must contain JSON object')
    return data


def require_field(data: Dict[str, Any], key: str, expected_type: Union[Type[Any], Tuple[Type[Any], ...]]) -> Any:
    if key not in data:
        raise ValidationError(message=f"Missing required field: {key}")
    value = data.get(key)
    if not isinstance(value, expected_type):
        raise ValidationError(message=f"Invalid type for {key}", details={'field': key, 'expected': _type_name(expected_type), 'actual': type(value).__name__})
    return value


def optional_field(data: Dict[str, Any], key: str, expected_type: Union[Type[Any], Tuple[Type[Any], ...]], default: Any = None) -> Any:
    if key not in data:
        return default
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, expected_type):
        raise ValidationError(message=f"Invalid type for {key}", details={'field': key, 'expected': _type_name(expected_type), 'actual': type(value).__name__})
    return value


def require_dependency(obj: Any, name: str) -> Any:
    if obj is None:
        raise DatabaseError(message=f"{name} not available", details={'dependency': name})
    return obj


def register_api_error_handlers(bp: Blueprint) -> None:
    def _wants_json() -> bool:
        try:
            if request.path.startswith('/api/'):
                return True
            best = request.accept_mimetypes.best
            if best is None:
                return False
            return best == 'application/json'
        except Exception:  # noqa: broad-except - defensive: MIME negotiation failures default to JSON
            return True

    @bp.errorhandler(ValidationError)
    def _handle_validation_error(error: ValidationError):
        logging.getLogger(bp.name).exception("Validation error")
        if _wants_json():
            return jsonify({'success': False, 'request_id': get_correlation_id(), **error.to_dict()}), 400
        return (error.public_message or error.message), 400

    @bp.errorhandler(AuthError)
    def _handle_auth_error(error: AuthError):
        logging.getLogger(bp.name).exception("Auth error")
        if _wants_json():
            return jsonify({'success': False, 'request_id': get_correlation_id(), **error.to_dict()}), error.status_code
        return (error.public_message or error.message), error.status_code

    @bp.errorhandler(DatabaseError)
    def _handle_database_error(error: DatabaseError):
        logging.getLogger(bp.name).exception("Database/system error")
        if _wants_json():
            return jsonify({'success': False, 'request_id': get_correlation_id(), **error.to_dict()}), 503
        return (error.public_message or error.message), 503

    @bp.errorhandler(AppError)
    def _handle_app_error(error: AppError):
        logging.getLogger(bp.name).exception("Application error")
        if _wants_json():
            return jsonify({'success': False, 'request_id': get_correlation_id(), **error.to_dict()}), error.status_code
        return (error.public_message or error.message), error.status_code

    @bp.errorhandler(Exception)
    def _handle_unexpected_error(error: Exception):
        logging.getLogger(bp.name).exception("Unhandled error")
        if _wants_json():
            return jsonify({'success': False, 'request_id': get_correlation_id(), 'error': 'Internal server error', 'code': 'internal_error'}), 500
        return 'Internal server error', 500


def _type_name(t: Union[Type[Any], Tuple[Type[Any], ...]]) -> str:
    if isinstance(t, tuple):
        return '|'.join(x.__name__ for x in t)
    return t.__name__
