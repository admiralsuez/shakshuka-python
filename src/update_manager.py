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
except Exception:
    GITHUB_REPO_OWNER = "admiralsuez"
    GITHUB_REPO_NAME = "shakshuka-python"

class UpdateManager:
    def __init__(self, app_dir: str, data_dir: str = "data"):
        self.app_dir = Path(app_dir)
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / "backups"
        # Store downloaded updates in user-writable data directory to avoid Program Files permission issues
        self.update_dir = self.data_dir / "updates"
        self.version_file = self.app_dir / "config" / "version.json"
        self.update_config_file = self.data_dir / "update_config.json"
        
        # Create necessary directories (all under user data dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.update_dir.mkdir(parents=True, exist_ok=True)
        
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
        self._download_total = 0
        self._download_downloaded = 0
        self._download_cancel_event = threading.Event()
        self._current_update_file = None  # absolute path to downloaded file
        self._current_update_version = None
        self._download_thread = None
        
    def _load_current_version(self) -> Dict:
        """Load current application version"""
        try:
            if self.version_file.exists():
                with open(self.version_file, 'r') as f:
                    return json.load(f)
            else:
                # Fall back to default version info without writing to app_dir (may be read-only)
                version_info = {
                    "version": "1.0.0",
                    "build": "1",
                    "release_date": datetime.now().isoformat(),
                    "update_channel": "stable"
                }
                return version_info
        except Exception as e:
            self.logger.error(f"Error loading version: {e}")
            return {"version": "1.0.0", "build": "1", "release_date": datetime.now().isoformat()}
    
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
        try:
            if self.update_config_file.exists():
                with open(self.update_config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default config
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
        except Exception as e:
            self.logger.error(f"Error loading update config: {e}")
            return {"auto_check_enabled": True, "check_interval_hours": 24}
    
    def _save_update_config(self, config: Dict):
        """Save update configuration"""
        try:
            with open(self.update_config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving update config: {e}")
    
    def check_for_updates(self) -> Optional[Dict]:
        """Check for available updates"""
        try:
            if not self.update_config.get("auto_check_enabled", True):
                return None
            
            # Check if enough time has passed since last check
            last_check = self.update_config.get("last_check")
            if last_check:
                last_check_time = datetime.fromisoformat(last_check)
                check_interval = timedelta(hours=self.update_config.get("check_interval_hours", 24))
                if datetime.now() - last_check_time < check_interval:
                    return None
            
            # Update last check time
            self.update_config["last_check"] = datetime.now().isoformat()
            self._save_update_config(self.update_config)
            
            # Check for updates from server
            if not REQUESTS_AVAILABLE:
                self.logger.warning("Requests module not available. Cannot check for updates.")
                return None
                
            response = requests.get(
                self.update_config.get("update_server_url", ""),
                timeout=10
            )
            
            if response.status_code == 200:
                release_info = response.json()
                latest_version = str(release_info.get("tag_name", "")).lstrip("v")
                
                # Attempt to pick platform-specific asset
                assets = release_info.get("assets", []) or []
                download_url = ""
                file_size = 0
                
                # Determine platform-specific file extension
                platform_extensions = {
                    'win32': ['.exe'],
                    'linux': ['.deb'],
                    'darwin': ['.dmg', '.pkg']
                }
                current_platform = sys.platform
                preferred_extensions = platform_extensions.get(current_platform, ['.zip'])
                
                # First, try to find platform-specific package
                for ext in preferred_extensions:
                    for a in assets:
                        name = a.get("name", "").lower()
                        if name.endswith(ext):
                            download_url = a.get("browser_download_url", "")
                            file_size = int(a.get("size", 0))
                            break
                    if download_url:
                        break
                
                # Fallback to .zip if no platform-specific package found
                if not download_url:
                    for a in assets:
                        name = a.get("name", "").lower()
                        if name.endswith('.zip'):
                            download_url = a.get("browser_download_url", "")
                            file_size = int(a.get("size", 0))
                            break
                
                # Final fallback to first asset
                if not download_url and assets:
                    first = assets[0]
                    download_url = first.get("browser_download_url", "")
                    file_size = int(first.get("size", 0))
                
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
            
        except Exception as e:
            self.logger.error(f"Error checking for updates: {e}")
            return None
    
    def _is_newer_version(self, new_version: str, current_version: str) -> bool:
        """Compare version strings"""
        try:
            new_parts = [int(x) for x in new_version.split('.')]
            current_parts = [int(x) for x in current_version.split('.')]
            
            # Pad with zeros if needed
            max_len = max(len(new_parts), len(current_parts))
            new_parts.extend([0] * (max_len - len(new_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            
            return new_parts > current_parts
        except:
            return False
    
    def download_update(self, update_info: Dict, progress_callback=None) -> bool:
        """Download update package (synchronous) with internal progress tracking.
        Prefer using start_download() to run in background and query progress via get_download_status().
        """
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests module not available. Cannot download updates.")
            return False
            
        try:
            download_url = update_info.get("download_url")
            if not download_url:
                return False
            version = update_info.get("version", "unknown")
            
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
            
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            with self._download_lock:
                self._download_total = total_size
            
            downloaded_size = 0
            
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._download_cancel_event.is_set():
                        # Cleanup and mark canceled
                        try:
                            f.close()
                        except Exception:
                            pass
                        try:
                            os.unlink(temp_file.name)
                        except Exception:
                            pass
                        with self._download_lock:
                            self._download_status = 'canceled'
                            self._download_progress = 0.0
                        return False
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
            
            # Move to update directory
            update_file = self.update_dir / f"update_{version}.zip"
            shutil.move(temp_file.name, update_file)
            
            with self._download_lock:
                self._download_status = 'ready'
                self._current_update_file = str(update_file)
                self._download_progress = 100.0
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading update: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error = str(e)
            return False
    
    def start_download(self, update_info: Dict) -> None:
        """Start download in background thread."""
        if self._download_thread and self._download_thread.is_alive():
            # Already downloading
            return
        def worker():
            try:
                self.download_update(update_info)
            except Exception as e:
                self.logger.error(f"Download worker error: {e}")
                with self._download_lock:
                    self._download_status = 'failed'
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
            
            # Resolve relative to update_dir if necessary
            if not os.path.isabs(update_file):
                update_file = str(self.update_dir / update_file)
            
            # Determine platform and install method
            platform = sys.platform
            
            if platform == 'win32':
                return self._install_windows(update_file, backup_data)
            elif platform.startswith('linux'):
                return self._install_linux(update_file, backup_data)
            elif platform == 'darwin':
                return self._install_macos(update_file, backup_data)
            else:
                # Fallback to generic zip extraction
                return self._install_generic(update_file, backup_data)
                
        except Exception as e:
            self.logger.error(f"Error installing update: {e}")
            with self._download_lock:
                self._download_status = 'failed'
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
                
        except subprocess.TimeoutExpired:
            self.logger.error("Installer timeout")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Installer failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error installing Windows update: {e}")
            return False
    
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
                
        except subprocess.TimeoutExpired:
            self.logger.error("Package installation timeout")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Package installation failed: {e}")
            return False
        except FileNotFoundError:
            self.logger.error("dpkg not found. Cannot install .deb package.")
            return False
        except Exception as e:
            self.logger.error(f"Error installing Linux update: {e}")
            return False
    
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
                        self.logger.error("No .app bundle found in DMG")
                        return False
                        
                finally:
                    # Unmount DMG
                    subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)
                    shutil.rmtree(mount_point, ignore_errors=True)
                
                return True
            else:
                # Fallback to generic installation
                return self._install_generic(update_file, backup_data)
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"macOS installation failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error installing macOS update: {e}")
            return False
    
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
                self._download_status = 'completed'
                self._current_update_file = update_file
                self.current_version = new_version_info
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in generic installation: {e}")
            with self._download_lock:
                self._download_status = 'failed'
                self._download_error = str(e)
            return False
    
    def install_update(self, update_file: str, backup_data: bool = True) -> bool:
        """Install downloaded update (backward compatibility - uses platform-specific method)"""
        return self.install_update_platform_specific(update_file, backup_data)
    
    def _extract_version_from_filename(self, filename: str) -> str:
        """Extract version from update filename"""
        try:
            # Extract version from filename like "update_1.2.3.zip"
            basename = os.path.basename(filename)
            version_part = basename.replace("update_", "").replace(".zip", "")
            return version_part
        except:
            return "1.0.0"
    
    def create_backup(self, backup_type: str = "manual") -> bool:
        """Create backup of current data"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{backup_type}_{timestamp}"
            backup_path = self.backup_dir / backup_name
            
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Copy data files
            if self.data_dir.exists():
                for item in self.data_dir.iterdir():
                    if item.is_file() and not item.name.startswith('.'):
                        shutil.copy2(item, backup_path / item.name)
            
            # Create backup manifest
            manifest = {
                "backup_type": backup_type,
                "created_at": datetime.now().isoformat(),
                "version": self.current_version["version"],
                "files": [f.name for f in backup_path.iterdir() if f.is_file()]
            }
            
            with open(backup_path / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Clean up old backups (keep last 10)
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False
    
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
            backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                return False
            
            # Read manifest
            manifest_file = backup_path / "manifest.json"
            if not manifest_file.exists():
                return False
            
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            # Restore files
            for file_name in manifest.get("files", []):
                if file_name != "manifest.json":
                    src_file = backup_path / file_name
                    dst_file = self.data_dir / file_name
                    
                    if src_file.exists():
                        shutil.copy2(src_file, dst_file)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            return False
    
    def get_backup_list(self) -> List[Dict]:
        """Get list of available backups"""
        backups = []
        try:
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    manifest_file = backup_dir / "manifest.json"
                    if manifest_file.exists():
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                        backups.append({
                            "name": backup_dir.name,
                            "type": manifest.get("backup_type", "unknown"),
                            "created_at": manifest.get("created_at", ""),
                            "version": manifest.get("version", "unknown")
                        })
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error getting backup list: {e}")
        
        return backups
    
    def start_auto_update_check(self):
        """Start automatic update checking in background"""
        if self.update_check_thread and self.update_check_thread.is_alive():
            return
        
        self.update_check_enabled = True
        self.update_check_thread = threading.Thread(target=self._auto_update_check_worker, daemon=True)
        self.update_check_thread.start()
    
    def stop_auto_update_check(self):
        """Stop automatic update checking"""
        self.update_check_enabled = False
        if self.update_check_thread:
            self.update_check_thread.join(timeout=5)
    
    def _auto_update_check_worker(self):
        """Background worker for automatic update checking and installation"""
        while self.update_check_enabled:
            try:
                # Check for updates
                update_info = self.check_for_updates()
                
                if update_info:
                    self.logger.info(f"Update available: {update_info['version']}")
                    
                    # Check if auto-install is enabled
                    if self.update_config.get("auto_install_enabled", False):
                        self.logger.info(f"Auto-install enabled. Starting download and installation of version {update_info['version']}")
                        
                        # Start download in background
                        self.start_download(update_info)
                        
                        # Wait for download to complete (with timeout)
                        max_wait_time = 600  # 10 minutes
                        wait_interval = 2  # Check every 2 seconds
                        waited = 0
                        
                        while waited < max_wait_time:
                            status = self.get_download_status()
                            if status['status'] == 'ready':
                                # Download complete, install it
                                self.logger.info(f"Download complete. Installing update {update_info['version']}")
                                update_file = status.get('update_file_path')
                                if update_file:
                                    backup = self.update_config.get("backup_before_update", True)
                                    install_success = self.install_update_platform_specific(update_file, backup)
                                    if install_success:
                                        self.logger.info(f"Update {update_info['version']} installed successfully")
                                    else:
                                        self.logger.error(f"Failed to install update {update_info['version']}")
                                break
                            elif status['status'] == 'failed':
                                self.logger.error(f"Download failed: {status.get('error', 'Unknown error')}")
                                break
                            elif status['status'] == 'canceled':
                                self.logger.info("Download was canceled")
                                break
                            
                            time.sleep(wait_interval)
                            waited += wait_interval
                        
                        if waited >= max_wait_time:
                            self.logger.warning("Download timeout. Update will be installed on next check.")
                    else:
                        # Just log that update is available
                        self.logger.info(f"Update available but auto-install is disabled. User can install manually.")
                
                # Sleep for check interval
                sleep_time = self.update_config.get("check_interval_hours", 24) * 3600
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in auto update check: {e}")
                time.sleep(3600)  # Sleep for 1 hour on error
    
    def schedule_weekly_backup(self):
        """Schedule weekly automatic backups"""
        def backup_worker():
            while True:
                try:
                    # Check if it's time for weekly backup
                    last_backup = self.update_config.get("last_weekly_backup")
                    if last_backup:
                        last_backup_time = datetime.fromisoformat(last_backup)
                        if datetime.now() - last_backup_time < timedelta(days=7):
                            time.sleep(3600)  # Sleep for 1 hour
                            continue
                    
                    # Create weekly backup
                    if self.create_backup("weekly"):
                        self.update_config["last_weekly_backup"] = datetime.now().isoformat()
                        self._save_update_config(self.update_config)
                        self.logger.info("Weekly backup created successfully")
                    
                    # Sleep for 24 hours
                    time.sleep(24 * 3600)
                    
                except Exception as e:
                    self.logger.error(f"Error in weekly backup: {e}")
                    time.sleep(3600)  # Sleep for 1 hour on error
        
        backup_thread = threading.Thread(target=backup_worker, daemon=True)
        backup_thread.start()
    
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
