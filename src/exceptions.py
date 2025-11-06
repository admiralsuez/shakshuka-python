"""
Custom exceptions for Shakshuka application
"""


class ShakshukaException(Exception):
    """Base exception for all Shakshuka errors"""
    pass


class DataManagerException(ShakshukaException):
    """Exception raised for data manager errors"""
    pass


class ValidationException(ShakshukaException):
    """Exception raised for validation errors"""
    pass


class DatabaseException(ShakshukaException):
    """Exception raised for database-related errors"""
    pass


class AuthenticationException(ShakshukaException):
    """Exception raised for authentication errors"""
    pass


class ConfigurationException(ShakshukaException):
    """Exception raised for configuration errors"""
    pass


class UserNotFoundException(DataManagerException):
    """Exception raised when user is not found"""
    pass


class TaskNotFoundException(DataManagerException):
    """Exception raised when task is not found"""
    pass
