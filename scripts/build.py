import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from datetime import datetime

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
        # Increase build as well on version bump
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

def build_executable():
    """Build the executable using PyInstaller"""
    
    print("Building Shakshuka executable...")
    
    # PyInstaller command using Python module execution
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',  # Create a single executable file
        '--console',  # Show console window for debugging
        '--name=Shakshuka',  # Name of the executable
        '--target-arch=x86_64',  # Explicitly target 64-bit
        '--icon=assets/static/images/icon.ico',  # Embed app icon into the EXE
        '--clean',  # Clean cache before building
        '--add-data=assets/templates;templates',  # Include templates
        '--add-data=assets/static;static',  # Include static files
        '--add-data=data;data',  # Include data directory
        '--add-data=config/version.json;.',  # Include version file
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=main',
        '--hidden-import=src',
        '--hidden-import=cryptography',
        '--hidden-import=cryptography.fernet',
        '--hidden-import=cryptography.hazmat',
        '--hidden-import=cryptography.hazmat.primitives',
        '--hidden-import=cryptography.hazmat.primitives.hashes',
        '--hidden-import=cryptography.hazmat.primitives.kdf',
        '--hidden-import=cryptography.hazmat.primitives.kdf.pbkdf2',
        '--hidden-import=cryptography.hazmat.backends',
        '--hidden-import=cryptography.hazmat.backends.openssl',
        '--hidden-import=schedule',
        '--hidden-import=psutil',
        '--hidden-import=winreg',
        '--hidden-import=requests',
        '--hidden-import=requests.adapters',
        '--hidden-import=requests.auth',
        '--hidden-import=requests.cookies',
        '--hidden-import=requests.exceptions',
        '--hidden-import=requests.models',
        '--hidden-import=requests.sessions',
        '--hidden-import=requests.utils',
        '--hidden-import=urllib3',
        '--hidden-import=urllib3.util',
        '--hidden-import=urllib3.util.retry',
        '--hidden-import=urllib3.util.connection',
        '--hidden-import=certifi',
        '--hidden-import=charset_normalizer',
        '--hidden-import=idna',
        '--hidden-import=werkzeug',
        '--hidden-import=werkzeug.serving',
        '--hidden-import=werkzeug.utils',
        '--hidden-import=jinja2',
        '--hidden-import=jinja2.ext',
        '--hidden-import=markupsafe',
        '--hidden-import=itsdangerous',
        '--hidden-import=click',
        '--hidden-import=blinker',
        '--hidden-import=python_dotenv',
        '--hidden-import=dotenv',
        '--hidden-import=bcrypt',
        '--hidden-import=keyring',
        '--hidden-import=keyring.backends',
        '--hidden-import=keyring.backends.Windows',
        '--collect-all=requests',
        '--collect-all=urllib3',
        '--collect-all=cryptography',
        '--collect-all=flask',
        '--collect-all=werkzeug',
        '--collect-all=jinja2',
        '--add-data=src;src',
        '--add-data=tools/autostart.py;.',
        '--add-data=config/version.json;.',
        '--hidden-import=src.core',
        '--hidden-import=src.core.config',
        '--hidden-import=src.core.app_context',
        '--hidden-import=src.core.launcher',
        '--hidden-import=src.middleware',
        '--hidden-import=src.middleware.auth_middleware',
        '--hidden-import=src.middleware.csrf_middleware',
        '--hidden-import=src.utils',
        '--hidden-import=src.utils.validators',
        '--hidden-import=src.utils.sanitizers',
        'main.py'
    ]
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Executable built successfully!")
        
        # Move executable to root directory
        exe_path = Path('dist/Shakshuka.exe')
        if exe_path.exists():
            shutil.move(str(exe_path), 'Shakshuka.exe')
            print("Executable moved to root directory")
        
        # Clean up build files
        cleanup_build_files()
        
        print("\nExecutable build complete!")
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    return True

def find_inno_setup():
    """Find Inno Setup 6 installation"""
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup\ISCC.exe",
        r"C:\Program Files\Inno Setup\ISCC.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try to find it in PATH
    try:
        result = subprocess.run(['where', 'iscc'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return None

def build_installer():
    """Build installer using Inno Setup 6"""
    print("\nBuilding installer with Inno Setup 6...")
    
    # Find Inno Setup
    inno_path = find_inno_setup()
    if not inno_path:
        print("ERROR: Inno Setup 6 not found!")
        print("Please install Inno Setup 6 from: https://jrsoftware.org/isinfo.php")
        print("Or ensure it's in your PATH")
        return False
    
    print(f"Found Inno Setup at: {inno_path}")
    
    # Read current version (already bumped in main)
    version, build = get_version_info()
    print(f"Building installer for version {version} (build {build})")

    # Update installer script with current version
    update_installer_script(version, build)
    
    # Build installer
    installer_script = Path('scripts/installer.iss')
    if not installer_script.exists():
        print(f"ERROR: Installer script not found: {installer_script}")
        return False
    
    try:
        cmd = [inno_path, str(installer_script)]
        print(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Installer built successfully!")
        
        # Check for installer without build suffix (e.g., v6.1)
        installer_path = Path('scripts/dist/Shakshuka-Setup-v' + str(version) + '.exe')
        if installer_path.exists():
            print(f"Installer created: {installer_path}")
            print(f"Size: {installer_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Copy to root directory for easy access
            root_installer = Path('Shakshuka-Setup-v' + str(version) + '.exe')
            shutil.copy2(installer_path, root_installer)
            print(f"Installer copied to: {root_installer}")
            
            return True
        else:
            print("ERROR: Installer file not found after build")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Installer build failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error building installer: {e}")
        return False

def update_changelog(version: str, notes: str = None):
    """Prepend a changelog entry for the given version if not already present."""
    changelog_path = Path('config/changelog.txt')
    try:
        existing = ''
        if changelog_path.exists():
            existing = changelog_path.read_text(encoding='utf-8')
            if f"## Version {version} " in existing or f"## Version {version}\n" in existing:
                print(f"Changelog already has an entry for v{version}; skipping")
                return
        now = datetime.now().isoformat()
        # Determine release title based on major version
        try:
            major = int(str(version).split('.')[0])
        except Exception:
            major = None
        if major == 6:
            title_suffix = "Birthday Update"
        elif major == 7:
            title_suffix = "Post Birthday Update"
        else:
            title_suffix = "Release"
        lines = [
            f"## Version {version} - {title_suffix}",
            f"Release Date: {now}",
            "",
            "Highlights",
            "- Daily strikes persistence in SQLite (new migration)",
            "- Reduced duplicate planner schedule GET calls",
            "- Static cache-bust params unified to ?v=6.2",
            "- Installer script echoes dynamic version",
            "",
            "---",
            "",
        ]
        changelog_path.write_text("\n".join(lines) + existing, encoding='utf-8')
        print(f"Changelog updated with v{version}")
    except Exception as e:
        print(f"Warning: Failed to update changelog: {e}")


def update_installer_script(version, build):
    """Update the installer script with current version (no build suffix in filename)"""
    installer_script = Path('scripts/installer.iss')
    
    if not installer_script.exists():
        print(f"Warning: Installer script not found: {installer_script}")
        return
    
    try:
        # Read the current script - handle both CRLF and LF line endings
        with open(installer_script, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update version and build in Inno Setup defines
        import re
        
        # Update MyAppVersion
        content = re.sub(r'#define MyAppVersion "[^"]*"', f'#define MyAppVersion "{version}"', content)
        
        # Also update VersionInfoVersion and VersionInfoProductVersion with build number
        # Format: major.minor.patch.build
        # Parse version string (e.g., "6.2" becomes "6.2.0")
        version_parts = version.split('.')
        while len(version_parts) < 3:
            version_parts.append('0')
        # Use two-part version for display/file names; keep 4-part for Windows metadata with zeros
        full_version = f"{version_parts[0]}.{version_parts[1]}.0.0"
        
        # Update VersionInfoVersion line - use more specific pattern for Inno Setup
        content = re.sub(
            r'^VersionInfoVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Update VersionInfoProductVersion line
        content = re.sub(
            r'^VersionInfoProductVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoProductVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Write back the updated script with consistent line endings
        with open(installer_script, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(content)
        
        print(f"Updated installer script with version {version} (build {build})")
        print(f"  - MyAppVersion: {version}")
        print(f"  - VersionInfoVersion: {full_version}")
        print(f"  - VersionInfoProductVersion: {full_version}")
        
    except Exception as e:
        print(f"Warning: Could not update installer script: {e}")
        import traceback
        traceback.print_exc()

def cleanup_build_files():
    """Clean up PyInstaller build files"""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    files_to_remove = ['Shakshuka.spec']
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed {dir_name}/")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"Removed {file_name}")

def create_icon():
    """Create a simple icon file if it doesn't exist"""
    icon_path = Path('assets/static/images/icon.ico')
    if not icon_path.exists():
        # Create images directory if it doesn't exist
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        
        # For now, we'll skip the icon creation
        # In a real scenario, you'd want to create a proper .ico file
        print("No icon file found. Building without custom icon...")

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'config/requirements.txt'], 
                      check=True, capture_output=True, text=True)
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

def generate_build_report(version, build, build_success=True):
    """Generate a detailed build report"""
    from datetime import datetime
    
    # Create build_reports directory if it doesn't exist
    report_dir = Path('build_reports')
    report_dir.mkdir(exist_ok=True)
    
    # Generate report filename
    report_filename = f"BUILD_REPORT_v{version}.md"
    report_path = report_dir / report_filename
    
    # Gather build information
    exe_path = Path('Shakshuka.exe')
    installer_path = Path(f'Shakshuka-Setup-v{version}.exe')
    
    exe_size = exe_path.stat().st_size / (1024*1024) if exe_path.exists() else 0
    installer_size = installer_path.stat().st_size / (1024*1024) if installer_path.exists() else 0
    
    # Read changelog
    changelog = "Not available"
    try:
        with open('config/changelog.txt', 'r', encoding='utf-8') as f:
            changelog = f.read()
    except:
        pass
    
    # Generate report content
    report_content = f"""# Build Report - Shakshuka v{version}-b{build}

## Build Information
- **Version:** {version}
- **Build Number:** {build}
- **Build Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Build Status:** {'✅ SUCCESS' if build_success else '❌ FAILED'}
- **Platform:** Windows (x86_64)

## Build Artifacts

### 1. Standalone Executable
- **Filename:** `Shakshuka.exe`
- **Size:** {exe_size:.2f} MB
- **Type:** PyInstaller Single-File Executable
- **Status:** {'✅ Created' if exe_path.exists() else '❌ Not Found'}

### 2. Installer Package
- **Filename:** `Shakshuka-Setup-v{version}.exe`
- **Size:** {installer_size:.2f} MB
- **Type:** Inno Setup Installer
- **Status:** {'✅ Created' if installer_path.exists() else '❌ Not Found'}

## Build Configuration
- **Python Version:** {sys.version.split()[0]}
- **Build Script:** `scripts/build.py`
- **Installer Script:** `scripts/installer.iss`
- **PyInstaller:** Single-file, console mode
- **Architecture:** 64-bit (x86_64)

## Features Included
- Flask web server (port 8989)
- SQLite database backend
- System tray integration
- Auto-save functionality
- Task management system
- User authentication (optional)
- Settings persistence
- Auto-update capability
- Monitoring and analytics

## File Locations
- **Executable:** `{exe_path.absolute()}`
- **Installer:** `{installer_path.absolute()}`
- **Source Distribution:** `scripts/dist/`

## Installation Methods

### Method 1: Standalone Executable
1. Run `Shakshuka.exe` directly
2. No installation required
3. Portable - can run from any location

### Method 2: Professional Installer
1. Run `Shakshuka-Setup-v{version}-b{build}.exe`
2. Follow installation wizard
3. Installs to `Program Files`
4. Creates Start Menu shortcuts
5. Adds uninstaller

## Changelog
{changelog}

## Next Steps
1. Test the standalone executable
2. Test the installer package
3. Verify all features work correctly
4. Check for any errors in logs
5. Update documentation if needed

## Build System
- **Auto-Increment:** Build number automatically incremented
- **Version File:** `config/version.json`
- **Build Reports:** Saved to `build_reports/`

---
*Report generated automatically by build.py*
"""
    
    # Write report to file
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\nBuild report generated: {report_path}")
        return str(report_path)
    except Exception as e:
        print(f"Warning: Could not generate build report: {e}")
        return None

def main():
    """Main build process"""
    print("Shakshuka Build Script with Inno Setup 6")
    print("=" * 50)
    
    # Check if we're on Windows
    if sys.platform != 'win32':
        print("Warning: This build script is designed for Windows. Some features may not work on other platforms.")
    
    # Skip dependency installation since they're already installed
    print("Dependencies already installed, proceeding with build...")
    
    # Create icon
    create_icon()
    
    # Bump two-part version and update changelog
    version, build = bump_version_two_part()
    update_changelog(version)
    
    # Build executable
    if not build_executable():
        print("\nBuild failed. Please check the error messages above.")
        return
    
    # Build installer
    if build_installer():
        print("\n" + "=" * 50)
        print("BUILD COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("\nFiles created:")
        print("1. Shakshuka.exe - Standalone executable")
        
        version, build = get_version_info()
        installer_name = f"Shakshuka-Setup-v{version}.exe"
        print(f"2. {installer_name} - Professional Windows installer")
        
        # Generate build report
        generate_build_report(version, build, build_success=True)
        
        print("\nNext steps:")
        print("1. Test the standalone executable: Run Shakshuka.exe")
        print("2. Test the installer: Run the installer to install Shakshuka")
        print("3. The app will open in your default browser at http://127.0.0.1:8989")
        print("4. Your data will be stored in the 'data' folder")
        print("5. Enable autostart in Settings if desired")
    else:
        print("\nInstaller build failed, but executable was created successfully.")
        print("You can still run Shakshuka.exe directly.")
        
        # Generate build report even if installer failed
        version, build = get_version_info()
        generate_build_report(version, build, build_success=False)

if __name__ == '__main__':
    main()
