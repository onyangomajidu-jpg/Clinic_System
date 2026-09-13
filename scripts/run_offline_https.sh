#!/usr/bin/env bash
# Clinic System - LOCAL OFFLINE-FIRST (HTTPS, for PWA/mobile over LAN)
# Same as run_offline.sh but HTTPS so the PWA install + offline mode work
# on phone browsers. Requires django-extensions (runserver_plus) + werkzeug.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python manage.py runserver_plus 0.0.0.0:8000 \
    --cert-file dev.crt --key-file dev.key