#!/bin/bash

# Database restore script for ai_ethical_dm
# This script restores a PostgreSQL database from a backup file

# Configuration
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"
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
dropdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} --if-exists ${DB_NAME}

# Create a new empty database
echo "Creating new database..."
createdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME}

# Restore the database from the backup
echo "Restoring from backup..."
pg_restore -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v "${BACKUP_FILE}"

# Check if restore was successful
if [ $? -eq 0 ]; then
    echo "Restore completed successfully!"
else
    echo "Restore completed with some errors. Please check the output above."
    exit 1
fi

exit 0
