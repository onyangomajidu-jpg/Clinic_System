# How to Open Firewall Port - Step by Step

## The Problem
You need to run the firewall command as **Administrator** (with elevated privileges).

## Solution: Run Command Prompt as Administrator

### Method 1: Using the Batch File (EASIEST)

**Step 1: Find the batch file**
- Go to: `D:\project\clinic_system\Clinic_System\`
- Look for: `open_firewall_port.bat`

**Step 2: Right-click and Run as Administrator**
- **Right-click** on `open_firewall_port.bat`
- Select **"Run as administrator"**
- Click **Yes** on the UAC prompt
- Wait for the command to complete

**Step 3: Verify it worked**
- You should see: "Firewall rule created successfully!"
- Press any key to close

**Step 4: Test from mobile**
- Open browser on mobile
- Go to: http://10.36.169.35:8000/
- It should load now!

---

### Method 2: Manual Command (If batch file doesn't work)

**Step 1: Open Command Prompt as Administrator**

**Option A - From Start Menu:**
1. Press **Windows Key**
2. Type: `cmd`
3. Right-click "Command Prompt"
4. Select **"Run as administrator"**
5. Click **Yes** on UAC prompt

**Option B - From PowerShell:**
1. Press **Windows Key**
2. Type: `powershell`
3. Right-click "Windows PowerShell"
4. Select **"Run as administrator"**
5. Click **Yes** on UAC prompt

**Step 2: Run the firewall command**

In the Administrator Command Prompt, type:
```bash
netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Django Development Server"
```

Press **Enter**

**Step 3: Verify success**
You should see:
```
Ok.
```

**Step 4: Test from mobile**
- Open browser on mobile device
- Go to: http://10.36.169.35:8000/
- Page should load!

---

### Method 3: Using Windows Defender Firewall GUI

**Step 1: Open Windows Defender Firewall**

Press **Windows Key**, type `firewall`, open **"Windows Defender Firewall"**

**Step 2: Click Advanced Settings**
- Click **"Advanced settings"** on the left side
- Click **Yes** on UAC prompt

**Step 3: Create New Inbound Rule**
- Click **"Inbound Rules"** on the left
- Click **"New Rule"** on the right

**Step 4: Configure the Rule**

**Screen 1 - Rule Type:**
- Select: **Port**
- Click **Next**

**Screen 2 - Protocol and Ports:**
- Select: **TCP**
- Select: **Specific local ports**
- Type: `8000`
- Click **Next**

**Screen 3 - Action:**
- Select: **Allow the connection**
- Click **Next**

**Screen 4 - Profile:**
- Check all three:
  - ✅ Domain
  - ✅ Private
  - ✅ Public
- Click **Next**

**Screen 5 - Name:**
- Name: `Django Dev Server`
- Description: `Django Development Server for Mobile Access`
- Click **Finish**

**Step 5: Test from mobile**
- Go to: http://10.36.169.35:8000/
- Should work now!

---

## Verify the Firewall Rule Was Created

**After running any of the methods above, verify:**

Open Command Prompt (as Administrator) and run:
```bash
netsh advfirewall firewall show rule name="Django Dev Server"
```

You should see output showing:
- Name: Django Dev Server
- Direction: In
- Action: Allow
- Protocol: TCP
- LocalPort: 8000
- Enabled: Yes

---

## Test the Connection

**From your computer:**
```bash
Test-NetConnection -ComputerName 10.36.169.35 -Port 8000
```
Should show: `TcpTestSucceeded : True`

**From mobile device:**
- Open browser
- Go to: http://10.36.169.35:8000/
- Page should load!

---

## If Still Not Working

### Check if Firewall is Actually the Problem

**Temporarily disable firewall completely:**

Open Command Prompt as Administrator:
```bash
netsh advfirewall set allprofiles state off
```

**Test from mobile immediately:**
- Go to: http://10.36.169.35:8000/

**If it works now:** Firewall was the problem. Re-enable firewall and add the rule properly.

**If still doesn't work:** The issue is NOT firewall. Check:
1. Router client isolation
2. Mobile is on same WiFi
3. Antivirus software blocking

**Re-enable firewall after testing:**
```bash
netsh advfirewall set allprofiles state on
```

---

## Common Issues

### "Access is denied" error
**Solution:** You MUST run as Administrator. Right-click → "Run as administrator"

### "The specified rule already exists"
**Solution:** The rule was already created. Test from mobile - it should work now.

### Still can't access from mobile after rule is created

**Check router settings:**
1. Access router admin (usually http://192.168.1.1)
2. Look for "AP Isolation" or "Client Isolation"
3. Disable it
4. Save and restart router

**Check antivirus:**
- Temporarily disable antivirus firewall
- Test from mobile
- If works, add exception in antivirus

---

## Quick Reference: Important URLs

**Your Server:**
- Local: http://127.0.0.1:8000/
- Network: http://10.36.169.35:8000/

**Test Commands:**
```bash
# Test if port is listening
netstat -ano | findstr :8000

# Test if firewall rule exists
netsh advfirewall firewall show rule name="Django Dev Server"

# Test port connectivity
Test-NetConnection -ComputerName 10.36.169.35 -Port 8000

# Check firewall status
netsh advfirewall show allprofiles
```

---

## Success Checklist

After completing the steps above:

- [ ] Firewall rule "Django Dev Server" exists
- [ ] Rule shows: Action=Allow, Protocol=TCP, LocalPort=8000
- [ ] Can access http://10.36.169.35:8000/ from computer
- [ ] Can access http://10.36.169.35:8000/ from mobile device
- [ ] Page loads on mobile browser
- [ ] PWA install prompt appears

---

## Need Help?

If you're still having issues, tell me:
1. Which method did you try?
2. Did you get any error messages?
3. What exactly happens when you try to access from mobile?
4. Are both devices on the same WiFi network?

The most common issue is **not running as Administrator**. Make sure you right-click and select "Run as administrator"!
