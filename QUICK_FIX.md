# Quick Fix: Mobile Device Can't Access Server

## Problem
Mobile device shows "Site can't be reached" when accessing http://10.36.169.35:8000/

## Solution Options (Try in order)

### Option 1: Disable Firewall Temporarily (Fastest Test)

**Step 1:** Right-click `disable_firewall.bat` → **Run as administrator**

**Step 2:** Test from mobile device: http://10.36.169.35:8000/

**Step 3:** After testing, re-enable firewall: Right-click `enable_firewall.bat` → **Run as administrator**

**If this works:** The issue is Windows Firewall. You need to add a permanent rule (see Option 2).

---

### Option 2: Add Firewall Rule (Permanent Fix)

**Run PowerShell as Administrator** and execute:

```powershell
netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Django Development Server for Mobile Access"
```

Then test from mobile device.

---

### Option 3: Use ngrok (Bypasses All Firewall Issues)

**This is the EASIEST and MOST RELIABLE solution!**

**Step 1:** Download ngrok from https://ngrok.com/download

**Step 2:** Sign up for free account at https://dashboard.ngrok.com/signup

**Step 3:** Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken

**Step 4:** Run in Command Prompt (NOT PowerShell):
```bash
ngrok http 8000
```

**Step 5:** ngrok will show you a URL like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

**Step 6:** Use that HTTPS URL on your mobile device:
```
https://abc123.ngrok.io
```

**Benefits:**
- ✅ No firewall issues
- ✅ Works from anywhere (not just local WiFi)
- ✅ HTTPS included (required for PWA)
- ✅ No network configuration needed
- ✅ Free tier available

---

### Option 4: Check Router Settings

If Options 1-3 don't work, your router might have **Client Isolation** enabled.

**Step 1:** Access your router admin panel
- Usually: http://192.168.1.1 or http://192.168.0.1
- Check router manual for admin URL

**Step 2:** Look for these settings:
- **Wireless Settings** → **AP Isolation** → Disable
- **Security Settings** → **Client Isolation** → Disable
- **Advanced** → **Multi-AP Isolation** → Disable

**Step 3:** Save settings and restart router

**Step 4:** Test again from mobile

---

### Option 5: Check Antivirus/Firewall Software

Third-party antivirus might be blocking port 8000.

**Step 1:** Check if you have antivirus software:
- Norton, McAfee, Kaspersky, Avast, etc.

**Step 2:** Open antivirus settings

**Step 3:** Look for **Firewall** or **Network Protection**

**Step 4:** Add exception for:
- Python.exe (usually in `.venv\Scripts\python.exe`)
- Port 8000

**Step 5:** Save and test

---

### Option 6: Use Different Port

Sometimes port 8000 might be blocked by ISP or router.

**Step 1:** Stop current server (Ctrl+C in terminal)

**Step 2:** Start on different port:
```bash
python manage.py runserver 0.0.0.0:8080
```

**Step 3:** Update firewall rule:
```powershell
netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8080 description="Django Dev Server"
```

**Step 4:** Access from mobile: http://10.36.169.35:8080/

---

## Recommended Solution

### For Quick Testing: Use ngrok (Option 3)

This bypasses ALL network issues:

```bash
# Install ngrok (download from https://ngrok.com/download)
# Run:
ngrok http 8000

# Use the HTTPS URL it provides on your mobile device
```

### For Permanent Local Access: Fix Firewall (Option 2)

Run this in PowerShell as Administrator:
```powershell
netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Django Development Server"
```

---

## Diagnostic Commands

Run these to check current status:

```powershell
# Check if server is listening
netstat -ano | findstr :8000

# Check firewall rules
netsh advfirewall firewall show rule name="Django Dev Server"

# Test port from same machine
Test-NetConnection -ComputerName 10.36.169.35 -Port 8000

# Check network profile
Get-NetConnectionProfile -InterfaceAlias WiFi
```

---

## Still Not Working?

If none of the above work, please provide:

1. **Router model** (check bottom of router)
2. **Antivirus software** you're using (if any)
3. **Mobile device** (Android/iOS, model)
4. **Error message** on mobile (exact text)
5. **Output of this command:**
   ```powershell
   netsh advfirewall show allprofiles
   ```

---

## Quick Checklist

- [ ] Server running (checked - YES)
- [ ] Port 8000 listening (checked - YES)
- [ ] Can access from localhost (checked - YES)
- [ ] Can ping 10.36.169.35 (checked - YES)
- [ ] Firewall allows port 8000 (NEEDS TO BE FIXED)
- [ ] Mobile on same WiFi (verify)
- [ ] Router client isolation disabled (check)

**Most likely issue:** Windows Firewall blocking port 8000. Use Option 1 or 2 to fix.
