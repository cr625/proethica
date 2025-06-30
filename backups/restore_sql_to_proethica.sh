#!/bin/bash
# restore_sql_to_proethica.sh: Restore SQL backup into proethica database
# Usage: bash backups/restore_sql_to_proethica.sh

set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKUP_FILE="backups/ai_ethical_dm_20250521_202723_with_section_embeddings.sql.gz"
CONTAINER=proethica-postgres
DB_NAME=proethica
DB_USER=postgres

echo -e "${YELLOW}WARNING: This will drop and recreate the $DB_NAME database.${NC}"
echo -e "${YELLOW}Are you sure you want to continue? (y/N)${NC}"
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
  echo -e "${RED}Restore cancelled.${NC}"
  exit 1
fi

echo -e "${GREEN}Dropping and recreating database $DB_NAME...${NC}"
docker exec -u postgres "$CONTAINER" psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec -u postgres "$CONTAINER" psql -c "CREATE DATABASE $DB_NAME;"
docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo -e "${GREEN}Decompressing and restoring SQL backup...${NC}"
gunzip -c "$BACKUP_FILE" | docker exec -i -u postgres "$CONTAINER" psql -d $DB_NAME

echo -e "${GREEN}Database restore complete.${NC}"
echo -e "${GREEN}Verifying world 1 and ontologies...${NC}"

# Verify world 1 exists
WORLD_INFO=$(docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -t -c "SELECT id, name FROM worlds WHERE id = 1;")
if [ -n "$WORLD_INFO" ]; then
  echo -e "${GREEN}✓ World found: $WORLD_INFO${NC}"
else
  echo -e "${RED}✗ World 1 not found${NC}"
fi

# Verify ontologies
echo -e "${GREEN}Ontologies in database:${NC}"
docker exec -u postgres "$CONTAINER" psql -d $DB_NAME -c "SELECT id, name FROM ontologies;"