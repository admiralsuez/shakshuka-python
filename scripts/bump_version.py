#!/usr/bin/env python3
"""
Simple version bump script - increments build number and updates all related files
Usage: python scripts/bump_version.py [--major] [--minor] [--build-only]
"""

import json
import re
from pathlib import Path
from datetime import datetime
import sys

def get_version_info():
    """Get current version info"""
    try:
        with open('config/version.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading version.json: {e}")
        return None

def bump_build(data):
    """Increment build number"""
    current_build = int(data.get('build', 0))
    data['build'] = str(current_build + 1)
    data['release_date'] = datetime.now().isoformat()
    return current_build, current_build + 1

def bump_minor(data):
    """Increment minor version"""
    version = data.get('version', '1.0')
    parts = version.split('.')
    parts[1] = str(int(parts[1]) + 1)
    data['version'] = '.'.join(parts)
    data['build'] = '1'
    data['release_date'] = datetime.now().isoformat()
    return data['version']

def bump_major(data):
    """Increment major version"""
    version = data.get('version', '1.0')
    parts = version.split('.')
    parts[0] = str(int(parts[0]) + 1)
    data['version'] = '.'.join(parts)
    data['build'] = '1'
    data['release_date'] = datetime.now().isoformat()
    return data['version']

def save_version_info(data):
    """Save version info back to file"""
    try:
        with open('config/version.json', 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving version.json: {e}")
        return False

def update_installer_script(version, build):
    """Update installer.iss with new version"""
    installer_script = Path('scripts/installer.iss')
    
    if not installer_script.exists():
        print(f"Warning: Installer script not found")
        return False
    
    try:
        with open(installer_script, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update MyAppVersion
        content = re.sub(
            r'#define MyAppVersion \"[^\"]*\"',
            f'#define MyAppVersion "{version}"',
            content
        )
        
        # Build full version string
        version_parts = version.split('.')
        while len(version_parts) < 3:
            version_parts.append('0')
        full_version = f"{'.'.join(version_parts)}.{build}"
        
        # Update VersionInfoVersion
        content = re.sub(
            r'^VersionInfoVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Update VersionInfoProductVersion
        content = re.sub(
            r'^VersionInfoProductVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoProductVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Write back
        with open(installer_script, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(content)
        
        print(f"✓ Updated installer.iss")
        print(f"  - MyAppVersion: {version}")
        print(f"  - VersionInfo: {full_version}")
        return True
    except Exception as e:
        print(f"Error updating installer.iss: {e}")
        return False

def verify_changes():
    """Verify that all files have been updated correctly"""
    print("\n=== Verification ===")
    
    # Check version.json
    with open('config/version.json', 'r') as f:
        data = json.load(f)
    print(f"✓ version.json: v{data['version']} build {data['build']}")
    
    # Check installer.iss
    with open('scripts/installer.iss', 'r') as f:
        content = f.read()
    
    myapp_match = re.search(r'#define MyAppVersion "([^"]*)"', content)
    version_info_match = re.search(r'^VersionInfoVersion=([\d\.]+)$', content, re.MULTILINE)
    
    if myapp_match:
        print(f"✓ installer.iss MyAppVersion: {myapp_match.group(1)}")
    if version_info_match:
        print(f"✓ installer.iss VersionInfoVersion: {version_info_match.group(1)}")

def main():
    """Main function"""
    print("Shakshuka Version Bumper")
    print("=" * 50)
    
    # Load current version
    data = get_version_info()
    if not data:
        print("Failed to read version.json")
        return 1
    
    print(f"Current version: {data['version']} (build {data['build']})")
    print()
    
    # Parse arguments
    bump_type = 'build'  # default
    if '--major' in sys.argv:
        bump_type = 'major'
    elif '--minor' in sys.argv:
        bump_type = 'minor'
    elif '--build-only' in sys.argv:
        bump_type = 'build'
    
    # Bump version
    if bump_type == 'major':
        new_version = bump_major(data)
        print(f"Bumped MAJOR version: {data['version']} (build {data['build']})")
    elif bump_type == 'minor':
        new_version = bump_minor(data)
        print(f"Bumped MINOR version: {data['version']} (build {data['build']})")
    else:  # build
        old_build, new_build = bump_build(data)
        print(f"Bumped BUILD: {old_build} → {new_build}")
    
    # Save changes
    if not save_version_info(data):
        print("Failed to save version.json")
        return 1
    
    # Update installer
    if not update_installer_script(data['version'], data['build']):
        print("Failed to update installer.iss")
        return 1
    
    # Verify
    verify_changes()
    
    print("\n✓ Version bump complete!")
    print(f"\nNext steps:")
    print(f"1. Run: python scripts/build.py")
    print(f"2. This will build the executable with version {data['version']} (build {data['build']})")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
