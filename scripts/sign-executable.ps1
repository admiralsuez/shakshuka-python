# Code Signing Script for Shakshuka
# This script signs the executable with a code signing certificate

param(
    [Parameter(Mandatory=$true)]
    [string]$CertificatePath,
    
    [Parameter(Mandatory=$false)]
    [string]$CertificatePassword = "",
    
    [Parameter(Mandatory=$true)]
    [string]$ExecutablePath,
    
    [Parameter(Mandatory=$false)]
    [string]$TimestampServer = "http://timestamp.digicert.com"
)

Write-Host "======================================"
Write-Host "   Shakshuka Code Signing Script"
Write-Host "======================================"
Write-Host ""

# Check if signtool exists
$signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
if (-not (Test-Path $signtool)) {
    # Try to find signtool in common locations
    $possiblePaths = @(
        "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
        "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe"
    )
    
    foreach ($path in $possiblePaths) {
        $found = Get-ChildItem $path -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $signtool = $found.FullName
            break
        }
    }
}

if (-not (Test-Path $signtool)) {
    Write-Host "ERROR: signtool.exe not found!" -ForegroundColor Red
    Write-Host "Please install Windows SDK from: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using signtool: $signtool"
Write-Host ""

# Check if executable exists
if (-not (Test-Path $ExecutablePath)) {
    Write-Host "ERROR: Executable not found: $ExecutablePath" -ForegroundColor Red
    exit 1
}

# Check if certificate exists
if (-not (Test-Path $CertificatePath)) {
    Write-Host "ERROR: Certificate not found: $CertificatePath" -ForegroundColor Red
    exit 1
}

Write-Host "Signing executable: $ExecutablePath"
Write-Host "Using certificate: $CertificatePath"
Write-Host ""

# Build signtool command
$signArgs = @(
    "sign",
    "/f", "`"$CertificatePath`"",
    "/tr", $TimestampServer,
    "/td", "SHA256",
    "/fd", "SHA256"
)

# Add password if provided
if ($CertificatePassword -ne "") {
    $signArgs += @("/p", $CertificatePassword)
}

# Add description and URL
$signArgs += @(
    "/d", "Shakshuka Task Manager",
    "/du", "https://vibinandvanshika.in"
)

# Add executable path
$signArgs += "`"$ExecutablePath`""

# Execute signing
Write-Host "Running signtool..." -ForegroundColor Cyan
$signArgsString = $signArgs -join " "
Write-Host "Command: $signtool $signArgsString" -ForegroundColor Gray
Write-Host ""

try {
    & $signtool $signArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Successfully signed: $ExecutablePath" -ForegroundColor Green
        Write-Host ""
        
        # Verify signature
        Write-Host "Verifying signature..."
        & $signtool verify /pa "`"$ExecutablePath`""
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✓ Signature verified successfully!" -ForegroundColor Green
        }
    } else {
        Write-Host ""
        Write-Host "✗ Failed to sign executable" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "✗ Error during signing: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "======================================"
Write-Host "   Signing Complete"
Write-Host "======================================"





