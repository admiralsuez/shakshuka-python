import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_executable():
    """Build the executable using PyInstaller"""
    
    print("Building Shakshuka executable...")
    
    # PyInstaller command using Python module execution
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',  # Create a single executable file
        '--windowed',  # Hide console window
        '--name=Shakshuka',  # Name of the executable
        '--add-data=templates;templates',  # Include templates
        '--add-data=static;static',  # Include static files
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=cryptography',
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
        '--collect-all=requests',
        '--add-data=update_manager.py;.',
        '--add-data=installer.py;.',
        'app.py'
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
        
        print("\nBuild complete! You can now run Shakshuka.exe")
        
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

def create_icon():
    """Create a simple icon file if it doesn't exist"""
    icon_path = Path('static/images/icon.ico')
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
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True, capture_output=True, text=True)
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

def main():
    """Main build process"""
    print("Shakshuka Build Script")
    print("=" * 50)
    
    # Check if we're on Windows
    if sys.platform != 'win32':
        print("Warning: This build script is designed for Windows. Some features may not work on other platforms.")
    
    # Skip dependency installation since they're already installed
    print("Dependencies already installed, proceeding with build...")
    
    # Create icon
    create_icon()
    
    # Build executable
    if build_executable():
        print("\nBuild completed successfully!")
        print("\nNext steps:")
        print("1. Run Shakshuka.exe to start the application")
        print("2. The app will open in your default browser at http://127.0.0.1:8989")
        print("3. Your data will be stored in the 'data' folder")
        print("4. Enable autostart in Settings if desired")
    else:
        print("\nBuild failed. Please check the error messages above.")

if __name__ == '__main__':
    main()
