"""Executable building for Shakshuka using PyInstaller"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_executable(output_dir=None):
    """Build the executable using PyInstaller.

    output_dir:
        Optional path where the built executable should be placed.
        Defaults to a top-level 'dist' directory for backward compatibility.
    """

    print("Building Shakshuka executable...")

    # Determine output directory
    if output_dir is None:
        output_dir = Path('dist')
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--console',
        '--name=Shakshuka',
        '--target-arch=x86_64',
        '--icon=assets/static/images/icon.ico',
        '--clean',
        f'--distpath={str(output_dir)}',
        '--add-data=assets/templates;templates',
        '--add-data=assets/static;static',
        '--add-data=data;data',
        '--add-data=config/version.json;.',
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
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Executable built successfully!")
        
        exe_path = output_dir / 'Shakshuka.exe'
        if exe_path.exists():
            print(f"Executable created at: {exe_path}")
            print(f"Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
        
        cleanup_build_files()
        print("\nExecutable build complete!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def cleanup_build_files():
    """Clean up PyInstaller build files"""
    dirs_to_remove = ['build', '__pycache__']
    files_to_remove = ['Shakshuka.spec']
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed {dir_name}/")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"Removed {file_name}")


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


def create_icon():
    """Create a simple icon file if it doesn't exist"""
    icon_path = Path('assets/static/images/icon.ico')
    if not icon_path.exists():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        print("No icon file found. Building without custom icon...")
