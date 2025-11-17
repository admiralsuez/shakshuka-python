import os
import sys
import subprocess
from pathlib import Path

# Only import winreg on Windows
if sys.platform == 'win32':
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None  # Not available on Linux/Mac

class WindowsAutostart:
    """Cross-platform autostart manager for Windows, Linux, and macOS"""
    
    def __init__(self, app_name="Shakshuka"):
        self.app_name = app_name
        self.platform = sys.platform
        
        if self.platform == 'win32':
            self.reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        elif self.platform == 'darwin':
            # macOS Launch Agent directory
            self.launch_agents_dir = Path.home() / 'Library' / 'LaunchAgents'
            self.plist_file = self.launch_agents_dir / f'com.{app_name.lower()}.plist'
        elif self.platform.startswith('linux'):
            # Linux autostart directory
            self.autostart_dir = Path.home() / '.config' / 'autostart'
            self.desktop_file = self.autostart_dir / f'{app_name.lower()}.desktop'
        else:
            self.reg_key = None
    
    def enable_autostart(self, app_path=None):
        """Enable autostart on Windows, Linux, or macOS"""
        if self.platform == 'win32':
            return self._enable_windows(app_path)
        elif self.platform == 'darwin':
            return self._enable_macos(app_path)
        elif self.platform.startswith('linux'):
            return self._enable_linux(app_path)
        else:
            print(f"Autostart not supported on platform: {self.platform}")
            return False
    
    def _enable_windows(self, app_path=None):
        """Enable autostart on Windows using registry"""
        if winreg is None:
            print("Autostart is not available on Windows (winreg module missing)")
            return False
        
        try:
            # Get the path to the autostart batch script
            if getattr(sys, 'frozen', False):
                # Running as compiled executable - find the batch script relative to the exe
                exe_dir = os.path.dirname(sys.executable)
                autostart_script = os.path.join(exe_dir, "scripts", "Start-Shakshuka-Autostart.bat")
                
                # Fallback to looking in the same directory as the exe
                if not os.path.exists(autostart_script):
                    autostart_script = os.path.join(exe_dir, "Start-Shakshuka-Autostart.bat")
            else:
                # Running as script - use the script from the scripts directory
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                autostart_script = os.path.join(root_dir, "scripts", "Start-Shakshuka-Autostart.bat")
            
            # Ensure the batch script exists
            if not os.path.exists(autostart_script):
                print(f"Error: Autostart script not found: {autostart_script}")
                return False
            
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_SET_VALUE)
            
            # Use cmd.exe to run the batch script hidden
            registry_value = f'cmd /c start /min "" "{autostart_script}"'
            
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, registry_value)
            
            # Close the key
            winreg.CloseKey(key)
            
            print(f"Autostart enabled with delayed silent launch: {registry_value}")
            return True
        except Exception as e:
            print(f"Error enabling autostart: {e}")
            return False
    
    def _enable_linux(self, app_path=None):
        """Enable autostart on Linux using .desktop file"""
        try:
            # Get the application path
            if app_path is None:
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable
                    exec_line = sys.executable
                else:
                    # Running as script - need to use python3
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    script_path = os.path.join(root_dir, "main.py")
                    # Exec line can have multiple arguments separated by spaces
                    exec_line = f"{sys.executable} {script_path}"
            else:
                exec_line = app_path
            
            # Ensure autostart directory exists
            self.autostart_dir.mkdir(parents=True, exist_ok=True)
            
            # Create .desktop file content
            desktop_content = f"""[Desktop Entry]
Type=Application
Name={self.app_name}
Exec={exec_line}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Start {self.app_name} automatically on login
"""
            
            # Write .desktop file
            self.desktop_file.write_text(desktop_content)
            
            # Make it executable
            os.chmod(self.desktop_file, 0o755)
            
            print(f"Autostart enabled on Linux: {self.desktop_file}")
            return True
        except Exception as e:
            print(f"Error enabling autostart on Linux: {e}")
            return False
    
    def _enable_macos(self, app_path=None):
        """Enable autostart on macOS using Launch Agent"""
        try:
            # Get the application path
            if app_path is None:
                if getattr(sys, 'frozen', False):
                    # Running as .app bundle
                    app_path = sys.executable
                else:
                    # Running as script
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    app_path = os.path.join(root_dir, "main.py")
            
            # Ensure LaunchAgents directory exists
            self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
            
            # Create plist content
            # If running as script, use python3 to execute
            if app_path.endswith('.py'):
                program_args = [sys.executable, app_path]
            else:
                program_args = [app_path]
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{self.app_name.lower()}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{program_args[0]}</string>
"""
            if len(program_args) > 1:
                plist_content += f'        <string>{program_args[1]}</string>\n'
            plist_content += """    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
            
            # Write plist file
            self.plist_file.write_text(plist_content)
            
            # Load the Launch Agent
            try:
                subprocess.run(['launchctl', 'load', str(self.plist_file)], 
                             check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # Try unload first in case it's already loaded
                try:
                    subprocess.run(['launchctl', 'unload', str(self.plist_file)], 
                                 capture_output=True)
                    subprocess.run(['launchctl', 'load', str(self.plist_file)], 
                                 check=True, capture_output=True)
                except:
                    pass  # Will be loaded on next login
            
            print(f"Autostart enabled on macOS: {self.plist_file}")
            return True
        except Exception as e:
            print(f"Error enabling autostart on macOS: {e}")
            return False
    
    def disable_autostart(self):
        """Disable autostart on Windows, Linux, or macOS"""
        if self.platform == 'win32':
            return self._disable_windows()
        elif self.platform == 'darwin':
            return self._disable_macos()
        elif self.platform.startswith('linux'):
            return self._disable_linux()
        else:
            print(f"Autostart not supported on platform: {self.platform}")
            return False
    
    def _disable_windows(self):
        """Disable autostart on Windows"""
        if winreg is None:
            return False
        
        try:
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_SET_VALUE)
            
            # Delete the value
            winreg.DeleteValue(key, self.app_name)
            
            # Close the key
            winreg.CloseKey(key)
            
            return True
        except FileNotFoundError:
            # Already disabled
            return True
        except Exception as e:
            print(f"Error disabling autostart on Windows: {e}")
            return False
    
    def _disable_linux(self):
        """Disable autostart on Linux"""
        try:
            if self.desktop_file.exists():
                self.desktop_file.unlink()
                print(f"Autostart disabled on Linux: {self.desktop_file}")
            return True
        except Exception as e:
            print(f"Error disabling autostart on Linux: {e}")
            return False
    
    def _disable_macos(self):
        """Disable autostart on macOS"""
        try:
            # Unload the Launch Agent
            if self.plist_file.exists():
                try:
                    subprocess.run(['launchctl', 'unload', str(self.plist_file)], 
                                 capture_output=True)
                except:
                    pass  # May not be loaded
            
            # Remove the plist file
            if self.plist_file.exists():
                self.plist_file.unlink()
                print(f"Autostart disabled on macOS: {self.plist_file}")
            return True
        except Exception as e:
            print(f"Error disabling autostart on macOS: {e}")
            return False
    

    def get_autostart_command(self):
        """Get the current autostart command"""
        if self.platform == 'win32':
            return self._get_windows_command()
        elif self.platform == 'darwin':
            return self._get_macos_command()
        elif self.platform.startswith('linux'):
            return self._get_linux_command()
        return None
    
    def _get_windows_command(self):
        """Get autostart command from Windows registry"""
        if winreg is None:
            return None
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                return value
            except FileNotFoundError:
                # Scan all values for anything pointing to Shakshuka
                try:
                    i = 0
                    found = None
                    while True:
                        name, val, _ = winreg.EnumValue(key, i)
                        if 'shakshuka' in name.lower() or ('shakshuka' in str(val).lower()):
                            found = val
                            break
                        i += 1
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(key)
                return found
        except Exception as e:
            print(f"Error getting autostart command: {e}")
            return None
    
    def _get_linux_command(self):
        """Get autostart command from Linux .desktop file"""
        try:
            if self.desktop_file.exists():
                with open(self.desktop_file, 'r') as f:
                    for line in f:
                        if line.startswith('Exec='):
                            return line[5:].strip()
        except Exception as e:
            print(f"Error reading Linux autostart file: {e}")
        return None
    
    def _get_macos_command(self):
        """Get autostart command from macOS plist file"""
        try:
            if self.plist_file.exists():
                # Read plist and extract ProgramArguments
                import plistlib
                with open(self.plist_file, 'rb') as f:
                    plist = plistlib.load(f)
                    args = plist.get('ProgramArguments', [])
                    if args:
                        return ' '.join(args)
        except Exception as e:
            print(f"Error reading macOS plist file: {e}")
        return None

    def is_autostart_enabled(self):
        """Check if autostart is enabled"""
        if self.platform == 'win32':
            return self._is_windows_enabled()
        elif self.platform == 'darwin':
            return self._is_macos_enabled()
        elif self.platform.startswith('linux'):
            return self._is_linux_enabled()
        return False
    
    def _is_windows_enabled(self):
        """Check if autostart is enabled on Windows"""
        if winreg is None:
            return False
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                # Scan all values for Shakshuka
                try:
                    i = 0
                    while True:
                        name, val, _ = winreg.EnumValue(key, i)
                        if 'shakshuka' in name.lower() or ('shakshuka' in str(val).lower()):
                            winreg.CloseKey(key)
                            return True
                        i += 1
                except OSError:
                    pass
                finally:
                    try:
                        winreg.CloseKey(key)
                    except Exception:
                        pass
                return False
        except Exception as e:
            print(f"Error checking autostart on Windows: {e}")
            return False
    
    def _is_linux_enabled(self):
        """Check if autostart is enabled on Linux"""
        try:
            return self.desktop_file.exists()
        except Exception:
            return False
    
    def _is_macos_enabled(self):
        """Check if autostart is enabled on macOS"""
        try:
            return self.plist_file.exists()
        except Exception:
            return False

