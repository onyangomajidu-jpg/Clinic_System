# Offline Use — Setup & Fix Guide (FR-12 / FR-13, SDD §2)

This guide explains why the system must run **locally** to work offline, and
how to set it up. It follows the requirements in `UR.md` (FR-12, FR-13,
Acceptance Criterion 2) and `SDD.md` (§2.2 Deployment Models, §4.3 Sync).

---

## 1. Why "offline" depends on WHERE the app runs

The Clinic System is a **server-rendered web app**: every screen and every
save (register patient, record visit, dispense, invoice) is a request to the
Django server, which reads/writes one database.

| Deployment | Can it run fully offline? | Why |
|---|---|---|
| **Cloud (Render)** | **No** | The server *and* its PostgreSQL database are on the internet. No internet → no server → nothing runs. |
| **Local (clinic computer/LAN)** | **Yes** | The server *and* the SQLite database are on the clinic's own device/network. Internet is not needed for core work. |

**Conclusion:** to meet UR FR-12 ("registration, consultation, dispensing,
billing must work fully offline") the system must be installed **locally** —
this is exactly the "single-clinic local deployment" in SDD §2.2 model 1.
The cloud/Render copy is the *online* multi-clinic option and cannot be
offline by design.

---

## 2. Run it fully offline (local, no internet)

### Windows (the clinic has a Windows PC)

Double-click **`run_offline.bat`** (or run `run_https.bat`). It starts Django
on `0.0.0.0:8000` bound to `db.sqlite3` — the local database. No internet is
used.

- On the clinic PC itself, open **https://localhost:8000**
- Other devices on the clinic Wi-Fi open **https://<this-PC-IP>:8000**
  (find the IP with `ipconfig`).

> `run_offline.bat` uses the self-signed `dev.crt`/`dev.key` and HTTPS so the
> PWA install + offline mode also work on phone browsers (browsers block
> service workers on plain http:// over a network).

### Linux / Raspberry Pi (low-cost clinic server)

```bash
# Plain HTTP (fine for desktop browsers on the clinic network)
./scripts/run_offline.sh

# HTTPS (so mobile PWA/offline works) — needs django-extensions + werkzeug
./scripts/run_offline_https.sh
```

Then open **http://<clinic-server-IP>:8000** (or **https://...** for HTTPS).

### Docker (recommended for long-term deployment)

```bash
cp .env.example .env      # ensure DB_ENGINE=sqlite3 (default) or leave unset
docker-compose up --build
```
or follow the **"Single-Clinic Local Deployment"** section in `DEPLOYMENT.md`.

---

## 3. What needs internet (and what does NOT)

| Works fully offline | Needs internet |
|---|---|
| Register / search patients | SMS reminders (Africa's Talking) |
| Record visits & prescriptions | Daily cloud backups (optional) |
| Dispense drugs / stock alerts | Multi-clinic sync (`manage.py sync`) to central server |
| Billing, payments, receipts | Deploying to / pulling from the cloud (Render) |
| Reports & daily summaries |  |

> If the internet drops while the app runs **locally**, all core clinic work
> continues; only the optional items above wait for connectivity.

---

## 4. Data lives locally — keep it safe

- The database is the single file **`db.sqlite3`** next to `manage.py`.
- Back it up daily (see `scripts/backup.sh`). Copying that one file is a full
  backup (SDD §10).
- NFR-6: an automated daily backup is recommended.

---

## 5. Multi-clinic (sync when online) — FR-13

If you later run several clinics, each runs this same local install and uses
the built-in sync (already implemented in `core/sync.py`):

```bash
python manage.py sync            # push local changes to the central server
```

See `core/sync.py` and the "Multi-Clinic Centralized Deployment" section in
`DEPLOYMENT.md`.