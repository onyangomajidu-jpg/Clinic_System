@echo off
echo ================================================
echo Opening Windows Firewall Port 8000 for Django
echo ================================================
echo.
echo This will allow mobile devices to access the server.
echo.
echo Please run this file as Administrator!
echo.
pause

netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Django Development Server"

echo.
echo ================================================
echo Firewall rule created successfully!
echo ================================================
echo.
echo You can now access the server from mobile devices:
echo http://10.36.169.35:8000/
echo.
echo Make sure your mobile device is on the same WiFi network!
echo.
pause
