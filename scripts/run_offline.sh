#!/usr/bin/env bash
# ============================================================
# Clinic System - LOCAL OFFLINE-FIRST LAUNCHER  (FR-12 / SDD 2.2 model 1)
# ============================================================
# Starts the system on this clinic computer using the LOCAL SQLite
# database (db.sqlite3). NO internet is required for registration,
# visits, dispensing, billing, or reports.
#
# Other devices on the clinic Wi-Fi connect to:
#     http://<this-computer-IP>:8000
#
# For PWA offline mode on MOBILE browsers you need HTTPS; use
# runserver_plus with --cert-file/--key-file (see run_offline_https.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python manage.py runserver 0.0.0.0:8000