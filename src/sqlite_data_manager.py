import os
import sqlite3
import sys
import threading
import json
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional
import uuid

class SQLiteDataManager:
    """Thread-safe SQLite data manager with user-specific data isolation"""
    
    def __init__(self, data_dir="data"):
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
        
        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            print(f"Data directory ensured: {os.path.abspath(self.data_dir)}")
        except Exception as e:
            raise Exception(f"Failed to create data directory '{self.data_dir}': {e}")
        
        # Setup logging
        self._setup_logging()
        
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
                        due_date TIMESTAMP,
                        estimated_duration INTEGER DEFAULT 60,
                        scheduled_hour INTEGER,
                        scheduled_duration INTEGER,
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
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
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
                
                # Create user if not exists
                conn.execute('''
                    INSERT INTO users (id, username, is_active)
                    VALUES (?, ?, ?)
                ''', (user_id, f"user_{user_id[:8]}", 1))
                
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
            task.get('due_date'),
            task.get('estimated_duration', 60),
            task.get('scheduled_hour'),
            task.get('scheduled_duration'),
            task.get('created_at', datetime.now().isoformat()),
            task.get('updated_at', datetime.now().isoformat())
        )
    
    def _row_to_task_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to task dictionary"""
        return {
            'id': row['id'],
            'title': row['title'],
            'description': row['description'] or '',
            'project': row['project'] or '',
            'priority': row['priority'] or 'medium',
            'status': row['status'] or 'pending',
            'completed': bool(row['completed']),
            'due_date': row['due_date'],
            'estimated_duration': row['estimated_duration'] or 60,
            'scheduled_hour': row['scheduled_hour'],
            'scheduled_duration': row['scheduled_duration'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    
    # Task Management Methods
    def load_tasks_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load tasks for a specific user from database"""
        with self._lock:
            try:
                self._ensure_user_exists(user_id)
                
                with self._get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT * FROM tasks 
                        WHERE user_id = ? 
                        ORDER BY created_at DESC
                    ''', (user_id,))
                    
                    tasks = [self._row_to_task_dict(row) for row in cursor.fetchall()]
                    self.logger.info(f"Loaded {len(tasks)} tasks for user {user_id}")
                    return tasks
                    
            except Exception as e:
                self.logger.error(f"Error loading tasks for user {user_id}: {e}")
                return []
    
    def save_tasks_for_user(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Save tasks for a specific user to database"""
        with self._lock:
            try:
                # Validate data first
                if not self._validate_tasks(tasks):
                    self.logger.error(f"Task validation failed for user {user_id}")
                    return False
                
                self._ensure_user_exists(user_id)
                
                with self._get_connection() as conn:
                    # Delete existing tasks for user
                    conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
                    
                    # Insert new tasks
                    task_rows = [self._task_dict_to_row(task, user_id) for task in tasks]
                    conn.executemany('''
                        INSERT INTO tasks (
                            id, user_id, title, description, project, priority, status,
                            completed, due_date, estimated_duration, scheduled_hour,
                            scheduled_duration, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', task_rows)
                    
                    conn.commit()
                    self.logger.info(f"Saved {len(tasks)} tasks for user {user_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error saving tasks for user {user_id}: {e}")
                return False
    
    def create_task_for_user(self, user_id: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a single task for a user"""
        with self._lock:
            try:
                self._ensure_user_exists(user_id)
                
                # Generate task ID if not provided
                if 'id' not in task_data:
                    task_data['id'] = str(uuid.uuid4())
                
                # Validate task
                if not self._validate_task(task_data):
                    return None
                
                with self._get_connection() as conn:
                    task_row = self._task_dict_to_row(task_data, user_id)
                    conn.execute('''
                        INSERT INTO tasks (
                            id, user_id, title, description, project, priority, status,
                            completed, due_date, estimated_duration, scheduled_hour,
                            scheduled_duration, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', task_row)
                    
                    conn.commit()
                    
                    # Return the created task
                    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_data['id'],))
                    row = cursor.fetchone()
                    if row:
                        return self._row_to_task_dict(row)
                    
            except Exception as e:
                self.logger.error(f"Error creating task for user {user_id}: {e}")
            
            return None
    
    def update_task_for_user(self, user_id: str, task_id: str, task_data: Dict[str, Any]) -> bool:
        """Update a specific task for a user"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # Check if task exists and belongs to user
                    cursor = conn.execute('''
                        SELECT id FROM tasks WHERE id = ? AND user_id = ?
                    ''', (task_id, user_id))
                    
                    if not cursor.fetchone():
                        self.logger.error(f"Task {task_id} not found for user {user_id}")
                        return False
                    
                    # Update task
                    conn.execute('''
                        UPDATE tasks SET
                            title = ?, description = ?, project = ?, priority = ?,
                            status = ?, completed = ?, due_date = ?, estimated_duration = ?,
                            scheduled_hour = ?, scheduled_duration = ?, updated_at = ?
                        WHERE id = ? AND user_id = ?
                    ''', (
                        task_data.get('title', ''),
                        task_data.get('description', ''),
                        task_data.get('project', ''),
                        task_data.get('priority', 'medium'),
                        task_data.get('status', 'pending'),
                        task_data.get('completed', False),
                        task_data.get('due_date'),
                        task_data.get('estimated_duration', 60),
                        task_data.get('scheduled_hour'),
                        task_data.get('scheduled_duration'),
                        datetime.now().isoformat(),
                        task_id,
                        user_id
                    ))
                    
                    conn.commit()
                    self.logger.info(f"Updated task {task_id} for user {user_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error updating task {task_id} for user {user_id}: {e}")
                return False
    
    def delete_task_for_user(self, user_id: str, task_id: str) -> bool:
        """Delete a specific task for a user"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute('''
                        DELETE FROM tasks WHERE id = ? AND user_id = ?
                    ''', (task_id, user_id))
                    
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Deleted task {task_id} for user {user_id}")
                        return True
                    else:
                        self.logger.error(f"Task {task_id} not found for user {user_id}")
                        return False
                        
            except Exception as e:
                self.logger.error(f"Error deleting task {task_id} for user {user_id}: {e}")
                return False
    
    # Settings Management Methods
    def load_settings_for_user(self, user_id: str) -> Dict[str, Any]:
        """Load settings for a specific user from database"""
        with self._lock:
            try:
                self._ensure_user_exists(user_id)
                
                with self._get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT * FROM settings WHERE user_id = ?
                    ''', (user_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        return {
                            'theme': row['theme'],
                            'dpi_scale': row['dpi_scale'],
                            'autosave_interval': row['autosave_interval'],
                            'notifications': bool(row['notifications'])
                        }
                    else:
                        # Return default settings
                        return {
                            'theme': 'orange',
                            'dpi_scale': 100,
                            'autosave_interval': 30,
                            'notifications': True
                        }
                        
            except Exception as e:
                self.logger.error(f"Error loading settings for user {user_id}: {e}")
                return {
                    'theme': 'orange',
                    'dpi_scale': 100,
                    'autosave_interval': 30,
                    'notifications': True
                }
    
    def save_settings_for_user(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Save settings for a specific user to database"""
        with self._lock:
            try:
                self._ensure_user_exists(user_id)
                
                with self._get_connection() as conn:
                    conn.execute('''
                        INSERT OR REPLACE INTO settings (
                            user_id, theme, dpi_scale, autosave_interval, notifications, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        settings.get('theme', 'orange'),
                        settings.get('dpi_scale', 100),
                        settings.get('autosave_interval', 30),
                        settings.get('notifications', True),
                        datetime.now().isoformat()
                    ))
                    
                    conn.commit()
                    self.logger.info(f"Settings saved for user {user_id}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error saving settings for user {user_id}: {e}")
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

