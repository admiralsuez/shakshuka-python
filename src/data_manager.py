import os
import json
import sys
import tempfile
import shutil
import threading
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional
import uuid

class SimpleDataManager:
    """Thread-safe data manager with atomic writes, validation, and user-specific data"""
    def __init__(self, data_dir="data"):
        # Handle PyInstaller bundle path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = os.path.join(base_path, data_dir)
        self.users_dir = os.path.join(self.data_dir, "users")
        
        # Thread safety
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        
        # Caching per user
        self._user_caches = {}
        self._cache_ttl = 60  # seconds
        self._dirty_flags = {}
        
        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.users_dir, exist_ok=True)
            print(f"Data directory ensured: {os.path.abspath(self.data_dir)}")
        except Exception as e:
            raise Exception(f"Failed to create data directory '{self.data_dir}': {e}")
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the data manager"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _get_default_user_id(self) -> str:
        """Get the first available user ID for system operations"""
        try:
            users_file = os.path.join(self.data_dir, "users.json")
            if os.path.exists(users_file):
                with open(users_file, 'r') as f:
                    users = json.load(f)
                    if users:
                        # Return the first user ID
                        return list(users.keys())[0]
            return "default"
        except Exception as e:
            self.logger.error(f"Error getting default user ID: {e}")
            return "default"
    
    def _get_user_files(self, user_id: str) -> Dict[str, str]:
        """Get file paths for a specific user"""
        user_dir = os.path.join(self.users_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        return {
            'tasks': os.path.join(user_dir, "tasks.json"),
            'settings': os.path.join(user_dir, "settings.json"),
            'user_dir': user_dir
        }
    
    def _get_user_cache(self, user_id: str) -> Dict[str, Any]:
        """Get or create cache for a specific user"""
        if user_id not in self._user_caches:
            self._user_caches[user_id] = {
                'tasks': None,
                'settings': None,
                'cache_expiry': None,
                'dirty': False
            }
        return self._user_caches[user_id]
    
    def _mark_user_dirty(self, user_id: str):
        """Mark user data as needing save"""
        with self._lock:
            cache = self._get_user_cache(user_id)
            cache['dirty'] = True
    
    def _is_user_dirty(self, user_id: str) -> bool:
        """Check if user data needs saving"""
        with self._lock:
            cache = self._get_user_cache(user_id)
            return cache['dirty']
    
    def _clear_user_dirty(self, user_id: str):
        """Clear dirty flag for user"""
        with self._lock:
            cache = self._get_user_cache(user_id)
            cache['dirty'] = False
    
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
    
    def _atomic_save(self, data: Any, file_path: str) -> bool:
        """Atomically save data to file"""
        try:
            # Write to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(dir=self.data_dir, suffix='.tmp')
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                # Create backup of current file
                if os.path.exists(file_path):
                    backup_path = f"{file_path}.bak"
                    shutil.copy2(file_path, backup_path)
                
                # Atomic rename
                shutil.move(temp_path, file_path)
                
                self.logger.info(f"Data saved successfully to {file_path}")
                return True
            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e}")
            return False
    
    
    def save_tasks_for_user(self, user_id: str, tasks):
        """Save tasks for a specific user to JSON file with validation and atomic writes"""
        with self._write_lock:
            # Validate data first
            if not self._validate_tasks(tasks):
                self.logger.error(f"Task validation failed for user {user_id}")
                return False
            
            # Get user-specific file path
            user_files = self._get_user_files(user_id)
            tasks_file = user_files['tasks']
            
            # Use atomic save
            success = self._atomic_save(tasks, tasks_file)
            if success:
                # Update cache
                with self._lock:
                    cache = self._get_user_cache(user_id)
                    cache['tasks'] = tasks.copy()
                    cache['cache_expiry'] = datetime.now() + timedelta(seconds=self._cache_ttl)
                    cache['dirty'] = False
            
            return success
    
    def load_tasks_for_user(self, user_id: str, use_cache=True):
        """Load tasks for a specific user from JSON file with caching"""
        with self._lock:
            now = datetime.now()
            cache = self._get_user_cache(user_id)
            
            # Check cache
            if use_cache and cache['tasks'] and cache['cache_expiry']:
                if now < cache['cache_expiry']:
                    return cache['tasks'].copy()
            
            # Load from disk
            tasks = self._load_from_file(user_id)
            
            # Update cache
            cache['tasks'] = tasks.copy()
            cache['cache_expiry'] = now + timedelta(seconds=self._cache_ttl)
            
            return tasks
    
    def _load_from_file(self, user_id: str):
        """Load tasks from file for a specific user without caching"""
        try:
            user_files = self._get_user_files(user_id)
            tasks_file = user_files['tasks']
            
            if os.path.exists(tasks_file):
                with open(tasks_file, 'r') as f:
                    tasks = json.load(f)
                self.logger.info(f"Loaded {len(tasks)} tasks for user {user_id}")
                return tasks
            else:
                self.logger.info(f"Tasks file not found for user {user_id}, returning empty list")
                return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for user {user_id}: {e}")
            # Try to restore from backup
            user_files = self._get_user_files(user_id)
            backup_file = f"{user_files['tasks']}.bak"
            if os.path.exists(backup_file):
                self.logger.info(f"Attempting to restore from backup for user {user_id}")
                try:
                    with open(backup_file, 'r') as f:
                        tasks = json.load(f)
                    self.logger.info(f"Successfully restored from backup for user {user_id}")
                    return tasks
                except Exception as backup_error:
                    self.logger.error(f"Backup restore failed for user {user_id}: {backup_error}")
            return []
        except Exception as e:
            self.logger.error(f"Error loading tasks for user {user_id}: {e}")
            return []
    
    def save_settings_for_user(self, user_id: str, settings):
        """Save settings for a specific user to JSON file"""
        try:
            user_files = self._get_user_files(user_id)
            settings_file = user_files['settings']
            
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2, default=str)
            
            # Update cache
            with self._lock:
                cache = self._get_user_cache(user_id)
                cache['settings'] = settings.copy()
            
            self.logger.info(f"Settings saved successfully for user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving settings for user {user_id}: {e}")
            return False
    
    def load_settings_for_user(self, user_id: str):
        """Load settings for a specific user from JSON file"""
        try:
            user_files = self._get_user_files(user_id)
            settings_file = user_files['settings']
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                
                # Update cache
                with self._lock:
                    cache = self._get_user_cache(user_id)
                    cache['settings'] = settings.copy()
                
                return settings
            else:
                # Return default settings for new user
                default_settings = {
                    'theme': 'orange',
                    'dpi_scale': 100,
                    'autosave_interval': 30,
                    'notifications': True
                }
                
                # Save default settings
                self.save_settings(user_id, default_settings)
                return default_settings
        except Exception as e:
            self.logger.error(f"Error loading settings for user {user_id}: {e}")
            return {
                'theme': 'orange',
                'dpi_scale': 100,
                'autosave_interval': 30,
                'notifications': True
            }
    
    def change_password(self, new_password):
        """Password change not needed in simple mode"""
        return True
    
    # Backward compatibility methods for system operations
    def load_settings(self, user_id: str = None):
        """Load settings with optional user_id (uses default user if not provided)"""
        if user_id is None:
            user_id = self._get_default_user_id()
        return self.load_settings_for_user(user_id)
    
    def save_settings(self, *args):
        """Save settings with flexible parameter handling"""
        if len(args) == 1:
            # Called with one argument: save_settings(settings)
            settings = args[0]
            user_id = self._get_default_user_id()
        elif len(args) == 2:
            # Called with two arguments: save_settings(user_id, settings)
            user_id, settings = args
        else:
            raise TypeError("save_settings() takes 1 or 2 arguments")
        
        return self.save_settings_for_user(user_id, settings)
    
    def load_tasks(self, user_id: str = None):
        """Load tasks with optional user_id (uses default user if not provided)"""
        if user_id is None:
            user_id = self._get_default_user_id()
        return self.load_tasks_for_user(user_id)
    
    def save_tasks(self, tasks, user_id: str = None):
        """Save tasks with optional user_id (uses default user if not provided)"""
        if user_id is None:
            user_id = self._get_default_user_id()
        return self.save_tasks_for_user(user_id, tasks)

# Keep the old EncryptedDataManager for backward compatibility
# Removed unused encryption imports - were only used by EncryptedDataManager

# EncryptedDataManager class removed - was unused dead code (199 lines)
