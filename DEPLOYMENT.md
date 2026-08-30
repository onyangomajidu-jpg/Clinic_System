# Deployment Guide — Clinic Management System v1.0-beta

This guide walks through deploying the Clinic Management System to a community
health clinic device. It covers both **single-clinic local deployment** (the
recommended pilot setup) and **multi-clinic centralized deployment**.

---

## 1. Prerequisites

### Hardware (minimum)
- **CPU:** 2 cores (Intel i3 or equivalent)
- **RAM:** 4 GB
- **Storage:** 20 GB free disk space
- **OS:** Windows 10/11, Ubuntu 20.04+, or Raspberry Pi OS
- **Network:** No internet required for daily operation (offline-first)

### Software
- **Docker** and **Docker Compose** (recommended)
  - Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - Ubuntu: `sudo apt install docker.io docker-compose-v2`
- **Git** (for pulling the latest code)
- **Python 3.12+** (only needed for non-Docker deployment)

---

## 2. Single-Clinic Local Deployment (Recommended)

This is the standard deployment for a community clinic. The system runs
entirely on the clinic's local device with no internet dependency.

### Step 1: Get the code

```bash
git clone https://github.com/onyangomajidu-jpg/Clinic_System.git
cd Clinic_System
git checkout v1.0-beta
```

### Step 2: Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set a **strong secret key**:

```
DJANGO_SECRET_KEY=change-this-to-a-long-random-string
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
```

> **Note:** Add the clinic device's local IP address to `DJANGO_ALLOWED_HOSTS`
> so other computers/tablets on the clinic's local network can access the system.

### Step 3: Build and start

```bash
docker-compose up --build -d
```

### Step 4: Run migrations and create admin user

```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### Step 5: Verify

Open a browser and visit:

```
http://localhost:8000/api/health/
```

You should see:
```json
{"status": "ok", "service": "clinic-system"}
```

Then log in at `http://localhost:8000/accounts/login/` with the admin
credentials you created.

### Step 6: Access from other devices on the clinic network

Other computers/tablets on the same local network can access the system at:

```
http://<clinic-device-ip>:8000/
```

Find the device IP with:
```bash
ip addr show   # Linux
ipconfig       # Windows
```

---

## 3. Multi-Clinic Centralized Deployment

For district/regional deployments where multiple clinics sync to a central
server.

### Central Server

1. Deploy the same Docker setup on a VPS (e.g., DigitalOcean, AWS).
2. Set `DJANGO_DEBUG=False` and configure HTTPS (see Section 5).
3. Use PostgreSQL (already configured in docker-compose.yml).

### Clinic Devices

Each clinic runs the same local deployment. The sync service
(`python manage.py sync`) pushes local changes to the central server when
connectivity is available.

---

## 4. Backup & Restore

### Automated Daily Backup

A backup script is included. Set it up as a cron job (Linux) or Task
Scheduler (Windows).

**Linux (cron):**
```bash
# Edit crontab
crontab -e

# Add daily backup at 11 PM
0 23 * * * /path/to/Clinic_System/scripts/backup.sh
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create a new task
3. Trigger: Daily at 11:00 PM
4. Action: Run `scripts\backup.bat`

### Manual Backup

```bash
# SQLite (local deployment)
cp db.sqlite3 backups/db-$(date +%Y%m%d).sqlite3

# PostgreSQL (Docker)
docker-compose exec db pg_dump -U clinic_user clinic_system > backups/db-$(date +%Y%m%d).sql
```

### Restore

```bash
# SQLite
cp backups/db-YYYYMMDD.sqlite3 db.sqlite3

# PostgreSQL
cat backups/db-YYYYMMDD.sql | docker-compose exec -T db psql -U clinic_user clinic_system
```

---

## 5. Production Hardening

### HTTPS (for centralized deployments)

Use a reverse proxy (nginx or Caddy) in front of the Django server:

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name clinic.example.org;

    ssl_certificate /etc/letsencrypt/live/clinic.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clinic.example.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Security Checklist

- [ ] `DJANGO_DEBUG=False` in production
- [ ] Strong `DJANGO_SECRET_KEY` (use `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- [ ] HTTPS enabled for any internet-facing deployment
- [ ] Daily automated backups configured
- [ ] Database file permissions restricted to the application user
- [ ] Staff accounts use strong passwords
- [ ] Regular review of staff accounts (remove inactive users)

---

## 5b. Hosting on Render (free, internet-accessible)

Render runs the app 24/7 on the internet with HTTPS and a managed PostgreSQL
database, so phones can reach a **permanent** URL (great for the PWA
install prompt vs. the changing Cloudflare quick-tunnel addresses).

### What the repo already contains

- `render.yaml` — Render Blueprint: builds the Dockerfile, creates a Postgres
  DB, wires `DATABASE_URL`, runs `collectstatic` + `migrate` on startup, and
  binds gunicorn to Render's `$PORT`.
- Production settings in `clinic_system/settings.py` (WhiteNoise static
  serving, `DATABASE_URL` support, HTTPS/proxy + secure-cookie flags, and
  `ALLOWED_HOSTS`/CSRF defaults for `*.onrender.com`).
- `.dockerignore` so `.venv`, `db.sqlite3`, `.env`, logs, and scripts aren't
  baked into the image.

### Steps

1. **Push this repo to GitHub** (if not already the source of truth):
   ```bash
   git add .
   git commit -m "Add Render hosting support"
   git push origin main
   ```
   Make sure the commit above (with `render.yaml`) is on the default branch.

2. **Create a Render account** at https://render.com (free tier works).

3. **Add a Blueprint**:
   - Dashboard → **New +** → **Blueprint** → connect your GitHub account/repo.
   - Render detects `render.yaml` and lets you deploy the **web service** and
     the **PostgreSQL** database at once.

4. **Wait for the first build/deploy** (a few minutes). Render runs:
   `collectstatic` → `migrate` → `create_admin` → starts gunicorn.

5. **Admin login is created automatically.** On startup the container runs
   `python manage.py create_admin`, which provisions a superuser **and** the
   "Admin / In-charge" staff record from these env vars (set in `render.yaml`):
   - `DJANGO_ADMIN_USERNAME` = `admin`
   - `DJANGO_ADMIN_EMAIL` = `admin@example.com`
   - `DJANGO_ADMIN_PASSWORD` = auto-generated (`generateValue: true`)

   To see the auto-generated password, go to your service → **Environment** →
   **Reveal Config Vars**. You can rotate it anytime by editing/writing
   `DJANGO_ADMIN_PASSWORD` in Render and re-deploying (the command is
   idempotent and resets the password to whatever the env says on startup).
   To change the username/email, edit `DJANGO_ADMIN_USERNAME`/`DJANGO_ADMIN_EMAIL`
   in `render.yaml` and re-push.

6. **Open your app** at the URL Render shows, e.g.
   `https://clinic-system.onrender.com/`. Log in and use the system from any
   device/browser. HTTPS + a stable URL make the **PWA install prompt**
   reliable.

### Env vars on Render (auto-set by `render.yaml`)
| var | value |
|-----|-------|
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | auto-generated |
| `DJANGO_ADMIN_USERNAME` | `admin` |
| `DJANGO_ADMIN_EMAIL` | `admin@example.com` |
| `DJANGO_ADMIN_PASSWORD` | auto-generated (reveal it in Render → Environment) |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com,localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` |
| `DJANGO_SESSION_COOKIE_SECURE` | `true` |
| `DJANGO_CSRF_COOKIE_SECURE` | `true` |
| `DATABASE_URL` | Render Postgres connection string (from Blueprint) |

> Add a custom domain under **Settings → Custom Domains** if you want one.
> Add the exact `https://your-domain` to `DJANGO_CSRF_TRUSTED_ORIGINS` and
> the host to `DJANGO_ALLOWED_HOSTS`.

### Deployment notes / caveats
- **Render free Postgres expires after 30 days** (auto-removed). For a
  permanent store pick the paid Postgres or re-provision and re-migrate.
- The database is ephemeral-backed on the free tier; back up regularly
  (see Section 4).
- Each push to the connected branch triggers an auto-deploy.

---

## 6. Troubleshooting

### "Connection refused" when accessing from another device
- Check the device IP is in `DJANGO_ALLOWED_HOSTS`
- Check firewall allows port 8000
- Verify both devices are on the same network

### Database migration errors
```bash
docker-compose exec web python manage.py migrate --noinput
```

### Reset the database (loses all data — use only for testing)
```bash
docker-compose down -v
docker-compose up --build -d
docker-compose exec web python manage.py migrate
```

### View logs
```bash
docker-compose logs -f web
```

---

## 7. System Requirements Checklist

| Requirement | Status |
|---|---|
| Works offline (no internet) | ✅ FR-12 |
| Syncs when online | ✅ FR-13 |
| Runs on modest hardware (4GB RAM) | ✅ NFR-2 |
| No paid subscription | ✅ NFR-4 |
| Daily automated backups | ✅ NFR-6 |
| Role-based access control | ✅ FR-9 |
| SMS reminders (Africa's Talking) | ✅ FR-10 |
| Printable patient cards, prescriptions, receipts | ✅ FR-14 |