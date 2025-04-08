#!/bin/bash

# Database restore script for ai_ethical_dm
# This script restores a PostgreSQL database from a backup file

# Configuration
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"
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

# Verify the database was created successfully
echo "Verifying database creation..."
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -lqt | cut -d \| -f 1 | grep -qw ${DB_NAME}
if [ $? -ne 0 ]; then
    echo "Error: Failed to create the database ${DB_NAME}!"
    exit 1
fi
echo "Database ${DB_NAME} created successfully."

# Restore the database from the backup
echo "Restoring from backup..."
pg_restore -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v "${BACKUP_FILE}"
RESTORE_STATUS=$?

# Check if restore was successful
if [ $RESTORE_STATUS -eq 0 ]; then
    echo "Restore completed successfully!"
elif [ $RESTORE_STATUS -eq 1 ]; then
    echo "Restore completed with some warnings. The database should still be usable."
else
    echo "Restore completed with some errors. Please check the output above."
    exit 1
fi

exit 0
