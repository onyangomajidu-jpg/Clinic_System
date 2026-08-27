@echo off
REM Launcher for the Clinic System development server over HTTPS.
REM HTTPS is REQUIRED for the PWA install prompt and offline mode to work
REM on mobile devices (browsers block service workers on http:// over LAN).
set PYTHONPATH=d:\project\clinic_system\Clinic_System
d:\project\clinic_system\Clinic_System\.venv\Scripts\python.exe d:\project\clinic_system\Clinic_System\manage.py runserver_plus 0.0.0.0:8000 --cert-file d:\project\clinic_system\Clinic_System\dev.crt --key-file d:\project\clinic_system\Clinic_System\dev.key
