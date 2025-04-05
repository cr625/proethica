#!/bin/bash
# Script to completely drop and recreate the database
# This uses the direct_recreate_db.sql script
# WARNING: This will delete all data in the database!

set -e  # Exit on error

# Default configuration
DB_NAME="ai_ethical_dm"
BACKUP=true
MIGRATE=true
CREATE_ADMIN=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-backup) BACKUP=false; shift ;;
    --no-migrate) MIGRATE=false; shift ;;
    --no-admin) CREATE_ADMIN=false; shift ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --no-backup    Skip creating a backup before dropping the database"
      echo "  --no-migrate   Skip running migrations after recreation"
      echo "  --no-admin     Skip creating admin user"
      echo "  --help, -h     Show this help message"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Function to create a backup
create_backup() {
  echo -e "${YELLOW}Creating database backup...${NC}"
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  BACKUP_NAME="backup_before_drop_${TIMESTAMP}"
  
  if bash backups/backup_database.sh "$BACKUP_NAME"; then
    echo -e "${GREEN}Backup created: backups/${BACKUP_NAME}.dump${NC}"
    return 0
  else
    echo -e "${RED}Failed to create backup!${NC}"
    return 1
  fi
}

# Function to run migrations
run_migrations() {
  echo -e "${YELLOW}Running database migrations...${NC}"
  if flask db upgrade; then
    echo -e "${GREEN}Migrations completed successfully${NC}"
    return 0
  else
    echo -e "${RED}Failed to run migrations!${NC}"
    return 1
  fi
}

# Function to create admin user
create_admin_user() {
  echo -e "${YELLOW}Creating admin user...${NC}"
  if python scripts/create_admin_user.py; then
    echo -e "${GREEN}Admin user created successfully${NC}"
    return 0
  else
    echo -e "${RED}Failed to create admin user!${NC}"
    return 1
  fi
}

# Main execution
echo -e "${RED}WARNING: This will completely drop and recreate the database '${DB_NAME}'${NC}"
echo -e "${RED}All data will be lost!${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
  echo "Operation cancelled."
  exit 0
fi

# Create backup if requested
if $BACKUP; then
  create_backup
  if [ $? -ne 0 ]; then
    read -p "Backup failed. Continue anyway? (yes/no): " CONTINUE
    if [[ "$CONTINUE" != "yes" ]]; then
      echo "Operation cancelled."
      exit 1
    fi
  fi
fi

# Run the SQL script to recreate the database
echo -e "${YELLOW}Dropping and recreating database...${NC}"
if sudo -u postgres psql -f scripts/direct_recreate_db.sql; then
  echo -e "${GREEN}Database dropped and recreated successfully${NC}"
else
  echo -e "${RED}Failed to recreate database!${NC}"
  exit 1
fi

# Run migrations if requested
if $MIGRATE; then
  run_migrations
  if [ $? -ne 0 ]; then
    echo -e "${RED}Migration failed. Database might be in an inconsistent state.${NC}"
    exit 1
  fi
fi

# Create admin user if requested
if $CREATE_ADMIN; then
  create_admin_user
fi

echo -e "\n${GREEN}Database recreation completed!${NC}"
echo -e "✅ Database has been recreated"
if $BACKUP; then
  echo -e "✅ Backup was created before dropping the database"
fi
if $MIGRATE; then
  echo -e "✅ Migrations have been applied"
fi
if $CREATE_ADMIN; then
  echo -e "✅ Admin user has been created"
fi
