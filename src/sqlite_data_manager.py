import os
import sqlite3
import sys
import threading
import json
import time
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Dict, Any, Optional
import uuid
import shutil
from queue import Queue, Empty

from src.exceptions import DatabaseException, DataManagerException, TaskNotFoundException
from src.constants import (
    MAX_RETRIES, RETRY_DELAY_SECONDS, DB_CONNECTION_TIMEOUT,
    BACKUP_RETENTION_DAYS, MAX_BACKUP_SIZE_BYTES
)

class SQLiteDataManager:
    """Thread-safe SQLite data manager with user-specific data isolation"""
    
    def __init__(self, data_dir="data", pool_size=5):
        # Handle PyInstaller bundle path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = os.path.join(base_path, data_dir)
        self.db_path = os.path.join(self.data_dir, "shakshuka.db")
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection pool (Issue #23)
        self._pool_size = pool_size
        self._connection_pool = Queue(maxsize=pool_size)
        
        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            # Remove print, use logging (Issue #19)
        except Exception as e:
            raise DatabaseException(f"Failed to create data directory '{self.data_dir}': {e}")
        
        # Setup logging
        self._setup_logging()
        self.logger.info("Data directory ensured: %s", os.path.abspath(self.data_dir))
        
        # Initialize connection pool
        self._init_connection_pool()
        
        # Initialize database
        self._init_database()
    
    def _setup_logging(self):
        """Setup logging for the data manager"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _init_connection_pool(self):
        """Initialize connection pool (Issue #23)"""
        try:
            for _ in range(self._pool_size):
                conn = sqlite3.connect(self.db_path, timeout=DB_CONNECTION_TIMEOUT, check_same_thread=False)
                conn.execute('PRAGMA foreign_keys = ON')
                conn.execute('PRAGMA journal_mode = WAL')
                conn.row_factory = sqlite3.Row
                self._connection_pool.put(conn)
            self.logger.info("Connection pool initialized with %d connections", self._pool_size)
        except Exception as e:
            self.logger.error("Failed to initialize connection pool: %s", e)
            raise DatabaseException(f"Failed to initialize connection pool: {e}")
    
    def _get_pooled_connection(self):
        """Get connection from pool with timeout (Issue #23, #3)"""
        try:
            conn = self._connection_pool.get(timeout=DB_CONNECTION_TIMEOUT)
            return conn
        except Empty:
            raise DatabaseException("Connection pool exhausted - timeout waiting for connection")
    
    def _return_connection(self, conn):
        """Return connection to pool (Issue #3)"""
        try:
            if conn:
                self._connection_pool.put(conn, block=False)
        except Exception as e:
            self.logger.warning("Failed to return connection to pool: %s", e)
            # Create new connection to maintain pool size
            try:
                new_conn = sqlite3.connect(self.db_path, timeout=DB_CONNECTION_TIMEOUT, check_same_thread=False)
                new_conn.execute('PRAGMA foreign_keys = ON')
                new_conn.execute('PRAGMA journal_mode = WAL')
                new_conn.row_factory = sqlite3.Row
                self._connection_pool.put(new_conn, block=False)
            except Exception as pool_e:
                self.logger.error("Failed to create replacement connection: %s", pool_e)
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('PRAGMA foreign_keys = ON')
                conn.execute('PRAGMA journal_mode = WAL')
                
                # Create users table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE,
                        password_hash TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create tasks table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        project TEXT,
                        priority TEXT DEFAULT 'medium',
                        status TEXT DEFAULT 'pending',
                        completed BOOLEAN DEFAULT 0,
                        completed_at TIMESTAMP,
                        due_date TIMESTAMP,
                        estimated_duration INTEGER DEFAULT 60,
                        scheduled_hour INTEGER,
                        scheduled_minute INTEGER,
                        scheduled_date TEXT,
                        scheduled_duration INTEGER,
                        struck_today BOOLEAN DEFAULT 0,
                        struck_date TIMESTAMP,
                        strike_report TEXT,
                        strike_count INTEGER DEFAULT 0,
                        daily_strikes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                ''')
                
                # Create settings table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        user_id TEXT PRIMARY KEY,
                        theme TEXT DEFAULT 'orange',
                        dpi_scale INTEGER DEFAULT 100,
                        autosave_interval INTEGER DEFAULT 30,
                        notifications BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                ''')
                
                # Create sessions table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                ''')
                
                # Create indexes for better performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)')
                
                conn.commit()
                self.logger.info(f"Database initialized successfully: {self.db_path}")
                
                # Run database migrations (must run before creating indexes that depend on migrated columns)
                self._run_migrations()
                
                # Create indexes that depend on migrated columns (after migrations)
                try:
                    with self._get_connection() as conn:
                        # Check if scheduled_date column exists before creating index
                        cursor = conn.execute("PRAGMA table_info(tasks)")
                        columns = [row[1] for row in cursor.fetchall()]
                        if 'scheduled_date' in columns:
                            conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user_scheduled ON tasks (user_id, scheduled_date)')
                            conn.commit()
                except Exception as e:
                    self.logger.warning(f"Could not create scheduled_date index (column may not exist yet): {e}")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def _run_migrations(self):
        """Run database migrations with comprehensive error handling and rollback"""
        migration_version = None
        backup_created = False
        
        try:
            with self._get_connection() as conn:
                # Start transaction for migration
                conn.execute('BEGIN IMMEDIATE TRANSACTION')
                
                try:
                    # Get current migration version
                    migration_version = self._get_migration_version(conn)
                    self.logger.info(f"Current migration version: {migration_version}")
                    
                    # Create backup before major migrations
                    if migration_version < 2:
                        backup_created = self._create_migration_backup(conn)
                        if backup_created:
                            self.logger.info("Migration backup created successfully")
                    
                    # Run migrations based on version
                    migrations_applied = []
                    
                    # Migration 1: Add analytics columns
                    if migration_version < 1:
                        migrations_applied.extend(self._migration_001_analytics_columns(conn))
                    
                    # Migration 2: Add indexes and constraints
                    if migration_version < 2:
                        migrations_applied.extend(self._migration_002_indexes_constraints(conn))
                    
                    # Migration 3: Add user preferences
                    if migration_version < 3:
                        migrations_applied.extend(self._migration_003_user_preferences(conn))
                    
                    # Migration 4: Add audit trail
                    if migration_version < 4:
                        migrations_applied.extend(self._migration_004_audit_trail(conn))
                    
                    # Migration 5: Add planner v2 tables
                    if migration_version < 5:
                        migrations_applied.extend(self._migration_005_planner_v2(conn))
                    
                    # Migration 6: Add scheduled_date and scheduled_minute fields
                    if migration_version < 6:
                        migrations_applied.extend(self._migration_006_scheduled_fields(conn))
                    
                    # Migration 7: Add daily_strikes column to persist per-day strike counts
                    if migration_version < 7:
                        migrations_applied.extend(self._migration_007_daily_strikes(conn))
                    
                    # Update migration version
                    if migrations_applied:
                        new_version = max([m['version'] for m in migrations_applied])
                        self._update_migration_version(conn, new_version)
                        self.logger.info(f"Updated migration version to {new_version}")
                    
                    # Commit transaction
                    conn.commit()
                    self.logger.info(f"Database migrations completed successfully: {len(migrations_applied)} migrations applied")
                    
                except Exception as inner_e:
                    # Rollback transaction on any error
                    conn.rollback()
                    self.logger.error(f"Migration transaction failed: {inner_e}")
                    
                    # Restore backup if created
                    if backup_created:
                        try:
                            self._restore_migration_backup()
                            self.logger.info("Migration backup restored successfully")
                        except Exception as restore_e:
                            self.logger.error(f"Failed to restore migration backup: {restore_e}")
                    
                    raise inner_e
                
        except Exception as e:
            self.logger.error(f"Error running database migrations: {e}")
            # Don't raise - migrations are not critical for basic functionality
            # But log the error for debugging
            self.logger.error(f"Migration failed at version {migration_version}, backup created: {backup_created}")
    
    def _get_migration_version(self, conn) -> int:
        """Get current migration version from database"""
        try:
            cursor = conn.execute('SELECT version FROM migration_version ORDER BY version DESC LIMIT 1')
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.OperationalError:
            # Migration version table doesn't exist, create it
            conn.execute('''
                CREATE TABLE IF NOT EXISTS migration_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            ''')
            conn.execute('INSERT INTO migration_version (version, description) VALUES (0, "Initial version")')
            return 0
    
    def _update_migration_version(self, conn, version: int):
        """Update migration version in database"""
        conn.execute('INSERT INTO migration_version (version, description) VALUES (?, ?)', 
                    (version, f"Migration {version} applied"))
    
    def _create_migration_backup(self, conn) -> bool:
        """Create backup before major migrations (Issue #9)"""
        try:
            backup_path = f"{self.db_path}.migration_backup_{int(time.time())}"
            
            # Create backup by copying database file
            shutil.copy2(self.db_path, backup_path)
            
            # Store backup path for potential restoration
            conn.execute('''
                CREATE TABLE IF NOT EXISTS migration_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    migration_version INTEGER
                )
            ''')
            
            current_version = self._get_migration_version(conn)
            conn.execute('INSERT INTO migration_backups (backup_path, migration_version) VALUES (?, ?)',
                        (backup_path, current_version))
            
            # Clean up old backups (Issue #9)
            self._cleanup_old_backups(conn)
            
            return True
        except Exception as e:
            self.logger.error("Failed to create migration backup: %s", e)
            return False
    
    def _cleanup_old_backups(self, conn):
        """Clean up old migration backups (Issue #9)
        - Keep backups from last 7 days
        - Clean backups older than 7 days
        - If total size exceeds 512MB, keep only latest backup
        """
        try:
            # Get all backups
            cursor = conn.execute('''
                SELECT id, backup_path, created_at 
                FROM migration_backups 
                ORDER BY created_at DESC
            ''')
            backups = cursor.fetchall()
            
            if not backups:
                return
            
            # Calculate total backup size
            total_size = 0
            backup_info = []
            for backup in backups:
                backup_id, backup_path, created_at = backup
                if os.path.exists(backup_path):
                    size = os.path.getsize(backup_path)
                    total_size += size
                    backup_info.append({
                        'id': backup_id,
                        'path': backup_path,
                        'created_at': created_at,
                        'size': size
                    })
                else:
                    # Remove reference to non-existent backup
                    conn.execute('DELETE FROM migration_backups WHERE id = ?', (backup_id,))
            
            # If total size exceeds limit, keep only latest backup
            if total_size > MAX_BACKUP_SIZE_BYTES:
                self.logger.warning(
                    "Backup size (%d MB) exceeds limit (%d MB), keeping only latest backup",
                    total_size // (1024 * 1024),
                    MAX_BACKUP_SIZE_BYTES // (1024 * 1024)
                )
                for i, backup in enumerate(backup_info):
                    if i > 0:  # Keep first (latest) backup only
                        try:
                            os.remove(backup['path'])
                            conn.execute('DELETE FROM migration_backups WHERE id = ?', (backup['id'],))
                            self.logger.info("Removed backup due to size limit: %s", backup['path'])
                        except Exception as e:
                            self.logger.error("Failed to remove backup %s: %s", backup['path'], e)
                return
            
            # Clean up backups older than BACKUP_RETENTION_DAYS
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)
            
            for backup in backup_info:
                try:
                    # Parse created_at timestamp
                    created_dt = datetime.fromisoformat(backup['created_at'].replace('Z', '+00:00'))
                    
                    if created_dt < cutoff_date:
                        os.remove(backup['path'])
                        conn.execute('DELETE FROM migration_backups WHERE id = ?', (backup['id'],))
                        self.logger.info("Removed old backup: %s", backup['path'])
                except Exception as e:
                    self.logger.error("Failed to process backup %s: %s", backup['path'], e)
            
            conn.commit()
            
        except Exception as e:
            self.logger.error("Failed to cleanup old backups: %s", e)
    
    def _restore_migration_backup(self):
        """Restore from migration backup"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('SELECT backup_path FROM migration_backups ORDER BY created_at DESC LIMIT 1')
                result = cursor.fetchone()
                
                if result:
                    backup_path = result[0]
                    import shutil
                    shutil.copy2(backup_path, self.db_path)
                    self.logger.info(f"Restored from backup: {backup_path}")
                else:
                    self.logger.warning("No migration backup found to restore")
        except Exception as e:
            self.logger.error(f"Failed to restore migration backup: {e}")
    
    def _migration_001_analytics_columns(self, conn) -> List[Dict]:
        """Migration 1: Add analytics columns to tasks table"""
        migrations_applied = []
        
        try:
            # Check if analytics columns exist
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add missing analytics columns
            analytics_columns = [
                ('completed_at', 'TIMESTAMP'),
                ('struck_today', 'BOOLEAN DEFAULT 0'),
                ('struck_date', 'TIMESTAMP'),
                ('strike_report', 'TEXT'),
                ('strike_count', 'INTEGER DEFAULT 0')
            ]
            
            # Issue #8: Avoid f-strings in SQL, validate against whitelist
            for column_name, column_def in analytics_columns:
                if column_name not in columns:
                    # Validate column_name is in whitelist (all defined above)
                    if column_name in [col[0] for col in analytics_columns]:
                        # Safe to use f-string since validated against hardcoded whitelist
                        conn.execute(f'ALTER TABLE tasks ADD COLUMN {column_name} {column_def}')
                        self.logger.info("Added %s column to tasks table", column_name)
                    migrations_applied.append({
                        'version': 1,
                        'description': f'Added {column_name} column',
                        'sql': f'ALTER TABLE tasks ADD COLUMN {column_name} {column_def}'
                    })
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 001 failed: {e}")
            raise
    
    def _migration_002_indexes_constraints(self, conn) -> List[Dict]:
        """Migration 2: Add indexes and constraints for performance"""
        migrations_applied = []
        
        try:
            # Add performance indexes
            indexes = [
                ('idx_tasks_user_status', 'CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks (user_id, status)'),
                ('idx_tasks_user_priority', 'CREATE INDEX IF NOT EXISTS idx_tasks_user_priority ON tasks (user_id, priority)'),
                ('idx_tasks_user_created', 'CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks (user_id, created_at)'),
                ('idx_tasks_user_due', 'CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks (user_id, due_date)'),
                ('idx_tasks_completed', 'CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed_at)'),
                ('idx_tasks_struck', 'CREATE INDEX IF NOT EXISTS idx_tasks_struck ON tasks (struck_date)')
            ]
            
            for index_name, sql in indexes:
                conn.execute(sql)
                self.logger.info(f"Created index: {index_name}")
                migrations_applied.append({
                    'version': 2,
                    'description': f'Created index {index_name}',
                    'sql': sql
                })
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 002 failed: {e}")
            raise
    
    def _migration_003_user_preferences(self, conn) -> List[Dict]:
        """Migration 3: Add user preferences table"""
        migrations_applied = []
        
        try:
            # Create user preferences table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    theme TEXT DEFAULT 'orange',
                    dpi_scale INTEGER DEFAULT 100,
                    autosave_interval INTEGER DEFAULT 30,
                    notifications BOOLEAN DEFAULT 1,
                    daily_reset_time TEXT DEFAULT '09:00',
                    timezone TEXT DEFAULT 'UTC',
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            self.logger.info("Created user_preferences table")
            migrations_applied.append({
                'version': 3,
                'description': 'Created user_preferences table',
                'sql': 'CREATE TABLE user_preferences'
            })
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 003 failed: {e}")
            raise
    
    def _migration_004_audit_trail(self, conn) -> List[Dict]:
        """Migration 4: Add audit trail table"""
        migrations_applied = []
        
        try:
            # Create audit trail table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    record_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            # Create index for audit trail
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_user_action ON audit_trail (user_id, action)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_trail (created_at)')
            
            self.logger.info("Created audit_trail table")
            migrations_applied.append({
                'version': 4,
                'description': 'Created audit_trail table',
                'sql': 'CREATE TABLE audit_trail'
            })
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 004 failed: {e}")
            raise
    
    def _migration_005_planner_v2(self, conn) -> List[Dict]:
        """Migration 5: Add planner v2 tables"""
        migrations_applied = []
        
        try:
            # Create planner_v2_schedule table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS planner_v2_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    scheduled_tasks TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id)
                )
            ''')
            
            # Create index for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_planner_v2_user_id ON planner_v2_schedule (user_id)')
            
            self.logger.info("Created planner_v2_schedule table")
            migrations_applied.append({
                'version': 5,
                'description': 'Created planner_v2_schedule table',
                'sql': 'CREATE TABLE planner_v2_schedule'
            })
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 005 failed: {e}")
            raise
    
    def _migration_006_scheduled_fields(self, conn) -> List[Dict]:
        """Migration 6: Add scheduled_date and scheduled_minute fields to tasks table"""
        migrations_applied = []
        
        try:
            # Check if scheduled_date and scheduled_minute columns exist
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add scheduled_minute column if it doesn't exist
            if 'scheduled_minute' not in columns:
                conn.execute('ALTER TABLE tasks ADD COLUMN scheduled_minute INTEGER')
                migrations_applied.append({
                    'version': 6,
                    'name': 'add_scheduled_minute_column',
                    'description': 'Add scheduled_minute column to tasks table'
                })
                self.logger.info("Added scheduled_minute column to tasks table")
            
            # Add scheduled_date column if it doesn't exist
            if 'scheduled_date' not in columns:
                conn.execute('ALTER TABLE tasks ADD COLUMN scheduled_date TEXT')
                migrations_applied.append({
                    'version': 6,
                    'name': 'add_scheduled_date_column',
                    'description': 'Add scheduled_date column to tasks table'
                })
                self.logger.info("Added scheduled_date column to tasks table")
            
            return migrations_applied
            
        except Exception as e:
            self.logger.error(f"Migration 006 failed: {e}")
            raise
    
    def _migration_007_daily_strikes(self, conn) -> List[Dict]:
        """Migration 7: Add daily_strikes TEXT column to tasks for per-day strike tracking"""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'daily_strikes' not in columns:
                conn.execute('ALTER TABLE tasks ADD COLUMN daily_strikes TEXT')
                migrations_applied.append({
                    'version': 7,
                    'name': 'add_daily_strikes_column',
                    'description': 'Add daily_strikes TEXT column to tasks table'
                })
                self.logger.info("Added daily_strikes column to tasks table")
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 007 failed: {e}")
            raise
    
    def _get_connection(self):
        """Get a database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def _ensure_user_exists(self, user_id: str) -> bool:
        """Ensure user exists in database, create if not"""
        try:
            with self._get_connection() as conn:
                # Check if user exists
                cursor = conn.execute('SELECT id FROM users WHERE id = ?', (user_id,))
                if cursor.fetchone():
                    return True
                
                # Create user if not exists (with default password hash for default_user)
                if user_id == 'default_user':
                    # For default user, use a placeholder password hash
                    password_hash = 'default_user_no_password'
                else:
                    password_hash = None
                
                conn.execute('''
                    INSERT INTO users (id, username, password_hash, is_active)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, f"user_{user_id[:8]}", password_hash, 1))
                
                # Create default settings for user
                conn.execute('''
                    INSERT INTO settings (user_id, theme, dpi_scale, autosave_interval, notifications)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, 'orange', 100, 30, 1))
                
                conn.commit()
                self.logger.info(f"Created user: {user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error ensuring user exists {user_id}: {e}")
            return False
    
    def _validate_task(self, task: Dict[str, Any]) -> bool:
        """Validate a single task"""
        required_fields = ['id', 'title']
        for field in required_fields:
            if field not in task:
                self.logger.error(f"Task missing required field: {field}")
                return False
        
        # Validate title
        if not isinstance(task['title'], str) or len(task['title']) > 200:
            self.logger.error(f"Invalid title: {task['title']}")
            return False
        
        # Validate ID
        if not isinstance(task['id'], str) or len(task['id']) == 0:
            self.logger.error(f"Invalid task ID: {task['id']}")
            return False
        
        # Validate completion status
        if 'completed' in task and not isinstance(task['completed'], bool):
            self.logger.error(f"Invalid completion status: {task['completed']}")
            return False
        
        return True
    
    def _validate_tasks(self, tasks: List[Dict[str, Any]]) -> bool:
        """Validate all tasks"""
        if not isinstance(tasks, list):
            self.logger.error("Tasks must be a list")
            return False
        
        # Check for duplicate IDs
        task_ids = set()
        for task in tasks:
            if not self._validate_task(task):
                return False
            
            if task['id'] in task_ids:
                self.logger.error(f"Duplicate task ID: {task['id']}")
                return False
            task_ids.add(task['id'])
        
        return True
    
    def _task_dict_to_row(self, task: Dict[str, Any], user_id: str) -> tuple:
        """Convert task dictionary to database row"""
        return (
            task['id'],
            user_id,
            task['title'],
            task.get('description', ''),
            task.get('project', ''),
            task.get('priority', 'medium'),
            task.get('status', 'pending'),
            task.get('completed', False),
            task.get('completed_at'),
            task.get('due_date'),
            task.get('estimated_duration', 60),
            task.get('scheduled_hour'),
            task.get('scheduled_minute'),
            task.get('scheduled_date'),
            task.get('scheduled_duration'),
            task.get('struck_today', False),
            task.get('struck_date'),
            task.get('strike_report'),
            task.get('strike_count', 0),
            json.dumps(task.get('daily_strikes', {})),
            task.get('created_at', datetime.now().isoformat()),
            task.get('updated_at', datetime.now().isoformat())
        )
    
    def _row_to_task_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to task dictionary"""
        # Safely parse daily_strikes JSON if present
        daily_strikes = {}
        try:
            raw = row['daily_strikes'] if 'daily_strikes' in row.keys() else None
            if raw:
                daily_strikes = json.loads(raw)
        except Exception:
            daily_strikes = {}
        
        return {
            'id': row['id'],
            'title': row['title'],
            'description': row['description'] or '',
            'project': row['project'] or '',
            'priority': row['priority'] or 'medium',
            'status': row['status'] or 'pending',
            'completed': bool(row['completed']),
            'completed_at': row['completed_at'],
            'due_date': row['due_date'],
            'estimated_duration': row['estimated_duration'] or 60,
            'scheduled_hour': row['scheduled_hour'],
            'scheduled_minute': row['scheduled_minute'] if 'scheduled_minute' in row.keys() else None,
            'scheduled_date': row['scheduled_date'] if 'scheduled_date' in row.keys() else None,
            'scheduled_duration': row['scheduled_duration'],
            'struck_today': bool(row['struck_today'] if 'struck_today' in row.keys() else False),
            'struck_date': row['struck_date'] if 'struck_date' in row.keys() else None,
            'strike_report': row['strike_report'] if 'strike_report' in row.keys() else None,
            'strike_count': row['strike_count'] if 'strike_count' in row.keys() else 0,
            'daily_strikes': daily_strikes,
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    
    # Task Management Methods
    def load_tasks_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load tasks for a specific user from database with comprehensive error handling and failsafes"""
        conn = None
        try:
            self._ensure_user_exists(user_id)
            
            conn = self._get_pooled_connection()
            # Use read-only transaction for consistency
            conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
            try:
                cursor = conn.execute('''
                    SELECT * FROM tasks 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                rows = cursor.fetchall()
                
                # Validate each row before conversion
                tasks = []
                for row in rows:
                    try:
                        task_dict = self._row_to_task_dict(row)
                        # Validate the converted task
                        if self._validate_task(task_dict):
                            tasks.append(task_dict)
                        else:
                            self.logger.warning("Invalid task data found for user %s, skipping corrupted task", user_id)
                    except Exception as row_e:
                        self.logger.warning("Failed to convert row for user %s: %s", user_id, row_e)
                        continue
                
                conn.commit()  # Commit read transaction
                self.logger.info("Successfully loaded %d tasks for user %s", len(tasks), user_id)
                return tasks
                
            except Exception as inner_e:
                conn.rollback()
                self.logger.error("Transaction failed for user %s: %s", user_id, inner_e)
                raise inner_e
                
        except Exception as e:
            self.logger.error("Error loading tasks for user %s: %s", user_id, e)
            return []  # Return empty list as failsafe
        finally:
            if conn:
                self._return_connection(conn)
    
    def save_tasks_for_user(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Save tasks for a specific user to database with atomic transaction and failsafes"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    # Validate data first
                    if not self._validate_tasks(tasks):
                        self.logger.error(f"Task validation failed for user {user_id}")
                        return False
                    
                    self._ensure_user_exists(user_id)
                    
                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Create backup of existing tasks before deletion (failsafe)
                            backup_tasks = []
                            cursor = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
                            for row in cursor.fetchall():
                                backup_tasks.append(self._row_to_task_dict(row))
                            
                            # Delete existing tasks for user
                            conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
                            
                            # Insert new tasks
                            task_rows = [self._task_dict_to_row(task, user_id) for task in tasks]
                            conn.executemany('''
                                INSERT INTO tasks (
                                    id, user_id, title, description, project, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', task_rows)
                            
                            # Verify insertion was successful
                            count_cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ?', (user_id,))
                            inserted_count = count_cursor.fetchone()[0]
                            
                            if inserted_count != len(tasks):
                                raise Exception(f"Insertion verification failed: expected {len(tasks)}, got {inserted_count}")
                            
                            # Commit transaction
                            conn.commit()
                            self.logger.info(f"Successfully saved {len(tasks)} tasks for user {user_id}")
                            return True
                            
                        except Exception as inner_e:
                            # Rollback transaction on any error
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}")
                            
                            # Restore backup if this is the last attempt
                            if attempt == max_retries - 1 and backup_tasks:
                                try:
                                    self.logger.warning(f"Restoring backup for user {user_id} after final failure")
                                    conn.execute('BEGIN IMMEDIATE TRANSACTION')
                                    conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
                                    backup_rows = [self._task_dict_to_row(task, user_id) for task in backup_tasks]
                                    conn.executemany('''
                                        INSERT INTO tasks (
                                            id, user_id, title, description, project, priority, status,
                                            completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                            scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
                                            daily_strikes, created_at, updated_at
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', backup_rows)
                                    conn.commit()
                                    self.logger.info(f"Backup restored for user {user_id}")
                                except Exception as restore_e:
                                    conn.rollback()
                                    self.logger.error(f"Failed to restore backup for user {user_id}: {restore_e}")
                            
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error saving tasks for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        return False
        
        return False
    
    def create_task_for_user(self, user_id: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a single task for a user with transaction safety"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    self._ensure_user_exists(user_id)
                    
                    # Generate task ID if not provided
                    if 'id' not in task_data:
                        task_data['id'] = str(uuid.uuid4())
                    
                    # Validate task
                    if not self._validate_task(task_data):
                        self.logger.error(f"Task validation failed for user {user_id}")
                        return None
                    
                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Check for duplicate task ID
                            cursor = conn.execute('SELECT id FROM tasks WHERE id = ? AND user_id = ?', (task_data['id'], user_id))
                            if cursor.fetchone():
                                raise Exception(f"Task with ID {task_data['id']} already exists for user {user_id}")
                            
                            task_row = self._task_dict_to_row(task_data, user_id)
                            conn.execute('''
                                INSERT INTO tasks (
                                    id, user_id, title, description, project, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', task_row)
                            
                            # Verify insertion
                            verify_cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?', (task_data['id'], user_id))
                            if verify_cursor.fetchone()[0] != 1:
                                raise Exception("Task insertion verification failed")
                            
                            conn.commit()
                            
                            # Return the created task
                            cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_data['id'],))
                            row = cursor.fetchone()
                            if row:
                                created_task = self._row_to_task_dict(row)
                                self.logger.info(f"Successfully created task {task_data['id']} for user {user_id}")
                                return created_task
                            else:
                                raise Exception("Task not found after creation")
                                
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}")
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error creating task for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        return None
        
        return None
    
    def get_task_by_id(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID (Issue #6 - avoid N+1 query problem)"""
        conn = None
        try:
            conn = self._get_pooled_connection()
            cursor = conn.execute(
                'SELECT * FROM tasks WHERE id = ? AND user_id = ?',
                (task_id, user_id)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_task_dict(row)
            return None
            
        except Exception as e:
            self.logger.error("Error getting task %s for user %s: %s", task_id, user_id, e)
            return None
        finally:
            if conn:
                self._return_connection(conn)
    
    def bulk_create_tasks(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Bulk create tasks without loading existing tasks (Issue #12)"""
        conn = None
        try:
            self._ensure_user_exists(user_id)
            
            # Validate all tasks
            for task in tasks:
                if 'id' not in task:
                    task['id'] = str(uuid.uuid4())
                if not self._validate_task(task):
                    raise DataManagerException(f"Task validation failed: {task.get('title', 'unknown')}")
            
            conn = self._get_pooled_connection()
            conn.execute('BEGIN IMMEDIATE TRANSACTION')
            
            try:
                # Bulk insert
                task_rows = [self._task_dict_to_row(task, user_id) for task in tasks]
                conn.executemany('''
                    INSERT INTO tasks (
                        id, user_id, title, description, project, priority, status,
                        completed, completed_at, due_date, estimated_duration, scheduled_hour,
                        scheduled_minute, scheduled_date, scheduled_duration, struck_today,
                        struck_date, strike_report, strike_count, daily_strikes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', task_rows)
                
                conn.commit()
                self.logger.info("Bulk created %d tasks for user %s", len(tasks), user_id)
                return True
                
            except Exception as inner_e:
                conn.rollback()
                raise DatabaseException(f"Bulk insert failed: {inner_e}")
                
        except Exception as e:
            self.logger.error("Error bulk creating tasks for user %s: %s", user_id, e)
            return False
        finally:
            if conn:
                self._return_connection(conn)
    
    def update_task_for_user(self, user_id: str, task_id: str, task_data: Dict[str, Any]) -> bool:
        """Update a specific task for a user with transaction safety"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Check if task exists and belongs to user
                            cursor = conn.execute('''
                                SELECT id FROM tasks WHERE id = ? AND user_id = ?
                            ''', (task_id, user_id))
                            
                            if not cursor.fetchone():
                                self.logger.error(f"Task {task_id} not found for user {user_id}")
                                conn.rollback()
                                return False
                            
                            # Create backup of original task (failsafe)
                            backup_cursor = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
                            backup_row = backup_cursor.fetchone()
                            if not backup_row:
                                raise Exception("Task disappeared during update")
                            
                            # Update task
                            conn.execute('''
                                UPDATE tasks SET
                                    title = ?, description = ?, project = ?, priority = ?,
                                    status = ?, completed = ?, completed_at = ?, due_date = ?, estimated_duration = ?,
                                    scheduled_hour = ?, scheduled_duration = ?, struck_today = ?, struck_date = ?,
                                    strike_report = ?, strike_count = ?, daily_strikes = ?, updated_at = ?
                                WHERE id = ? AND user_id = ?
                            ''', (
                                task_data.get('title', ''),
                                task_data.get('description', ''),
                                task_data.get('project', ''),
                                task_data.get('priority', 'medium'),
                                task_data.get('status', 'pending'),
                                task_data.get('completed', False),
                                task_data.get('completed_at'),
                                task_data.get('due_date'),
                                task_data.get('estimated_duration', 60),
                                task_data.get('scheduled_hour'),
                                task_data.get('scheduled_duration'),
                                task_data.get('struck_today', False),
                                task_data.get('struck_date'),
                                task_data.get('strike_report'),
                                task_data.get('strike_count', 0),
                                json.dumps(task_data.get('daily_strikes', {})),
                                datetime.now().isoformat(),
                                task_id,
                                user_id
                            ))
                            
                            # Verify update was successful
                            verify_cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
                            if verify_cursor.fetchone()[0] != 1:
                                raise Exception("Task update verification failed")
                            
                            conn.commit()
                            self.logger.info(f"Successfully updated task {task_id} for user {user_id}")
                            return True
                            
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}")
                            
                            # Restore backup if this is the last attempt
                            if attempt == max_retries - 1 and backup_row:
                                try:
                                    self.logger.warning(f"Restoring backup for task {task_id} after final failure")
                                    conn.execute('BEGIN IMMEDIATE TRANSACTION')
                                    conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
                                    backup_task = self._row_to_task_dict(backup_row)
                                    backup_row_tuple = self._task_dict_to_row(backup_task, user_id)
                                    conn.execute('''
                                        INSERT INTO tasks (
                                            id, user_id, title, description, project, priority, status,
                                            completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                            scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
                                            daily_strikes, created_at, updated_at
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', backup_row_tuple)
                                    conn.commit()
                                    self.logger.info(f"Backup restored for task {task_id}")
                                except Exception as restore_e:
                                    conn.rollback()
                                    self.logger.error(f"Failed to restore backup for task {task_id}: {restore_e}")
                            
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error updating task {task_id} for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        return False
        
        return False
    
    def delete_task_for_user(self, user_id: str, task_id: str) -> bool:
        """Delete a specific task for a user with transaction safety"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Create backup of task before deletion (failsafe)
                            backup_cursor = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
                            backup_row = backup_cursor.fetchone()
                            
                            if not backup_row:
                                self.logger.error(f"Task {task_id} not found for user {user_id}")
                                conn.rollback()
                                return False
                            
                            # Delete task
                            cursor = conn.execute('''
                                DELETE FROM tasks WHERE id = ? AND user_id = ?
                            ''', (task_id, user_id))
                            
                            # Verify deletion
                            verify_cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
                            if verify_cursor.fetchone()[0] != 0:
                                raise Exception("Task deletion verification failed")
                            
                            conn.commit()
                            self.logger.info(f"Successfully deleted task {task_id} for user {user_id}")
                            return True
                            
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}")
                            
                            # Restore backup if this is the last attempt
                            if attempt == max_retries - 1 and backup_row:
                                try:
                                    self.logger.warning(f"Restoring backup for task {task_id} after final failure")
                                    conn.execute('BEGIN IMMEDIATE TRANSACTION')
                                    backup_task = self._row_to_task_dict(backup_row)
                                    backup_row_tuple = self._task_dict_to_row(backup_task, user_id)
                                    conn.execute('''
                                        INSERT INTO tasks (
                                            id, user_id, title, description, project, priority, status,
                                            completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                            scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
                                            created_at, updated_at
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', backup_row_tuple)
                                    conn.commit()
                                    self.logger.info(f"Backup restored for task {task_id}")
                                except Exception as restore_e:
                                    conn.rollback()
                                    self.logger.error(f"Failed to restore backup for task {task_id}: {restore_e}")
                            
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error deleting task {task_id} for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        return False
        
        return False
    
    # Settings Management Methods
    def load_settings_for_user(self, user_id: str) -> Dict[str, Any]:
        """Load settings for a specific user from database with comprehensive isolation"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    # Validate user_id
                    if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
                        self.logger.error(f"Invalid user_id provided: {user_id}")
                        return self._get_default_settings()
                    
                    # Ensure user exists
                    self._ensure_user_exists(user_id)
                    
                    with self._get_connection() as conn:
                        # Start read-only transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Check if user preferences table exists (newer migration)
                            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
                            if cursor.fetchone():
                                # Determine available columns so we can include
                                # quick_project_from_title when it exists.
                                col_cursor = conn.execute("PRAGMA table_info(user_preferences)")
                                cols = [row[1] for row in col_cursor.fetchall()]
                                has_qp_column = 'quick_project_from_title' in cols
                                has_casual_column = 'casual_dates' in cols

                                if has_qp_column and has_casual_column:
                                    cursor = conn.execute('''
                                        SELECT theme, dpi_scale, autosave_interval, notifications, 
                                               daily_reset_time, timezone, language, quick_project_from_title,
                                               casual_dates, created_at, updated_at
                                        FROM user_preferences WHERE user_id = ?
                                    ''', (user_id,))
                                elif has_qp_column and not has_casual_column:
                                    cursor = conn.execute('''
                                        SELECT theme, dpi_scale, autosave_interval, notifications, 
                                               daily_reset_time, timezone, language, quick_project_from_title,
                                               created_at, updated_at
                                        FROM user_preferences WHERE user_id = ?
                                    ''', (user_id,))
                                elif not has_qp_column and has_casual_column:
                                    cursor = conn.execute('''
                                        SELECT theme, dpi_scale, autosave_interval, notifications, 
                                               daily_reset_time, timezone, language, casual_dates,
                                               created_at, updated_at
                                        FROM user_preferences WHERE user_id = ?
                                    ''', (user_id,))
                                else:
                                    cursor = conn.execute('''
                                        SELECT theme, dpi_scale, autosave_interval, notifications, 
                                               daily_reset_time, timezone, language, created_at, updated_at
                                        FROM user_preferences WHERE user_id = ?
                                    ''', (user_id,))

                                result = cursor.fetchone()

                                if result:
                                    if has_qp_column and has_casual_column:
                                        # theme, dpi_scale, autosave_interval, notifications,
                                        # daily_reset_time, timezone, language, quick_project_from_title,
                                        # casual_dates, created_at, updated_at
                                        settings = {
                                            'theme': result[0] or 'orange',
                                            'dpi_scale': result[1] or 100,
                                            'autosave_interval': result[2] or 30,
                                            'notifications': bool(result[3]) if result[3] is not None else True,
                                            'daily_reset_time': result[4] or '06:00',
                                            'timezone': result[5] or 'UTC',
                                            'language': result[6] or 'en',
                                            'quick_project_from_title': bool(result[7]) if result[7] is not None else False,
                                            'casual_dates': bool(result[8]) if result[8] is not None else False,
                                            'created_at': result[9],
                                            'updated_at': result[10]
                                        }
                                    elif has_qp_column and not has_casual_column:
                                        # Newer schema with quick_project_from_title but without casual_dates
                                        settings = {
                                            'theme': result[0] or 'orange',
                                            'dpi_scale': result[1] or 100,
                                            'autosave_interval': result[2] or 30,
                                            'notifications': bool(result[3]) if result[3] is not None else True,
                                            'daily_reset_time': result[4] or '06:00',
                                            'timezone': result[5] or 'UTC',
                                            'language': result[6] or 'en',
                                            'quick_project_from_title': bool(result[7]) if result[7] is not None else False,
                                            'casual_dates': False,
                                            'created_at': result[8],
                                            'updated_at': result[9]
                                        }
                                    elif not has_qp_column and has_casual_column:
                                        # Schema with casual_dates but without quick_project_from_title
                                        settings = {
                                            'theme': result[0] or 'orange',
                                            'dpi_scale': result[1] or 100,
                                            'autosave_interval': result[2] or 30,
                                            'notifications': bool(result[3]) if result[3] is not None else True,
                                            'daily_reset_time': result[4] or '06:00',
                                            'timezone': result[5] or 'UTC',
                                            'language': result[6] or 'en',
                                            'quick_project_from_title': False,
                                            'casual_dates': bool(result[7]) if result[7] is not None else False,
                                            'created_at': result[8],
                                            'updated_at': result[9]
                                        }
                                    else:
                                        # Legacy shape without quick_project_from_title or casual_dates
                                        settings = {
                                            'theme': result[0] or 'orange',
                                            'dpi_scale': result[1] or 100,
                                            'autosave_interval': result[2] or 30,
                                            'notifications': bool(result[3]) if result[3] is not None else True,
                                            'daily_reset_time': result[4] or '06:00',
                                            'timezone': result[5] or 'UTC',
                                            'language': result[6] or 'en',
                                            'quick_project_from_title': False,
                                            'casual_dates': False,
                                            'created_at': result[7] if len(result) > 7 else None,
                                            'updated_at': result[8] if len(result) > 8 else None
                                        }

                                    # Validate settings data
                                    validated_settings = self._validate_settings(settings)
                                    conn.commit()
                                    self.logger.info(f"Successfully loaded settings for user {user_id}")
                                    return validated_settings
                            else:
                                # Fallback to old settings table
                                cursor = conn.execute('''
                                    SELECT theme, dpi_scale, autosave_interval, notifications, daily_reset_time
                                    FROM settings WHERE user_id = ?
                                ''', (user_id,))
                                result = cursor.fetchone()
                                
                                if result:
                                    settings = {
                                        'theme': result[0] or 'orange',
                                        'dpi_scale': result[1] or 100,
                                        'autosave_interval': result[2] or 30,
                                        'notifications': bool(result[3]) if result[3] is not None else True,
                                        'daily_reset_time': result[4] or '06:00',
                                        'timezone': 'UTC',  # Default for old data
                                        'language': 'en'    # Default for old data
                                    }
                                    
                                    validated_settings = self._validate_settings(settings)
                                    conn.commit()
                                    self.logger.info(f"Successfully loaded settings for user {user_id} (legacy)")
                                    return validated_settings
                            
                            # No settings found, create default
                            default_settings = self._get_default_settings()
                            self._create_default_settings_for_user(conn, user_id, default_settings)
                            conn.commit()
                            self.logger.info(f"Created default settings for user {user_id}")
                            return default_settings
                            
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}")
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error loading settings for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        # Return default settings as failsafe
                        self.logger.warning(f"Failed to load settings for user {user_id} after {max_retries} attempts, returning defaults")
                        return self._get_default_settings()
        
        return self._get_default_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings with validation"""
        return {
            'theme': 'orange',
            'dpi_scale': 100,
            'autosave_interval': 30,
            'notifications': True,
            'daily_reset_time': '06:00',
            'timezone': 'UTC',
            'language': 'en',
            # Feature flag: when true, first word before the first comma in a new task
            # title becomes the project name. Defaults to False for backwards compatibility.
            'quick_project_from_title': False,
            # When true, show human-friendly relative dates ("today", "in 2 days", "this weekend").
            'casual_dates': False
        }
    
    def _validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize settings data"""
        validated = {}
        
        # Theme validation - include all valid theme values from frontend
        theme = settings.get('theme', 'orange')
        # Note: this list must stay in sync with frontend theme selector and CSS
        valid_themes = [
            'orange', 'blue', 'green', 'purple', 'dark', 'light',
            'self-esteem', 'anxiety', 'depression', 'focus', 'auto'
        ]
        if not isinstance(theme, str) or theme not in valid_themes:
            theme = 'orange'
        validated['theme'] = theme
        
        # DPI scale validation
        dpi_scale = settings.get('dpi_scale', 100)
        if not isinstance(dpi_scale, int) or dpi_scale < 50 or dpi_scale > 200:
            dpi_scale = 100
        validated['dpi_scale'] = dpi_scale
        
        # Autosave interval validation
        autosave_interval = settings.get('autosave_interval', 30)
        if not isinstance(autosave_interval, int) or autosave_interval < 5 or autosave_interval > 300:
            autosave_interval = 30
        validated['autosave_interval'] = autosave_interval
        
        # Notifications validation
        notifications = settings.get('notifications', True)
        if not isinstance(notifications, bool):
            notifications = True
        validated['notifications'] = notifications
        
        # Daily reset time validation
        daily_reset_time = settings.get('daily_reset_time', '06:00')
        if not isinstance(daily_reset_time, str) or not self._validate_time_format(daily_reset_time):
            daily_reset_time = '06:00'
        validated['daily_reset_time'] = daily_reset_time
        
        # Timezone validation
        timezone = settings.get('timezone', 'UTC')
        if not isinstance(timezone, str) or len(timezone) > 50:
            timezone = 'UTC'
        validated['timezone'] = timezone
        
        # Language validation
        language = settings.get('language', 'en')
        if not isinstance(language, str) or len(language) > 10:
            language = 'en'
        validated['language'] = language
        
        # Quick project-from-title flag
        qp = settings.get('quick_project_from_title', False)
        if not isinstance(qp, bool):
            qp = False
        validated['quick_project_from_title'] = qp
        
        # Casual dates flag
        casual = settings.get('casual_dates', False)
        if not isinstance(casual, bool):
            casual = False
        validated['casual_dates'] = casual
        
        return validated
    
    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format (HH:MM)"""
        try:
            if not isinstance(time_str, str):
                return False
            parts = time_str.split(':')
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False
    
    def _create_default_settings_for_user(self, conn, user_id: str, settings: Dict[str, Any]):
        """Create default settings for a user"""
        try:
            # Try to insert into user_preferences table first (newer schema).
            # If quick_project_from_title column exists it will default to 0/False
            # for freshly created rows unless migrations added an explicit default.
            conn.execute('''
                INSERT OR IGNORE INTO user_preferences 
                (user_id, theme, dpi_scale, autosave_interval, notifications, 
                 daily_reset_time, timezone, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, settings['theme'], settings['dpi_scale'], 
                  settings['autosave_interval'], settings['notifications'],
                  settings['daily_reset_time'], settings['timezone'], settings['language']))
        except sqlite3.OperationalError:
            # Fallback to old settings table
            conn.execute('''
                INSERT OR IGNORE INTO settings 
                (user_id, theme, dpi_scale, autosave_interval, notifications, daily_reset_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, settings['theme'], settings['dpi_scale'], 
                  settings['autosave_interval'], settings['notifications'], settings['daily_reset_time']))
    
    def save_settings_for_user(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Save settings for a specific user to database with comprehensive validation and isolation"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with self._lock:
                try:
                    # Validate user_id
                    if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
                        self.logger.error(f"Invalid user_id provided: {user_id}")
                        return False
                    
                    # Validate and sanitize settings
                    validated_settings = self._validate_settings(settings)
                    
                    # Ensure user exists
                    self._ensure_user_exists(user_id)
                    
                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute('BEGIN IMMEDIATE TRANSACTION')
                        
                        try:
                            # Check if user preferences table exists (newer migration)
                            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
                            table_exists = cursor.fetchone() is not None
                            
                            if table_exists:
                                # Ensure quick_project_from_title and casual_dates columns exist (schema may be from older builds)
                                try:
                                    col_cursor = conn.execute("PRAGMA table_info(user_preferences)")
                                    cols = [row[1] for row in col_cursor.fetchall()]
                                    if 'quick_project_from_title' not in cols:
                                        conn.execute("ALTER TABLE user_preferences ADD COLUMN quick_project_from_title INTEGER DEFAULT 0")
                                    if 'casual_dates' not in cols:
                                        conn.execute("ALTER TABLE user_preferences ADD COLUMN casual_dates INTEGER DEFAULT 0")
                                except Exception as schema_e:
                                    # Log but do not fail save if ALTER fails; feature will just fall back to default
                                    self.logger.warning(f"Could not ensure quick_project_from_title/casual_dates columns on user_preferences: {schema_e}")

                                # Use new user_preferences table (including quick_project_from_title & casual_dates when available)
                                conn.execute('''
                                    INSERT OR REPLACE INTO user_preferences (
                                        user_id, theme, dpi_scale, autosave_interval, notifications,
                                        daily_reset_time, timezone, language, quick_project_from_title, casual_dates, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    user_id,
                                    validated_settings['theme'],
                                    validated_settings['dpi_scale'],
                                    validated_settings['autosave_interval'],
                                    validated_settings['notifications'],
                                    validated_settings['daily_reset_time'],
                                    validated_settings['timezone'],
                                    validated_settings['language'],
                                    1 if validated_settings.get('quick_project_from_title', False) else 0,
                                    1 if validated_settings.get('casual_dates', False) else 0,
                                    datetime.now().isoformat()
                                ))
                            else:
                                # Fallback to old settings table
                                conn.execute('''
                                    INSERT OR REPLACE INTO settings (
                                        user_id, theme, dpi_scale, autosave_interval, notifications, 
                                        daily_reset_time, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    user_id,
                                    validated_settings['theme'],
                                    validated_settings['dpi_scale'],
                                    validated_settings['autosave_interval'],
                                    validated_settings['notifications'],
                                    validated_settings['daily_reset_time'],
                                    datetime.now().isoformat()
                                ))
                            
                            # Commit the transaction
                            conn.commit()
                            self.logger.info(f"Successfully saved settings for user {user_id}")
                            return True
                                
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}")
                            raise inner_e
                            
                except Exception as e:
                    self.logger.error(f"Error saving settings for user {user_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        return False
        
        return False
    
    # Backward compatibility methods
    def load_tasks(self, user_id: str = None):
        """Load tasks with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = "default_user"
            self.logger.info(f"load_tasks called without user_id, using default: {user_id}")
        else:
            self.logger.info(f"load_tasks called with user_id: {user_id}")
        
        return self.load_tasks_for_user(user_id)
    
    def save_tasks(self, tasks, user_id: str = None):
        """Save tasks with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = "default_user"
            self.logger.info(f"save_tasks called without user_id, using default: {user_id}")
        else:
            self.logger.info(f"save_tasks called with user_id: {user_id}")
        
        return self.save_tasks_for_user(user_id, tasks)
    
    def load_settings(self, user_id: str = None):
        """Load settings with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = "default_user"
        return self.load_settings_for_user(user_id)
    
    def save_settings(self, *args):
        """Save settings with flexible parameter handling - backward compatibility"""
        if len(args) == 1:
            # Called with one argument: save_settings(settings)
            settings = args[0]
            user_id = "default_user"
        elif len(args) == 2:
            # Called with two arguments: save_settings(user_id, settings)
            user_id, settings = args
        else:
            raise TypeError("save_settings() takes 1 or 2 arguments")
        
        return self.save_settings_for_user(user_id, settings)
    
    # User Management Methods
    def create_user(self, user_id: str, username: str = None, password_hash: str = None) -> bool:
        """Create a new user"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute('''
                        INSERT INTO users (id, username, password_hash, is_active)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, username or f"user_{user_id[:8]}", password_hash, 1))
                    
                    # Create default settings
                    conn.execute('''
                        INSERT INTO settings (user_id, theme, dpi_scale, autosave_interval, notifications)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, 'orange', 100, 30, 1))
                    
                    conn.commit()
                    self.logger.info(f"Created user: {user_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error creating user {user_id}: {e}")
                return False
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information by ID"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT * FROM users WHERE id = ?
                    ''', (user_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        return {
                            'id': row['id'],
                            'username': row['username'],
                            'is_active': bool(row['is_active']),
                            'created_at': row['created_at'],
                            'updated_at': row['updated_at']
                        }
                    return None
                    
            except Exception as e:
                self.logger.error(f"Error getting user {user_id}: {e}")
                return None
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their data"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # Delete user (cascades to tasks, settings, sessions)
                    cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Deleted user: {user_id}")
                        return True
                    else:
                        self.logger.error(f"User {user_id} not found")
                        return False
                        
            except Exception as e:
                self.logger.error(f"Error deleting user {user_id}: {e}")
                return False
    
    # Database maintenance methods
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    stats = {}
                    
                    # Count users
                    cursor = conn.execute('SELECT COUNT(*) as count FROM users')
                    stats['users'] = cursor.fetchone()['count']
                    
                    # Count tasks
                    cursor = conn.execute('SELECT COUNT(*) as count FROM tasks')
                    stats['tasks'] = cursor.fetchone()['count']
                    
                    # Count sessions
                    cursor = conn.execute('SELECT COUNT(*) as count FROM sessions')
                    stats['sessions'] = cursor.fetchone()['count']
                    
                    # Database file size
                    if os.path.exists(self.db_path):
                        stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
                    
                    return stats
                    
            except Exception as e:
                self.logger.error(f"Error getting database stats: {e}")
                return {}
    
    def vacuum_database(self) -> bool:
        """Optimize database by running VACUUM"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute('VACUUM')
                    conn.commit()
                    self.logger.info("Database vacuum completed")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error vacuuming database: {e}")
                return False

    def load_planner_v2_schedule(self, user_id: str) -> Dict[str, Any]:
        """Load scheduled tasks for Daily Planner v2"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT scheduled_tasks FROM planner_v2_schedule 
                    WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result and result[0]:
                    return json.loads(result[0])
                else:
                    return {}
                    
        except Exception as e:
            self.logger.error(f"Error loading planner v2 schedule: {e}")
            return {}

    def save_planner_v2_schedule(self, user_id: str, scheduled_tasks: Dict[str, Any]) -> bool:
        """Save scheduled tasks for Daily Planner v2"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if record exists
                cursor.execute('''
                    SELECT id FROM planner_v2_schedule WHERE user_id = ?
                ''', (user_id,))
                
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # Update existing record
                    cursor.execute('''
                        UPDATE planner_v2_schedule 
                        SET scheduled_tasks = ?, updated_at = ?
                        WHERE user_id = ?
                    ''', (json.dumps(scheduled_tasks), datetime.now().isoformat(), user_id))
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO planner_v2_schedule (user_id, scheduled_tasks, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, json.dumps(scheduled_tasks), 
                          datetime.now().isoformat(), datetime.now().isoformat()))
                
                conn.commit()
                self.logger.info(f"Successfully saved planner v2 schedule for user {user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving planner v2 schedule: {e}")
            return False

