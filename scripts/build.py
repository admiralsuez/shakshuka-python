"""
Shakshuka Build Script
Builds executable and installer using modular build system.
"""

import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from build.version import get_version_info, bump_version_two_part
from build.executable import build_executable, create_icon
from build.installer import build_installer
from build.report import generate_build_report, update_changelog


def main():
    """Main build process"""
    print("Shakshuka Build Script")
    print("=" * 50)
    
    if sys.platform != 'win32':
        print("Warning: This build script is designed for Windows.")
    
    # Create icon if needed
    create_icon()
    
    # Bump version and update changelog
    version, build = bump_version_two_part()
    update_changelog(version)
    
    # Build executable
    if not build_executable():
        print("\nBuild failed. Please check the error messages above.")
        generate_build_report(version, build, build_success=False)
        return
    
    # Build installer
    if build_installer():
        print("\n" + "=" * 50)
        print("BUILD COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("\nFiles created in dist/:")
        print("  1. Shakshuka.exe - Standalone executable")
        print(f"  2. Shakshuka-Setup-v{version}.exe - Windows installer")
        
        generate_build_report(version, build, build_success=True)
        
        print("\nNext steps:")
        print("  1. Test: Run dist/Shakshuka.exe")
        print("  2. Install: Run the installer from dist/")
        print("  3. App opens at http://127.0.0.1:8989")
    else:
        print("\nInstaller build failed, but executable was created.")
        print("You can still run dist/Shakshuka.exe directly.")
        generate_build_report(version, build, build_success=False)


if __name__ == '__main__':
    main()
