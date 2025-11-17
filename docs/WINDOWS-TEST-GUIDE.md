# Windows Testing & Build Guide

## 🪟 Windows Par Testing (Development Mode)

### Step 1: Dependencies Install Karein

```powershell
# PowerShell mein
python -m pip install -r config/requirements.txt
```

### Step 2: App Test Karein

```powershell
# App start karein
python main.py
```

**Expected Output:**
```
🍳 Shakshuka Task Manager
============================================================
Server: http://127.0.0.1:8989
Status: Starting...
============================================================

💡 Tips:
  • Access the app in your browser
  • System tray icon for quick access
  • Press Ctrl+C to stop the server
```

### Step 3: Browser Mein Open Karein

App automatically browser mein open hoga, ya manually:
- **URL:** http://127.0.0.1:8989
- Browser mein yeh URL open karein

### Step 4: Stop Karna

- **Ctrl+C** press karein PowerShell mein
- Ya PowerShell window close karein

---

## 🐧 Linux .deb Package Build (Windows Se)

Windows par directly .deb package **nahi** ban sakta. Aapko Linux chahiye.

### Option 1: WSL (Windows Subsystem for Linux) - **Recommended** ✅

#### Install WSL:

```powershell
# PowerShell as Administrator
wsl --install
```

#### WSL Mein Build:

```bash
# WSL open karein
wsl

# Project directory mein jao
cd /mnt/d/shakshuka-python

# Linux dependencies install karein
pip3 install -r config/requirements-linux.txt

# fpm install karein
sudo apt-get update
sudo apt-get install ruby-dev build-essential
sudo gem install fpm

# .deb package build karein
python3 scripts/build-deb.py
```

**Output:** `dist/python3-shakshuka_8.3_all.deb`

---

### Option 2: Linux VM (VirtualBox/VMware)

1. **VirtualBox install karein** (free)
2. **Ubuntu 22.04 LTS** download karein
3. **VM create karein** aur Ubuntu install karein
4. **Files copy karein** (shared folder ya network)
5. **Build karein** same commands se

---

### Option 3: Cloud Linux Server

- **AWS EC2**, **DigitalOcean**, **Linode** use karein
- Remote Linux machine par build karein
- `.deb` file download karein

---

## 📋 Quick Reference

### Windows Commands

| Task | Command |
|------|---------|
| **Install dependencies** | `python -m pip install -r config/requirements.txt` |
| **Run app** | `python main.py` |
| **Check Python** | `python --version` |
| **Check pip** | `python -m pip --version` |

### Linux Build Commands (WSL/VM)

| Task | Command |
|------|---------|
| **Install fpm** | `sudo gem install fpm` |
| **Install dependencies** | `pip3 install -r config/requirements-linux.txt` |
| **Build .deb** | `python3 scripts/build-deb.py` |
| **Install package** | `sudo dpkg -i dist/python3-shakshuka_*.deb` |

---

## 🔍 Troubleshooting

### Windows Par App Start Nahi Ho Raha?

1. **Check dependencies:**
   ```powershell
   python -m pip list
   ```

2. **Port already in use?**
   - Check: `netstat -ano | findstr :8989`
   - Kill process ya port change karein

3. **Import errors?**
   ```powershell
   python -m pip install -r config/requirements.txt --force-reinstall
   ```

### WSL Install Nahi Ho Raha?

1. **Windows 10/11 required**
2. **BIOS mein Virtualization enable** karein
3. **Restart** karein after WSL install

---

## ✅ Summary

### Windows Par (Abhi):
- ✅ **Test app:** `python main.py`
- ✅ **Development:** Full features available
- ❌ **Build .deb:** Not possible (Linux needed)

### Linux Par (WSL/VM):
- ✅ **Build .deb:** `python3 scripts/build-deb.py`
- ✅ **Install:** `sudo dpkg -i dist/python3-shakshuka_*.deb`
- ✅ **Run:** `shakshuka`

---

## 🚀 Next Steps

1. **Windows par app test karein** (development)
2. **WSL install karein** (agar .deb build karna hai)
3. **Linux par build karein** (WSL/VM/Cloud)

**Recommendation:** Pehle Windows par app test karein, phir WSL install karke .deb build karein.



