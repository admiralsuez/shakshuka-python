# Shakshuka Troubleshooting Guide

## Common Issues and Solutions

### HTTP 500 Internal Server Error

**Symptoms:**
- Browser shows "Load tasks attempt 1 failed: Error: HTTP 500: INTERNAL SERVER ERROR"
- JSON parsing errors
- Application won't load tasks or settings

**Solutions:**

#### 1. Missing Dependencies (Most Common)
**Problem:** The executable was built without all required dependencies.

**Solution:** Download the latest version from the distribution package that includes all dependencies bundled.

#### 2. Data Directory Issues
**Problem:** The application can't access or create the data directory.

**Solutions:**
- Run as Administrator
- Check folder permissions
- Ensure the application folder is not read-only
- Try running from a different location (e.g., Desktop instead of Program Files)

#### 3. Port Already in Use
**Problem:** Port 8989 is already being used by another application.

**Solutions:**
```cmd
# Check what's using port 8989
netstat -ano | findstr :8989

# Kill the process (replace PID with actual process ID)
taskkill /F /PID <PID>

# Or kill all Shakshuka processes
taskkill /F /IM Shakshuka.exe
```

#### 4. Antivirus Interference
**Problem:** Antivirus software blocking the application.

**Solutions:**
- Add Shakshuka.exe to antivirus exclusions
- Temporarily disable real-time protection during installation
- Run as Administrator

### Content Security Policy Errors

**Symptoms:**
- "Content-Security-Policy: The page's settings blocked the loading of a resource"
- Font Awesome icons not displaying
- External resources blocked

**Solutions:**
- This is usually cosmetic and doesn't affect functionality
- The application includes a CSP header that may block some external resources
- All core functionality should work despite these warnings

### Browser Issues

**Symptoms:**
- Application doesn't open in browser automatically
- Browser shows connection errors

**Solutions:**
1. **Manual Navigation:** Open browser and go to `http://127.0.0.1:8989`
2. **Check Default Browser:** Ensure you have a default browser set
3. **Firewall:** Check Windows Firewall settings
4. **Different Browser:** Try a different browser (Chrome, Firefox, Edge)

### Installation Issues

**Symptoms:**
- PowerShell script won't run
- "Execution policy" errors

**Solutions:**
```powershell
# Set execution policy (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or for all users
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

### Data Loss Prevention

**Important:** Always backup your data before troubleshooting!

**Backup Location:** `data/` folder in the application directory

**Manual Backup:**
1. Copy the entire `data/` folder
2. Store it in a safe location
3. Restore by copying back if needed

### Performance Issues

**Symptoms:**
- Slow loading
- High memory usage
- Application freezes

**Solutions:**
1. **Close Other Applications:** Free up system resources
2. **Restart Application:** Stop and restart Shakshuka
3. **Check Data Size:** Large task lists may slow down the application
4. **Clear Browser Cache:** Clear browser cache and cookies

### Network Issues

**Symptoms:**
- Can't access from other devices on network
- Connection refused errors

**Solutions:**
1. **Firewall:** Add exception for port 8989 in Windows Firewall
2. **Network Access:** The application runs on localhost (127.0.0.1) by default
3. **Port Forwarding:** If accessing remotely, configure port forwarding

### Debugging Steps

If you're still experiencing issues:

1. **Check Console Output:**
   - Run `Shakshuka.exe` from command prompt to see error messages
   - Look for specific error details

2. **Check Logs:**
   - Look for log files in the application directory
   - Check Windows Event Viewer for system errors

3. **Test Basic Functionality:**
   - Can you access `http://127.0.0.1:8989` in browser?
   - Does the page load (even if tasks don't)?
   - Are there any JavaScript errors in browser console?

4. **System Requirements:**
   - Windows 10/11 (64-bit)
   - At least 4GB RAM
   - 100MB free disk space
   - Administrator privileges for installation

### Getting Help

If none of these solutions work:

1. **Collect Information:**
   - Windows version
   - Error messages (screenshot or copy text)
   - Steps to reproduce the issue
   - Console output from running Shakshuka.exe

2. **Check for Updates:**
   - Download the latest version
   - Ensure you have the most recent build

3. **Clean Installation:**
   - Uninstall completely
   - Delete all application folders
   - Restart computer
   - Install fresh copy

### Emergency Recovery

If the application is completely broken:

1. **Stop All Processes:**
   ```cmd
   taskkill /F /IM Shakshuka.exe
   ```

2. **Backup Data:**
   ```cmd
   copy "data" "data_backup"
   ```

3. **Clean Installation:**
   - Delete application folder
   - Download fresh copy
   - Install as Administrator
   - Restore data from backup

---

**Remember:** Always backup your data before making any changes!


