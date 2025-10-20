#!/usr/bin/env python3
"""
Main entry point for Shakshuka application.
This file serves as the main entry point and imports the actual application from src/.
"""

import sys
import os

def setup_paths():
    """Setup Python paths for both development and bundled modes"""
    if getattr(sys, 'frozen', False):
        # Running as bundled executable
        base_path = sys._MEIPASS
        sys.path.insert(0, base_path)
    else:
        # Running as development script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)

def main():
    """Main application entry point"""
    setup_paths()
    
    try:
        # Import and run the main application with proper initialization
        from src.app import app, initialize_data_manager, start_auto_save, start_scheduler, start_system_tray
        
        print("Starting Shakshuka Task Manager...")
        print("Opening browser at http://127.0.0.1:8989")
        print("Press Ctrl+C to stop the application")
        print()
        
        # Initialize data manager
        print("Initializing data manager...")
        if not initialize_data_manager():
            print("Failed to initialize data manager")
            sys.exit(1)
        print("Data manager initialized successfully")
        
        # Start auto-save
        print("Starting auto-save...")
        start_auto_save()
        print("Auto-save started")
        
        # Start scheduler for daily resets
        print("Starting scheduler...")
        start_scheduler()
        print("Scheduler started")
        
        # Start system tray
        print("Attempting to start system tray...")
        try:
            start_system_tray()
            print("System tray started successfully")
        except Exception as e:
            print(f"Could not start system tray: {e}")
        
        # Open browser automatically
        import webbrowser
        import threading
        
        def open_browser():
            import time
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open('http://127.0.0.1:8989')
        
        # Start browser in a separate thread
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Run the Flask app
        print("Starting Shakshuka...")
        print("Opening browser at http://127.0.0.1:8989")
        print("System tray icon available for app management")
        print("Press Ctrl+C to stop the application")
        print()
        
        # Fix console encoding issues for PyInstaller
        import sys
        import os
        
        # Set console encoding to UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except:
                pass
        
        # Suppress Flask banner and CLI to avoid encoding issues
        os.environ['FLASK_SKIP_DOTENV'] = '1'
        os.environ['FLASK_CLI'] = '0'
        
        # Custom Flask runner to avoid click.echo issues
        try:
            from werkzeug.serving import run_simple
            print("Server starting on http://127.0.0.1:8989")
            run_simple('127.0.0.1', 8989, app, use_reloader=False, use_debugger=False)
        except Exception as e:
            print(f"Error starting server: {e}")
            # Fallback to standard Flask run
            app.run(host='127.0.0.1', port=8989, debug=False, use_reloader=False)
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please make sure all dependencies are installed and the src directory exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
