#!/bin/bash

# Database restore script for ai_ethical_dm in Codespace environment
# This script restores a PostgreSQL database from a backup file using Docker

# Configuration
CONTAINER="proethica-postgres"
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_PASS="PASS"  # Default password for the codespace container
BACKUP_DIR="$(dirname "$0")"  # Use the directory where this script is located

# Check if a backup file was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_filename>"
    echo "Available backups:"
    ls -lh "${BACKUP_DIR}"/${DB_NAME}_backup_*.dump 2>/dev/null | sort
    exit 1
fi

BACKUP_FILE="$1"

# Check if the backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    # Try with the backup directory prefix
    if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
    else
        echo "Error: Backup file '${BACKUP_FILE}' not found!"
        echo "Available backups:"
        ls -lh "${BACKUP_DIR}"/${DB_NAME}_backup_*.dump 2>/dev/null | sort
        exit 1
    fi
fi

# Check if the container is running
if ! docker ps | grep -q "$CONTAINER"; then
    echo "Error: Container '$CONTAINER' is not running!"
    echo "Please ensure the database container is running before restoration."
    exit 1
fi

# Confirm restore
echo "WARNING: This will overwrite the current '${DB_NAME}' database with the backup from:"
echo "  ${BACKUP_FILE}"
echo
read -p "Are you sure you want to proceed? (y/n): " CONFIRM

if [ "${CONFIRM}" != "y" ] && [ "${CONFIRM}" != "Y" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Display restore start message
echo "Starting restore of database '${DB_NAME}' from ${BACKUP_FILE}"

# Drop the existing database (if it exists)
echo "Dropping existing database..."
docker exec -u postgres "$CONTAINER" dropdb --if-exists "$DB_NAME"

# Create a new empty database
echo "Creating new database..."
docker exec -u postgres "$CONTAINER" createdb "$DB_NAME"

# Verify the database was created successfully
echo "Verifying database creation..."
if ! docker exec -u postgres "$CONTAINER" psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "Error: Failed to create the database ${DB_NAME}!"
    exit 1
fi
echo "Database ${DB_NAME} created successfully."

# Copy the backup file into the container
TEMP_BACKUP_PATH="/tmp/$(basename "$BACKUP_FILE")"
echo "Copying backup file to container..."
docker cp "$BACKUP_FILE" "$CONTAINER":"$TEMP_BACKUP_PATH"

# Restore the database from the backup
echo "Restoring from backup..."
docker exec -u postgres "$CONTAINER" pg_restore -d "$DB_NAME" -v "$TEMP_BACKUP_PATH"
RESTORE_STATUS=$?

# Clean up the temporary file in the container
echo "Cleaning up temporary files..."
docker exec "$CONTAINER" rm "$TEMP_BACKUP_PATH"

# Check if restore was successful
if [ $RESTORE_STATUS -eq 0 ]; then
    echo "Restore completed successfully!"
elif [ $RESTORE_STATUS -eq 1 ]; then
    echo "Restore completed with some warnings. The database should still be usable."
else
    echo "Restore completed with some errors. Please check the output above."
    exit 1
fi

echo "Database ${DB_NAME} has been restored from ${BACKUP_FILE}"
exit 0
