@echo off
:: This batch file MUST be run as Administrator
:: Right-click this file and select "Run as administrator"

echo.
echo ========================================
echo  FIREWALL FIX FOR DJANGO SERVER
echo ========================================
echo.
echo This will allow mobile devices to connect.
echo.
echo MAKE SURE YOU ARE RUNNING AS ADMINISTRATOR!
echo.
echo If you see "Access is denied", you need to:
echo 1. Right-click this file
echo 2. Select "Run as administrator"
echo 3. Click Yes on the UAC prompt
echo.
pause

echo.
echo Opening firewall port 8000...
echo.

netsh advfirewall firewall add rule name="Django Dev Server" dir=in action=allow protocol=TCP localport=8000 description="Allow Django Development Server" enable=yes

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  SUCCESS! Firewall port opened.
    echo ========================================
    echo.
    echo You can now access the server from mobile devices:
    echo.
    echo   http://10.36.169.35:8000/
    echo.
    echo Make sure your mobile device is on the same WiFi network!
    echo.
) else (
    echo.
    echo ========================================
    echo  ERROR: Could not add firewall rule
    echo ========================================
    echo.
    echo You MUST run this as Administrator!
    echo.
    echo To fix:
    echo 1. Right-click this file
    echo 2. Click "Run as administrator"
    echo 3. Click Yes on the UAC prompt
    echo.
)

echo.
pause
