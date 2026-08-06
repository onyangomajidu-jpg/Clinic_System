#!/bin/bash
# Daily backup script for Clinic Management System
# Usage: ./scripts/backup.sh
# Set up as cron: 0 23 * * * /path/to/Clinic_System/scripts/backup.sh

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_ENGINE="${DB_ENGINE:-sqlite}"

# Create backup directory
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)

echo "=== Clinic System Backup ==="
echo "Date: $(date)"
echo "Backup directory: $BACKUP_DIR"

# Backup database
if [ "$DB_ENGINE" = "postgresql" ]; then
    echo "Backing up PostgreSQL database..."
    docker-compose exec -T db pg_dump -U "${DB_USER:-clinic_user}" "${DB_NAME:-clinic_system}" > "$BACKUP_DIR/db_$DATE.sql"
    echo "PostgreSQL backup saved: db_$DATE.sql"
else
    echo "Backing up SQLite database..."
    if [ -f "db.sqlite3" ]; then
        cp db.sqlite3 "$BACKUP_DIR/db_$DATE.sqlite3"
        echo "SQLite backup saved: db_$DATE.sqlite3"
    else
        echo "WARNING: db.sqlite3 not found - skipping database backup"
    fi
fi

# Backup media files (if any)
if [ -d "media" ]; then
    tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" media/
    echo "Media backup saved: media_$DATE.tar.gz"
fi

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "db_*" -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name "media_*" -mtime "+$RETENTION_DAYS" -delete

echo "=== Backup complete ==="
echo "Files in backup directory:"
ls -lh "$BACKUP_DIR"