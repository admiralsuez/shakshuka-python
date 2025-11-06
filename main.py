#!/usr/bin/env python3
"""
Main entry point for Shakshuka application.
Simplified launcher that delegates to the core launcher module.
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
    # Setup paths first
    setup_paths()
    
    try:
        # Import and launch the application
        from src.core.launcher import launch_application
        launch_application()
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("\n💡 Troubleshooting:")
        print("  • Make sure all dependencies are installed")
        print("  • Run: pip install -r config/requirements.txt")
        print("  • Ensure the src/ directory exists")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

