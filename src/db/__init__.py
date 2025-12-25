"""
Database module for Shakshuka.
Provides modular database access with connection pooling and type-safe queries.
"""

from .connection import ConnectionPool, get_connection
from .schema import SCHEMA_VERSION, create_tables, run_migrations

__all__ = [
    'ConnectionPool',
    'get_connection', 
    'SCHEMA_VERSION',
    'create_tables',
    'run_migrations',
]
