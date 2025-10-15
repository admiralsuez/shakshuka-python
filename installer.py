"""
Shakshuka Update Installer
Handles manual installation of updates
"""

import os
import sys
import shutil
import zipfile
import json
from pathlib import Path
import argparse

def install_update(update_file, app_dir, backup=True):
    """Install update from zip file"""
    try:
        app_path = Path(app_dir)
        data_dir = app_path / "data"
        backup_dir = data_dir / "backups"
        
        # Create backup if requested
        if backup and data_dir.exists():
            backup_name = f"pre_manual_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Copy data files
            for item in data_dir.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    shutil.copy2(item, backup_path / item.name)
            
            print(f"Backup created: {backup_name}")
        
        # Extract update
        with zipfile.ZipFile(update_file, 'r') as zip_ref:
            # Extract to temporary directory
            temp_extract = tempfile.mkdtemp()
            zip_ref.extractall(temp_extract)
            
            # Copy files, preserving data directory
            for root, dirs, files in os.walk(temp_extract):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, temp_extract)
                    dst_path = app_path / rel_path
                    
                    # Skip data directory
                    if "data" in rel_path.split(os.sep):
                        continue
                    
                    # Ensure destination directory exists
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(src_path, dst_path)
            
            # Clean up temporary directory
            shutil.rmtree(temp_extract)
        
        print("Update installed successfully!")
        return True
        
    except Exception as e:
        print(f"Error installing update: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Shakshuka Update Installer')
    parser.add_argument('update_file', help='Path to update zip file')
    parser.add_argument('--app-dir', default='.', help='Application directory')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.update_file):
        print(f"Update file not found: {args.update_file}")
        sys.exit(1)
    
    success = install_update(args.update_file, args.app_dir, not args.no_backup)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    import tempfile
    from datetime import datetime
    main()

