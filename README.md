# Clinic System

A Django-based clinic management system for community health clinics in Uganda.

## Tech stack

- Python 3.12 / Django 6.0
- PostgreSQL (via Docker) or SQLite (local, no Docker)
- Docker & docker-compose
- Gunicorn (production web server)

## Project status

**v1.0-beta — Ready for pilot use.** All 14 functional requirements (FR-1
through FR-14) from the UR.md are implemented and verified by **173 passing
tests**. The system is deployed via Docker and ready for deployment to a
pilot community clinic.

### Feature summary (all 14 days)

| Day | Module | Status |
|---|---|---|
| 1 | Project setup & health check | ✅ |
| 2 | Database models (Patient, Visit, Staff, Drug, Prescription, Invoice) | ✅ |
| 3 | User management & RBAC | ✅ |
| 4 | Patient registration, search, card printing | ✅ |
| 5 | Visit management (vitals, diagnosis, history) | ✅ |
| 6 | Integration & testing (Week 1 complete, v0.1) | ✅ |
| 7 | Prescriptions linked to pharmacy stock | ✅ |
| 8 | Pharmacy & inventory (dispensing, stock decrement, alerts) | ✅ |
| 9 | Billing & payments (invoices, cash/mobile money, receipts) | ✅ |
| 10 | Appointments & SMS reminders (Africa's Talking) | ✅ |
| 11 | Reporting & analytics (patient volumes, diagnoses, revenue, drug usage) | ✅ |
| 12 | Offline capability & sync (PWA, service worker, sync service) | ✅ |
| 13 | Full integration testing & UAT (173 tests) | ✅ |
| 14 | Deployment & handover (Docker, docs, training) | ✅ |

## Quick start

### Option A: Docker (recommended for deployment)

```bash
# 1. Clone and checkout the release
git clone https://github.com/onyangomajidu-jpg/Clinic_System.git
cd Clinic_System
git checkout v1.0-beta

# 2. Configure environment
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DJANGO_DEBUG=False

# 3. Deploy (builds, migrates, creates admin, verifies health)
./scripts/deploy.sh

# 4. Access
# http://localhost:8000/
```

### Option B: Local development with SQLite

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Full deployment guide for clinic devices
- **[TRAINING.md](TRAINING.md)** — User training material for clinic staff
- **[SDD.md](../SDD.md)** — Software Design Document
- **[UR.md](../UR.md)** — User Requirements Specification

## Deployment scripts

- `scripts/deploy.sh` — One-command deployment (build, migrate, admin, health check)
- `scripts/backup.sh` — Daily automated backup (SQLite or PostgreSQL)

## Branch structure

- `main` — stable, production-ready code (v1.0-beta tagged)
- `develop` — integration branch; features are merged here first
- `feature/*` — short-lived branches cut from `develop`, merged via PR

## Environment variables

See [`.env.example`](.env.example) for all configurable values, including
how to switch between SQLite and PostgreSQL via `DB_ENGINE`.

## Project structure

```
clinic_system/       # Django project settings, root URLconf, WSGI/ASGI
core/                # Core app (models, views, forms, services, reports, sync)
accounts/            # User management & RBAC
templates/           # Shared templates
static/              # Static assets (CSS, PWA icons)
scripts/             # Deployment & backup scripts
DEPLOYMENT.md        # Deployment guide
TRAINING.md          # User training material
Dockerfile
docker-compose.yml
.env.example
```

## License

TBD