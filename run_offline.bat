@echo off
REM ============================================================
REM Clinic System - LOCAL OFFLINE-FIRST LAUNCHER  (FR-12 / SDD 2.2 model 1)
REM ============================================================
REM Starts the system on this clinic computer using the LOCAL SQLite
REM database (db.sqlite3). NO internet is required for registration,
REM visits, dispensing, billing, or reports.
REM
REM Other devices on the clinic Wi-Fi connect to:
REM     https://<this-computer-IP>:8000
REM (Type "ipconfig" to find this computer's IP address.)
REM
REM HTTPS + self-signed cert is used so the PWA install / offline mode
REM works on mobile browsers too (browsers block service workers on
REM plain http:// over the network).
REM ============================================================
set PYTHONPATH=d:\project\clinic_system\Clinic_System
d:\project\clinic_system\Clinic_System\.venv\Scripts\python.exe d:\project\clinic_system\Clinic_System\manage.py runserver_plus 0.0.0.0:8000 --cert-file d:\project\clinic_system\Clinic_System\dev.crt --key-file d:\project\clinic_system\Clinic_System\dev.key