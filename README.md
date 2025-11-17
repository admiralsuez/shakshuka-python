# Shakshuka Build Instructions

This guide explains how to build Shakshuka for both **Windows** (EXE) and **Linux** (.deb package).

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Windows Build (EXE)](#windows-build-exe)
- [Linux Build (.deb)](#linux-build-deb)
- [Troubleshooting](#troubleshooting)
- [Version Management](#version-management)

---

## 🔧 Prerequisites

### For Windows Build:
- **Python 3.8+** installed
- **PyInstaller** (`pip install pyinstaller`)
- **Inno Setup 6** (for creating installer) - Download from [jrsoftware.org](https://jrsoftware.org/isinfo.php)
- All dependencies from `config/requirements.txt` installed

### For Linux Build:
- **Python 3.8+** installed
- **fpm** (Fancy Package Manager) - Install with:
  ```bash
  sudo apt-get install ruby-dev build-essential
  sudo gem install fpm
  ```
- **dpkg** (usually pre-installed on Debian/Ubuntu)
- All dependencies from `config/requirements.txt` installed

### Common Prerequisites:
```bash
# Install Python dependencies
pip install -r config/requirements.txt
```

---

## 🪟 Windows Build (EXE)

### Step 1: Install Inno Setup 6
1. Download Inno Setup 6 from [https://jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php)
2. Install it to the default location: `C:\Program Files (x86)\Inno Setup 6\`
3. The build script will automatically find it

### Step 2: Run the Build Script
```bash
python scripts/build.py
```

### What the Script Does:
1. ✅ **Auto-increments build number** in `config/version.json`
2. ✅ **Updates version info** in installer script
3. ✅ **Builds standalone EXE** using PyInstaller
4. ✅ **Creates Windows installer** using Inno Setup 6
5. ✅ **Generates build report** in `build_reports/`

### Output Files:
- **`Shakshuka.exe`** - Standalone executable (in project root)
- **`Shakshuka-Setup-vX.X.exe`** - Windows installer (in project root)
- **Build report** - `build_reports/BUILD_REPORT_vX.X.md`

### Build Process Details:
- **PyInstaller**: Creates single-file executable with all dependencies
- **Architecture**: 64-bit (x86_64)
- **Console Mode**: Shows console window for debugging
- **Icon**: Uses `assets/static/images/icon.ico` (if available)
- **Bundled Files**: Templates, static files, data directory, version.json

### Manual Build (Alternative):
If you want to build manually without the script:

```bash
# 1. Build executable
python -m PyInstaller --onefile --console --name=Shakshuka --icon=assets/static/images/icon.ico --clean --add-data="assets/templates;templates" --add-data="assets/static;static" --add-data="data;data" --add-data="config/version.json;." main.py

# 2. Move executable to root
move dist\Shakshuka.exe .

# 3. Build installer (requires Inno Setup)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts\installer.iss
```

---

## 🐧 Linux Build (.deb)

### Step 1: Install fpm
```bash
# Install Ruby and build tools
sudo apt-get update
sudo apt-get install ruby-dev build-essential

# Install fpm gem
sudo gem install fpm
```

### Step 2: Verify fpm Installation
```bash
fpm --version
```

### Step 3: Run the Build Script
```bash
python3 scripts/build-deb.py
```

### What the Script Does:
1. ✅ **Reads version** from `config/version.json`
2. ✅ **Creates .deb package** using fpm
3. ✅ **Moves package** to `dist/` directory
4. ✅ **Outputs installation instructions**

### Output File:
- **`dist/shakshuka_X.X_all.deb`** - Debian package (where X.X is the version)

### Install the Package:
```bash
# Install the .deb package
sudo dpkg -i dist/shakshuka_X.X_all.deb

# Fix any dependency issues
sudo apt-get install -f
```

### Manual Build (Alternative):
If you want to build manually:

```bash
# Build .deb package directly with fpm
fpm -s python -t deb \
  --python-bin python3 \
  --python-pip pip3 \
  --python-package-name-prefix python3 \
  --no-python-dependencies \
  --name shakshuka \
  --version 8.3 \
  --description "Shakshuka application" \
  --depends python3 \
  --depends python3-pip \
  setup.py
```

---

## 🔍 Troubleshooting

### Windows Build Issues:

#### "Inno Setup 6 not found"
- **Solution**: Install Inno Setup 6 to default location or add to PATH
- **Check**: The script looks in:
  - `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
  - `C:\Program Files\Inno Setup 6\ISCC.exe`

#### "PyInstaller not found"
- **Solution**: Install PyInstaller
  ```bash
  pip install pyinstaller
  ```

#### "Module not found" errors
- **Solution**: Ensure all dependencies are installed
  ```bash
  pip install -r config/requirements.txt
  ```

#### Executable too large
- **Normal**: PyInstaller bundles Python interpreter and all dependencies
- **Size**: Typically 50-100 MB for a Flask app
- **Optimization**: Use `--exclude-module` to remove unused modules

### Linux Build Issues:

#### "fpm: command not found"
- **Solution**: Install fpm (see Prerequisites section)
  ```bash
  sudo apt-get install ruby-dev build-essential
  sudo gem install fpm
  ```

#### "dpkg: error processing package"
- **Solution**: Fix dependencies
  ```bash
  sudo apt-get install -f
  ```

#### "Package file not found"
- **Check**: Look for `.deb` files in current directory
  ```bash
  ls -la *.deb
  ```
- **Solution**: The package might be in `dist/` directory

#### "setup.py not found"
- **Solution**: Run the script from project root directory
  ```bash
  cd /path/to/shakshuka-python
  python3 scripts/build-deb.py
  ```

### Common Issues:

#### Version not updating
- **Check**: `config/version.json` exists and is readable
- **Solution**: The build script auto-increments build number, but version number requires manual edit

#### Database migration errors
- **Issue**: New database fields not in old executable
- **Solution**: Run Python source version once to migrate database, then use new executable

---

## 📝 Version Management

### Version File Location:
- **`config/version.json`** - Contains version and build number

### Version Format:
```json
{
  "version": "8.3",
  "build": "1",
  "release_date": "2025-10-20T12:00:00Z",
  "update_channel": "stable"
}
```

### Auto-Increment:
- **Windows Build**: Automatically increments build number
- **Linux Build**: Uses version from `config/version.json`

### Manual Version Update:
1. Edit `config/version.json`
2. Change `version` field (e.g., "8.3" → "8.4")
3. Reset `build` to "1" for new version
4. Run build script

### Version Display:
- **Windows**: Shows as `v8.3.1` (version.build)
- **Linux**: Shows as `8.3` (version only)

---

## 📦 Build Artifacts

### Windows:
- `Shakshuka.exe` - Standalone executable
- `Shakshuka-Setup-vX.X.exe` - Installer package
- `build_reports/BUILD_REPORT_vX.X.md` - Build report

### Linux:
- `dist/shakshuka_X.X_all.deb` - Debian package

### Cleanup:
The build script automatically cleans up:
- `build/` directory
- `dist/` directory (except final artifacts)
- `__pycache__/` directories
- `Shakshuka.spec` file

---

## 🚀 Quick Start

### Windows:
```bash
# 1. Install dependencies
pip install -r config/requirements.txt

# 2. Install Inno Setup 6 (if not already installed)

# 3. Build
python scripts/build.py

# 4. Find your files
# - Shakshuka.exe (standalone)
# - Shakshuka-Setup-vX.X.exe (installer)
```

### Linux:
```bash
# 1. Install fpm
sudo apt-get install ruby-dev build-essential
sudo gem install fpm

# 2. Install dependencies
pip3 install -r config/requirements.txt

# 3. Build
python3 scripts/build-deb.py

# 4. Install
sudo dpkg -i dist/shakshuka_X.X_all.deb
sudo apt-get install -f
```

---

## 📚 Additional Resources

- **Build Script**: `scripts/build.py` (Windows)
- **Deb Build Script**: `scripts/build-deb.py` (Linux)
- **Installer Script**: `scripts/installer.iss` (Windows)
- **Setup Script**: `setup.py` (Linux)
- **Version Config**: `config/version.json`
- **Requirements**: `config/requirements.txt`

---

## ✅ Verification Checklist

After building, verify:

### Windows:
- [ ] `Shakshuka.exe` exists and runs
- [ ] Installer package created
- [ ] Version number correct in app
- [ ] All features work correctly
- [ ] No console errors

### Linux:
- [ ] `.deb` package created in `dist/`
- [ ] Package installs without errors
- [ ] Application runs correctly
- [ ] Version number correct
- [ ] All features work correctly

---

**Last Updated**: October 2025  
**Maintained By**: Shakshuka Development Team

