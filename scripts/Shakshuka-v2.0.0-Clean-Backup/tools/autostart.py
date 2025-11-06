import os
import sys
import winreg
import subprocess
from pathlib import Path

class WindowsAutostart:
    def __init__(self, app_name="TaskManager"):
        self.app_name = app_name
        self.reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    
    def enable_autostart(self, app_path=None):
        """Enable autostart with Windows"""
        try:
            # Get the full path to the executable
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                exe_path = sys.executable
            else:
                # Running as script - use the provided path or default to main.py
                if app_path:
                    exe_path = app_path
                else:
                    # Get the root directory (parent of tools/)
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    exe_path = os.path.join(root_dir, "main.py")
            
            # Ensure the path exists
            if not os.path.exists(exe_path):
                print(f"Error: Path does not exist: {exe_path}")
                return False
            
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_SET_VALUE)
            
            # Set the value with proper Python execution for .py files
            if exe_path.endswith('.py'):
                # For Python scripts, use python.exe to execute them
                python_exe = sys.executable
                registry_value = f'"{python_exe}" "{exe_path}"'
            else:
                # For executables, use the path directly
                registry_value = f'"{exe_path}"'
            
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, registry_value)
            
            # Close the key
            winreg.CloseKey(key)
            
            print(f"Autostart enabled: {registry_value}")
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
    
    def test_autostart_command(self):
        """Test if the autostart command would work (dry run)"""
        try:
            command = self.get_autostart_command()
            if not command:
                print("No autostart command found")
                return False
            
            print(f"Testing autostart command: {command}")
            
            # Check if the Python executable exists
            if '"' in command:
                # Parse the command
                parts = command.split('"')
                python_exe = parts[1] if len(parts) > 1 else None
                script_path = parts[3] if len(parts) > 3 else None
                
                if python_exe and not os.path.exists(python_exe):
                    print(f"Error: Python executable not found: {python_exe}")
                    return False
                
                if script_path and not os.path.exists(script_path):
                    print(f"Error: Script file not found: {script_path}")
                    return False
                
                print("+ Python executable exists")
                print("+ Script file exists")
                print("+ Autostart command should work")
                return True
            else:
                print("Error: Invalid command format")
                return False
                
        except Exception as e:
            print(f"Error testing autostart command: {e}")
            return False

    def get_autostart_command(self):
        """Get the current autostart command from registry"""
        try:
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            
            # Try to read the value
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                return value
            except FileNotFoundError:
                winreg.CloseKey(key)
                return None
        except Exception as e:
            print(f"Error getting autostart command: {e}")
            return None

    def is_autostart_enabled(self):
        """Check if autostart is enabled"""
        try:
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            
            # Try to read the value
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                print(f"Autostart registry value: {value}")
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                print("Autostart not found in registry")
                return False
        except Exception as e:
            print(f"Error checking autostart: {e}")
            return False

