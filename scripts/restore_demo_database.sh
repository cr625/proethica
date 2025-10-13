#!/bin/bash

# ProEthica Demo Database Restore Script
# Restores a PostgreSQL dump to the database (use on production server)
# Usage: ./restore_demo_database.sh <backup_file.sql>

set -e  # Exit on error

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql>"
    echo ""
    echo "Example:"
    echo "  ./restore_demo_database.sh /tmp/proethica_demo_20251012_123456.sql"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "================================================"
echo "ProEthica Demo Database Restore"
echo "================================================"
echo ""
echo "WARNING: This will REPLACE the current database!"
echo "Database: ai_ethical_dm"
echo "Backup file: $BACKUP_FILE"
echo "File size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo ""
    echo "Restore cancelled"
    exit 0
fi

echo ""
echo "Creating backup of current database before restore..."
CURRENT_BACKUP="backups/pre_restore_backup_$(date +%Y%m%d_%H%M%S).sql"
mkdir -p backups
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm \
  --clean --if-exists --no-owner --no-privileges \
  -f "$CURRENT_BACKUP" 2>/dev/null || echo "Warning: Could not create pre-restore backup"

echo ""
echo "Restoring database from: $BACKUP_FILE"
echo "This may take a few moments..."
echo ""

PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm < "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database restored successfully!"
    echo ""

    # Verify restore by counting records
    echo "Verifying restore..."
    DOCUMENT_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs)
    ENTITY_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "SELECT COUNT(*) FROM temporary_rdf_storage;" 2>/dev/null | xargs)

    echo "Documents in database: $DOCUMENT_COUNT"
    echo "Entities in database: $ENTITY_COUNT"
    echo ""

    if [ -f "$CURRENT_BACKUP" ]; then
        echo "Pre-restore backup saved to: $CURRENT_BACKUP"
        echo "(Keep this file for rollback if needed)"
    fi
    echo ""
    echo "Next steps:"
    echo "  1. Restart ProEthica: sudo systemctl restart proethica"
    echo "  2. Check status: sudo systemctl status proethica"
    echo "  3. Test: curl https://proethica.org"
else
    echo ""
    echo "✗ Restore failed!"
    echo ""
    if [ -f "$CURRENT_BACKUP" ]; then
        echo "You can restore the previous database with:"
        echo "  PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm < $CURRENT_BACKUP"
    fi
    exit 1
fi
