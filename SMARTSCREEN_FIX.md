# 🛡️ Windows SmartScreen Warning - Quick Fix

## ⚡ Immediate Solution (For You & Testers)

When you see the blue "Windows protected your PC" screen:

### Step 1: Click "More info"
Look for the small **"More info"** text link in the dialog

### Step 2: Click "Run anyway"  
A **"Run anyway"** button will appear - click it

✅ **Your installer will now run!**

---

## 📊 Why This Happens

| Issue | Status |
|-------|--------|
| **Executable is unsigned** | ❌ No digital signature |
| **Publisher shows "Unknown"** | ⚠️ No code signing certificate |
| **SmartScreen blocks it** | 🛡️ Windows security feature |

---

## 🔧 For Distribution (Choose One)

### Option A: Get Code Signing Certificate (Best)
**Cost:** $200-500/year  
**Time:** 3-7 days  
**Result:** ✅ No warnings, professional distribution

**Quick Links:**
- [Sectigo](https://sectigo.com/ssl-certificates-tls/code-signing) - $200-300/yr
- [SSL.com](https://www.ssl.com/code-signing/) - $250-350/yr  
- [DigiCert](https://www.digicert.com/signing/code-signing-certificates) - $400-500/yr

👉 **See `docs/CODE_SIGNING_GUIDE.md` for complete instructions**

### Option B: Distribute as ZIP
**Cost:** $0  
**Time:** Immediate  
**Result:** ⚠️ Users must extract manually, EXE still shows warning

```bash
# Create ZIP distribution
Compress-Archive -Path Shakshuka.exe,assets,config,docs -DestinationPath Shakshuka-v3.0.0-b21.zip
```

**Include README with instructions:**
1. Extract ZIP to a folder
2. Run Shakshuka.exe
3. Click "More info" → "Run anyway" (first time only)

---

## 🚀 What I've Done

✅ **Updated installer with publisher info**
- Added company name: vibinandvanshika.in
- Added contact: support@vibinandvanshika.in  
- Added copyright and version info

✅ **Created signing script** (`scripts/sign-executable.ps1`)
- Ready to use when you get a certificate

✅ **Added signing to Inno Setup**  
- Commented out, ready to enable with certificate

✅ **Created comprehensive guide** (`docs/CODE_SIGNING_GUIDE.md`)

---

## 📋 Current Build Status

**Version:** 3.0.0-b21  
**Build Date:** October 28, 2025  
**Status:** ✅ Functional, ⚠️ Unsigned  
**Files:**
- `Shakshuka.exe` (21.54 MB) - Standalone executable
- `Shakshuka-Setup-v3.0.0-b21.exe` (23.62 MB) - Installer

**Bug Fixes Included:**
- ✅ Task creation SQL bindings
- ✅ Settings save indentation

---

## 💡 Recommendations

**For personal/internal use:**
→ Use "More info" → "Run anyway" bypass

**For friends/family (< 20 users):**
→ Provide instructions + use "Run anyway"

**For public distribution (> 50 users):**
→ **Get code signing certificate** (Essential!)

**For commercial use:**
→ **Get EV code signing certificate** (Best experience)

---

## 🆘 Need Help?

1. **Read full guide:** `docs/CODE_SIGNING_GUIDE.md`
2. **Email support:** support@vibinandvanshika.in
3. **Check certificate providers:** Sectigo, SSL.com, DigiCert

---

## ✅ Summary

**What users see now:**
```
⚠️ Windows protected your PC
Publisher: Unknown publisher
```

**After code signing:**
```
✅ Do you want to allow this app to make changes?
Publisher: vibinandvanshika.in
Verified publisher
```

**Bottom line:** For testing, use "Run anyway". For distribution, get a certificate.





