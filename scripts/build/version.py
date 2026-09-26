"""Version management for Shakshuka builds"""

import json
from datetime import datetime
from pathlib import Path


def get_version_info():
    """Get version information from config/version.json"""
    try:
        with open('config/version.json', 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        return version_data.get('version', '1.0'), version_data.get('build', '1')
    except Exception as e:
        print(f"Warning: Could not read version.json: {e}")
        return '1.0', '1'


def bump_version_two_part():
    """Increment two-part version X.Y -> X.(Y+1); when Y==9, roll to (X+1).0. Updates version.json."""
    try:
        with open('config/version.json', 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        cur = str(version_data.get('version', '1.0')).strip()
        parts = cur.split('.')
        major = int(parts[0]) if parts and parts[0].isdigit() else 1
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if minor < 9:
            minor += 1
        else:
            major += 1
            minor = 0
        new_version = f"{major}.{minor}"
        version_data['version'] = new_version
        version_data['release_date'] = datetime.now().isoformat()
        version_data['build'] = str(int(version_data.get('build', 0)) + 1)
        with open('config/version.json', 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2)
        print(f"Version bumped: {cur} -> {new_version}")
        return new_version, version_data['build']
    except Exception as e:
        print(f"Warning: Could not bump version: {e}")
        return get_version_info()


def increment_build_number():
    """Increment only the build number and update version.json"""
    try:
        with open('config/version.json', 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        current_build = int(version_data.get('build', 0))
        new_build = current_build + 1
        version_data['build'] = str(new_build)
        version_data['release_date'] = datetime.now().isoformat()
        with open('config/version.json', 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2)
        print(f"Build number incremented: {current_build} -> {new_build}")
        return version_data.get('version', '1.0'), str(new_build)
    except Exception as e:
        print(f"Warning: Could not increment build number: {e}")
        return get_version_info()
