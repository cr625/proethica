#!/bin/bash
# restore_to_proethica.sh: Restore ai_ethical_dm database backup into proethica database
# Usage: bash backups/restore_to_proethica.sh <backup_file>

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKUP_FILE="$1"
CONTAINER=proethica-postgres
DB_NAME=proethica
DB_USER=postgres

if [ -z "$BACKUP_FILE" ]; then
  echo -e "${RED}Usage: $0 <backup_file>${NC}"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo -e "${RED}Backup file $BACKUP_FILE does not exist!${NC}"
  exit 1
fi

echo -e "${YELLOW}WARNING: This will drop and recreate the $DB_NAME database.${NC}"
echo -e "${YELLOW}Are you sure you want to continue? (y/N)${NC}"
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
  echo -e "${RED}Restore cancelled.${NC}"
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

echo -e "${GREEN}Cleaning up temporary file...${NC}"
docker exec "$CONTAINER" rm /tmp/backup.dump

echo -e "${GREEN}Database restore complete.${NC}"
echo -e "${GREEN}Verifying world 1 and ontologies...${NC}"

# Verify world 1 exists
WORLD_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM worlds WHERE id = 1;")
if [ "$WORLD_COUNT" -gt 0 ]; then
  echo -e "${GREEN}✓ World 1 (Engineering) found${NC}"
else
  echo -e "${RED}✗ World 1 not found${NC}"
fi

# Verify ontologies
ONTOLOGY_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM ontologies;")
echo -e "${GREEN}Found $ONTOLOGY_COUNT ontologies in database${NC}"