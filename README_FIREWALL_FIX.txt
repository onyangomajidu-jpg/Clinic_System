╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           HOW TO FIX FIREWALL - READ THIS CAREFULLY         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

THE PROBLEM:
-----------
Your Windows Firewall is blocking port 8000, so mobile devices
cannot connect to the Django server.

THE SOLUTION:
------------
You need to run a command as Administrator to open the firewall port.

STEP-BY-STEP INSTRUCTIONS:
--------------------------

1. OPEN FILE EXPLORER
   - Press Windows Key + E
   - Navigate to: D:\project\clinic_system\Clinic_System\

2. FIND THE FILE
   - Look for: FIX_NOW.bat
   - It should be in the Clinic_System folder

3. RIGHT-CLICK THE FILE
   - Click RIGHT mouse button on FIX_NOW.bat
   - A menu will appear

4. SELECT "RUN AS ADMINISTRATOR"
   - Click on "Run as administrator"
   - Windows will ask: "Do you want to allow this app to make changes?"
   - Click "Yes"

5. A COMMAND WINDOW WILL OPEN
   - It will show some text
   - It will say "Opening firewall port 8000..."
   - Wait for it to complete

6. YOU SHOULD SEE:
   ┌─────────────────────────────────────┐
   │  SUCCESS! Firewall port opened.     │
   │                                     │
   │  You can now access the server      │
   │  from mobile devices:               │
   │                                     │
   │    http://10.36.169.35:8000/        │
   │                                     │
   └─────────────────────────────────────┘

7. PRESS ANY KEY to close the window

8. TEST FROM MOBILE DEVICE:
   - Connect mobile to same WiFi (Abdulmajidu)
   - Open Chrome/Safari
   - Go to: http://10.36.169.35:8000/
   - It should load!

═══════════════════════════════════════════════════════════════

IF YOU GET "ACCESS IS DENIED" ERROR:
-------------------------------------

This means you did NOT run as Administrator. Do this:

1. Right-click FIX_NOW.bat again
2. This time, look for "Run as administrator" (NOT just "Run")
3. Click it
4. Click Yes on the UAC prompt
5. The command window will open with Administrator privileges

═══════════════════════════════════════════════════════════════

ALTERNATIVE: MANUAL COMMAND
-----------------------------

If the batch file still doesn't work, do this:

1. Press Windows Key
2. Type: cmd
3. Right-click "Command Prompt"
4. Select "Run as administrator"
5. Click Yes
6. Type this command EXACTLY:
   
   netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Allow Django Development Server"
   
7. Press Enter
8. You should see: "Ok."
9. Test from mobile: http://10.36.169.35:8000/

═══════════════════════════════════════════════════════════════

AFTER THE FIREWALL IS OPEN:
----------------------------

Your mobile device can now access the server!

1. Make sure mobile is on same WiFi: "Abdulmajidu"
2. Open browser on mobile
3. Go to: http://10.36.169.35:8000/
4. Page should load!
5. Tap "Install" button to install the app

═══════════════════════════════════════════════════════════════

TROUBLESHOOTING:
---------------

Q: I right-clicked but don't see "Run as administrator"
A: You need to right-click on the FILE, not inside the file

Q: It says "Access is denied"
A: You must click "Yes" on the UAC prompt that appears

Q: Still not working after firewall fix
A: Check if mobile is on same WiFi network

Q: Mobile says "Site can't be reached"
A: Try restarting the Django server after firewall fix

═══════════════════════════════════════════════════════════════

THE KEY POINT:
-------------
You MUST run the command as Administrator. This is the #1 reason
why it fails. Always right-click → "Run as administrator"

═══════════════════════════════════════════════════════════════
