# Code Signing Guide for Shakshuka

## Problem: Windows SmartScreen Warning

When users try to install Shakshuka, they see:
```
Windows protected your PC
Microsoft Defender SmartScreen prevented an unrecognized app from starting.
App: Shakshuka-Setup-v3.0.0-b21.exe
Publisher: Unknown publisher
```

This happens because the executable is **not digitally signed**.

---

## Solutions

### 🔧 Option 1: For Testing/Development (Immediate)

**For you (the developer):**
1. Right-click the installer → Properties
2. Check "Unblock" at the bottom → Apply → OK
3. Run the installer

**For users installing your app:**
1. Click **"More info"** in the SmartScreen dialog
2. Click **"Run anyway"**

**Note:** This is only suitable for testing and trusted users.

---

### 🏆 Option 2: Code Signing Certificate (Recommended)

This is the **proper solution** for distributing to end users.

#### Step 1: Purchase a Code Signing Certificate

| Provider | Price/Year | Delivery | Type |
|----------|-----------|----------|------|
| **Sectigo** | $200-$300 | 1-3 days | Standard |
| **SSL.com** | $250-$350 | 1-5 days | EV or Standard |
| **DigiCert** | $400-$500 | 1-3 days | EV or Standard |
| **GlobalSign** | $300-$450 | 1-5 days | Standard |

**Recommendation:** Start with **Sectigo** or **SSL.com** for affordability.

**EV vs Standard:**
- **EV (Extended Validation):** Instant trust, no SmartScreen warning (~$400+)
- **Standard:** Requires reputation building, cheaper (~$200+)

#### Step 2: Verify Your Identity

You'll need to provide:
- ✅ Business registration documents (or personal ID for individual)
- ✅ Phone number verification
- ✅ Email verification
- ✅ Physical address verification
- ✅ DUNS number (for EV certificates)

#### Step 3: Receive Certificate

You'll receive:
- `.pfx` or `.p12` file (certificate + private key)
- Password to unlock the certificate

**Store securely!** Never commit to Git or share publicly.

#### Step 4: Sign Your Executables

**Using the provided script:**

```powershell
# Sign the main executable
.\scripts\sign-executable.ps1 `
    -CertificatePath "C:\path\to\your\certificate.pfx" `
    -CertificatePassword "YourPassword" `
    -ExecutablePath ".\Shakshuka.exe"

# Sign the installer
.\scripts\sign-executable.ps1 `
    -CertificatePath "C:\path\to\your\certificate.pfx" `
    -CertificatePassword "YourPassword" `
    -ExecutablePath ".\Shakshuka-Setup-v3.0.0-b21.exe"
```

**Or manually with signtool:**

```powershell
# Install Windows SDK if you don't have signtool
# Download from: https://developer.microsoft.com/windows/downloads/windows-sdk/

# Sign the executable
signtool sign /f "certificate.pfx" /p "password" /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 "Shakshuka.exe"

# Verify signature
signtool verify /pa "Shakshuka.exe"
```

#### Step 5: Integrate into Build Process

Update `scripts/build.py` to automatically sign after building:

```python
# Add at the end of build_executable() function
def sign_executable(exe_path, cert_path, cert_password):
    """Sign the executable with code signing certificate"""
    if not os.path.exists(cert_path):
        print("Warning: Certificate not found, skipping signing")
        return
    
    print("Signing executable...")
    result = subprocess.run([
        'powershell.exe',
        '-ExecutionPolicy', 'Bypass',
        '-File', 'scripts/sign-executable.ps1',
        '-CertificatePath', cert_path,
        '-CertificatePassword', cert_password,
        '-ExecutablePath', exe_path
    ])
    
    if result.returncode == 0:
        print("✓ Executable signed successfully")
    else:
        print("✗ Failed to sign executable")

# Usage (add to build script)
cert_path = os.getenv('CODE_SIGNING_CERT_PATH')
cert_password = os.getenv('CODE_SIGNING_CERT_PASSWORD')
if cert_path and cert_password:
    sign_executable('Shakshuka.exe', cert_path, cert_password)
```

#### Step 6: Set Environment Variables

Create a `.env` file (DON'T commit to Git):

```bash
CODE_SIGNING_CERT_PATH=C:\secure\location\certificate.pfx
CODE_SIGNING_CERT_PASSWORD=YourSecurePassword
```

Add to `.gitignore`:
```
.env
*.pfx
*.p12
```

---

### 🔐 Option 3: Self-Signed Certificate (For Internal Testing Only)

**Warning:** Self-signed certificates don't remove SmartScreen warnings but allow installation in controlled environments.

```powershell
# Create self-signed certificate
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=vibinandvanshika.in, O=Shakshuka, C=IN" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(5)

# Export to PFX
$certPassword = ConvertTo-SecureString -String "YourPassword" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath "shakshuka-selfsigned.pfx" -Password $certPassword

# Sign executable
signtool sign /f "shakshuka-selfsigned.pfx" /p "YourPassword" /fd SHA256 "Shakshuka.exe"
```

**Note:** Users will still see warnings unless they manually trust your certificate.

---

## Building SmartScreen Reputation

Even with a **Standard** certificate, you may see SmartScreen warnings initially. To build reputation:

1. ✅ **Sign all executables** - Consistency is key
2. ✅ **Use the same certificate** - Don't switch certificates
3. ✅ **Accumulate downloads** - 100-1000+ unique users needed
4. ✅ **No malware reports** - Keep your software clean
5. ✅ **Time** - Can take 2-12 weeks to build reputation

**EV certificates** skip this process and provide instant trust.

---

## Best Practices

### Security
- ✅ Store certificates in secure, encrypted location
- ✅ Never commit certificates to version control
- ✅ Use environment variables for passwords
- ✅ Restrict access to certificate files
- ✅ Use hardware security tokens for EV certificates

### Build Process
- ✅ Sign all executables (EXE, DLL, MSI)
- ✅ Use timestamp servers (allows signature to remain valid after cert expires)
- ✅ Verify signatures after signing
- ✅ Automate signing in CI/CD pipeline

### Distribution
- ✅ Provide SHA-256 checksums alongside downloads
- ✅ Distribute via HTTPS only
- ✅ Keep your contact information updated
- ✅ Respond to user security concerns

---

## Cost-Benefit Analysis

| Option | Cost | User Experience | Best For |
|--------|------|-----------------|----------|
| No signing | $0 | ❌ Poor (SmartScreen warning) | Internal testing |
| Self-signed | $0 | ❌ Poor (Still shows warning) | Controlled environments |
| Standard cert | $200-300/yr | ⚠️ Warning initially, then good | Small distribution |
| EV cert | $400-500/yr | ✅ Excellent (Instant trust) | Public distribution |

**Recommendation:** If distributing to more than 50 users, get an **EV certificate**. Otherwise, start with a **Standard certificate** and build reputation.

---

## Alternative: Distribute as ZIP (No Signing Needed)

If code signing is not feasible right now:

1. Distribute as ZIP file instead of installer
2. Users extract and run Shakshuka.exe
3. Provide clear instructions in README
4. Include SHA-256 checksum for verification

**Pros:**
- No SmartScreen warning on ZIP file
- No certificate cost

**Cons:**
- Less professional
- Manual installation process
- No automatic updates
- Still shows warning when running EXE

---

## Current Status

✅ **Installer includes publisher information**  
⚠️ **Not digitally signed** - Shows SmartScreen warning  
📋 **Next step:** Acquire code signing certificate

---

## Quick Links

- [Windows SDK (for signtool)](https://developer.microsoft.com/windows/downloads/windows-sdk/)
- [Sectigo Code Signing](https://sectigo.com/ssl-certificates-tls/code-signing)
- [SSL.com Code Signing](https://www.ssl.com/code-signing/)
- [DigiCert Code Signing](https://www.digicert.com/signing/code-signing-certificates)
- [Microsoft Authenticode](https://docs.microsoft.com/windows/win32/seccrypto/cryptography-tools)

---

## Support

For issues with code signing:
1. Check certificate is valid and not expired
2. Verify signtool is installed (Windows SDK)
3. Ensure certificate password is correct
4. Use timestamp server to avoid expiration issues
5. Contact certificate provider if signature fails validation

For questions, contact: support@vibinandvanshika.in





