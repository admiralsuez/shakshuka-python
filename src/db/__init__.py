"""
Database module for Shakshuka.
Provides modular database access with connection pooling and type-safe queries.

NOTE: This module provides a refactored, modular DataManager that coexists with
the legacy SQLiteDataManager (in src/sqlite_data_manager.py). Currently, only the
legacy SQLiteDataManager is used in production. The modular DataManager and its
repositories serve as a foundation for future refactoring. No conflicts exist as
they are imported from different locations and not used simultaneously.
"""

from .connection import ConnectionPool, get_connection
from .schema import SCHEMA_VERSION, create_tables, run_migrations
from .data_manager import DataManager

__all__ = [
    'ConnectionPool',
    'get_connection', 
    'SCHEMA_VERSION',
    'create_tables',
    'run_migrations',
    'DataManager',
]
