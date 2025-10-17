"""
Graceful shutdown handling for Shakshuka application
"""
import signal
import sys
import threading
import time
from typing import Optional, Callable
from datetime import datetime

class GracefulShutdown:
    """Handle graceful shutdown of the application"""
    
    def __init__(self):
        self.shutdown_requested = False
        self.shutdown_callbacks = []
        self.shutdown_timeout = 30  # seconds
        self._shutdown_start_time: Optional[datetime] = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Windows-specific signals
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        print(f"\nReceived {signal_name} signal. Initiating graceful shutdown...")
        
        if self.shutdown_requested:
            print("Shutdown already in progress. Forcing exit...")
            sys.exit(1)
        
        self.shutdown_requested = True
        self._shutdown_start_time = datetime.now()
        
        # Start shutdown process in a separate thread to avoid blocking
        shutdown_thread = threading.Thread(target=self._perform_shutdown, daemon=True)
        shutdown_thread.start()
    
    def add_shutdown_callback(self, callback: Callable[[], None], name: str = ""):
        """Add a callback to be executed during shutdown"""
        self.shutdown_callbacks.append((callback, name))
    
    def _perform_shutdown(self):
        """Perform the actual shutdown process"""
        try:
            print("Starting graceful shutdown process...")
            
            # Execute shutdown callbacks
            for callback, name in self.shutdown_callbacks:
                try:
                    print(f"Executing shutdown callback: {name}")
                    callback()
                except Exception as e:
                    print(f"Error in shutdown callback '{name}': {e}")
            
            # Wait for shutdown to complete or timeout
            elapsed = 0
            while elapsed < self.shutdown_timeout:
                if not self._any_threads_running():
                    print("All threads completed. Shutdown successful.")
                    sys.exit(0)
                
                time.sleep(0.1)
                elapsed += 0.1
            
            print(f"Shutdown timeout reached ({self.shutdown_timeout}s). Forcing exit...")
            sys.exit(0)
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
            sys.exit(1)
    
    def _any_threads_running(self) -> bool:
        """Check if any non-daemon threads are still running"""
        active_threads = threading.active_count()
        daemon_threads = sum(1 for t in threading.enumerate() if t.daemon)
        
        # If we have more than 1 non-daemon thread (main thread + others), we're still running
        return active_threads - daemon_threads > 1
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self.shutdown_requested
    
    def get_shutdown_elapsed_time(self) -> Optional[float]:
        """Get elapsed time since shutdown was requested"""
        if self._shutdown_start_time:
            return (datetime.now() - self._shutdown_start_time).total_seconds()
        return None

# Global shutdown handler
shutdown_handler = GracefulShutdown()

def register_shutdown_callback(callback: Callable[[], None], name: str = ""):
    """Register a callback for graceful shutdown"""
    shutdown_handler.add_shutdown_callback(callback, name)

def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested"""
    return shutdown_handler.is_shutdown_requested()

def get_shutdown_elapsed_time() -> Optional[float]:
    """Get elapsed time since shutdown was requested"""
    return shutdown_handler.get_shutdown_elapsed_time()

