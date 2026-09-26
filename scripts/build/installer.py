"""Installer building for Shakshuka using Inno Setup"""

import os
import re
import subprocess
import shutil
from pathlib import Path

from .version import get_version_info


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
    
    try:
        result = subprocess.run(['where', 'iscc'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return None


def build_installer(output_dir=None):
    """Build installer using Inno Setup 6.

    output_dir:
        Optional final directory where the installer should be placed.
        Defaults to a top-level 'dist' directory for backward compatibility.
    """
    print("\nBuilding installer with Inno Setup 6...")
    
    inno_path = find_inno_setup()
    if not inno_path:
        print("ERROR: Inno Setup 6 not found!")
        print("Please install Inno Setup 6 from: https://jrsoftware.org/isinfo.php")
        return False
    
    print(f"Found Inno Setup at: {inno_path}")
    
    version, build = get_version_info()
    print(f"Building installer for version {version} (build {build})")

    update_installer_script(version, build)
    
    installer_script = Path('scripts/installer.iss')
    if not installer_script.exists():
        print(f"ERROR: Installer script not found: {installer_script}")
        return False
    
    try:
        cmd = [inno_path, str(installer_script)]
        print(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Installer built successfully!")
        
        # Check for installer in scripts/dist
        installer_path = Path('scripts/dist/Shakshuka-Setup-v' + str(version) + '.exe')
        if installer_path.exists():
            print(f"Installer created: {installer_path}")
            print(f"Size: {installer_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Determine final output directory
            if output_dir is None:
                final_dir = Path('dist')
            else:
                final_dir = Path(output_dir)
            final_dir.mkdir(parents=True, exist_ok=True)

            dest_installer = final_dir / installer_path.name
            shutil.move(str(installer_path), str(dest_installer))
            print(f"Installer moved to: {dest_installer}")
            
            # Clean up scripts/dist folder only if it's not our final_dir
            scripts_dist = Path('scripts/dist')
            try:
                if scripts_dist.exists() and scripts_dist.resolve() != final_dir.resolve():
                    shutil.rmtree(scripts_dist)
                    print("Cleaned up scripts/dist/")
            except Exception:
                # non-fatal
                pass
            
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


def update_installer_script(version, build):
    """Update the installer script with current version"""
    installer_script = Path('scripts/installer.iss')
    
    if not installer_script.exists():
        print(f"Warning: Installer script not found: {installer_script}")
        return
    
    try:
        with open(installer_script, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = re.sub(r'#define MyAppVersion "[^"]*"', f'#define MyAppVersion "{version}"', content)
        
        version_parts = version.split('.')
        while len(version_parts) < 3:
            version_parts.append('0')
        full_version = f"{version_parts[0]}.{version_parts[1]}.0.0"
        
        content = re.sub(
            r'^VersionInfoVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        content = re.sub(
            r'^VersionInfoProductVersion\s*=\s*[\d\.]+\s*$',
            f'VersionInfoProductVersion={full_version}',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        with open(installer_script, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(content)
        
        print(f"Updated installer script with version {version}")
        
    except Exception as e:
        print(f"Warning: Could not update installer script: {e}")
