"""
Application Launcher - Handles application startup and initialization
"""
import sys
import os
import time
import threading
import webbrowser
import logging
from werkzeug.serving import run_simple

from src.core import config

logger = logging.getLogger(__name__)


class ApplicationLauncher:
    """Handles the complete application launch sequence"""
    
    def __init__(self):
        self.app = None
        self.app_context = None
        
    def setup_paths(self):
        """Setup Python paths for both development and bundled modes"""
        if getattr(sys, 'frozen', False):
            # Running as bundled executable
            base_path = sys._MEIPASS
            sys.path.insert(0, base_path)
        else:
            # Running as development script
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, current_dir)
        
        logger.info("Python paths configured")
    
    def setup_console_encoding(self):
        """Fix console encoding issues for PyInstaller"""
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
                logger.info("Console encoding set to UTF-8")
            except Exception as e:
                logger.warning(f"Could not reconfigure console encoding: {e}")
        
        # Suppress Flask banner and CLI to avoid encoding issues
        os.environ['FLASK_SKIP_DOTENV'] = '1'
        os.environ['FLASK_CLI'] = '0'
    
    def initialize_data_manager(self):
        """Initialize the data manager"""
        try:
            from src.app import initialize_data_manager
            
            logger.info("Initializing data manager...")
            if not initialize_data_manager():
                logger.error("Failed to initialize data manager")
                return False
            
            logger.info("Data manager initialized successfully")
            return True
        except Exception as e:
            # Check if error is actually from system tray (not data manager)
            error_msg = str(e)
            if 'Gtk' in error_msg or 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
                # This is a system tray error, not a data manager error
                logger.warning(f"System tray error during import (GTK/AppIndicator not installed): {e}")
                logger.info("This is not a data manager error - app will continue without system tray")
                # Try to initialize data manager again (without system tray)
                try:
                    from src.app import initialize_data_manager
                    if initialize_data_manager():
                        logger.info("Data manager initialized successfully (after system tray error)")
                        return True
                except Exception as e2:
                    logger.error(f"Error initializing data manager: {e2}")
                    return False
            else:
                logger.error(f"Error initializing data manager: {e}")
                return False
    
    def start_auto_save(self):
        """Start the auto-save background thread"""
        try:
            from src.app import start_auto_save
            
            logger.info("Starting auto-save...")
            start_auto_save()
            logger.info("Auto-save started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting auto-save: {e}")
            return False
    
    def start_scheduler(self):
        """Start the task scheduler for daily resets"""
        try:
            from src.app import start_scheduler
            
            logger.info("Starting scheduler...")
            start_scheduler()
            logger.info("Scheduler started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            return False
    
    def start_system_tray(self):
        """Start the system tray icon"""
        try:
            from src.app import start_system_tray
            
            logger.info("Starting system tray...")
            start_system_tray()
            logger.info("System tray started successfully")
            return True
        except Exception as e:
            # System tray is optional - don't fail the app if it doesn't work
            error_msg = str(e)
            if 'Gtk' in error_msg or 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
                logger.warning(f"System tray not available (GTK/AppIndicator not installed): {e}")
                logger.info("App will continue without system tray icon")
            else:
                logger.warning(f"Could not start system tray: {e}")
            return False  # Non-critical, app continues
    
    def open_browser_delayed(self, url, delay=1.5):
        """Open browser after a delay"""
        def open_browser():
            time.sleep(delay)
            try:
                webbrowser.open(url)
                logger.info(f"Opened browser at {url}")
            except Exception as e:
                logger.error(f"Could not open browser: {e}")
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
    
    def start_server(self):
        """Start the Flask web server"""
        try:
            from src.app import app
            self.app = app
            
            url = f"http://{config.DEFAULT_HOST}:{config.DEFAULT_PORT}"
            
            print("\n" + "="*60)
            print("🍳 Shakshuka Task Manager")
            print("="*60)
            print(f"Server: {url}")
            print(f"Status: Starting...")
            print("="*60)
            print("\n💡 Tips:")
            print("  • Access the app in your browser")
            print("  • System tray icon for quick access")
            print("  • Press Ctrl+C to stop the server")
            print("\n")
            
            # Open browser
            self.open_browser_delayed(url)
            
            # Start server
            logger.info(f"Starting server on {url}")
            run_simple(
                config.DEFAULT_HOST,
                config.DEFAULT_PORT,
                app,
                use_reloader=False,
                use_debugger=False
            )
            
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            # Fallback to standard Flask run
            try:
                self.app.run(
                    host=config.DEFAULT_HOST,
                    port=config.DEFAULT_PORT,
                    debug=False,
                    use_reloader=False
                )
            except Exception as fallback_error:
                logger.critical(f"Fallback server start failed: {fallback_error}")
                raise
    
    def launch(self):
        """
        Main launch sequence.
        Returns True if launch successful, False otherwise.
        """
        try:
            # Setup
            self.setup_paths()
            self.setup_console_encoding()
            
            # Initialize components
            if not self.initialize_data_manager():
                return False
            
            self.start_auto_save()
            self.start_scheduler()
            self.start_system_tray()  # Non-critical, continues even if fails
            
            # Start server (blocking call)
            self.start_server()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
            print("\n\n👋 Shutting down Shakshuka...")
            return True
            
        except Exception as e:
            logger.critical(f"Fatal error during launch: {e}", exc_info=True)
            print(f"\n❌ Error starting application: {e}")
            print("\nPlease check the logs for more details.")
            return False


def launch_application():
    """
    Main entry point for launching the application.
    Can be called from main.py or other entry points.
    """
    launcher = ApplicationLauncher()
    success = launcher.launch()
    sys.exit(0 if success else 1)

