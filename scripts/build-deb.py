#!/usr/bin/env python3
"""
Build script for creating Debian package (.deb) using fpm
Usage: python3 scripts/build-deb.py
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def get_version():
    """Get version from version.json"""
    version_file = Path("config/version.json")
    if version_file.exists():
        try:
            with open(version_file, 'r') as f:
                version_data = json.load(f)
                return version_data.get('version', '8.3')
        except Exception:
            pass
    return "8.3"

def check_fpm():
    """Check if fpm is installed"""
    try:
        subprocess.run(['fpm', '--version'], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def build_deb():
    """Build the .deb package using fpm"""
    print("Building Debian package for Shakshuka...")
    print("=" * 50)
    
    # Get version
    version = get_version()
    print(f"Version: {version}")
    print()
    
    # Check if fpm is installed
    if not check_fpm():
        print("❌ Error: fpm is not installed!")
        print()
        print("Install fpm with:")
        print("  sudo apt-get install ruby-dev build-essential")
        print("  sudo gem install fpm")
        print()
        return False
    
    # Check if setup.py exists
    if not Path("setup.py").exists():
        print("❌ Error: setup.py not found!")
        print("Please run this script from the project root.")
        return False
    
    # Create dist directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Build the .deb package
    print("Creating .deb package with fpm...")
    print()
    
    # Check if postinst script exists
    postinst_script = Path("scripts/postinst.sh")
    if postinst_script.exists():
        # Make it executable
        os.chmod(postinst_script, 0o755)
    
    cmd = [
        'fpm',
        '-s', 'python',
        '-t', 'deb',
        '--python-bin', 'python3',
        '--python-pip', 'pip3',
        '--python-package-name-prefix', 'python3',
        '--no-python-dependencies',
        '--name', 'shakshuka',
        '--version', version,
        '--description', 'Shakshuka application',
        '--depends', 'python3',
        '--depends', 'python3-pip',
    ]
    
    # Add post-install script if it exists
    if postinst_script.exists():
        cmd.extend(['--after-install', str(postinst_script)])
    
    cmd.append('setup.py')
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # Check if package was created (fpm may create with or without python3- prefix)
        deb_file_with_prefix = f"python3-shakshuka_{version}_all.deb"
        deb_file_without_prefix = f"shakshuka_{version}_all.deb"
        
        deb_file = None
        if Path(deb_file_with_prefix).exists():
            deb_file = deb_file_with_prefix
        elif Path(deb_file_without_prefix).exists():
            deb_file = deb_file_without_prefix
        
        if deb_file and Path(deb_file).exists():
            # Move to dist directory
            dist_file = dist_dir / deb_file
            Path(deb_file).rename(dist_file)
            
            print()
            print("✅ Package created successfully!")
            print(f"File: {dist_file}")
            print()
            print("To install the package:")
            print(f"  sudo dpkg -i {dist_file}")
            print("  sudo apt-get install -f  # Fix dependencies if needed")
            print()
            
            return True
        else:
            print("❌ Error: Package file not found!")
            print(f"Expected: {deb_file_with_prefix} or {deb_file_without_prefix}")
            print("\nChecking for any .deb files in current directory:")
            import glob
            deb_files = glob.glob("*.deb")
            if deb_files:
                print(f"Found: {deb_files}")
            return False
            
    except subprocess.CalledProcessError as e:
        print("❌ Error building package:")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main function"""
    if build_deb():
        return 0
    else:
        return 1

if __name__ == '__main__':
    sys.exit(main())

