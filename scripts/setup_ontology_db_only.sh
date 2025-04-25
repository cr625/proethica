#!/bin/bash
# Script to migrate from file-based ontologies to database-only ontologies
# This combines the complete migration process into one script

set -e  # Exit on error

# Get base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$BASE_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}===== ProEthica Ontology Database Migration =====${NC}"
echo -e "This script will migrate all ontologies to be database-only"
echo -e "${YELLOW}Make sure the application is running with an active database connection${NC}"
echo

# Check prerequisites
echo -e "${BOLD}Step 1: Checking prerequisites...${NC}"
if ! python scripts/check_ontologies_in_db.py >/dev/null 2>&1; then
    echo -e "${RED}Error: Cannot access ontologies in database${NC}"
    echo "Run this command to import ontologies to database first:"
    echo "    python scripts/migrate_ontologies_to_db.py"
    exit 1
fi

echo -e "${GREEN}✓ Database connection and ontologies verified${NC}"

# Verify user wants to proceed
echo
echo -e "${YELLOW}WARNING: This process will modify the MCP server to load ontologies from database${NC}"
echo -e "${YELLOW}and replace original TTL files with placeholders.${NC}"
echo
read -p "Do you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Operation cancelled${NC}"
    exit 1
fi

# Archive original files
echo
echo -e "${BOLD}Step 2: Archiving original TTL files...${NC}"
ARCHIVE_DIR="ontologies_archive_$(date +%Y%m%d_%H%M%S)"
python scripts/archive_ontology_files.py --dir "$ARCHIVE_DIR"

echo -e "${GREEN}✓ Original TTL files archived to $ARCHIVE_DIR${NC}"

# Update MCP server to load from database
echo
echo -e "${BOLD}Step 3: Updating MCP server to load ontologies from database...${NC}"
python scripts/update_ontology_mcp_server.py

echo -e "${GREEN}✓ MCP server updated${NC}"

# Replace TTL files with placeholders
echo
echo -e "${BOLD}Step 4: Replacing TTL files with placeholders...${NC}"
python scripts/remove_ontology_files.py

echo -e "${GREEN}✓ TTL files replaced with placeholders${NC}"

# Restart MCP server
echo
echo -e "${BOLD}Step 5: Restarting MCP server...${NC}"
./scripts/restart_mcp_server.sh

echo -e "${GREEN}✓ MCP server restarted${NC}"

# Summary
echo
echo -e "${BOLD}===== Migration Complete =====${NC}"
echo -e "The system is now configured to use ontologies from the database."
echo -e "Original files are archived in: ${GREEN}$ARCHIVE_DIR${NC}"
echo
echo -e "To verify the migration, run:"
echo "    python scripts/check_ontologies_in_db.py"
echo
echo -e "If you encounter any issues, refer to the migration guide at:"
echo -e "${GREEN}docs/ontology_file_migration_guide.md${NC}"
echo
