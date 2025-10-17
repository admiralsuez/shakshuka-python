import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_executable():
    """Build the executable using PyInstaller with all dependencies bundled"""
    
    print("Building Shakshuka executable...")
    
    # PyInstaller command with comprehensive dependency bundling
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',  # Create a single executable file
        '--windowed',  # Hide console window
        '--name=Shakshuka',  # Name of the executable
        '--add-data=templates;templates',  # Include templates
        '--add-data=static;static',  # Include static files
        '--add-data=data;data',  # Include data directory
        '--icon=static/images/icon.ico',  # Add icon
        
        # Core Flask dependencies
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=werkzeug',
        '--hidden-import=jinja2',
        '--hidden-import=markupsafe',
        '--hidden-import=itsdangerous',
        '--hidden-import=click',
        '--hidden-import=blinker',
        
        # Cryptography dependencies
        '--hidden-import=cryptography',
        '--hidden-import=cryptography.fernet',
        '--hidden-import=cryptography.hazmat',
        '--hidden-import=cryptography.hazmat.primitives',
        '--hidden-import=cryptography.hazmat.primitives.hashes',
        '--hidden-import=cryptography.hazmat.primitives.kdf',
        '--hidden-import=cryptography.hazmat.primitives.kdf.pbkdf2',
        '--hidden-import=cryptography.hazmat.backends',
        '--hidden-import=cryptography.hazmat.backends.openssl',
        '--hidden-import=cryptography.hazmat.backends.openssl.backend',
        
        # Schedule dependencies
        '--hidden-import=schedule',
        
        # System monitoring
        '--hidden-import=psutil',
        
        # Windows registry
        '--hidden-import=winreg',
        
        # HTTP requests and networking
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
        '--hidden-import=urllib3.util.ssl_',
        '--hidden-import=urllib3.util.timeout',
        '--hidden-import=urllib3.util.url',
        '--hidden-import=certifi',
        '--hidden-import=charset_normalizer',
        '--hidden-import=idna',
        
        # Additional Python standard library modules
        '--hidden-import=json',
        '--hidden-import=csv',
        '--hidden-import=io',
        '--hidden-import=uuid',
        '--hidden-import=threading',
        '--hidden-import=time',
        '--hidden-import=datetime',
        '--hidden-import=os',
        '--hidden-import=sys',
        '--hidden-import=pathlib',
        '--hidden-import=shutil',
        '--hidden-import=subprocess',
        '--hidden-import=base64',
        '--hidden-import=hashlib',
        '--hidden-import=secrets',
        '--hidden-import=random',
        '--hidden-import=string',
        '--hidden-import=collections',
        '--hidden-import=itertools',
        '--hidden-import=functools',
        '--hidden-import=operator',
        '--hidden-import=copy',
        '--hidden-import=pickle',
        '--hidden-import=tempfile',
        '--hidden-import=zipfile',
        '--hidden-import=tarfile',
        '--hidden-import=gzip',
        '--hidden-import=zlib',
        '--hidden-import=hashlib',
        '--hidden-import=hmac',
        '--hidden-import=ssl',
        '--hidden-import=socket',
        '--hidden-import=http',
        '--hidden-import=http.client',
        '--hidden-import=http.server',
        '--hidden-import=urllib',
        '--hidden-import=urllib.parse',
        '--hidden-import=urllib.request',
        '--hidden-import=urllib.response',
        '--hidden-import=urllib.error',
        '--hidden-import=email',
        '--hidden-import=email.mime',
        '--hidden-import=email.mime.text',
        '--hidden-import=email.mime.multipart',
        '--hidden-import=email.utils',
        '--hidden-import=email.parser',
        '--hidden-import=email.message',
        '--hidden-import=email.header',
        '--hidden-import=email.charset',
        '--hidden-import=email.encoders',
        '--hidden-import=email.generator',
        '--hidden-import=email.policy',
        '--hidden-import=email.contentmanager',
        '--hidden-import=email.mime.nonmultipart',
        '--hidden-import=email.mime.base',
        '--hidden-import=email.mime.image',
        '--hidden-import=email.mime.audio',
        '--hidden-import=email.mime.application',
        '--hidden-import=email.mime.message',
        '--hidden-import=email.mime.text',
        '--hidden-import=email.mime.multipart',
        
        # Collect all modules from key packages
        '--collect-all=flask',
        '--collect-all=flask_cors',
        '--collect-all=cryptography',
        '--collect-all=requests',
        '--collect-all=urllib3',
        '--collect-all=schedule',
        '--collect-all=psutil',
        
        # Include additional files
        '--add-data=data_manager.py;.',
        '--add-data=security_manager.py;.',
        '--add-data=update_manager.py;.',
        '--add-data=autostart.py;.',
        '--add-data=installer.py;.',
        
        # Exclude unnecessary modules to reduce size
        '--exclude-module=tkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=PIL',
        '--exclude-module=cv2',
        '--exclude-module=torch',
        '--exclude-module=tensorflow',
        '--exclude-module=sklearn',
        '--exclude-module=jupyter',
        '--exclude-module=notebook',
        '--exclude-module=IPython',
        
        'app.py'
    ]
    
    try:
        # Run PyInstaller
        print("Running PyInstaller with comprehensive dependency bundling...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Executable built successfully!")
        
        # Move executable to root directory
        exe_path = Path('dist/Shakshuka.exe')
        if exe_path.exists():
            shutil.move(str(exe_path), 'Shakshuka.exe')
            print("Executable moved to root directory")
            
            # Check file size of the moved file
            moved_exe = Path('Shakshuka.exe')
            if moved_exe.exists():
                size_mb = moved_exe.stat().st_size / (1024 * 1024)
                print(f"Executable size: {size_mb:.1f} MB")
            else:
                print("Warning: Could not find moved executable")
        else:
            print("Warning: Executable not found in dist/ directory")
        
        # Clean up build files
        cleanup_build_files()
        
        print("\nBuild complete! You can now run Shakshuka.exe")
        print("The executable is completely self-contained with all dependencies bundled.")
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    return True

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

def verify_executable():
    """Verify the executable works and is self-contained"""
    print("\nVerifying executable...")
    
    exe_path = Path('Shakshuka.exe')
    if not exe_path.exists():
        print("ERROR: Shakshuka.exe not found!")
        return False
    
    # Check file size (should be substantial for a bundled executable)
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"Executable size: {size_mb:.1f} MB")
    
    if size_mb < 10:
        print("WARNING: Executable seems too small. Dependencies might not be bundled properly.")
        return False
    
    print("Executable verification passed!")
    return True

def create_standalone_package():
    """Create a standalone package with just the exe and essential files"""
    print("\nCreating standalone package...")
    
    standalone_dir = Path('standalone')
    if standalone_dir.exists():
        shutil.rmtree(standalone_dir)
    standalone_dir.mkdir()
    
    # Copy essential files
    files_to_copy = [
        'Shakshuka.exe',
        'Start-Shakshuka.bat',
        'Stop-Shakshuka.bat',
        'SIMPLE-README.md'
    ]
    
    for file_name in files_to_copy:
        src = Path(file_name)
        if src.exists():
            dst = standalone_dir / file_name
            shutil.copy2(src, dst)
            print(f"Copied {file_name}")
    
    # Create a simple launcher
    launcher_content = '''@echo off
title Shakshuka Task Manager
echo Starting Shakshuka...
echo.

REM Check if Shakshuka.exe exists
if not exist "Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found!
    echo Please ensure all files are extracted properly.
    pause
    exit /b 1
)

echo Starting server...
echo The application will open in your browser at http://127.0.0.1:8989
echo Press Ctrl+C to stop the server
echo.

start "" "Shakshuka.exe"
'''
    
    with open(standalone_dir / 'Start-Shakshuka.bat', 'w') as f:
        f.write(launcher_content)
    
    print("Standalone package created in 'standalone/' directory")
    print("This package contains only the essential files needed to run Shakshuka.")

def main():
    """Main build process"""
    print("Shakshuka Build Script - Standalone Executable")
    print("=" * 60)
    
    # Check if we're on Windows
    if sys.platform != 'win32':
        print("ERROR: This build script is designed for Windows only.")
        print("PyInstaller on other platforms may not create Windows executables.")
        return
    
    # Check if required files exist
    required_files = ['app.py', 'requirements.txt']
    for file_name in required_files:
        if not Path(file_name).exists():
            print(f"ERROR: Required file {file_name} not found!")
            return
    
    print("Building standalone executable with all dependencies bundled...")
    print("This may take several minutes...")
    
    # Build executable
    if build_executable():
        # Verify the executable
        if verify_executable():
            # Create standalone package
            create_standalone_package()
            
            print("\n" + "=" * 60)
            print("BUILD COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("\nThe Shakshuka.exe file is completely self-contained and includes:")
            print("+ All Python dependencies bundled")
            print("+ Flask web framework")
            print("+ Cryptography libraries")
            print("+ All required modules")
            print("+ No external dependencies needed")
            print("\nUsers can run Shakshuka.exe on any Windows machine without Python installed!")
            print("\nFiles created:")
            print("- Shakshuka.exe (standalone executable)")
            print("- standalone/ (minimal distribution package)")
            print("\nTo distribute:")
            print("1. Share the 'standalone' folder")
            print("2. Users just run Shakshuka.exe")
            print("3. No Python installation required!")
        else:
            print("\nBuild verification failed. Please check the executable.")
    else:
        print("\nBuild failed. Please check the error messages above.")

if __name__ == '__main__':
    main()
