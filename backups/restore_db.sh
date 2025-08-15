#!/usr/bin/env bash
# restore_db.sh
# One-stop restore script for the Postgres DB used by this project.
# - Works with Docker container (default) or local psql tools
# - Supports .dump, .sql, .sql.gz
# - Defaults from repo: container=proethica-postgres, db=ai_ethical_dm, user=postgres, host=localhost, port=5433
# Usage examples:
#   bash backups/restore_db.sh backups/ai_ethical_dm_20250809_235352.dump
#   bash backups/restore_db.sh backups/snapshot.sql.gz --db ai_ethical_dm
#   bash backups/restore_db.sh backups/snapshot.sql --mode local --host localhost --port 5433

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Defaults
MODE="docker"                 # docker | local
CONTAINER="proethica-postgres"
DB_NAME="ai_ethical_dm"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5433"
BACKUP_FILE=""

# Try to read password from .env if present
DB_PASS=""
if [ -f "$(dirname "$0")/../.env" ]; then
  DB_PASS=$(grep -E '^DATABASE_URL=' "$(dirname "$0")/../.env" | sed -E 's/.*postgres:([^@]+)@.*/\1/' || true)
elif [ -f "$(dirname "$0")/../../.env" ]; then
  DB_PASS=$(grep -E '^DATABASE_URL=' "$(dirname "$0")/../../.env" | sed -E 's/.*postgres:([^@]+)@.*/\1/' || true)
fi
[ -z "${DB_PASS}" ] && DB_PASS="PASS"

usage() {
  cat <<USAGE
Usage: $0 <backup_file> [--mode docker|local] [--db NAME] [--user USER] [--host HOST] [--port PORT] [--container NAME] [--no-prompt]

Examples:
  $0 backups/ai_ethical_dm_20250809_235352.dump
  $0 backups/snapshot.sql.gz --db ai_ethical_dm
  $0 backups/snapshot.sql --mode local --host localhost --port 5433
USAGE
}

NO_PROMPT="false"

# Parse args
if [ $# -lt 1 ]; then
  usage; exit 1
fi
BACKUP_FILE="$1"; shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2;;
    --db) DB_NAME="$2"; shift 2;;
    --user) DB_USER="$2"; shift 2;;
    --host) DB_HOST="$2"; shift 2;;
    --port) DB_PORT="$2"; shift 2;;
    --container) CONTAINER="$2"; shift 2;;
    --no-prompt) NO_PROMPT="true"; shift;;
    -h|--help) usage; exit 0;;
    *) echo -e "${RED}Unknown arg: $1${NC}"; usage; exit 1;;
  esac
done

# Validate backup file
if [ ! -f "$BACKUP_FILE" ]; then
  # Try relative to backups/
  if [ -f "$(dirname "$0")/$(basename "$BACKUP_FILE")" ]; then
    BACKUP_FILE="$(dirname "$0")/$(basename "$BACKUP_FILE")"
  else
    echo -e "${RED}Backup file not found: $BACKUP_FILE${NC}"; exit 1
  fi
fi

# Confirm
if [ "$NO_PROMPT" != "true" ]; then
  echo -e "${YELLOW}WARNING: This will drop and recreate the ${DB_NAME} database.${NC}"
  read -r -p "Proceed? (y/N): " RESP
  case "$RESP" in
    y|Y) ;;
    *) echo -e "${RED}Cancelled.${NC}"; exit 1;;
  esac
fi

# Helper: drop/create DB and ensure vector extension
create_db_docker() {
  docker exec -u postgres "$CONTAINER" psql -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
  docker exec -u postgres "$CONTAINER" psql -c "CREATE DATABASE \"$DB_NAME\";"
  docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
}
create_db_local() {
  export PGPASSWORD="$DB_PASS"
  dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$DB_NAME" || true
  createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
}

# Restore dispatcher
restore_dump_docker() {
  local tmp="/tmp/$(basename "$BACKUP_FILE")"
  docker cp "$BACKUP_FILE" "$CONTAINER":"$tmp"
  docker exec -u postgres "$CONTAINER" pg_restore -d "$DB_NAME" -v "$tmp"
  docker exec "$CONTAINER" rm -f "$tmp" || true
}
restore_dump_local() {
  export PGPASSWORD="$DB_PASS"
  pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v "$BACKUP_FILE"
}
restore_sql_docker() {
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | docker exec -i -u postgres "$CONTAINER" psql -d "$DB_NAME"
  else
    cat "$BACKUP_FILE" | docker exec -i -u postgres "$CONTAINER" psql -d "$DB_NAME"
  fi
}
restore_sql_local() {
  export PGPASSWORD="$DB_PASS"
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
  else
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$BACKUP_FILE"
  fi
}

# Ensure docker container is running when in docker mode
if [ "$MODE" = "docker" ]; then
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}Container '${CONTAINER}' is not running.${NC}"
    echo "Start it with: docker compose up -d (from project root)"
    exit 1
  fi
fi

# Create DB fresh
echo -e "${GREEN}Resetting database '${DB_NAME}' (${MODE} mode)...${NC}"
if [ "$MODE" = "docker" ]; then
  create_db_docker
else
  create_db_local
fi

# Restore based on file type
echo -e "${GREEN}Restoring from ${BACKUP_FILE}...${NC}"
if [[ "$BACKUP_FILE" == *.dump ]]; then
  if [ "$MODE" = "docker" ]; then restore_dump_docker; else restore_dump_local; fi
elif [[ "$BACKUP_FILE" == *.sql || "$BACKUP_FILE" == *.sql.gz ]]; then
  if [ "$MODE" = "docker" ]; then restore_sql_docker; else restore_sql_local; fi
else
  echo -e "${RED}Unsupported backup type: $BACKUP_FILE${NC}"; exit 1
fi

# Basic sanity checks
echo -e "${GREEN}Verifying restored data...${NC}"
if [ "$MODE" = "docker" ]; then
  docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM worlds;" | tr -d ' \n' | awk '{print "worlds count:" $0}'
  docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM ontologies;" | tr -d ' \n' | awk '{print " ontologies count:" $0}'
else
  export PGPASSWORD="$DB_PASS"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM worlds;" | tr -d ' \n' | awk '{print "worlds count:" $0}'
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM ontologies;" | tr -d ' \n' | awk '{print " ontologies count:" $0}'
fi

echo -e "${GREEN}Restore complete.${NC}"
