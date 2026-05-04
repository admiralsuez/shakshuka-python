"""
Update Manager for Shakshuka
Handles OTA updates, manual updates, data preservation, and backups
"""

import os
import json
import shutil
import zipfile
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple
import hashlib
import subprocess
import sys

from src.exceptions import ValidationError

# Try to import requests, but handle gracefully if not available
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests module not available. Update functionality will be limited.")

# Repo constants
try:
    from src.constants import GITHUB_REPO_OWNER, GITHUB_REPO_NAME
except Exception:  # noqa: broad-except
    GITHUB_REPO_OWNER = "admiralsuez"
    GITHUB_REPO_NAME = "shakshuka-python"


class UpdateManagerError(Exception):
    pass


class UpdateIOError(UpdateManagerError):
    pass


class UpdateIntegrityError(UpdateManagerError):
    pass


class UpdateCancelled(UpdateManagerError):
    pass

class UpdateManager:
    def __init__(self, app_dir: str, data_dir: str = "data"):
        if not app_dir or not isinstance(app_dir, str):
            raise ValidationError(message="Invalid app_dir", details={'app_dir': app_dir})
        if not data_dir or not isinstance(data_dir, str):
            raise ValidationError(message="Invalid data_dir", details={'data_dir': data_dir})

        self.app_dir = Path(app_dir)
        self.data_dir = Path(data_dir)

        if not self.app_dir.exists():
            raise UpdateIOError(f"app_dir does not exist: {self.app_dir}")

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Failed to create data_dir: {self.data_dir}") from e

        self.backup_dir = self.data_dir / "backups"
        # Store downloaded updates in user-writable data directory to avoid Program Files permission issues
        self.update_dir = self.data_dir / "updates"
        self.version_file = self.app_dir / "config" / "version.json"
        self.update_config_file = self.data_dir / "update_config.json"
        
        # Create necessary directories (all under user data dir)
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            self.update_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, IOError) as e:
            raise UpdateIOError("Failed to initialize update/backup directories") from e
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Load current version
        self.current_version = self._load_current_version()
        
        # Load update configuration
        self.update_config = self._load_update_config()
        
        # Update check thread
        self.update_check_thread = None
        self.update_check_enabled = True
        
        # Download/Install state
        self._download_lock = threading.RLock()
        self._download_progress = 0.0
        self._download_status = 'idle'  # idle | downloading | ready | installing | completed | failed | canceled
        self._download_error = None
        self._download_error_type = None  # io | integrity | canceled | validation | unknown
        self._download_total = 0
        self._download_downloaded = 0
        self._download_cancel_event = threading.Event()
        self._current_update_file = None  # absolute path to downloaded file
        self._current_update_version = None
        self._download_thread = None
        
    def _load_current_version(self) -> Dict:
        """Load current application version"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r') as f:
                    payload = json.load(f)
            except (OSError, IOError) as e:
                raise ValidationError(message="Failed to read version file", details={'path': str(self.version_file)}, cause=e)
            except json.JSONDecodeError as e:
                raise ValidationError(message="Invalid JSON in version file", details={'path': str(self.version_file)}, cause=e)

            if not isinstance(payload, dict):
                raise ValidationError(message="Invalid version file format", details={'path': str(self.version_file)})

            version = payload.get('version')
            build = payload.get('build')
            if not isinstance(version, str) or not version.strip():
                raise ValidationError(message="Invalid version value", details={'path': str(self.version_file), 'version': version})
            if not isinstance(build, (str, int)):
                raise ValidationError(message="Invalid build value", details={'path': str(self.version_file), 'build': build})
            return payload

        # Fall back to default version info without writing to app_dir (may be read-only)
        version_info = {
            "version": "1.0.0",
            "build": "1",
            "release_date": datetime.now().isoformat(),
            "update_channel": "stable"
        }
        return version_info
    
    def _save_version_info(self, version_info: Dict):
        """Save version information"""
        try:
            # Try writing to app_dir version file first
            with open(self.version_file, 'w') as f:
                json.dump(version_info, f, indent=2)
        except Exception as e:
            # Fallback: write a copy to data_dir so UI can optionally read it
            try:
                fallback = self.data_dir / 'version.json'
                with open(fallback, 'w') as f:
                    json.dump(version_info, f, indent=2)
                self.logger.warning(f"Could not save version to {self.version_file}: {e}; saved to {fallback} instead")
            except Exception as e2:
                self.logger.error(f"Error saving version: {e2}")
    
    def _load_update_config(self) -> Dict:
        """Load update configuration"""
        if self.update_config_file.exists():
            try:
                with open(self.update_config_file, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
            except (OSError, IOError) as e:
                raise UpdateIOError(f"Failed to read update config: {self.update_config_file}") from e
            except json.JSONDecodeError as e:
                raise UpdateIntegrityError(f"Invalid JSON in update config: {self.update_config_file}") from e
            if payload is None:
                payload = {}
            if not isinstance(payload, dict):
                raise UpdateIntegrityError("Invalid update config format")
            return payload

        config = {
            "auto_check_enabled": True,
            "check_interval_hours": 24,
            "auto_install_enabled": False,
            "backup_before_update": True,
            "update_channel": "stable",
            "last_check": None,
            # Default to GitHub latest release API
            "update_server_url": f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
        }
        self._save_update_config(config)
        return config
    
    def _save_update_config(self, config: Dict):
        """Save update configuration"""
        try:
            with open(self.update_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Error saving update config: {self.update_config_file}") from e
    
    def check_for_updates(self) -> Optional[Dict]:
        """Check for available updates"""
        if not self.update_config.get("auto_check_enabled", True):
            return None

        last_check = self.update_config.get("last_check")
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
            except ValueError as e:
                raise UpdateIntegrityError(f"Invalid last_check timestamp: {last_check}") from e
            check_interval = timedelta(hours=self.update_config.get("check_interval_hours", 24))
            if datetime.now() - last_check_time < check_interval:
                return None

        self.update_config["last_check"] = datetime.now().isoformat()
        self._save_update_config(self.update_config)

        if not REQUESTS_AVAILABLE:
            raise UpdateIOError("Requests module not available. Cannot check for updates.")

        url = self.update_config.get("update_server_url", "")
        if not url:
            raise UpdateIntegrityError("Missing update_server_url")

        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            raise UpdateIOError(f"Failed to reach update server: {e}") from e

        if response.status_code != 200:
            raise UpdateIOError(f"Update server returned HTTP {response.status_code}")

        try:
            release_info = response.json()
        except Exception as e:
            raise UpdateIntegrityError(f"Invalid JSON response from update server: {e}") from e

        latest_version = str(release_info.get("tag_name", "")).lstrip("v")
        if not latest_version:
            raise UpdateIntegrityError("Update response missing tag_name")

        assets = release_info.get("assets", []) or []
        download_url = ""
        file_size = 0

        platform_extensions = {
            'win32': ['.exe'],
            'linux': ['.deb'],
            'darwin': ['.dmg', '.pkg']
        }
        current_platform = sys.platform
        preferred_extensions = platform_extensions.get(current_platform, ['.zip'])

        for ext in preferred_extensions:
            for a in assets:
                name = str(a.get("name", "")).lower()
                if name.endswith(ext):
                    download_url = str(a.get("browser_download_url", ""))
                    file_size = int(a.get("size", 0) or 0)
                    break
            if download_url:
                break

        if not download_url:
            for a in assets:
                name = str(a.get("name", "")).lower()
                if name.endswith('.zip'):
                    download_url = str(a.get("browser_download_url", ""))
                    file_size = int(a.get("size", 0) or 0)
                    break

        if not download_url and assets:
            first = assets[0]
            download_url = str(first.get("browser_download_url", ""))
            file_size = int(first.get("size", 0) or 0)

        if not download_url:
            raise UpdateIntegrityError("No downloadable asset found in update response")

        if self._is_newer_version(latest_version, self.current_version["version"]):
            return {
                "version": latest_version,
                "release_notes": release_info.get("body", ""),
                "download_url": download_url,
                "file_size": file_size,
                "published_at": release_info.get("published_at", ""),
                "prerelease": bool(release_info.get("prerelease", False))
            }

        return None
    
    def _is_newer_version(self, new_version: str, current_version: str) -> bool:
        """Compare version strings"""
        def _parse_parts(v: str) -> List[int]:
            if not isinstance(v, str) or not v.strip():
                raise ValidationError(message="Invalid version string", details={'version': v})
            parts: List[int] = []
            for p in v.strip().split('.'):
                if p == '':
                    raise ValidationError(message="Invalid version string", details={'version': v})
                try:
                    parts.append(int(p))
                except Exception as e:
                    raise ValidationError(message="Invalid version component", details={'version': v, 'component': p}, cause=e)
            return parts

        new_parts = _parse_parts(new_version)
        current_parts = _parse_parts(current_version)

        max_len = max(len(new_parts), len(current_parts))
        new_parts.extend([0] * (max_len - len(new_parts)))
        current_parts.extend([0] * (max_len - len(current_parts)))

        return new_parts > current_parts
    
    def download_update(self, update_info: Dict, progress_callback=None) -> bool:
        """Download update package (synchronous) with internal progress tracking.
        Prefer using start_download() to run in background and query progress via get_download_status().
        """
        if not REQUESTS_AVAILABLE:
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'io'
                self._download_error = 'Requests module not available. Cannot download updates.'
            return False

        temp_path = None
        try:
            if update_info is None or not isinstance(update_info, dict):
                raise ValidationError(message='update_info must be a JSON object')

            download_url = update_info.get("download_url")
            if not download_url or not isinstance(download_url, str):
                raise ValidationError(message='download_url required')

            version = update_info.get("version", "unknown")
            if not isinstance(version, str) or not version.strip():
                raise ValidationError(message='version required')
            
            with self._download_lock:
                self._download_status = 'downloading'
                self._download_error = None
                self._download_progress = 0.0
                self._download_total = 0
                self._download_downloaded = 0
                self._download_cancel_event.clear()
                self._current_update_file = None
                self._current_update_version = version
            
            # Create temporary file for download
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_path = temp_file.name
            
            try:
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
            except Exception as e:
                raise UpdateIOError(f"Download failed: {e}") from e
            
            total_size = int(response.headers.get('content-length', 0))
            with self._download_lock:
                self._download_total = total_size
            
            downloaded_size = 0
            
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._download_cancel_event.is_set():
                        raise UpdateCancelled('Download canceled')
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        with self._download_lock:
                            self._download_downloaded = downloaded_size
                            if total_size > 0:
                                self._download_progress = (downloaded_size / total_size) * 100.0
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress)
            
            if total_size > 0 and downloaded_size != total_size:
                raise UpdateIntegrityError(f"Downloaded size mismatch (downloaded={downloaded_size}, expected={total_size})")

            # Move to update directory
            update_file = self.update_dir / f"update_{version}.zip"
            shutil.move(temp_file.name, update_file)
            temp_path = None
            
            with self._download_lock:
                self._download_status = 'ready'
                self._current_update_file = str(update_file)
                self._download_progress = 100.0
            
            return True
            
        except UpdateCancelled as e:
            self.logger.info(str(e))
            with self._download_lock:
                self._download_status = 'canceled'
                self._download_error_type = 'canceled'
                self._download_error = str(e)
                self._download_progress = 0.0
            return False
        except ValidationError as e:
            self.logger.error(f"Download validation error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'validation'
                self._download_error = str(e)
            return False
        except UpdateIntegrityError as e:
            self.logger.error(f"Download integrity error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'integrity'
                self._download_error = str(e)
            return False
        except (OSError, IOError) as e:
            self.logger.error(f"Download IO error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'io'
                self._download_error = str(e)
            return False
        except Exception as e:
            self.logger.exception("Error downloading update")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'unknown'
                self._download_error = str(e)
            return False
        finally:
            if temp_path:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except OSError as e:
                    self.logger.debug("Failed to cleanup temp download file: %s", e)
    
    def start_download(self, update_info: Dict) -> None:
        """Start download in background thread."""
        if self._download_thread and self._download_thread.is_alive():
            # Already downloading
            return
        def worker():
            try:
                self.download_update(update_info)
            except Exception as e:
                self.logger.exception("Download worker error")
                with self._download_lock:
                    self._download_status = 'failed'
                    self._download_error_type = 'unknown'
                    self._download_error = str(e)
        self._download_thread = threading.Thread(target=worker, daemon=True)
        self._download_thread.start()
    
    def get_download_status(self) -> Dict:
        """Return current download/install status for polling."""
        with self._download_lock:
            return {
                'status': self._download_status,
                'progress': round(self._download_progress, 2),
                'downloaded': self._download_downloaded,
                'total': self._download_total,
                'error': self._download_error,
                'error_type': self._download_error_type,
                'update_file': os.path.basename(self._current_update_file) if self._current_update_file else None,
                'update_file_path': self._current_update_file,
                'version': self._current_update_version,
            }
    
    def cancel_download(self) -> None:
        with self._download_lock:
            if self._download_status == 'downloading':
                self._download_cancel_event.set()
            else:
                # No-op for other states
                pass
    
    def install_update_platform_specific(self, update_file: str, backup_data: bool = True) -> bool:
        """Install downloaded update using platform-specific method"""
        try:
            with self._download_lock:
                self._download_status = 'installing'
                self._download_error = None
                self._download_error_type = None
            
            # Resolve relative to update_dir if necessary
            if not os.path.isabs(update_file):
                update_file = str(self.update_dir / update_file)
            
            # Determine platform and install method
            platform = sys.platform

            # Validate platform assumptions and update file presence
            if not os.path.exists(update_file):
                raise UpdateIOError(f"Update file not found: {update_file}")
            if not os.path.isfile(update_file):
                raise UpdateIOError(f"Update path is not a file: {update_file}")
            
            if platform == 'win32':
                if update_file.lower().endswith('.exe'):
                    ok = self._install_windows(update_file, backup_data)
                else:
                    ok = self._install_generic(update_file, backup_data)
            elif platform.startswith('linux'):
                if update_file.lower().endswith('.deb'):
                    ok = self._install_linux(update_file, backup_data)
                else:
                    ok = self._install_generic(update_file, backup_data)
            elif platform == 'darwin':
                ok = self._install_macos(update_file, backup_data)
            else:
                ok = self._install_generic(update_file, backup_data)

            with self._download_lock:
                if ok:
                    self._download_status = 'completed'
                else:
                    self._download_status = 'failed'
                    if not self._download_error:
                        self._download_error = 'Install failed'
                    if not self._download_error_type:
                        self._download_error_type = 'unknown'

            return ok
                
        except UpdateIOError as e:
            self.logger.error(f"Install IO error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'io'
                self._download_error = str(e)
            return False
        except UpdateIntegrityError as e:
            self.logger.error(f"Install integrity error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'integrity'
                self._download_error = str(e)
            return False
        except ValidationError as e:
            self.logger.error(f"Install validation error: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'validation'
                self._download_error = str(e)
            return False
        except Exception as e:
            self.logger.exception("Error installing update")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error_type = 'unknown'
                self._download_error = str(e)
            return False
    
    def _install_windows(self, update_file: str, backup_data: bool) -> bool:
        """Install update on Windows using installer .exe"""
        try:
            if backup_data:
                self.create_backup("pre_update")
            
            # Check if it's an installer .exe
            if update_file.lower().endswith('.exe'):
                # Run installer silently
                self.logger.info(f"Running Windows installer: {update_file}")
                result = subprocess.run(
                    [update_file, '/SILENT', '/NORESTART'],
                    check=True,
                    timeout=300  # 5 minute timeout
                )
                self.logger.info("Windows installer completed successfully")
                return True
            else:
                # Fallback to generic installation
                return self._install_generic(update_file, backup_data)
                
        except subprocess.TimeoutExpired as e:
            raise UpdateIOError("Installer timeout") from e
        except subprocess.CalledProcessError as e:
            raise UpdateIOError(f"Installer failed: {e}") from e
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Error installing Windows update: {e}") from e
    
    def _install_linux(self, update_file: str, backup_data: bool) -> bool:
        """Install update on Linux using .deb package"""
        try:
            if backup_data:
                self.create_backup("pre_update")
            
            # Check if it's a .deb package
            if update_file.lower().endswith('.deb'):
                self.logger.info(f"Installing Linux .deb package: {update_file}")
                
                # Install using dpkg
                result = subprocess.run(
                    ['sudo', 'dpkg', '-i', update_file],
                    check=True,
                    timeout=300
                )
                
                # Fix dependencies if needed
                subprocess.run(
                    ['sudo', 'apt-get', 'install', '-f', '-y'],
                    timeout=120,
                    capture_output=True
                )
                
                self.logger.info("Linux package installed successfully")
                return True
            else:
                # Fallback to generic installation
                return self._install_generic(update_file, backup_data)
                
        except subprocess.TimeoutExpired as e:
            raise UpdateIOError("Package installation timeout") from e
        except subprocess.CalledProcessError as e:
            raise UpdateIOError(f"Package installation failed: {e}") from e
        except FileNotFoundError as e:
            raise UpdateIOError("dpkg not found. Cannot install .deb package.") from e
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Error installing Linux update: {e}") from e
    
    def _install_macos(self, update_file: str, backup_data: bool) -> bool:
        """Install update on macOS using .dmg or .app"""
        try:
            if backup_data:
                self.create_backup("pre_update")
            
            # Check if it's a .dmg file
            if update_file.lower().endswith('.dmg'):
                self.logger.info(f"Installing macOS .dmg: {update_file}")
                
                # Mount DMG
                mount_point = tempfile.mkdtemp()
                result = subprocess.run(
                    ['hdiutil', 'attach', update_file, '-mountpoint', mount_point, '-nobrowse'],
                    check=True,
                    capture_output=True
                )
                
                try:
                    # Find .app bundle in mounted DMG
                    app_bundle = None
                    for item in Path(mount_point).iterdir():
                        if item.suffix == '.app':
                            app_bundle = item
                            break
                    
                    if app_bundle:
                        # Copy .app to Applications
                        applications_dir = Path.home() / 'Applications'
                        dest_app = applications_dir / app_bundle.name
                        
                        # Remove old version if exists
                        if dest_app.exists():
                            shutil.rmtree(dest_app)
                        
                        # Copy new version
                        shutil.copytree(app_bundle, dest_app)
                        self.logger.info(f"macOS app installed to: {dest_app}")
                    else:
                        raise UpdateIntegrityError("No .app bundle found in DMG")
                        
                finally:
                    # Unmount DMG
                    subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)
                    shutil.rmtree(mount_point, ignore_errors=True)
                
                return True
            else:
                # Fallback to generic installation
                return self._install_generic(update_file, backup_data)
                
        except subprocess.CalledProcessError as e:
            raise UpdateIOError(f"macOS installation failed: {e}") from e
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Error installing macOS update: {e}") from e
    
    def _install_generic(self, update_file: str, backup_data: bool) -> bool:
        """Generic installation method (extract zip and copy files)"""
        try:
            if backup_data:
                self.create_backup("pre_update")
            
            # Extract update package
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                # Extract to temporary directory
                temp_extract = tempfile.mkdtemp()
                zip_ref.extractall(temp_extract)
                
                # Copy files, preserving data directory
                for root, dirs, files in os.walk(temp_extract):
                    for file in files:
                        src_path = os.path.join(root, file)
                        rel_path = os.path.relpath(src_path, temp_extract)
                        dst_path = self.app_dir / rel_path
                        
                        # Skip data directory
                        if "data" in rel_path.split(os.sep):
                            continue
                        
                        # Ensure destination directory exists
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy file
                        shutil.copy2(src_path, dst_path)
                
                # Clean up temporary directory
                shutil.rmtree(temp_extract)
            
            # Update version info
            new_version_info = {
                "version": self._extract_version_from_filename(update_file),
                "build": str(int(self.current_version.get("build", 1)) + 1),
                "release_date": datetime.now().isoformat(),
                "update_channel": self.current_version.get("update_channel", "stable")
            }
            self._save_version_info(new_version_info)
            
            with self._download_lock:
                self._current_update_file = update_file
                self.current_version = new_version_info
            
            return True
            
        except zipfile.BadZipFile as e:
            raise UpdateIntegrityError(f"Invalid update zip: {e}") from e
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Error in generic installation: {e}") from e
    
    def install_update(self, update_file: str, backup_data: bool = True) -> bool:
        """Install downloaded update (backward compatibility - uses platform-specific method)"""
        return self.install_update_platform_specific(update_file, backup_data)
    
    def _extract_version_from_filename(self, filename: str) -> str:
        """Extract version from update filename"""
        if not filename or not isinstance(filename, str):
            raise ValidationError(message="Invalid filename", details={'filename': filename})

        basename = os.path.basename(filename)
        if not basename.startswith('update_'):
            raise ValidationError(message="Unexpected update filename", details={'filename': basename})

        if basename.lower().endswith('.zip'):
            version_part = basename[len('update_'):-len('.zip')]
        else:
            version_part = basename[len('update_'):]

        if not version_part:
            raise ValidationError(message="Missing version in update filename", details={'filename': basename})

        # Validate that it parses as a version.
        _ = self._is_newer_version(version_part, '0.0.0')
        return version_part
    
    def create_backup(self, backup_type: str = "manual") -> str:
        """Create backup of current data"""
        if not backup_type or not isinstance(backup_type, str) or backup_type.strip() == "":
            raise ValidationError(message="Invalid backup_type", details={'backup_type': backup_type})

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            backup_name = f"{backup_type}_{timestamp}_{int(time.time())}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=False)
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Failed to create backup dir: {backup_path}") from e

        if not self.data_dir.exists():
            raise UpdateIOError(f"Data directory does not exist: {self.data_dir}")

        try:
            for item in self.data_dir.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    shutil.copy2(item, backup_path / item.name)
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Failed copying files into backup: {backup_name}") from e

        try:
            manifest = {
                "backup_type": backup_type,
                "created_at": datetime.now().isoformat(),
                "version": self.current_version["version"],
                "files": [f.name for f in backup_path.iterdir() if f.is_file()]
            }
            with open(backup_path / "manifest.json", 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
        except (OSError, IOError) as e:
            raise UpdateIOError(f"Failed writing backup manifest: {backup_name}") from e

        self._cleanup_old_backups()
        return backup_name
    
    def _cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backups, keeping only the most recent ones"""
        try:
            backups = []
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    manifest_file = backup_dir / "manifest.json"
                    if manifest_file.exists():
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                        backups.append((backup_dir, manifest.get("created_at", "")))
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old backups
            for backup_dir, _ in backups[keep_count:]:
                shutil.rmtree(backup_dir)
                
        except Exception as e:
            self.logger.error(f"Error cleaning up backups: {e}")
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore from backup"""
        try:
            if not backup_name or not isinstance(backup_name, str):
                raise ValidationError(message='backup_name required')
            if os.path.basename(backup_name) != backup_name:
                raise ValidationError(message='Invalid backup_name')

            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                return False

            manifest_file = backup_path / "manifest.json"
            if not manifest_file.exists():
                raise UpdateIntegrityError("Backup manifest missing")

            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except (OSError, IOError) as e:
                raise UpdateIOError(f"Failed to read backup manifest: {e}") from e
            except json.JSONDecodeError as e:
                raise UpdateIntegrityError(f"Invalid backup manifest JSON: {e}") from e

            files = manifest.get("files", [])
            if not isinstance(files, list):
                raise UpdateIntegrityError("Invalid backup manifest format")

            file_names: List[str] = []
            for fn in files:
                if not isinstance(fn, str):
                    raise UpdateIntegrityError("Invalid filename in manifest")
                if fn == 'manifest.json':
                    continue
                if os.path.basename(fn) != fn:
                    raise UpdateIntegrityError("Invalid filename in manifest")
                file_names.append(fn)

            stage_dir = Path(tempfile.mkdtemp(prefix='restore_stage_', dir=str(self.data_dir)))
            rollback_dir = Path(tempfile.mkdtemp(prefix='restore_rollback_', dir=str(self.data_dir)))

            try:
                # Stage restore files
                for fn in file_names:
                    src_file = backup_path / fn
                    if not src_file.exists():
                        raise UpdateIntegrityError(f"Backup file missing: {fn}")
                    shutil.copy2(src_file, stage_dir / fn)

                # Move current files to rollback
                for fn in file_names:
                    dst_file = self.data_dir / fn
                    if dst_file.exists():
                        shutil.move(str(dst_file), str(rollback_dir / fn))

                # Move staged files into place
                for fn in file_names:
                    shutil.move(str(stage_dir / fn), str(self.data_dir / fn))

                return True

            except Exception as e:
                # Roll back any partial restore
                for fn in file_names:
                    dst_file = self.data_dir / fn
                    try:
                        if dst_file.exists():
                            os.remove(dst_file)
                    except OSError as e:
                        self.logger.warning("Failed to remove file during restore rollback: %s", e)

                for fn in file_names:
                    rb_file = rollback_dir / fn
                    if rb_file.exists():
                        shutil.move(str(rb_file), str(self.data_dir / fn))

                raise e
            finally:
                shutil.rmtree(stage_dir, ignore_errors=True)
                shutil.rmtree(rollback_dir, ignore_errors=True)
            
        except ValidationError as e:
            self.logger.error(f"Restore validation error: {e}")
            return False
        except UpdateIntegrityError as e:
            self.logger.error(f"Restore integrity error: {e}")
            return False
        except (OSError, IOError) as e:
            self.logger.error(f"Restore IO error: {e}")
            return False
        except Exception as e:
            self.logger.exception("Error restoring backup")
            return False
    
    def get_backup_list(self) -> List[Dict]:
        """Get list of available backups"""
        backups = []
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                manifest_file = backup_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                    except (OSError, IOError) as e:
                        raise UpdateIOError(f"Failed to read backup manifest: {manifest_file}") from e
                    except json.JSONDecodeError as e:
                        raise UpdateIntegrityError(f"Invalid backup manifest JSON: {manifest_file}") from e

                    backups.append({
                        "name": backup_dir.name,
                        "type": manifest.get("backup_type", "unknown"),
                        "created_at": manifest.get("created_at", ""),
                        "version": manifest.get("version", "unknown")
                    })

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups
    
    def stop_auto_update_check(self):
        """Stop automatic update checking (deprecated - scheduler handles this)"""
        self.update_check_enabled = False
        if self.update_check_thread:
            self.update_check_thread.join(timeout=5)
    
    def _setup_auto_update_scheduler(self):
        """Setup auto-update checking with scheduler instead of daemon thread"""
        try:
            from src.services.scheduler import scheduler_service
            
            check_interval_hours = self.update_config.get("check_interval_hours", 24)
            
            # Schedule update check every N hours
            scheduler_service.schedule_job(
                'auto_update_check',
                job_func=self._check_and_install_update,
                trigger='interval',
                hours=check_interval_hours,
                replace_existing=True
            )
            
            self.logger.info(f"Auto-update check scheduled every {check_interval_hours} hours")
        except Exception as e:
            self.logger.exception("Failed to setup auto-update scheduler: %s", e)
    
    def _check_and_install_update(self):
        """Check for updates and install if auto-install enabled"""
        try:
            update_info = self.check_for_updates()
            
            if not update_info:
                self.logger.debug("No updates available")
                return
            
            self.logger.info(f"Update available: {update_info['version']}")
            
            if not self.update_config.get("auto_install_enabled", False):
                self.logger.info("Auto-install disabled, skipping")
                return
            
            # Start download in background (non-blocking)
            self.start_download(update_info)
            self.logger.info(f"Download started for version {update_info['version']}")
            
            # Don't wait for download - let it complete asynchronously
            # The download status endpoint will handle progress
            
        except UpdateIOError as e:
            self.logger.error(f"Auto update check IO error: {e}")
        except UpdateIntegrityError as e:
            self.logger.error(f"Auto update check integrity error: {e}")
        except ValidationError as e:
            self.logger.error(f"Auto update check validation error: {e}")
        except Exception as e:
            self.logger.exception("Error in auto update check")
    
    def _setup_weekly_backup_scheduler(self):
        """Setup weekly backup with scheduler instead of daemon thread"""
        try:
            from src.services.scheduler import scheduler_service
            
            # Schedule backup every Sunday at 2 AM
            scheduler_service.schedule_job(
                'weekly_backup',
                job_func=self._perform_weekly_backup,
                trigger='cron',
                day_of_week='sun',
                hour=2,
                minute=0,
                replace_existing=True
            )
            
            self.logger.info("Weekly backup scheduled for Sundays at 2:00 AM")
        except Exception as e:
            self.logger.exception("Failed to setup weekly backup scheduler: %s", e)
    
    def _perform_weekly_backup(self):
        """Perform weekly backup"""
        try:
            backup_name = self.create_backup("weekly")
            self.update_config["last_weekly_backup"] = datetime.now().isoformat()
            self.update_config["last_weekly_backup_name"] = backup_name
            self._save_update_config(self.update_config)
            self.logger.info("Weekly backup created successfully: %s", backup_name)
        except UpdateManagerError as e:
            self.logger.error(f"Error in weekly backup: {e}")
        except ValidationError as e:
            self.logger.error(f"Error in weekly backup: {e}")
        except Exception:  # noqa: broad-except
            self.logger.exception("Error in weekly backup")
    
    def get_update_status(self) -> Dict:
        """Get current update status"""
        return {
            "current_version": self.current_version["version"],
            "current_build": self.current_version["build"],
            "auto_check_enabled": self.update_config.get("auto_check_enabled", True),
            "last_check": self.update_config.get("last_check"),
            "update_channel": self.update_config.get("update_channel", "stable"),
            "backup_count": len(self.get_backup_list())
        }
