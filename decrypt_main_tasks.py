#!/usr/bin/env python3
"""
Script to decrypt the main tasks.enc file from ASDAD directory
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def decrypt_tasks_file(tasks_file_path, password, key_file, salt_file):
    """Decrypt tasks file using original key and salt files"""
    try:
        # Read encrypted data
        with open(tasks_file_path, 'rb') as f:
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
            print(f"Password verification failed")
            return None
        
        print(f"Password verified successfully!")
        
        # Decrypt data
        cipher = Fernet(stored_key)
        decrypted_data = cipher.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
        
    except Exception as e:
        print(f"Failed to decrypt {tasks_file_path}: {e}")
        return None

def main():
    password = "rooted89"
    key_file = "data/.key"
    salt_file = "data/.salt"
    tasks_file = "data/tasks_backup.enc"
    
    print("Attempting to decrypt main tasks file...")
    print(f"Tasks file: {tasks_file}")
    print(f"Key file: {key_file}")
    print(f"Salt file: {salt_file}")
    
    if not os.path.exists(tasks_file):
        print("Tasks file not found!")
        return
    
    if not os.path.exists(key_file) or not os.path.exists(salt_file):
        print("Key or salt files not found!")
        return
    
    tasks = decrypt_tasks_file(tasks_file, password, key_file, salt_file)
    
    if tasks is not None:
        print(f"Successfully decrypted {len(tasks)} tasks!")
        
        # Save to current tasks.json
        with open("data/tasks.json", 'w') as f:
            json.dump(tasks, f, indent=2, default=str)
        
        print("Tasks restored to data/tasks.json")
        
        # Show first few tasks as preview
        if tasks:
            print("\nPreview of restored tasks:")
            for i, task in enumerate(tasks[:3]):
                print(f"{i+1}. {task.get('title', 'No title')}")
            if len(tasks) > 3:
                print(f"... and {len(tasks) - 3} more tasks")
    else:
        print("Failed to decrypt tasks file")

if __name__ == "__main__":
    main()
