#!/bin/bash

# ProEthica Demo Database Backup Script
# Creates a PostgreSQL dump of demonstration cases for deployment to production
# Output: backups/proethica_demo_YYYYMMDD_HHMMSS.sql

set -e  # Exit on error

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
BACKUP_FILE="${BACKUP_DIR}/proethica_demo_${TIMESTAMP}.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "================================================"
echo "ProEthica Demo Database Backup"
echo "================================================"
echo ""
echo "Database: ai_ethical_dm"
echo "Output: $BACKUP_FILE"
echo ""

# Create database backup
echo "Creating backup..."
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
  --clean --if-exists --no-owner --no-privileges \
  -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Backup created successfully!"
    echo ""
    echo "File: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
    echo ""
    echo "To deploy to production:"
    echo "  1. scp $BACKUP_FILE digitalocean:/tmp/"
    echo "  2. ssh digitalocean 'cd /opt/proethica && ./scripts/restore_demo_database.sh /tmp/$(basename $BACKUP_FILE)'"
else
    echo ""
    echo "✗ Backup failed!"
    exit 1
fi
