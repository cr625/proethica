#!/bin/bash
# Selectively synchronize reference data from development to production

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Reference tables to sync (order matters for foreign keys)
REFERENCE_TABLES=(
    "worlds"
    "ontologies"
    "ontology_versions"
    "domains"
    "roles"
    "resources"
    "resource_types"
    "condition_types"
    "characters"
    "guidelines"
    "documents"
)

# Load environment variables
source "$PROJECT_ROOT/.env"

echo "========================================"
echo "Database Reference Data Synchronization"
echo "========================================"
echo "From: Local development (Docker)"
echo "To:   Production (${DROPLET_HOST})"
echo ""
echo "Tables to sync:"
printf '%s\n' "${REFERENCE_TABLES[@]}" | sed 's/^/  - /'
echo ""

# Confirm before proceeding
read -p "Continue with data sync? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "❌ Data sync cancelled"
    exit 0
fi

# Create backup directory on production
echo "📦 Creating production backup..."
ssh "${DROPLET_USER}@${DROPLET_HOST}" "mkdir -p ~/backups/data_sync_${TIMESTAMP}"

# Function to sync a single table
sync_table() {
    local table=$1
    echo "📊 Syncing table: $table"
    
    # Backup production table
    ssh "${DROPLET_USER}@${DROPLET_HOST}" \
        "pg_dump -U postgres -d ai_ethical_dm -t $table --data-only > ~/backups/data_sync_${TIMESTAMP}/${table}.sql"
    
    # Export from development
    docker exec proethica-postgres \
        pg_dump -U postgres -d ai_ethical_dm -t "$table" \
        --data-only --no-owner --column-inserts \
        > "/tmp/${table}_${TIMESTAMP}.sql"
    
    # Get row counts
    local dev_count=$(docker exec proethica-postgres \
        psql -U postgres -d ai_ethical_dm -t -c "SELECT COUNT(*) FROM $table")
    local prod_count=$(ssh "${DROPLET_USER}@${DROPLET_HOST}" \
        "psql -U postgres -d ai_ethical_dm -t -c 'SELECT COUNT(*) FROM $table'")
    
    echo "  Development: $dev_count rows"
    echo "  Production:  $prod_count rows"
    
    # Copy to production
    scp "/tmp/${table}_${TIMESTAMP}.sql" "${DROPLET_USER}@${DROPLET_HOST}:/tmp/"
    
    # Apply to production (with transaction)
    ssh "${DROPLET_USER}@${DROPLET_HOST}" << EOF
        psql -U postgres -d ai_ethical_dm << SQL
        BEGIN;
        -- Disable triggers temporarily
        SET session_replication_role = 'replica';
        
        -- Clear existing data
        TRUNCATE TABLE $table CASCADE;
        
        -- Import new data
        \i /tmp/${table}_${TIMESTAMP}.sql
        
        -- Re-enable triggers
        SET session_replication_role = 'origin';
        
        -- Verify import
        SELECT '$table: ' || COUNT(*) || ' rows imported' FROM $table;
        
        COMMIT;
SQL
        
        # Cleanup
        rm /tmp/${table}_${TIMESTAMP}.sql
EOF
    
    # Cleanup local file
    rm -f "/tmp/${table}_${TIMESTAMP}.sql"
    
    echo "  ✅ Table synced successfully"
    echo ""
}

# Sync each table
for table in "${REFERENCE_TABLES[@]}"; do
    sync_table "$table"
done

# Reset sequences
echo "🔢 Resetting sequences..."
ssh "${DROPLET_USER}@${DROPLET_HOST}" << 'EOF'
    psql -U postgres -d ai_ethical_dm << SQL
    -- Reset all sequences to max value + 1
    DO $$
    DECLARE
        r RECORD;
        max_val BIGINT;
    BEGIN
        FOR r IN 
            SELECT 
                schemaname,
                tablename,
                pg_get_serial_sequence(schemaname||'.'||tablename, 'id') as seq_name
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND pg_get_serial_sequence(schemaname||'.'||tablename, 'id') IS NOT NULL
        LOOP
            IF r.seq_name IS NOT NULL THEN
                EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I.%I', r.schemaname, r.tablename) INTO max_val;
                EXECUTE format('SELECT setval(%L, %s, false)', r.seq_name, max_val + 1);
                RAISE NOTICE 'Reset sequence % to %', r.seq_name, max_val + 1;
            END IF;
        END LOOP;
    END $$;
SQL
EOF

echo ""
echo "✅ Reference data synchronization completed!"
echo "Backups saved at: production:~/backups/data_sync_${TIMESTAMP}/"

# Optional: Verify data integrity
echo ""
read -p "Run data integrity check? (yes/no): " verify
if [[ "$verify" == "yes" ]]; then
    echo "🔍 Checking data integrity..."
    
    for table in "${REFERENCE_TABLES[@]}"; do
        dev_count=$(docker exec proethica-postgres \
            psql -U postgres -d ai_ethical_dm -t -c "SELECT COUNT(*) FROM $table")
        prod_count=$(ssh "${DROPLET_USER}@${DROPLET_HOST}" \
            "psql -U postgres -d ai_ethical_dm -t -c 'SELECT COUNT(*) FROM $table'")
        
        if [[ "$dev_count" -eq "$prod_count" ]]; then
            echo "✅ $table: $dev_count rows (matched)"
        else
            echo "❌ $table: dev=$dev_count, prod=$prod_count (MISMATCH)"
        fi
    done
fi