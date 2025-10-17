#!/usr/bin/env python3
"""
Script to decrypt backup files and restore tasks
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def decrypt_backup_data(encrypted_file_path, password):
    """Decrypt backup data using password"""
    try:
        # Read encrypted data
        with open(encrypted_file_path, 'rb') as f:
            encrypted_data = f.read()
        
        # For backup files, we need to derive the key from password
        # Since we don't have the original salt, we'll try common approaches
        password_bytes = password.encode('utf-8')
        
        # Try with a default salt (this might work if the backup was created with a standard salt)
        salt = b'default_salt_123'  # Common default salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
        
    except Exception as e:
        print(f"Failed to decrypt {encrypted_file_path}: {e}")
        return None

def restore_tasks_from_backup():
    """Restore tasks from the most recent backup"""
    password = "rooted89"
    
    # Try the most recent backup first (weekly_20251017_044054)
    backup_dir = "data/backups/weekly_20251017_044054"
    tasks_file = os.path.join(backup_dir, "tasks.enc")
    
    if os.path.exists(tasks_file):
        print(f"Attempting to decrypt tasks from: {tasks_file}")
        tasks = decrypt_backup_data(tasks_file, password)
        
        if tasks is not None:
            print(f"Successfully decrypted {len(tasks)} tasks!")
            
            # Save to current tasks.json
            with open("data/tasks.json", 'w') as f:
                json.dump(tasks, f, indent=2, default=str)
            
            print("Tasks restored to data/tasks.json")
            return True
        else:
            print("Failed to decrypt tasks from weekly backup")
    
    # Try the manual backup if weekly failed
    backup_dir = "data/backups/manual_20251016_191449"
    tasks_file = os.path.join(backup_dir, "tasks.enc")
    
    if os.path.exists(tasks_file):
        print(f"Attempting to decrypt tasks from: {tasks_file}")
        tasks = decrypt_backup_data(tasks_file, password)
        
        if tasks is not None:
            print(f"Successfully decrypted {len(tasks)} tasks!")
            
            # Save to current tasks.json
            with open("data/tasks.json", 'w') as f:
                json.dump(tasks, f, indent=2, default=str)
            
            print("Tasks restored to data/tasks.json")
            return True
        else:
            print("Failed to decrypt tasks from manual backup")
    
    print("Could not decrypt any backup files")
    return False

if __name__ == "__main__":
    print("Shakshuka Backup Recovery Tool")
    print("=" * 40)
    
    if restore_tasks_from_backup():
        print("\n✅ Task recovery completed successfully!")
        print("Your tasks have been restored. Please restart the application.")
    else:
        print("\n❌ Task recovery failed.")
        print("The backup files might be corrupted or the password might be incorrect.")
