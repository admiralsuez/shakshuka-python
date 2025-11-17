#!/usr/bin/env python3
"""
Build script for creating macOS .app bundle and .dmg file
Usage: python3 scripts/build-mac.py

This creates:
1. Shakshuka.app - A macOS application bundle
2. Shakshuka-vX.X.dmg - A disk image for drag-and-drop installation
"""

import os
import sys
import subprocess
import json
import shutil
import tempfile
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

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--version'], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_mac():
    """Check if running on macOS"""
    return sys.platform == 'darwin'

def build_app_bundle():
    """Build the .app bundle using PyInstaller"""
    print("Building macOS .app bundle for Shakshuka...")
    print("=" * 50)
    
    # Get version
    version = get_version()
    print(f"Version: {version}")
    print()
    
    # Check if running on macOS
    if not check_mac():
        print("⚠️  Warning: Not running on macOS. The .app bundle may not work correctly.")
        print()
    
    # Check if PyInstaller is installed
    if not check_pyinstaller():
        print("❌ Error: PyInstaller is not installed!")
        print()
        print("Install PyInstaller with:")
        print("  pip3 install pyinstaller")
        print()
        return False, version
    
    # Check if main.py exists
    if not Path("main.py").exists():
        print("❌ Error: main.py not found!")
        return False, version
    
    # Create dist directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Clean up old builds
    app_bundle = dist_dir / "Shakshuka.app"
    if app_bundle.exists():
        print("Cleaning up old .app bundle...")
        shutil.rmtree(app_bundle)
    
    # Check for icon file
    icon_path = None
    ico_file = Path("assets/static/images/icon.ico")
    icns_file = Path("assets/static/images/icon.icns")
    
    if icns_file.exists():
        icon_path = str(icns_file)
        print(f"Using icon: {icon_path}")
    elif ico_file.exists():
        print(f"⚠️  Found .ico icon, but .icns is preferred for macOS")
        print("   You can convert it with: sips -s format icns assets/static/images/icon.ico --out assets/static/images/icon.icns")
        icon_path = str(ico_file)
    
    # Build the .app bundle
    print()
    print("Creating .app bundle with PyInstaller...")
    print()
    
    # PyInstaller command for macOS .app bundle
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=Shakshuka',
        '--onedir',  # Create a directory bundle (required for .app)
        '--windowed',  # No console window (macOS app style)
        '--clean',  # Clean cache before building
        '--noconfirm',  # Overwrite without asking
    ]
    
    # Add icon if available
    if icon_path:
        cmd.extend(['--icon', icon_path])
    
    # Add data files (macOS uses : as separator)
    data_files = [
        ('assets/templates', 'templates'),
        ('assets/static', 'static'),
        ('data', 'data'),
        ('config/version.json', '.'),
    ]
    
    for src, dst in data_files:
        src_path = Path(src)
        if src_path.exists():
            cmd.extend(['--add-data', f'{src}:{dst}'])
    
    # Add hidden imports
    hidden_imports = [
        'flask', 'flask_cors', 'main', 'src',
        'cryptography', 'cryptography.fernet',
        'cryptography.hazmat', 'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.primitives.kdf',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        'schedule', 'psutil', 'requests',
        'urllib3', 'certifi', 'charset_normalizer', 'idna', 'werkzeug',
    ]
    
    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])
    
    # Add main.py
    cmd.append('main.py')
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # PyInstaller creates dist/Shakshuka/ directory, we need to rename it to .app
        app_dir = dist_dir / "Shakshuka"
        if app_dir.exists():
            # Rename to .app
            app_dir.rename(app_bundle)
            print()
            print("✅ .app bundle created successfully!")
            print(f"Location: {app_bundle}")
            return True, version
        else:
            print("❌ Error: App bundle directory not found!")
            print(f"Expected: {app_dir}")
            return False, version
            
    except subprocess.CalledProcessError as e:
        print("❌ Error building .app bundle:")
        print(e.stderr)
        if e.stdout:
            print("Output:")
            print(e.stdout)
        return False, version
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False, version

def create_dmg(app_bundle_path, version):
    """Create a .dmg file with the .app bundle"""
    print()
    print("Creating .dmg file...")
    print("=" * 50)
    
    dist_dir = Path("dist")
    dmg_name = f"Shakshuka-v{version}.dmg"
    dmg_path = dist_dir / dmg_name
    
    # Remove old DMG if exists
    if dmg_path.exists():
        dmg_path.unlink()
    
    # Create a temporary directory for DMG contents
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy app bundle to temp directory
        temp_app = temp_path / app_bundle_path.name
        shutil.copytree(app_bundle_path, temp_app)
        print(f"Copied app bundle to temporary directory")
        
        # Create Applications folder symlink
        applications_link = temp_path / "Applications"
        # Create a symlink to /Applications
        os.symlink("/Applications", applications_link)
        print("Created Applications folder link")
        
        # Create DMG using hdiutil
        print()
        print("Creating disk image...")
        cmd = [
            'hdiutil', 'create',
            '-volname', 'Shakshuka',
            '-srcfolder', str(temp_path),
            '-ov',  # Overwrite existing
            '-format', 'UDZO',  # Compressed read-only
            str(dmg_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print()
            print("✅ .dmg file created successfully!")
            print(f"File: {dmg_path}")
            print()
            print("Users can:")
            print("  1. Double-click the .dmg file to mount it")
            print("  2. Drag Shakshuka.app to the Applications folder")
            print("  3. Eject the disk image")
            print()
            return True
        except subprocess.CalledProcessError as e:
            print("❌ Error creating .dmg file:")
            print(e.stderr)
            if e.stdout:
                print("Output:")
                print(e.stdout)
            return False
        except FileNotFoundError:
            print("❌ Error: hdiutil not found!")
            print("This command is only available on macOS.")
            return False

def main():
    """Main function"""
    success, version = build_app_bundle()
    
    if success:
        app_bundle = Path("dist/Shakshuka.app")
        if app_bundle.exists():
            # Automatically create DMG
            create_dmg(app_bundle, version)
        return 0
    else:
        return 1

if __name__ == '__main__':
    sys.exit(main())

