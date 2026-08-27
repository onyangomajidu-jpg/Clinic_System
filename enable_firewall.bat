@echo off
echo ================================================
echo Re-enabling Windows Firewall
echo ================================================
echo.
netsh advfirewall set allprofiles state on
echo.
echo Firewall ENABLED
echo ================================================
echo.
pause
