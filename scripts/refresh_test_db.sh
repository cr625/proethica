#!/bin/bash
# Refresh test database from production (run on production server)
# This script copies the production database to the test database
# Usage: ./scripts/refresh_test_db.sh
#
# IMPORTANT: This script must be run on the production server (DigitalOcean)
# It requires sudo access for postgres user to create the database

set -e

echo "=== ProEthica Test Database Refresh ==="
echo "This script will copy production data to ai_ethical_dm_test"
echo ""

# Database credentials
DB_USER="proethica_user"
DB_PASS="ProEthicaSecure2025"
DB_HOST="localhost"
PROD_DB="ai_ethical_dm"
TEST_DB="ai_ethical_dm_test"
DUMP_FILE="/tmp/ai_ethical_dm_backup.dump"

# Step 1: Dump production database (custom format for reliability)
echo "Step 1: Dumping production database..."
PGPASSWORD=$DB_PASS pg_dump -U $DB_USER -h $DB_HOST -Fc $PROD_DB > $DUMP_FILE
echo "  Dump created: $(ls -lh $DUMP_FILE | awk '{print $5}')"

# Step 2: Drop and recreate test database
# This requires postgres superuser access via sudo
echo "Step 2: Recreating test database..."
sudo -u postgres psql << PSQL
DROP DATABASE IF EXISTS $TEST_DB;
CREATE DATABASE $TEST_DB OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $TEST_DB TO $DB_USER;
PSQL

# Step 3: Restore to test database
echo "Step 3: Restoring data to test database..."
PGPASSWORD=$DB_PASS pg_restore -U $DB_USER -h $DB_HOST -d $TEST_DB --no-owner $DUMP_FILE 2>&1 | grep -c 'error:' || true
echo "  Restore complete (some permission errors are expected)"

# Step 4: Verify
echo "Step 4: Verifying test database..."
PGPASSWORD=$DB_PASS psql -U $DB_USER -h $DB_HOST -d $TEST_DB -c "
SELECT
    (SELECT count(*) FROM documents) as documents,
    (SELECT count(*) FROM users) as users,
    (SELECT count(*) FROM extraction_prompts) as prompts,
    (SELECT pg_size_pretty(pg_database_size('$TEST_DB'))) as size;
"

# Cleanup
rm -f $DUMP_FILE
echo ""
echo "=== Test database refresh complete ==="
echo "Database: $TEST_DB"
echo ""
echo "To run tests:"
echo "  cd /opt/proethica"
echo "  source venv/bin/activate"
echo "  PYTHONPATH=/opt/proethica FLASK_ENV=testing pytest tests/ -v"
echo ""
echo "NOTE: Some pytest fixtures try to recreate the schema (db.create_all())"
echo "which requires superuser privileges. Tests that rely on those fixtures"
echo "may fail. Tests that work with existing data should pass."
