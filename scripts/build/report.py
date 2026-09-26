"""Build report generation for Shakshuka"""

import sys
from datetime import datetime
from pathlib import Path


def generate_build_report(version, build, build_success=True):
    """Generate a detailed build report"""
    
    report_dir = Path('build_reports')
    report_dir.mkdir(exist_ok=True)
    
    report_filename = f"BUILD_REPORT_v{version}.md"
    report_path = report_dir / report_filename
    
    exe_path = Path('dist/Shakshuka.exe')
    installer_path = Path(f'dist/Shakshuka-Setup-v{version}.exe')
    
    exe_size = exe_path.stat().st_size / (1024*1024) if exe_path.exists() else 0
    installer_size = installer_path.stat().st_size / (1024*1024) if installer_path.exists() else 0
    
    changelog = "Not available"
    try:
        with open('config/changelog.txt', 'r', encoding='utf-8') as f:
            changelog = f.read()
    except:
        pass
    
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
- **Location:** `dist/Shakshuka.exe`
- **Size:** {exe_size:.2f} MB
- **Status:** {'✅ Created' if exe_path.exists() else '❌ Not Found'}

### 2. Installer Package
- **Filename:** `Shakshuka-Setup-v{version}.exe`
- **Location:** `dist/Shakshuka-Setup-v{version}.exe`
- **Size:** {installer_size:.2f} MB
- **Status:** {'✅ Created' if installer_path.exists() else '❌ Not Found'}

## Build Configuration
- **Python Version:** {sys.version.split()[0]}
- **Build Script:** `scripts/build.py`
- **PyInstaller:** Single-file, console mode
- **Architecture:** 64-bit (x86_64)

## Changelog
{changelog}

---
*Report generated automatically by build system*
"""
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\nBuild report generated: {report_path}")
        return str(report_path)
    except Exception as e:
        print(f"Warning: Could not generate build report: {e}")
        return None


def update_changelog(version: str, notes: str = None):
    """Prepend a changelog entry for the given version if not already present.

    When *notes* is empty or missing, this function will NOT create a new
    entry. This prevents empty or placeholder sections from polluting the
    changelog when a build is run without real release notes.
    """
    changelog_path = Path('config/changelog.txt')
    try:
        existing = ''
        if changelog_path.exists():
            existing = changelog_path.read_text(encoding='utf-8')
            if f"## Version {version} " in existing or f"## Version {version}\n" in existing:
                print(f"Changelog already has an entry for v{version}; skipping")
                return

        notes_text = (notes or '').strip()
        if not notes_text:
            print(f"No release notes provided for v{version}; changelog entry will not be created.")
            return

        now = datetime.now().isoformat()
        
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
        ]

        # Treat notes as pre-formatted markdown. This allows bullet lists or
        # paragraphs to be authored directly in the release notes file.
        lines.extend(notes_text.splitlines())
        lines.extend([
            "",
            "---",
            "",
        ])

        changelog_path.write_text("\n".join(lines) + existing, encoding='utf-8')
        print(f"Changelog updated with v{version}")
    except Exception as e:
        print(f"Warning: Failed to update changelog: {e}")
