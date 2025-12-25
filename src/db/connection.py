"""
Database connection pooling and management.
"""

import sqlite3
import threading
import logging
from queue import Queue, Empty
from contextlib import contextmanager
from typing import Optional, Generator

from src.constants import DB_CONNECTION_TIMEOUT

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe SQLite connection pool."""
    
    def __init__(self, db_path: str, pool_size: int = 5, timeout: int = DB_CONNECTION_TIMEOUT):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.RLock()
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize the connection pool with connections."""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                for _ in range(self.pool_size):
                    conn = self._create_connection()
                    self._pool.put(conn)
                self._initialized = True
                logger.info("Connection pool initialized with %d connections", self.pool_size)
            except Exception as e:
                logger.error("Failed to initialize connection pool: %s", e)
                raise
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimal settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool."""
        if not self._initialized:
            self.initialize()
            
        try:
            conn = self._pool.get(timeout=self.timeout)
            return conn
        except Empty:
            raise RuntimeError("Connection pool exhausted - timeout waiting for connection")
    
    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool."""
        try:
            if conn:
                self._pool.put(conn, block=False)
        except Exception as e:
            logger.warning("Failed to return connection to pool: %s", e)
            self._replace_connection()
    
    def _replace_connection(self) -> None:
        """Create a replacement connection for the pool."""
        try:
            new_conn = self._create_connection()
            self._pool.put(new_conn, block=False)
        except Exception as e:
            logger.error("Failed to create replacement connection: %s", e)
    
    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for getting and returning connections."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except Empty:
                    break
            self._initialized = False


# Global connection pool instance
_pool: Optional[ConnectionPool] = None


def get_connection_pool(db_path: str, pool_size: int = 5) -> ConnectionPool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(db_path, pool_size)
    return _pool


@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Convenience function to get a database connection."""
    pool = get_connection_pool(db_path)
    with pool.connection() as conn:
        yield conn
