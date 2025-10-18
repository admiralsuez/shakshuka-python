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
        # Import and run the main application
        from src.app import app
        
        print("Starting Shakshuka Task Manager...")
        print("Opening browser at http://127.0.0.1:8989")
        print("Press Ctrl+C to stop the application")
        print()
        
        app.run(host='127.0.0.1', port=8989, debug=False, use_reloader=False)
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please make sure all dependencies are installed and the src directory exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
