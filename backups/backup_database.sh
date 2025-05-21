##!/bin/bash

# Database backup script for ai_ethical_dm
# This script creates a backup of the PostgreSQL database

# Configuration
CONTAINER="proethica-postgres"
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
BACKUP_DIR="$(dirname "$0")"  # Use the directory where this script is located

# IMPORTANT: Before using this script, ensure that md5 authentication is properly configured
# for the postgres user in pg_hba.conf. Otherwise, authentication might fail.

# Extract password from .env file
ENV_FILE="../.env"  # Path when running from backups directory
if [ -f "${ENV_FILE}" ]; then
    # Extract password from DATABASE_URL in .env file
    DB_PASS=$(grep DATABASE_URL "${ENV_FILE}" | sed -E 's/.*postgres:([^@]+)@.*/\1/')
    echo "Found database password in .env file"
else
    # Try with project root path (when running from project root)
    ENV_FILE=".env"
    if [ -f "${ENV_FILE}" ]; then
        # Extract password from DATABASE_URL in .env file
        DB_PASS=$(grep DATABASE_URL "${ENV_FILE}" | sed -E 's/.*postgres:([^@]+)@.*/\1/')
        echo "Found database password in .env file"
    else
        DB_PASS="PASS"  # Default password if .env not found
        echo "Warning: .env file not found, using default password"
    fi
fi

# Export the password for PostgreSQL commands
export PGPASSWORD="${DB_PASS}"

# Create timestamp for the backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.dump"

# Display backup start message
echo "Starting backup of database '${DB_NAME}' to ${BACKUP_FILE}"

# Run pg_dump inside the Docker container to create the backup
# Use a directory with proper permissions for the postgres user
BACKUP_PATH_IN_CONTAINER="/var/lib/postgresql/backup"
BACKUP_FILE_IN_CONTAINER="$BACKUP_PATH_IN_CONTAINER/backup.dump"

echo "Ensuring backup directory exists in container..."
docker exec -u postgres "$CONTAINER" mkdir -p "$BACKUP_PATH_IN_CONTAINER"

echo "Running pg_dump in container..."
docker exec -u postgres "$CONTAINER" pg_dump -Fc -d "$DB_NAME" -U "$DB_USER" -f "$BACKUP_FILE_IN_CONTAINER"

# Copy the backup file from the container to the host
echo "Copying backup file from container..."
docker cp "$CONTAINER":"$BACKUP_FILE_IN_CONTAINER" "$BACKUP_FILE"
docker exec -u postgres "$CONTAINER" rm "$BACKUP_FILE_IN_CONTAINER"

# Check if backup was successful
if [ $? -eq 0 ]; then
    echo "Backup completed successfully: ${BACKUP_FILE}"
    echo "Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)"
else
    echo "Backup failed!"
    exit 1
fi

# List all backups
echo -e "\nAvailable backups:"
ls -lh "${BACKUP_DIR}"/${DB_NAME}_backup_*.dump | sort

exit 0
