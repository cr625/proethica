#!/bin/bash

# This script sets up the PostgreSQL Docker container for GitHub Codespaces
# and restores the database from the latest backup

set -e  # Exit on error

# Check if we're in a GitHub Codespace
if [ "${CODESPACES}" != "true" ]; then
    echo "This script should only be run in GitHub Codespaces"
    exit 1
fi

echo "Setting up PostgreSQL Docker container for GitHub Codespace environment..."

# Configuration
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_PASSWORD="PASS"
DB_PORT="5433"
DB_CONTAINER_NAME="postgres17-pgvector-codespace"
BACKUP_DIR="$(pwd)/backups"

# Find the latest backup
LATEST_BACKUP=$(ls -t ${BACKUP_DIR}/${DB_NAME}_backup_*.dump 2>/dev/null | head -1)

if [ -z "${LATEST_BACKUP}" ]; then
    echo "No backup files found in ${BACKUP_DIR}"
    echo "Will proceed with empty database"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is required but not installed. Please install Docker."
    exit 1
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "${DB_CONTAINER_NAME}"; then
    echo "Container ${DB_CONTAINER_NAME} already exists"
    
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "${DB_CONTAINER_NAME}"; then
        echo "Container is already running"
    else
        echo "Starting existing container..."
        docker start ${DB_CONTAINER_NAME}
    fi
else
    echo "Creating PostgreSQL container..."
    docker run -d --name ${DB_CONTAINER_NAME} \
        -p ${DB_PORT}:5432 \
        -e POSTGRES_PASSWORD=${DB_PASSWORD} \
        -e POSTGRES_DB=${DB_NAME} \
        -v pgvector_data_codespace:/var/lib/postgresql/data \
        pgvector/pgvector:pg17
        
    echo "Waiting for PostgreSQL to start..."
    sleep 5  # Give PostgreSQL time to initialize
fi

# Test the connection
echo "Testing database connection..."
max_retries=10
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if docker exec -e PGPASSWORD=${DB_PASSWORD} ${DB_CONTAINER_NAME} psql -h localhost -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1" > /dev/null 2>&1; then
        echo "Database connection successful!"
        break
    fi
    
    echo "Connection failed, retrying in 2 seconds..."
    sleep 2
    retry_count=$((retry_count + 1))
done

if [ $retry_count -eq $max_retries ]; then
    echo "Failed to connect to the database after multiple attempts"
    exit 1
fi

# Restore from backup if available
if [ -n "${LATEST_BACKUP}" ]; then
    echo "Restoring from latest backup: $(basename ${LATEST_BACKUP})"
    
    # Drop existing database
    docker exec -e PGPASSWORD=${DB_PASSWORD} ${DB_CONTAINER_NAME} dropdb -h localhost -U ${DB_USER} --if-exists ${DB_NAME}
    
    # Create new database
    docker exec -e PGPASSWORD=${DB_PASSWORD} ${DB_CONTAINER_NAME} createdb -h localhost -U ${DB_USER} ${DB_NAME}
    
    # Restore from backup
    cat "${LATEST_BACKUP}" | docker exec -i -e PGPASSWORD=${DB_PASSWORD} ${DB_CONTAINER_NAME} pg_restore -h localhost -U ${DB_USER} -d ${DB_NAME}
    
    echo "Database restore completed"
fi

echo "PostgreSQL setup completed successfully!"
echo "Connection string: postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
echo
echo "You can now start the application with:"
echo "./start_proethica.sh"
