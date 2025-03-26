#!/bin/bash
# Demo workflow script to demonstrate the process of adding cases and using them in the agent-based system

# Set the world ID (default: 2 for Engineering Ethics (US) world)
WORLD_ID=2

# Set colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== AI Ethical Decision-Making Simulator: Case Studies Demo ===${NC}\n"

# Step 1: Process a case study
echo -e "${YELLOW}Step 1: Processing a case study from NSPE website...${NC}"
python utilities/test_process_case.py --world-id $WORLD_ID --case-index 0
echo -e "\n${GREEN}Case study processed successfully!${NC}\n"

# Step 2: Process another case study
echo -e "${YELLOW}Step 2: Processing another case study...${NC}"
python utilities/test_process_case.py --world-id $WORLD_ID --case-index 1
echo -e "\n${GREEN}Second case study processed successfully!${NC}\n"

# Step 3: Process a third case study
echo -e "${YELLOW}Step 3: Processing a third case study...${NC}"
python utilities/test_process_case.py --world-id $WORLD_ID --case-index 2
echo -e "\n${GREEN}Third case study processed successfully!${NC}\n"

# Step 4: Retrieve cases to verify they were added
echo -e "${YELLOW}Step 4: Retrieving cases to verify they were added...${NC}"
python utilities/retrieve_cases.py --world-id $WORLD_ID --limit 5
echo -e "\n${GREEN}Cases retrieved successfully!${NC}\n"

# Step 5: Use the CasesAgent demo to analyze a decision
echo -e "${YELLOW}Step 5: Using the CasesAgent demo to analyze a decision...${NC}"
python utilities/cases_agent_demo.py --world-id $WORLD_ID --decision "Should the engineer report a potential safety issue with a bridge design to the public authorities?"
echo -e "\n${GREEN}Decision analyzed successfully!${NC}\n"

# Step 6: Use the CasesAgent demo to analyze another decision
echo -e "${YELLOW}Step 6: Using the CasesAgent demo to analyze another decision...${NC}"
python utilities/cases_agent_demo.py --world-id $WORLD_ID --decision "Should the engineer accept a gift from a vendor who is bidding on a project?"
echo -e "\n${GREEN}Second decision analyzed successfully!${NC}\n"

echo -e "${BLUE}=== Demo Completed Successfully ===${NC}"
echo -e "You have now seen how to add case studies to the database and use them in the agent-based system."
echo -e "This workflow demonstrates the foundation for the CasesAgent in the agent-based architecture."
echo -e "For more information, see the README.md file in the utilities directory."
