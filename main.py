#!/usr/bin/env python3
"""
Main entry point for Shakshuka application.
Simplified launcher that delegates to the core launcher module.
"""

import sys
import os
import time
import socket
import urllib.request
import urllib.error
import subprocess


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


def _shutdown_running_instance() -> int:
    try:
        from src.core.config import config

        host = config.DEFAULT_HOST
        port = int(config.DEFAULT_PORT)
        url = f"http://{host}:{port}/api/shutdown"
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                try:
                    resp.read()
                except Exception:
                    pass
        except urllib.error.HTTPError as e:
            print(f"Shutdown request failed ({e.code}).")
            return 1
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return 0

        def _is_port_open() -> bool:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            try:
                s.connect((host, port))
                return True
            except OSError:
                return False
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        deadline = time.time() + 8
        while time.time() < deadline:
            if not _is_port_open():
                return 0
            time.sleep(0.2)

        # Fallback: if server is still up, force-close the running executable (Windows).
        if os.name == 'nt' and _is_port_open():
            try:
                subprocess.run(
                    ['taskkill', '/IM', 'Shakshuka.exe', '/T', '/F'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

            deadline2 = time.time() + 6
            while time.time() < deadline2:
                if not _is_port_open():
                    return 0
                time.sleep(0.2)

        return 1 if _is_port_open() else 0
    except Exception as e:
        print(f"Failed to request shutdown: {e}")
        return 1


def main():
    """Main application entry point"""
    # Setup paths first
    setup_paths()

    if any(arg == '--shutdown' for arg in sys.argv[1:]):
        sys.exit(_shutdown_running_instance())
    
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

