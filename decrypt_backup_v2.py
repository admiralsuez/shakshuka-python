#!/usr/bin/env python3
"""
Script to decrypt backup files using original key and salt
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def decrypt_backup_with_key_salt(encrypted_file_path, password, key_file, salt_file):
    """Decrypt backup data using original key and salt files"""
    try:
        # Read encrypted data
        with open(encrypted_file_path, 'rb') as f:
            encrypted_data = f.read()
        
        # Read original salt
        with open(salt_file, 'rb') as f:
            salt = f.read()
        
        # Read original key
        with open(key_file, 'rb') as f:
            stored_key = f.read()
        
        # Verify password by regenerating key
        password_bytes = password.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        # Check if derived key matches stored key
        if derived_key != stored_key:
            print(f"Password verification failed for {encrypted_file_path}")
            return None
        
        print(f"Password verified successfully for {encrypted_file_path}")
        
        # Decrypt data
        cipher = Fernet(stored_key)
        decrypted_data = cipher.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
        
    except Exception as e:
        print(f"Failed to decrypt {encrypted_file_path}: {e}")
        return None

def restore_tasks_from_backup():
    """Restore tasks from the most recent backup"""
    password = "rooted89"
    key_file = "data/.key"
    salt_file = "data/.salt"
    
    # Check if key and salt files exist
    if not os.path.exists(key_file) or not os.path.exists(salt_file):
        print("Key or salt files not found!")
        return False
    
    # Try the most recent backup first (weekly_20251017_044054)
    backup_dir = "data/backups/weekly_20251017_044054"
    tasks_file = os.path.join(backup_dir, "tasks.enc")
    
    if os.path.exists(tasks_file):
        print(f"Attempting to decrypt tasks from: {tasks_file}")
        tasks = decrypt_backup_with_key_salt(tasks_file, password, key_file, salt_file)
        
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
        tasks = decrypt_backup_with_key_salt(tasks_file, password, key_file, salt_file)
        
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
    print("Shakshuka Backup Recovery Tool (with original keys)")
    print("=" * 50)
    
    if restore_tasks_from_backup():
        print("\n✅ Task recovery completed successfully!")
        print("Your tasks have been restored. Please restart the application.")
    else:
        print("\n❌ Task recovery failed.")
        print("The backup files might be corrupted or the password might be incorrect.")
