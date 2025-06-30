#!/bin/bash
# restore_latest_backup.sh: Restore from the latest backup
# Usage: bash backups/restore_latest_backup.sh

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKUP_FILE="backups/ai_ethical_dm_backup_20250609_191443.dump"
CONTAINER=proethica-postgres
DB_NAME=ai_ethical_dm
DB_USER=postgres

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
WORLD_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM worlds WHERE id = 1;" | tr -d ' ')
if [ "$WORLD_COUNT" -gt 0 ]; then
  echo -e "${GREEN}✓ World 1 (Engineering) found${NC}"
else
  echo -e "${RED}✗ World 1 not found${NC}"
fi

# Verify ontologies
ONTOLOGY_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM ontologies;" | tr -d ' ')
echo -e "${GREEN}Found $ONTOLOGY_COUNT ontologies in database${NC}"

# Check guidelines
GUIDELINE_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM guidelines;" | tr -d ' ')
echo -e "${GREEN}Found $GUIDELINE_COUNT guidelines in database${NC}"

# Check documents
DOCUMENT_COUNT=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM documents;" | tr -d ' ')
echo -e "${GREEN}Found $DOCUMENT_COUNT documents in database${NC}"