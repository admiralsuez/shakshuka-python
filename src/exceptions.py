"""
Custom exceptions for Shakshuka application
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AppError(Exception):
    message: str
    code: str = 'app_error'
    status_code: int = 500
    details: Optional[Dict[str, Any]] = None
    public_message: Optional[str] = None
    cause: Optional[BaseException] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            'error': self.public_message or self.message,
            'code': self.code,
        }
        if self.details:
            payload['details'] = self.details
        return payload


class DatabaseError(AppError):
    def __init__(
        self,
        message: str = 'Database error',
        *,
        code: str = 'database_error',
        status_code: int = 503,
        details: Optional[Dict[str, Any]] = None,
        public_message: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
            public_message=public_message,
            cause=cause,
        )


class ValidationError(AppError):
    def __init__(
        self,
        message: str = 'Validation error',
        *,
        code: str = 'validation_error',
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        public_message: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
            public_message=public_message,
            cause=cause,
        )


class AuthError(AppError):
    def __init__(
        self,
        message: str = 'Authentication error',
        *,
        code: str = 'auth_error',
        status_code: int = 401,
        details: Optional[Dict[str, Any]] = None,
        public_message: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
            public_message=public_message,
            cause=cause,
        )


class SchedulerError(AppError):
    def __init__(
        self,
        message: str = 'Scheduler error',
        *,
        code: str = 'scheduler_error',
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        public_message: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
            public_message=public_message,
            cause=cause,
        )


class ShakshukaException(AppError):
    def __init__(
        self,
        message: str = 'Application error',
        *,
        code: str = 'shakshuka_error',
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        public_message: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
            public_message=public_message,
            cause=cause,
        )


class DataManagerException(ShakshukaException):
    """Exception raised for data manager errors"""
    def __init__(self, message: str = 'Data manager error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, code='data_manager_error', status_code=500, cause=cause)


class ValidationException(ValidationError):
    def __init__(self, message: str = 'Validation error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, cause=cause)


class DatabaseException(DatabaseError):
    def __init__(self, message: str = 'Database error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, cause=cause)


class AuthenticationException(AuthError):
    def __init__(self, message: str = 'Authentication error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, cause=cause)


class ConfigurationException(ShakshukaException):
    """Exception raised for configuration errors"""
    def __init__(self, message: str = 'Configuration error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, code='configuration_error', status_code=500, cause=cause)


class UserNotFoundException(DataManagerException):
    """Exception raised when user is not found"""
    def __init__(self, message: str = 'User not found', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, cause=cause)


class TaskNotFoundException(DataManagerException):
    """Exception raised when task is not found"""
    def __init__(self, message: str = 'Task not found', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, cause=cause)


class SettingsError(ShakshukaException):
    """Exception raised for settings load/save failures"""
    def __init__(self, message: str = 'Settings error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, code='settings_error', status_code=500, cause=cause)


class AutostartError(ShakshukaException):
    """Exception raised for autostart enable/disable failures"""
    def __init__(self, message: str = 'Autostart error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, code='autostart_error', status_code=500, cause=cause)


class ServiceError(ShakshukaException):
    """Exception raised for background service failures"""
    def __init__(self, message: str = 'Service error', *, cause: Optional[BaseException] = None):
        super().__init__(message=message, code='service_error', status_code=500, cause=cause)
