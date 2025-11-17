# Fix: shakshuka Command Not Working

## Problem

After installing the package, running `shakshuka` gives:
```
ModuleNotFoundError: No module named 'main'
```

## Solution

The `setup.py` has been updated to include `main.py` as a module. Rebuild and reinstall the package.

## Steps to Fix

### 1. Uninstall Old Package

```bash
sudo apt-get remove shakshuka
```

### 2. Rebuild Package

```bash
cd /mnt/d/shakshuka-python
rm -f dist/*.deb *.deb
python3 scripts/build-deb.py
```

### 3. Reinstall Package

```bash
sudo dpkg -i dist/shakshuka_8.3_all.deb
sudo apt-get install -f
```

### 4. Test Command

```bash
shakshuka
```

## What Was Fixed

- Added `py_modules=['main']` to `setup.py`
- This ensures `main.py` is included as a Python module in the package
- The entry point `shakshuka=main:main` will now work correctly


