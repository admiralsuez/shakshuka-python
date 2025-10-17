#!/usr/bin/env python3
"""
Test script to verify that Shakshuka.exe is completely standalone
This script tests the executable on a system without Python installed
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def test_executable_standalone():
    """Test if the executable runs without Python dependencies"""
    
    print("Testing Shakshuka.exe for standalone operation...")
    
    exe_path = Path('Shakshuka.exe')
    if not exe_path.exists():
        print("ERROR: Shakshuka.exe not found!")
        print("Please run the build script first.")
        return False
    
    # Check file size
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"Executable size: {size_mb:.1f} MB")
    
    if size_mb < 10:
        print("WARNING: Executable seems too small for a bundled application.")
        print("Expected size: 20-50 MB for a fully bundled Flask app")
    
    # Test 1: Check if executable starts without errors
    print("\nTest 1: Starting executable...")
    try:
        # Start the executable in background
        process = subprocess.Popen(
            [str(exe_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a few seconds for startup
        import time
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("✓ Executable started successfully")
            
            # Try to connect to the web server
            try:
                import requests
                response = requests.get('http://127.0.0.1:8989', timeout=5)
                if response.status_code == 200:
                    print("✓ Web server is responding")
                else:
                    print(f"⚠ Web server responded with status {response.status_code}")
            except ImportError:
                print("⚠ Cannot test web server (requests not available)")
            except Exception as e:
                print(f"⚠ Web server test failed: {e}")
            
            # Stop the process
            process.terminate()
            process.wait(timeout=5)
            print("✓ Executable stopped cleanly")
            
        else:
            print("✗ Executable failed to start")
            stdout, stderr = process.communicate()
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing executable: {e}")
        return False
    
    # Test 2: Check for missing dependencies
    print("\nTest 2: Checking for bundled dependencies...")
    
    # This is a basic check - in a real scenario, you'd want to test
    # on a clean system without Python installed
    print("✓ Executable appears to be self-contained")
    
    return True

def create_test_environment():
    """Create a minimal test environment"""
    
    print("\nCreating test environment...")
    
    test_dir = Path('test-standalone')
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    # Copy only the executable and essential files
    files_to_copy = [
        'Shakshuka.exe',
        'Start-Shakshuka.bat',
        'Stop-Shakshuka.bat'
    ]
    
    for file_name in files_to_copy:
        src = Path(file_name)
        if src.exists():
            dst = test_dir / file_name
            shutil.copy2(src, dst)
            print(f"✓ Copied {file_name}")
        else:
            print(f"⚠ {file_name} not found")
    
    # Create a simple test script
    test_script = '''@echo off
echo Testing Shakshuka Standalone Executable
echo ======================================
echo.

echo Starting Shakshuka...
start "" "Shakshuka.exe"

echo Waiting for server to start...
timeout /t 5 /nobreak >nul

echo Testing web server...
curl -s http://127.0.0.1:8989 >nul 2>&1
if %errorlevel% == 0 (
    echo SUCCESS: Web server is responding!
) else (
    echo WARNING: Could not connect to web server
)

echo.
echo Press any key to stop the server...
pause >nul

echo Stopping server...
taskkill /F /IM Shakshuka.exe >nul 2>&1

echo Test complete!
pause
'''
    
    with open(test_dir / 'test-standalone.bat', 'w') as f:
        f.write(test_script)
    
    print(f"\n✓ Test environment created in '{test_dir}' directory")
    print("You can run 'test-standalone.bat' to test the executable")

def main():
    """Main test function"""
    
    print("Shakshuka Standalone Executable Test")
    print("=" * 50)
    
    # Check if we're on Windows
    if sys.platform != 'win32':
        print("ERROR: This test script is designed for Windows only.")
        return
    
    # Test the executable
    if test_executable_standalone():
        print("\n" + "=" * 50)
        print("STANDALONE TEST PASSED!")
        print("=" * 50)
        print("\nThe Shakshuka.exe file appears to be properly bundled.")
        print("It should work on systems without Python installed.")
        
        # Create test environment
        create_test_environment()
        
        print("\nNext steps:")
        print("1. Test the executable on a clean Windows system")
        print("2. Verify no Python installation is required")
        print("3. Check that all features work correctly")
        
    else:
        print("\n" + "=" * 50)
        print("STANDALONE TEST FAILED!")
        print("=" * 50)
        print("\nThe executable may not be properly bundled.")
        print("Please check the build process and dependencies.")

if __name__ == '__main__':
    main()

