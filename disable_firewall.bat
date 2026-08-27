@echo off
echo ================================================
echo Temporarily Disabling Windows Firewall
echo ================================================
echo.
echo This will turn off firewall for ALL networks.
echo You can re-enable it after testing.
echo.
echo Press any key to continue...
pause > nul

netsh advfirewall set allprofiles state off

echo.
echo ================================================
echo Firewall DISABLED
echo ================================================
echo.
echo Now test from your mobile device:
echo http://10.36.169.35:8000/
echo.
echo IMPORTANT: Re-enable firewall after testing!
echo Run: enable_firewall.bat
echo.
pause
