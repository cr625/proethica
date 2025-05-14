#!/bin/bash
# Script to execute the complete workflow for testing the improved NSPE case pipeline
# 1. Delete Case 187 (if it exists)
# 2. Import Case 187 with the improved triple handling
# 3. Display success message

# Set up terminal colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}===========================================================${NC}"
echo -e "${YELLOW}  Testing Improved NSPE Case Pipeline with Triple Handling  ${NC}"
echo -e "${YELLOW}===========================================================${NC}"
echo ""

# Step 1: Delete Case 187 if it exists
echo -e "${YELLOW}Step 1: Deleting existing Case 187 (if it exists)...${NC}"
python delete_case_187.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully removed Case 187 and associated triples${NC}"
else
    echo -e "${RED}✗ Error during Case 187 deletion. Check the logs above.${NC}"
    echo -e "${YELLOW}Continuing with import anyway...${NC}"
fi

echo ""

# Step 2: Import Case 187 with improved triple handling
echo -e "${YELLOW}Step 2: Importing Case 187 with improved triple handling...${NC}"
python import_improved_case_187.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully imported Case 187 with enhanced triples${NC}"
else
    echo -e "${RED}✗ Error during Case 187 import. Check the logs above.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}  Pipeline Testing Complete! ${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo -e "The case can be viewed at: http://127.0.0.1:3333/cases/187"
echo -e "Note: Make sure the ProEthica server is running"
echo ""
echo -e "The improved pipeline now:"
echo -e "  - Creates proper McLaren extensional definition triples"
echo -e "  - Adds engineering ethics ontology triples"
echo -e "  - Enhances the UI display with color-coded triples"
echo ""
echo -e "${YELLOW}Don't forget to check both the triple display and case details${NC}"

exit 0
