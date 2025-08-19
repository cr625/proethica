#!/bin/bash

# Restore script for the working concept saving state
# Created: 2025-07-20
# Git tag: concept-saving-working
# Commit: 406d4d8

echo "🔄 Restoring to working concept saving state..."

# Restore git state
echo "📋 Checking out git tag: concept-saving-working"
git checkout concept-saving-working

# Restore database
BACKUP_FILE="database_backup_working_concept_saving_20250720_050236.sql"

if [ -f "$BACKUP_FILE" ]; then
    echo "🗄️  Restoring database from: $BACKUP_FILE"
    
    # Drop and recreate database
    echo "⚠️  Dropping existing database..."
    docker exec proethica-postgres psql -U postgres -c "DROP DATABASE IF EXISTS ai_ethical_dm;"
    docker exec proethica-postgres psql -U postgres -c "CREATE DATABASE ai_ethical_dm;"
    
    # Restore from backup
    echo "📥 Restoring database..."
    docker exec -i proethica-postgres psql -U postgres -d ai_ethical_dm < "$BACKUP_FILE"
    
    echo "✅ Database restored successfully!"
else
    echo "❌ Backup file $BACKUP_FILE not found!"
    exit 1
fi

echo "🎯 Restore complete! You're now at the working concept saving state."
echo "📌 Git commit: 406d4d8 (concept-saving-working tag)"
echo "💾 Database restored from: $BACKUP_FILE"
echo ""
echo "To return to develop branch: git checkout develop"