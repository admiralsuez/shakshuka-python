import os
import json
import sys
from datetime import datetime, timedelta
import logging

class SimpleDataManager:
    """Simple data manager without encryption for password-free operation"""
    def __init__(self, data_dir="data"):
        # Handle PyInstaller bundle path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = os.path.join(base_path, data_dir)
        self.tasks_file = os.path.join(self.data_dir, "tasks.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        
        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            print(f"Data directory ensured: {os.path.abspath(self.data_dir)}")
        except Exception as e:
            raise Exception(f"Failed to create data directory '{self.data_dir}': {e}")
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def save_tasks(self, tasks):
        """Save tasks to JSON file"""
        try:
            with open(self.tasks_file, 'w') as f:
                json.dump(tasks, f, indent=2, default=str)
            self.logger.info("Tasks saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving tasks: {e}")
            return False
    
    def load_tasks(self):
        """Load tasks from JSON file"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self.logger.error(f"Error loading tasks: {e}")
            return []
    
    def save_settings(self, settings):
        """Save settings to JSON file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2, default=str)
            self.logger.info("Settings saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            return {}
    
    def change_password(self, new_password):
        """Password change not needed in simple mode"""
        return True

# Keep the old EncryptedDataManager for backward compatibility
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class EncryptedDataManager:
    def __init__(self, data_dir="data", password=None):
        self.data_dir = data_dir
        self.key_file = os.path.join(data_dir, ".key")
        self.salt_file = os.path.join(data_dir, ".salt")
        self.tasks_file = os.path.join(data_dir, "tasks.enc")
        self.settings_file = os.path.join(data_dir, "settings.enc")
        
        if password is None:
            raise ValueError("Password is required for data encryption. Please set a password.")
        
        self.password = password
        
        # Create data directory if it doesn't exist
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"Data directory ensured: {os.path.abspath(data_dir)}")
        except Exception as e:
            raise Exception(f"Failed to create data directory '{data_dir}': {e}")
        
        # Initialize encryption key
        try:
            self.cipher = self._get_or_create_cipher()
            print("Encryption cipher initialized successfully")
        except Exception as e:
            raise Exception(f"Failed to initialize encryption: {e}")
        
        # Setup logging
        self._setup_logging()
    
    def is_first_run(self):
        """Check if this is the first run (no existing encrypted files)"""
        return not (os.path.exists(self.key_file) and os.path.exists(self.salt_file))
    
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _get_or_create_cipher(self):
        """Get existing encryption key or create a new one"""
        if os.path.exists(self.key_file) and os.path.exists(self.salt_file):
            # Load existing key and salt, then validate password
            try:
                with open(self.salt_file, 'rb') as f:
                    salt = f.read()
                
                # Generate key from provided password and stored salt
                password_bytes = self.password.encode('utf-8')
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
                
                # Verify the generated key matches the stored key
                with open(self.key_file, 'rb') as f:
                    stored_key = f.read()
                
                if key != stored_key:
                    raise Exception("Invalid password - key mismatch")
                
                print("Password validated successfully")
            except Exception as e:
                if "Invalid password" in str(e):
                    raise e
                raise Exception(f"Failed to validate password: {e}")
        else:
            # Generate a new key with user password
            try:
                password_bytes = self.password.encode('utf-8')
                salt = os.urandom(16)
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
                
                # Save key and salt
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                with open(self.salt_file, 'wb') as f:
                    f.write(salt)
                print("Generated and saved new encryption key and salt")
            except Exception as e:
                raise Exception(f"Failed to generate and save encryption key: {e}")
        
        try:
            return Fernet(key)
        except Exception as e:
            raise Exception(f"Failed to create Fernet cipher: {e}")
    
    def _encrypt_data(self, data):
        """Encrypt data before storing"""
        json_data = json.dumps(data, default=str)
        encrypted_data = self.cipher.encrypt(json_data.encode())
        return encrypted_data
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt data after reading"""
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            self.logger.error(f"Decryption error: {e}")
            return None
    
    def save_tasks(self, tasks):
        """Save tasks to encrypted file"""
        try:
            encrypted_data = self._encrypt_data(tasks)
            with open(self.tasks_file, 'wb') as f:
                f.write(encrypted_data)
            self.logger.info("Tasks saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving tasks: {e}")
            return False
    
    def load_tasks(self):
        """Load tasks from encrypted file"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'rb') as f:
                    encrypted_data = f.read()
                return self._decrypt_data(encrypted_data) or []
            return []
        except Exception as e:
            self.logger.error(f"Error loading tasks: {e}")
            return []
    
    def save_settings(self, settings):
        """Save settings to encrypted file"""
        try:
            encrypted_data = self._encrypt_data(settings)
            with open(self.settings_file, 'wb') as f:
                f.write(encrypted_data)
            self.logger.info("Settings saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def load_settings(self):
        """Load settings from encrypted file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'rb') as f:
                    encrypted_data = f.read()
                return self._decrypt_data(encrypted_data) or {}
            return {"autostart": False, "autosave_interval": 30, "theme": "orange", "dpi_scale": 100, "daily_reset_time": "09:00"}
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            return {"autostart": False, "autosave_interval": 30, "theme": "orange", "dpi_scale": 100, "daily_reset_time": "09:00"}
    
    def change_password(self, new_password):
        """Change the encryption password"""
        try:
            # Load existing data
            tasks = self.load_tasks()
            settings = self.load_settings()
            
            # Update password
            self.password = new_password
            
            # Generate new key with new password
            password_bytes = self.password.encode('utf-8')
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
            
            # Save new key and salt
            with open(self.key_file, 'wb') as f:
                f.write(key)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            
            # Re-encrypt data with new key
            self.cipher = Fernet(key)
            
            # Save data with new encryption
            self.save_tasks(tasks)
            self.save_settings(settings)
            
            self.logger.info("Password changed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error changing password: {e}")
            return False
