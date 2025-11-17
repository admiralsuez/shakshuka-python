"""
Application Context - Global application state management
"""
import threading
from typing import Optional, Dict, Any
from datetime import datetime

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
        self.data_manager = None
        self.user_manager = None
        self.update_manager = None
        self.autostart = None
        self.system_tray = None
        self.auto_save_thread = None
        self.scheduler_thread = None
        self.csrf_tokens: Dict[str, float] = {}
        self.server_thread = None
        self.server_running = False
        self.shutdown_event = threading.Event()
        self.app_version = "1.5.0"
        self.build_number = "33"
        
    def initialize_data_manager(self, data_manager):
        """Initialize the data manager"""
        self.data_manager = data_manager
        
    def initialize_user_manager(self, user_manager):
        """Initialize the user manager"""
        self.user_manager = user_manager
        
    def initialize_update_manager(self, update_manager):
        """Initialize the update manager"""
        self.update_manager = update_manager
        
    def initialize_autostart(self, autostart):
        """Initialize the autostart manager"""
        self.autostart = autostart
        
    def set_system_tray(self, tray):
        """Set the system tray icon"""
        self.system_tray = tray
        
    def set_auto_save_thread(self, thread):
        """Set the auto-save thread"""
        self.auto_save_thread = thread
        
    def set_scheduler_thread(self, thread):
        """Set the scheduler thread"""
        self.scheduler_thread = thread
        
    def is_server_running(self) -> bool:
        """Check if server is running"""
        return self.server_running
        
    def start_server(self):
        """Mark server as running"""
        self.server_running = True
        
    def stop_server(self):
        """Mark server as stopped"""
        self.server_running = False
        self.shutdown_event.set()
        
    def cleanup(self):
        """Cleanup resources"""
        self.stop_server()
        if self.auto_save_thread and self.auto_save_thread.is_alive():
            self.auto_save_thread.join(timeout=2)
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=2)


# Global singleton instance
app_context = AppContext()

