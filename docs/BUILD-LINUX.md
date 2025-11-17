# Building Debian Package (.deb) for Linux

This guide explains how to create a native Debian package (.deb) for Shakshuka using fpm.

## Prerequisites

1. **Install fpm** (Effing Package Manager):
   ```bash
   sudo apt-get update
   sudo apt-get install ruby-dev build-essential
   sudo gem install fpm
   ```

2. **Install Python dependencies** (for Linux):
   ```bash
   pip3 install -r config/requirements-linux.txt
   ```

## Building the .deb Package

### Method 1: Using the Build Script (Recommended)

**Bash Script:**
```bash
chmod +x scripts/build-deb.sh
./scripts/build-deb.sh
```

**Python Script:**
```bash
python3 scripts/build-deb.py
```

### Method 2: Using fpm Directly

```bash
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

**Note:** Replace `8.3` with the version from `config/version.json` if different.

## Output

The build script will create:
- `dist/python3-shakshuka_8.3_all.deb` - The Debian package

## Installing the Package

```bash
sudo dpkg -i dist/python3-shakshuka_8.3_all.deb
sudo apt-get install -f  # Fix dependencies if needed
```

## Running the Application

After installation, run:
```bash
shakshuka
```

Or access via the console script that will be installed.

## Uninstalling

```bash
sudo apt-get remove shakshuka
```

## Troubleshooting

### fpm not found
- Make sure fpm is installed: `gem list fpm`
- Check PATH: `which fpm`

### Package build fails
- Ensure `setup.py` exists in the project root
- Check that all Python dependencies are installed
- Verify version in `config/version.json` is correct

### Installation fails
- Check dependencies: `sudo apt-get install -f`
- Verify Python 3 is installed: `python3 --version`
- Check package info: `dpkg-deb -I dist/python3-shakshuka_*.deb`

## Files Created

- `setup.py` - Python package setup file for fpm
- `config/requirements-linux.txt` - Linux dependencies (without Windows-specific packages)
- `scripts/build-deb.sh` - Bash build script
- `scripts/build-deb.py` - Python build script

## Version Management

The version is automatically read from `config/version.json`. To change the version, update the `version` field in that file.

