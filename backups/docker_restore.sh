#!/bin/bash
# Script to restore database from a backup file to a Docker PostgreSQL container

set -e  # Exit on error

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the backup file from argument or use default
BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo -e "${YELLOW}No backup file specified, using latest backup.${NC}"
    BACKUP_FILE=$(ls -t ./ai_ethical_dm_backup_*.dump | head -1)
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file '$BACKUP_FILE' not found!${NC}"
    exit 1
fi

# Docker container name
CONTAINER_NAME="proethica-postgres"

# Check if container is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}Error: Docker container '$CONTAINER_NAME' is not running!${NC}"
    echo -e "${YELLOW}Please start the container first with: docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}Backup file: $BACKUP_FILE${NC}"
echo -e "${YELLOW}This will restore the database in the Docker container.${NC}"
echo -e "${RED}WARNING: This will overwrite any existing data in the database!${NC}"
echo -n "Do you want to proceed? (y/n): "
read -r confirm

if [ "$confirm" != "y" ]; then
    echo -e "${YELLOW}Database restore cancelled.${NC}"
    exit 0
fi

# Copy backup file to Docker container
echo -e "${GREEN}Copying backup file to Docker container...${NC}"
docker cp "$BACKUP_FILE" $CONTAINER_NAME:/tmp/backup.dump

# Drop and recreate database
echo -e "${GREEN}Dropping and recreating database...${NC}"
docker exec -it $CONTAINER_NAME psql -U postgres -c "DROP DATABASE IF EXISTS ai_ethical_dm;"
docker exec -it $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE ai_ethical_dm;"
docker exec -it $CONTAINER_NAME psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Restore backup with pg_restore
echo -e "${GREEN}Restoring database from backup...${NC}"
docker exec -it $CONTAINER_NAME bash -c "pg_restore -U postgres -O -x -v -d ai_ethical_dm /tmp/backup.dump"

# Check if restore was successful
RESTORE_STATUS=$?
if [ $RESTORE_STATUS -eq 0 ]; then
    echo -e "${GREEN}Database restored successfully!${NC}"
elif [ $RESTORE_STATUS -eq 1 ]; then
    echo -e "${YELLOW}Database restored with some warnings/errors.${NC}"
    echo -e "${YELLOW}This is often expected with pg_restore, especially for constraints and ownership issues.${NC}"
else
    echo -e "${RED}Database restore failed with errors.${NC}"
    exit $RESTORE_STATUS
fi

# Clean up
echo -e "${GREEN}Cleaning up...${NC}"
docker exec -it $CONTAINER_NAME bash -c "rm /tmp/backup.dump"

echo -e "${GREEN}Database restore completed.${NC}"
