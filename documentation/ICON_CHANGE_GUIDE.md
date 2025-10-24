# 🎨 How to Change the Shakshuka Icon

## 📍 Current Icon References

The teal leaf icon (`icon.ico`) is used in **7 places**:

### 1. **Browser Favicon**
- **File**: `assets/static/images/icon.ico`
- **Referenced in**: `src/app.py` (line 955-978)
- **Shows**: Browser tab icon

### 2. **Executable Icon**
- **File**: `assets/static/images/icon.ico`
- **Referenced in**: `scripts/build.py` (line 278-283)
- **Shows**: Shakshuka.exe file icon

### 3. **Installer Setup Icon**
- **File**: `assets/static/images/icon.ico`
- **Referenced in**: `scripts/installer.iss` (line 27)
- **Shows**: Setup wizard icon

### 4. **Start Menu Shortcuts** (5 places)
- **Referenced in**: `scripts/installer.iss` (lines 69-75)
- **Shows**: 
  - Start Shakshuka shortcut icon
  - Start (Silent) shortcut icon
  - Start (Verbose) shortcut icon
  - Stop Shakshuka shortcut icon
  - Desktop shortcut icon

### 5. **Installation Shortcuts**
- **Referenced in**: `tools/install.ps1` (lines 79, 92)
- **Shows**: Desktop and Start Menu shortcuts

### 6. **HTML Template** ⚠️ **MISSING!**
- **Should be in**: `assets/templates/index.html`
- **Currently**: No `<link rel="icon">` tag found!

---

## 🔧 How to Change the Icon

### Step 1: Prepare Your New Icon

#### Requirements:
- **Format**: `.ico` file (Windows icon format)
- **Size**: Multiple sizes in one file (recommended: 16x16, 32x32, 48x48, 256x256)
- **Tool**: Use [favicon.io](https://favicon.io/) or similar to create

#### From Image/PNG:
```bash
# Online tools (recommended):
# - https://favicon.io/favicon-converter/
# - https://convertio.co/png-ico/

# Or use ImageMagick:
magick convert your-icon.png -define icon:auto-resize=256,128,96,64,48,32,16 icon.ico
```

### Step 2: Replace the Icon File

```powershell
# Backup old icon
Copy-Item "assets\static\images\icon.ico" "assets\static\images\icon_backup.ico"

# Copy your new icon
Copy-Item "path\to\your\new-icon.ico" "assets\static\images\icon.ico"
```

### Step 3: Add Favicon to HTML (IMPORTANT!)

Add this to `assets/templates/index.html` in the `<head>` section (after line 6):

```html
<!-- Favicon -->
<link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='images/icon.ico') }}">
<link rel="shortcut icon" type="image/x-icon" href="{{ url_for('static', filename='images/icon.ico') }}">
```

Full context:
```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shakshuka - Modern Task Manager</title>
    
    <!-- Favicon -->
    <link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='images/icon.ico') }}">
    <link rel="shortcut icon" type="image/x-icon" href="{{ url_for('static', filename='images/icon.ico') }}">
    
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=1.0.1">
    ...
</head>
```

### Step 4: Rebuild the Application

```powershell
# Navigate to project
cd C:\Users\vibin\OneDrive\Desktop\shakshuka-python-final3

# Build new version
python scripts/build.py
```

This will:
- ✅ Include new icon in Shakshuka.exe
- ✅ Include new icon in installer
- ✅ Update all shortcuts with new icon

### Step 5: Clear Browser Cache

After rebuilding, clear your browser cache to see the new favicon:

**Chrome/Edge:**
- Press `Ctrl + Shift + Delete`
- Select "Cached images and files"
- Click "Clear data"

**Or force refresh:**
- `Ctrl + F5` on the Shakshuka page

---

## 📋 Files to Modify (Summary)

| File | What to Change | Line |
|------|---------------|------|
| `assets/static/images/icon.ico` | Replace with your new icon file | - |
| `assets/templates/index.html` | **ADD** favicon link tags | After line 6 |
| *(Optional)* `scripts/build.py` | Update icon path if moving location | 280 |
| *(Optional)* `scripts/installer.iss` | Update icon path if moving location | 27, 69-75 |

---

## 🎨 Icon Design Tips

### Recommended Sizes:
- **16x16** - Browser tab, file explorer
- **32x32** - Standard desktop icon
- **48x48** - Large icons view
- **256x256** - High-resolution displays

### Design Guidelines:
1. **Simple & Clear** - Works well at small sizes
2. **High Contrast** - Easy to see against any background
3. **Recognizable** - Unique and memorable
4. **Professional** - Matches your brand

### Current Icon:
- **Style**: Teal/turquoise leaf
- **Background**: Rounded square
- **Colors**: Teal (#4DB6AC or similar)

---

## 🧪 Testing Checklist

After changing the icon, verify it appears correctly:

- [ ] **Browser tab** - Favicon shows in tab
- [ ] **File explorer** - Shakshuka.exe shows new icon
- [ ] **Desktop shortcut** - Shortcut has new icon
- [ ] **Start menu** - All shortcuts have new icon
- [ ] **Installer** - Setup wizard shows new icon
- [ ] **System tray** - Tray icon shows new icon (if using)
- [ ] **Task manager** - Process shows new icon

---

## 🚀 Quick Change Script

Save this as `change-icon.ps1`:

```powershell
# Quick Icon Change Script
param(
    [Parameter(Mandatory=$true)]
    [string]$NewIconPath
)

Write-Host "`nShakshuka Icon Changer" -ForegroundColor Cyan
Write-Host "=====================`n"

# Validate new icon exists
if (-not (Test-Path $NewIconPath)) {
    Write-Host "ERROR: Icon file not found: $NewIconPath" -ForegroundColor Red
    exit 1
}

# Backup old icon
$backupPath = "assets\static\images\icon_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').ico"
Copy-Item "assets\static\images\icon.ico" $backupPath
Write-Host "✓ Backed up old icon to: $backupPath" -ForegroundColor Green

# Copy new icon
Copy-Item $NewIconPath "assets\static\images\icon.ico" -Force
Write-Host "✓ New icon copied" -ForegroundColor Green

# Add favicon to HTML if missing
$htmlPath = "assets\templates\index.html"
$htmlContent = Get-Content $htmlPath -Raw
if ($htmlContent -notlike "*favicon*") {
    Write-Host "`n⚠ Favicon link missing in HTML!" -ForegroundColor Yellow
    Write-Host "Please add this to index.html <head> section:" -ForegroundColor Yellow
    Write-Host '<link rel="icon" type="image/x-icon" href="{{ url_for(''static'', filename=''images/icon.ico'') }}">'
}

Write-Host "`n✓ Icon changed successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Add favicon link to HTML (if not already done)"
Write-Host "2. Run: python scripts\build.py"
Write-Host "3. Clear browser cache (Ctrl+Shift+Delete)"
Write-Host "4. Test all icon locations`n"
```

**Usage:**
```powershell
.\change-icon.ps1 -NewIconPath "C:\path\to\your\new-icon.ico"
```

---

## ❓ Troubleshooting

### Icon not showing in browser?
- Clear browser cache (Ctrl + Shift + Delete)
- Hard refresh (Ctrl + F5)
- Check if favicon link added to HTML
- Check browser console for 404 errors

### Icon not showing in executable?
- Rebuild the application: `python scripts/build.py`
- Check icon file exists at build time
- Icon must be `.ico` format

### Old icon still showing in shortcuts?
- Refresh icon cache: 
  ```cmd
  ie4uinit.exe -show
  ```
- Or restart Windows Explorer
- Or reinstall using new installer

---

## 📚 Related Files

All files that reference the icon:
1. `assets/static/images/icon.ico` - The actual icon file
2. `src/app.py` - Favicon route (lines 955-978)
3. `assets/templates/index.html` - HTML favicon link (needs adding!)
4. `scripts/build.py` - Icon for executable (line 280)
5. `scripts/installer.iss` - Installer icon (lines 27, 69-75)
6. `tools/install.ps1` - Shortcut icons (lines 79, 92)
7. `scripts/create-professional-installer.py` - Shortcut icons (lines 86, 92, 98, 108)

---

**Ready to change your icon?** Follow the steps above and rebuild! 🎨



