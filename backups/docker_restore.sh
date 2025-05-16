#!/bin/bash
# docker_restore.sh: Restore ai_ethical_dm database from a backup using the running Docker container
# Usage: bash backups/docker_restore.sh <backup_file>

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKUP_FILE="$1"
CONTAINER=proethica-postgres
DB_NAME=ai_ethical_dm
DB_USER=postgres

if [ -z "$BACKUP_FILE" ]; then
  echo -e "${RED}Usage: $0 <backup_file>${NC}"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo -e "${RED}Backup file $BACKUP_FILE does not exist!${NC}"
  exit 1
fi

echo -e "${GREEN}Copying backup file into container...${NC}"
docker cp "$BACKUP_FILE" "$CONTAINER":/tmp/backup.dump

echo -e "${GREEN}Dropping and recreating database $DB_NAME...${NC}"
docker exec -u postgres "$CONTAINER" psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec -u postgres "$CONTAINER" psql -c "CREATE DATABASE $DB_NAME;"
docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo -e "${GREEN}Restoring database from backup...${NC}"
docker exec -u postgres "$CONTAINER" pg_restore -d $DB_NAME /tmp/backup.dump

echo -e "${GREEN}Database restore complete.${NC}"
