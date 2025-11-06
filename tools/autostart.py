import os
import sys
import winreg

class WindowsAutostart:
    def __init__(self, app_name="Shakshuka"):
        self.app_name = app_name
        self.reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    
    def enable_autostart(self, app_path=None):
        """Enable autostart with Windows using the silent autostart batch script"""
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
    
    def disable_autostart(self):
        """Disable autostart with Windows"""
        try:
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_SET_VALUE)
            
            # Delete the value
            winreg.DeleteValue(key, self.app_name)
            
            # Close the key
            winreg.CloseKey(key)
            
            return True
        except Exception as e:
            print(f"Error disabling autostart: {e}")
            return False
    

    def get_autostart_command(self):
        """Get the current autostart command from registry; fall back to scanning for Shakshuka entries"""
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

    def is_autostart_enabled(self):
        """Check if autostart is enabled by name or any Shakshuka-related entry"""
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
            print(f"Error checking autostart: {e}")
            return False

