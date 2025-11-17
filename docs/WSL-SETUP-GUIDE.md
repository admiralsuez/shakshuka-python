# WSL Ubuntu Setup Guide

## Step 1: Install Python 3 and pip3

```bash
# Update package list
sudo apt-get update

# Install Python 3 and pip3
sudo apt-get install -y python3 python3-pip

# Verify installation
python3 --version
pip3 --version
```

## Step 2: Install Dependencies

```bash
# Install Python dependencies
pip3 install -r config/requirements-linux.txt
```

**Note:** Agar `pip3` nahi mil raha, to pehle install karein (Step 1).

## Step 3: Install fpm (for .deb package building)

```bash
# Install Ruby and build tools
sudo apt-get install -y ruby-dev build-essential

# Install fpm
sudo gem install fpm

# Verify installation
fpm --version
```

## Step 4: Build .deb Package

```bash
# Make sure you're in the project directory
cd /mnt/d/shakshuka-python

# Build package
python3 scripts/build-deb.py
```

## Troubleshooting

### pip3 command not found

```bash
# Install pip3
sudo apt-get update
sudo apt-get install -y python3-pip
```

### Permission denied

```bash
# Use sudo if needed
sudo pip3 install -r config/requirements-linux.txt
```

### Python 3 not found

```bash
# Install Python 3
sudo apt-get update
sudo apt-get install -y python3
```

## Complete Setup Commands

```bash
# 1. Update packages
sudo apt-get update

# 2. Install Python 3 and pip3
sudo apt-get install -y python3 python3-pip

# 3. Install Ruby and build tools (for fpm)
sudo apt-get install -y ruby-dev build-essential

# 4. Install fpm
sudo gem install fpm

# 5. Install Python dependencies
pip3 install -r config/requirements-linux.txt

# 6. Build .deb package
python3 scripts/build-deb.py
```

