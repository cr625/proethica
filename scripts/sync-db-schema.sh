#!/bin/bash
# Synchronize database schema from development to production

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Load environment variables
source "$PROJECT_ROOT/.env"

# Check if we're in development environment
if [[ "${ENVIRONMENT:-development}" != "development" ]]; then
    echo "❌ This script should only be run from development environment"
    exit 1
fi

echo "==================================="
echo "Database Schema Synchronization"
echo "==================================="
echo "From: Local development (Docker)"
echo "To:   Production (${DROPLET_HOST})"
echo ""

# Backup production schema first
echo "📦 Creating production schema backup..."
ssh "${DROPLET_USER}@${DROPLET_HOST}" \
    "pg_dump -U postgres -d ai_ethical_dm --schema-only > ~/backups/schema_backup_${TIMESTAMP}.sql"

# Export development schema
echo "📤 Exporting development schema..."
docker exec proethica-postgres \
    pg_dump -U postgres -d ai_ethical_dm --schema-only \
    --no-owner --no-privileges \
    > "/tmp/schema_${TIMESTAMP}.sql"

# Show schema differences
echo "🔍 Checking schema differences..."
ssh "${DROPLET_USER}@${DROPLET_HOST}" \
    "pg_dump -U postgres -d ai_ethical_dm --schema-only --no-owner --no-privileges" \
    > "/tmp/prod_schema_current.sql"

if command -v diff &> /dev/null; then
    echo "Schema changes:"
    diff -u "/tmp/prod_schema_current.sql" "/tmp/schema_${TIMESTAMP}.sql" || true
    echo ""
fi

# Confirm before applying
read -p "Apply schema changes to production? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "❌ Schema sync cancelled"
    exit 0
fi

# Apply schema to production
echo "📥 Applying schema to production..."
scp "/tmp/schema_${TIMESTAMP}.sql" "${DROPLET_USER}@${DROPLET_HOST}:/tmp/"

ssh "${DROPLET_USER}@${DROPLET_HOST}" << 'EOF'
    set -e
    
    # Create temporary database for testing
    echo "Testing schema on temporary database..."
    createdb -U postgres ai_ethical_dm_test || true
    
    # Test schema application
    if psql -U postgres -d ai_ethical_dm_test < /tmp/schema_*.sql; then
        echo "✅ Schema validation passed"
        
        # Apply to production database
        echo "Applying to production database..."
        psql -U postgres -d ai_ethical_dm < /tmp/schema_*.sql
        echo "✅ Schema updated successfully"
    else
        echo "❌ Schema validation failed"
        exit 1
    fi
    
    # Cleanup
    dropdb -U postgres ai_ethical_dm_test || true
    rm /tmp/schema_*.sql
EOF

# Cleanup local files
rm -f "/tmp/schema_${TIMESTAMP}.sql" "/tmp/prod_schema_current.sql"

echo ""
echo "✅ Schema synchronization completed!"
echo "Backup saved at: production:~/backups/schema_backup_${TIMESTAMP}.sql"