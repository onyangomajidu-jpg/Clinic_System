# Clinic System

A Django-based clinic management system.

## Tech stack

- Python 3.12 / Django 6.0
- PostgreSQL (via Docker) or SQLite (local, no Docker)
- Docker & docker-compose

## Project status

**Day 5 — Visit management.** Building on patient registration (Day 4),
this adds the clinical consultation workspace: record a visit with vitals
(BP, pulse, temperature, weight), chief complaint, diagnosis (with a
quick-pick list of common diagnoses), and notes; view a patient's full
visit history; and review individual visit details. The attending staff
member is captured automatically from the logged-in user's role.

**Previous days:**
- **Day 1 — Project setup.** Initial skeleton: a running Django project
  wired up for either SQLite (quick local dev) or PostgreSQL (via Docker),
  with a health-check endpoint to confirm everything boots.
- **Day 2 — Database models.** Core clinic data models (Patient, Visit,
  Staff, Drug, Prescription, Invoice, LabTest) with UUID primary keys and
  sync metadata per the SDD.
- **Day 3 — User management & RBAC.** Staff accounts, role-based access
  control, and role-scoped dashboard.
- **Day 4 — Patient registration.** Register patients, search by name/phone/
  card number, and print patient cards.

## Branch structure

- `main` — stable, production-ready code
- `develop` — integration branch; features are merged here first
- `setup/initial-scaffold`, `feature/*`, `fix/*`, etc. — short-lived
  branches cut from `develop`, merged back via pull request

Workflow: create a feature/fix branch from `develop` → open a PR into
`develop` → once `develop` is stable, PR it into `main` for a release.

## Getting started

### Option A: Run with Docker (recommended, uses PostgreSQL)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Build and start the containers:
   ```bash
   docker-compose up --build
   ```
3. In a separate terminal, run migrations:
   ```bash
   docker-compose exec web python manage.py migrate
   ```
4. Visit the health check endpoint:
   ```
   http://localhost:8000/api/health/
   ```
   You should see `{"status": "ok", "service": "clinic-system"}`.

### Option B: Run locally with SQLite (no Docker)

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example environment file (defaults to SQLite):
   ```bash
   cp .env.example .env
   ```
4. Run migrations and start the dev server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
5. Visit `http://localhost:8000/api/health/`.

## Environment variables

See [`.env.example`](.env.example) for all configurable values, including
how to switch between SQLite and PostgreSQL via `DB_ENGINE`.

## Project structure

```
clinic_system/       # Django project settings, root URLconf, WSGI/ASGI
core/                # Core app (health check endpoint, shared utilities)
manage.py
requirements.txt
Dockerfile
docker-compose.yml
.env.example
```

## Contributing

1. Branch from `develop`: `git checkout -b feature/your-feature develop`
2. Commit your changes with clear messages
3. Open a pull request into `develop`
4. After review and CI passes, merge

## License

TBD
