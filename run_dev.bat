@echo off
REM Launcher for the Clinic System development server.
REM Sets PYTHONPATH so Django can locate the clinic_system package
REM without needing to cd into the project directory.
set PYTHONPATH=d:\project\clinic_system\Clinic_System
d:\project\clinic_system\Clinic_System\.venv\Scripts\python.exe d:\project\clinic_system\Clinic_System\manage.py runserver 8000 --noreload
