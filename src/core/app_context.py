"""
Application Context - Global application state management
"""

import secrets
import threading
from typing import Dict, Optional

from cachetools import TTLCache

from src.constants import CSRF_TOKEN_EXPIRY_SECONDS
from src.security_manager import security_manager
from tools.autostart import WindowsAutostart

class AppContext:
    """
    Global application context for managing shared state across the application.
    Thread-safe singleton pattern.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True

        self._data_manager = None
        self._autostart_manager = WindowsAutostart("Shakshuka")
        self._update_manager = None
        self._pin_manager = None

        self._session_secrets: Dict[str, str] = {}
        self._csrf_tokens = TTLCache(maxsize=10000, ttl=CSRF_TOKEN_EXPIRY_SECONDS)

        self._mobile_pairing_codes = TTLCache(maxsize=1000, ttl=300)

        self._lock = threading.RLock()
        self._auto_save_lock = threading.RLock()

        self._auto_save_enabled = True
        self._auto_save_thread = None
        self._auto_save_running = False
        self._auto_save_stop_event = threading.Event()
        self._last_save_time = 0
        self._save_in_progress = False
        self._last_saved_tasks_signature = None

        self.system_tray = None
        

    @property
    def data_manager(self):
        return self._data_manager

    @data_manager.setter
    def data_manager(self, value):
        self._data_manager = value

    @property
    def autostart_manager(self):
        return self._autostart_manager

    @property
    def update_manager(self):
        return self._update_manager

    @update_manager.setter
    def update_manager(self, value):
        self._update_manager = value

    @property
    def pin_manager(self):
        return self._pin_manager

    @pin_manager.setter
    def pin_manager(self, value):
        self._pin_manager = value

    @property
    def auto_save_enabled(self):
        return self._auto_save_enabled

    @auto_save_enabled.setter
    def auto_save_enabled(self, value):
        self._auto_save_enabled = value

    @property
    def auto_save_thread(self):
        return self._auto_save_thread

    @auto_save_thread.setter
    def auto_save_thread(self, value):
        self._auto_save_thread = value

    def generate_session_secret(self, user_id):
        secret = security_manager.generate_session_secret(user_id)
        self._session_secrets[user_id] = secret
        return secret

    def validate_session_secret(self, user_id, secret):
        return self._session_secrets.get(user_id) == secret

    def generate_csrf_token(self):
        token = secrets.token_urlsafe(32)
        self._csrf_tokens[token] = True
        return token

    def validate_csrf_token(self, token):
        if not token or len(token) < 10:
            return False
        return token in self._csrf_tokens

    @property
    def csrf_tokens(self):
        return self._csrf_tokens

    def is_auto_save_running(self):
        with self._auto_save_lock:
            return self._auto_save_running

    def set_auto_save_running(self, running):
        with self._auto_save_lock:
            self._auto_save_running = running

    def is_save_in_progress(self):
        with self._auto_save_lock:
            return self._save_in_progress

    def set_save_in_progress(self, in_progress):
        with self._auto_save_lock:
            self._save_in_progress = in_progress

    def get_last_save_time(self):
        with self._auto_save_lock:
            return self._last_save_time

    def set_last_save_time(self, save_time):
        with self._auto_save_lock:
            self._last_save_time = save_time

    def get_last_saved_tasks_signature(self):
        with self._auto_save_lock:
            return self._last_saved_tasks_signature

    def set_last_saved_tasks_signature(self, signature):
        with self._auto_save_lock:
            self._last_saved_tasks_signature = signature

    def stop_auto_save_event(self):
        self._auto_save_stop_event.set()

    def wait_for_auto_save_stop(self, timeout=None):
        return self._auto_save_stop_event.wait(timeout)

    def clear_auto_save_stop_event(self):
        self._auto_save_stop_event.clear()


# Global singleton instance
app_context = AppContext()

