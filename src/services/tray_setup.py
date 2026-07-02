"""System tray service setup for Shakshuka.

Manages system tray icon initialization, menu creation, and teardown.
"""

import logging
import os
import sys
import subprocess
from typing import Callable, Optional, Any

from src.services import tray as tray_service

logger = logging.getLogger(__name__)


def check_system_tray_available(lazy_check: bool = True) -> bool:
    """Check if system tray is available on this platform.
    
    Args:
        lazy_check: If True, performs minimal check to avoid import errors.
                   If False, attempts actual pystray import.
    
    Returns:
        True if system tray might be available, False if definitely not.
    """
    if lazy_check:
        try:
            import pystray  # noqa: F401
            return True
        except ImportError:
            return False
    
    try:
        import pystray  # noqa: F401
        from PIL import Image, ImageDraw  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


def create_icon_image() -> Optional[Any]:
    """Create icon image for the system tray.
    
    Prefers the real app icon file (icon.ico / icon.png) so the tray matches
    the EXE/installer icon. Falls back to a drawn leaf icon if loading fails.
    
    Returns:
        PIL Image object or None if creation fails
    """
    try:
        from PIL import Image, ImageDraw

        # Determine app root both in dev and frozen (PyInstaller) modes
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_candidates = [
            os.path.join(base_dir, "assets", "static", "images", "icon.ico"),
            os.path.join(base_dir, "assets", "static", "images", "icon.png"),
        ]

        for path in icon_candidates:
            if os.path.exists(path):
                try:
                    logger.info(f"Loading system tray icon from {path}")
                    img = Image.open(path)
                    return img.convert("RGBA")
                except Exception as load_err:
                    logger.warning(f"Failed to load tray icon from {path}: {load_err}")

        # Fallback: draw the original simple leaf icon
        image = Image.new("RGBA", (64, 64), color="#FF8C42")
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill="white")  # Main leaf body
        draw.rectangle([30, 10, 34, 20], fill="#FF8C42")  # Stem
        return image

    except Exception as e:
        logger.error(f"Failed to create icon image: {e}")
        # Final fallback: simple colored square
        try:
            from PIL import Image as _Image

            return _Image.new("RGBA", (64, 64), color="#FF8C42")
        except Exception:  # noqa: broad-except
            return None


def start_system_tray(
    user_data_dir: str,
    dashboard_url: str,
    shutdown_url: str,
    config: Optional[Any] = None,
) -> None:
    """Start the system tray icon with menu.
    
    Args:
        user_data_dir: Path to user data directory
        dashboard_url: URL to open when clicking "Open Dashboard"
        shutdown_url: API endpoint URL for shutting down the server
        config: Optional configuration object
    """
    try:
        if not check_system_tray_available(lazy_check=True):
            logger.warning("System tray not available - skipping icon creation")
            return

        tray_service.start_system_tray(
            user_data_dir=user_data_dir,
            dashboard_url=dashboard_url,
            shutdown_url=shutdown_url,
            check_available_func=check_system_tray_available,
        )
        logger.info("System tray started successfully")
    except Exception as e:
        logger.warning(f"Error starting system tray: {e}")


def stop_system_tray() -> None:
    """Stop and cleanup the system tray icon."""
    try:
        tray_service.stop_system_tray()
        logger.info("System tray stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping system tray: {e}")


def open_url_in_browser(url: str) -> None:
    """Open a URL in the default web browser.
    
    Args:
        url: URL to open
    """
    try:
        import webbrowser

        webbrowser.open(url)
        logger.info(f"Opened URL in browser: {url}")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")


def open_folder(folder_path: str) -> None:
    """Open a folder in the system file manager.
    
    Args:
        folder_path: Path to the folder to open
    """
    try:
        if not os.path.exists(folder_path):
            logger.warning(f"Folder does not exist: {folder_path}")
            return

        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])

        logger.info(f"Opened folder in file manager: {folder_path}")
    except Exception as e:
        logger.error(f"Failed to open folder: {e}")
