#!/bin/bash
# Script to backup the AI Ethical DM database after section embeddings update

# Load environment variables from .env file
if [ -f .env ]; then
    echo "Loading environment from .env file"
    set -a
    source .env
    set +a
fi

# Extract database connection details from DATABASE_URL
# Format: postgresql://username:password@host:port/dbname
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Parse DATABASE_URL to extract components
DB_URL=${DATABASE_URL#postgresql://}
DB_USER=${DB_URL%%:*}
DB_URL=${DB_URL#*:}
DB_PASS=${DB_URL%%@*}
DB_URL=${DB_URL#*@}
DB_HOST=${DB_URL%%:*}
DB_URL=${DB_URL#*:}
DB_PORT=${DB_URL%%/*}
DB_NAME=${DB_URL#*/}

echo "Extracted database connection details:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"

# Create backup directory if it doesn't exist
BACKUP_DIR="backups"
mkdir -p $BACKUP_DIR

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/ai_ethical_dm_${TIMESTAMP}_with_section_embeddings.sql"

echo "Creating database backup to: $BACKUP_FILE"

# Perform the backup using pg_dump
PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -F p \
    -f "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    # Get file size
    FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup completed successfully!"
    echo "Backup file: $BACKUP_FILE"
    echo "Backup size: $FILESIZE"
    
    # Compress the backup to save space
    echo "Compressing backup file..."
    gzip "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        COMPRESSED_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
        echo "Compression complete: ${BACKUP_FILE}.gz (${COMPRESSED_SIZE})"
        echo "Database backup with section embeddings has been created successfully."
    else
        echo "Warning: Compression failed, but uncompressed backup is available at $BACKUP_FILE"
    fi
else
    echo "ERROR: Database backup failed!"
    exit 1
fi

# Add a backup record to a log file
echo "$(date): Created backup ${BACKUP_FILE}.gz with section embeddings data" >> backups/backup_history.log

echo "Backup process completed."
