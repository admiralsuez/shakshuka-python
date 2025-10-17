import os
import sys
import winreg
import subprocess
from pathlib import Path

class WindowsAutostart:
    def __init__(self, app_name="TaskManager"):
        self.app_name = app_name
        self.reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    
    def enable_autostart(self, app_path):
        """Enable autostart with Windows"""
        try:
            # Get the full path to the executable
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                exe_path = sys.executable
            else:
                # Running as script
                exe_path = os.path.join(os.path.dirname(__file__), "app.py")
            
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_SET_VALUE)
            
            # Set the value
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, exe_path)
            
            # Close the key
            winreg.CloseKey(key)
            
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
    
    def is_autostart_enabled(self):
        """Check if autostart is enabled"""
        try:
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            
            # Try to read the value
            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception as e:
            print(f"Error checking autostart: {e}")
            return False

