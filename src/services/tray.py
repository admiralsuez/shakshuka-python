from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

_system_tray_icon: Optional[Any] = None


def get_system_tray_icon() -> Optional[Any]:
    return _system_tray_icon


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
        logger.error(f"Failed to create icon image: {e}")
        try:
            from PIL import Image as _Image

            return _Image.new('RGBA', (64, 64), color='#FF8C42')
        except Exception:
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

            webbrowser.open(dashboard_url)

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
                logger.error(f"Failed to open logs folder: {e}")

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
                logger.error(f"Failed to open data folder: {e}")

        def quit_app():
            logger.info("Quitting application from system tray")
            try:
                import requests

                requests.post(shutdown_url, timeout=1)
            except Exception:
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
            logger.warning(f"System tray not available: {e}")
        return None


def start_system_tray(
    user_data_dir: str,
    dashboard_url: str,
    shutdown_url: str,
    check_available_func: Callable[[], bool],
) -> None:
    global _system_tray_icon

    if not check_available_func():
        logger.warning("System tray not available")
        return

    try:
        _system_tray_icon = create_system_tray_icon(
            user_data_dir=user_data_dir,
            dashboard_url=dashboard_url,
            shutdown_url=shutdown_url,
            check_available_func=check_available_func,
        )

        if _system_tray_icon:
            tray_thread = threading.Thread(target=_system_tray_icon.run, daemon=True)
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
            logger.warning(f"Error starting system tray: {e}")


def stop_system_tray() -> None:
    global _system_tray_icon

    if _system_tray_icon:
        try:
            _system_tray_icon.stop()
            logger.info("System tray icon stopped")
        except Exception as e:
            logger.error(f"Error stopping system tray: {e}")
        finally:
            _system_tray_icon = None
