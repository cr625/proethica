#!/bin/bash

# Database backup script for ai_ethical_dm in Codespace environment
# This script creates a backup of the PostgreSQL database from the codespace container

# Configuration
CONTAINER="proethica-postgres"
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_PASS="PASS"  # Default password for the codespace container
BACKUP_DIR="$(dirname "$0")"  # Use the directory where this script is located

# Create timestamp for the backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.dump"

# Display backup start message
echo "Starting backup of database '${DB_NAME}' from container '$CONTAINER' to ${BACKUP_FILE}"

# Check if the container is running
if ! docker ps | grep -q "$CONTAINER"; then
    echo "Error: Container '$CONTAINER' is not running!"
    echo "Please ensure the database container is running before backup."
    exit 1
fi

# Creating backup using pg_dump directly with output to stdout, piped to file
echo "Creating database backup using Docker container..."
docker exec -u postgres "$CONTAINER" pg_dump -Fc -d "$DB_NAME" -U "$DB_USER" > "$BACKUP_FILE"

# Check if backup file exists and has size > 0
if [ -s "$BACKUP_FILE" ]; then
    echo "Backup completed successfully: ${BACKUP_FILE}"
    echo "Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)"
else
    echo "Backup failed or file is empty!"
    exit 1
fi

# List all backups
echo -e "\nAvailable backups:"
ls -lh "${BACKUP_DIR}"/${DB_NAME}_backup_*.dump | sort

exit 0
