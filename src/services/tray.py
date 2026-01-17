from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

_tray_lock = threading.RLock()
_system_tray_icon: Optional[Any] = None
_system_tray_thread: Optional[threading.Thread] = None
_last_tray_error: Optional[str] = None


def get_system_tray_icon() -> Optional[Any]:
    with _tray_lock:
        return _system_tray_icon


def get_last_tray_error() -> Optional[str]:
    with _tray_lock:
        return _last_tray_error


def _set_last_tray_error(message: Optional[str]) -> None:
    global _last_tray_error
    with _tray_lock:
        _last_tray_error = message


def create_icon_image() -> Any:
    """Create icon image for the system tray."""
    try:
        from PIL import Image, ImageDraw

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_candidates = [
            os.path.join(base_dir, 'assets', 'static', 'images', 'icon.ico'),
            os.path.join(base_dir, 'assets', 'static', 'images', 'icon.png'),
        ]

        for path in icon_candidates:
            if os.path.exists(path):
                try:
                    logger.info(f"Loading system tray icon from {path}")
                    img = Image.open(path)
                    return img.convert('RGBA')
                except Exception as load_err:
                    logger.warning(f"Failed to load tray icon from {path}: {load_err}")

        image = Image.new('RGBA', (64, 64), color='#FF8C42')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white')
        draw.rectangle([30, 10, 34, 20], fill='#FF8C42')
        return image

    except Exception as e:
        logger.exception("Failed to create icon image")
        _set_last_tray_error(f"Failed to create tray icon image: {e}")
        try:
            from PIL import Image as _Image

            return _Image.new('RGBA', (64, 64), color='#FF8C42')
        except Exception:  # noqa: broad-except
            logger.exception("Failed to create fallback tray icon image")
            return None


def create_system_tray_icon(
    user_data_dir: str,
    dashboard_url: str,
    shutdown_url: str,
    check_available_func: Callable[[], bool],
) -> Optional[Any]:
    if not check_available_func():
        logger.warning("System tray not available - skipping icon creation")
        return None

    try:
        import pystray

        icon = create_icon_image()

        def open_dashboard():
            import webbrowser
            try:
                webbrowser.open(dashboard_url)
            except Exception as e:
                logger.exception("Failed to open dashboard")
                _set_last_tray_error(f"Failed to open dashboard: {e}")

        def open_logs_folder():
            folder = os.path.join(user_data_dir, 'logs')
            try:
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', folder])
                else:
                    subprocess.Popen(['xdg-open', folder])
            except Exception as e:
                logger.exception("Failed to open logs folder")
                _set_last_tray_error(f"Failed to open logs folder: {e}")

        def open_data_folder():
            folder = os.path.join(user_data_dir, 'data')
            try:
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', folder])
                else:
                    subprocess.Popen(['xdg-open', folder])
            except Exception as e:
                logger.exception("Failed to open data folder")
                _set_last_tray_error(f"Failed to open data folder: {e}")

        def quit_app():
            logger.info("Quitting application from system tray")
            last_error: Optional[Exception] = None
            for attempt in range(3):
                try:
                    req = urllib.request.Request(shutdown_url, data=b'', method='POST')
                    with urllib.request.urlopen(req, timeout=1):
                        return
                except Exception as e:
                    last_error = e
                    time.sleep(0.3)
            logger.error("Shutdown request failed after 3 attempts: %s", last_error)
            _set_last_tray_error(f"Shutdown request failed: {last_error}")
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard", lambda: open_dashboard()),
            pystray.MenuItem("Open Logs Folder", lambda: open_logs_folder()),
            pystray.MenuItem("Open Data Folder", lambda: open_data_folder()),
            pystray.MenuItem("Quit Shakshuka", lambda: quit_app()),
        )

        return pystray.Icon("shakshuka", icon, "Shakshuka Task Manager", menu)

    except Exception as e:
        error_msg = str(e)
        if 'Gtk' in error_msg or 'gtk' in error_msg.lower():
            logger.warning(f"System tray not available (GTK not available): {e}")
        elif 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
            logger.warning(f"System tray not available (AppIndicator not available): {e}")
        else:
            logger.exception("System tray not available")
            _set_last_tray_error(f"System tray error: {e}")
        return None


def start_system_tray(
    user_data_dir: str,
    dashboard_url: str,
    shutdown_url: str,
    check_available_func: Callable[[], bool],
) -> None:
    global _system_tray_icon, _system_tray_thread

    if not check_available_func():
        logger.warning("System tray not available")
        return

    try:
        with _tray_lock:
            if _system_tray_thread and _system_tray_thread.is_alive():
                logger.info("System tray already running")
                return
            _set_last_tray_error(None)

        icon = create_system_tray_icon(
            user_data_dir=user_data_dir,
            dashboard_url=dashboard_url,
            shutdown_url=shutdown_url,
            check_available_func=check_available_func,
        )

        with _tray_lock:
            _system_tray_icon = icon

        if _system_tray_icon:
            tray_thread = threading.Thread(target=_system_tray_icon.run, daemon=True)
            with _tray_lock:
                _system_tray_thread = tray_thread
            tray_thread.start()
            logger.info("System tray icon started successfully")
        else:
            logger.warning("Failed to create system tray icon")

    except Exception as e:
        error_msg = str(e)
        if 'Gtk' in error_msg or 'AyatanaAppIndicator3' in error_msg or 'AppIndicator3' in error_msg:
            logger.warning(f"System tray not available (GTK/AppIndicator not installed): {e}")
        elif 'g-io-error' in error_msg.lower() or 'Could not connect' in error_msg or 'D-Bus' in error_msg or 'dbus' in error_msg.lower():
            logger.warning(f"System tray not available (D-Bus connection error): {e}")
        else:
            logger.exception("Error starting system tray")
            _set_last_tray_error(f"Error starting tray: {e}")


def stop_system_tray() -> None:
    global _system_tray_icon, _system_tray_thread

    with _tray_lock:
        icon = _system_tray_icon

    if icon:
        try:
            icon.stop()
            logger.info("System tray icon stopped")
        except Exception as e:
            logger.exception("Error stopping system tray")
            _set_last_tray_error(f"Error stopping tray: {e}")
        finally:
            with _tray_lock:
                _system_tray_icon = None
                _system_tray_thread = None
