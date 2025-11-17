# WSL Ubuntu Par .deb Package Build Guide

## ✅ Prerequisites Check

Pehle verify karein ki sab kuch ready hai:

```bash
# WSL mein Ubuntu open karein
wsl

# Check Python
python3 --version

# Check pip
pip3 --version

# Check Ruby (fpm ke liye)
ruby --version
```

---

## 📦 Step 1: Install fpm

```bash
# Update package list
sudo apt-get update

# Install dependencies for fpm
sudo apt-get install -y ruby-dev build-essential

# Install fpm
sudo gem install fpm
```

**Verify:**
```bash
fpm --version
```

---

## 📂 Step 2: Project Directory Mein Jao

```bash
# Windows drive access karein
cd /mnt/d/shakshuka-python

# Verify files
ls -la setup.py
ls -la config/requirements-linux.txt
ls -la scripts/build-deb.py
```

---

## 🔧 Step 3: Linux Dependencies Install Karein

```bash
# Install Python dependencies (Linux ke liye)
pip3 install -r config/requirements-linux.txt
```

**Note:** Agar `pip3` nahi hai, to install karein:
```bash
sudo apt-get install -y python3-pip
```

---

## 🏗️ Step 4: Build .deb Package

### Method 1: Python Script (Recommended)

```bash
python3 scripts/build-deb.py
```

### Method 2: Direct fpm Command

```bash
# Version check karein
VERSION=$(python3 -c "import json; print(json.load(open('config/version.json'))['version'])")
echo "Version: $VERSION"

# Build package
fpm -s python -t deb \
    --python-bin python3 \
    --python-pip pip3 \
    --python-package-name-prefix python3 \
    --no-python-dependencies \
    --name shakshuka \
    --version "$VERSION" \
    --description "Shakshuka application" \
    --depends python3 \
    --depends python3-pip \
    setup.py
```

---

## 📁 Step 5: Check Output

```bash
# Package check karein
ls -lh dist/*.deb

# Package info dekhne ke liye
dpkg-deb -I dist/python3-shakshuka_*.deb
```

**Expected Output:**
```
dist/python3-shakshuka_8.3_all.deb
```

---

## 🧪 Step 6: Test Install (Optional)

```bash
# Package install karein (test ke liye)
sudo dpkg -i dist/python3-shakshuka_*.deb

# Dependencies fix karein (agar zarurat ho)
sudo apt-get install -f

# Test run
shakshuka

# Uninstall (agar test kiya)
sudo apt-get remove shakshuka
```

---

## 🔍 Troubleshooting

### fpm install nahi ho raha?

```bash
# Ruby install karein
sudo apt-get install -y ruby-full

# Phir fpm install karein
sudo gem install fpm
```

### Python dependencies install nahi ho rahi?

```bash
# pip3 install karein
sudo apt-get install -y python3-pip python3-dev

# Phir dependencies install karein
pip3 install -r config/requirements-linux.txt
```

### Permission errors?

```bash
# Sudo use karein
sudo python3 scripts/build-deb.py
```

### Version error?

```bash
# Manually version set karein
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

## 📋 Complete Command Sequence

```bash
# 1. WSL open karein
wsl

# 2. Project directory
cd /mnt/d/shakshuka-python

# 3. Install fpm (pehli baar)
sudo apt-get update
sudo apt-get install -y ruby-dev build-essential
sudo gem install fpm

# 4. Install Python dependencies
pip3 install -r config/requirements-linux.txt

# 5. Build package
python3 scripts/build-deb.py

# 6. Check output
ls -lh dist/*.deb
```

---

## ✅ Success Checklist

- [ ] fpm installed
- [ ] Python dependencies installed
- [ ] setup.py exists
- [ ] .deb package created in `dist/` folder
- [ ] Package size reasonable (check with `ls -lh`)

---

## 🎯 Next Steps

1. **Package ready:** `dist/python3-shakshuka_8.3_all.deb`
2. **Share karein:** Ye file kisi bhi Ubuntu/Debian system par install kar sakte hain
3. **Install:** `sudo dpkg -i dist/python3-shakshuka_*.deb`

---

## 💡 Tips

- **First time:** fpm install karna hoga (5-10 minutes)
- **Next builds:** Sirf `python3 scripts/build-deb.py` run karein
- **Version change:** `config/version.json` mein version update karein
- **Package location:** Windows mein `D:\shakshuka-python\dist\` folder mein milega

