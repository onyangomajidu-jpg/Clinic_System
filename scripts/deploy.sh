#!/bin/bash
# Deployment script for Clinic Management System
# Usage: ./scripts/deploy.sh [--reset] [--update]
#
# Options:
#   --reset   Reset the database (DANGER: loses all data)
#   --update  Pull latest code and update the running deployment

set -e

cd "$(dirname "$0")/.."

echo "=== Clinic System Deployment ==="
echo "Date: $(date)"

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    echo "See DEPLOYMENT.md for instructions."
    exit 1
fi

# Check docker-compose is available
if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not available."
    echo "See DEPLOYMENT.md for instructions."
    exit 1
fi

# Check .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env and set a strong DJANGO_SECRET_KEY!"
    echo "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
fi

# Handle --update flag
if [ "$1" = "--update" ]; then
    echo "Pulling latest code..."
    git pull origin main
fi

# Handle --reset flag
if [ "$1" = "--reset" ]; then
    echo "WARNING: Resetting the database. ALL DATA WILL BE LOST!"
    read -p "Type 'RESET' to confirm: " confirm
    if [ "$confirm" != "RESET" ]; then
        echo "Reset cancelled."
        exit 1
    fi
    echo "Stopping containers and removing volumes..."
    docker compose down -v
fi

# Build and start containers
echo "Building and starting containers..."
docker compose up --build -d

# Wait for database to be healthy
echo "Waiting for database to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker compose exec web python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
docker compose exec web python manage.py collectstatic --noinput 2>/dev/null || true

# Create admin user if it doesn't exist
echo "Checking for admin user..."
docker compose exec web python -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    print('NO_ADMIN')
else:
    print('ADMIN_EXISTS')
" | grep -q "NO_ADMIN" && {
    echo "Creating admin user..."
    docker compose exec web python manage.py createsuperuser
} || {
    echo "Admin user already exists."
}

# Verify health
echo "Verifying health check..."
sleep 5
HEALTH=$(curl -s http://localhost:8000/api/health/ || echo "FAILED")
echo "Health check response: $HEALTH"

if echo "$HEALTH" | grep -q '"status": "ok"'; then
    echo ""
    echo "=== Deployment successful! ==="
    echo "Access the system at: http://localhost:8000"
    echo "Login page: http://localhost:8000/accounts/login/"
    echo ""
    echo "For other devices on the network, use:"
    echo "  http://<this-device-ip>:8000/"
    echo ""
    echo "See DEPLOYMENT.md for backup and troubleshooting."
else
    echo ""
    echo "WARNING: Health check failed. Check logs with:"
    echo "  docker compose logs -f web"
    exit 1
fi