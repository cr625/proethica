#!/bin/bash
# Script to run the guideline analysis MCP integration test

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Guideline Analysis MCP Integration Test ===${NC}"

# Check if test guideline file exists
if [ ! -f "test_guideline.txt" ]; then
    echo -e "${YELLOW}Warning: test_guideline.txt not found${NC}"
    echo -e "Creating a sample test guideline..."
    
    cat > test_guideline.txt << 'EOL'
# Engineering Ethics Guidelines for AI Development

## Overview
These guidelines outline the ethical principles and professional responsibilities for engineers involved in artificial intelligence development. They are designed to ensure that AI systems are developed with appropriate consideration for safety, privacy, fairness, and social impact.

## Core Principles

### 1. Public Safety and Welfare
Engineers shall hold paramount the safety, health, and welfare of the public when developing AI systems. This includes:
- Conducting thorough risk assessments
- Implementing appropriate safeguards
- Designing systems that prioritize human well-being

### 2. Honesty and Integrity
Engineers shall be honest and impartial in their professional judgments regarding AI development:
- Providing truthful representations of system capabilities and limitations
- Disclosing potential risks and uncertainties
- Avoiding conflicts of interest that compromise professional judgment

### 3. Competence and Continuous Learning
Engineers shall maintain and improve their technical competence in AI development:
- Staying current with technological advancements
- Understanding the societal implications of AI systems
- Seeking interdisciplinary knowledge in ethics, law, and social sciences

### 4. Fairness and Non-Discrimination
Engineers shall ensure AI systems are designed to be fair and avoid discriminatory outcomes:
- Testing for and mitigating harmful biases
- Ensuring equitable access and impact across different communities
- Promoting diversity and inclusion in the development process

## Professional Obligations

### 1. Transparency and Explainability
Engineers shall strive to make AI systems transparent and explainable to users and stakeholders:
- Documenting design choices and data sources
- Providing clear information about how decisions are made
- Enabling meaningful human oversight

### 2. Privacy and Data Protection
Engineers shall respect and protect individual privacy in AI development:
- Minimizing data collection to what is necessary
- Implementing robust data security measures
- Obtaining informed consent for data usage when appropriate

### 3. Accountability
Engineers shall take responsibility for their work on AI systems:
- Establishing clear lines of responsibility
- Creating mechanisms for addressing unintended consequences
- Being responsive to concerns raised by users and affected communities

### 4. Collaboration and Shared Responsibility
Engineers shall recognize that AI development is a collective endeavor:
- Engaging with diverse stakeholders
- Sharing knowledge about risks and best practices
- Contributing to the development of professional standards

## Implementation Guidance

1. Regular ethical reviews should be integrated into the development lifecycle
2. Ethics training should be provided to all team members
3. Whistleblower protections should be established for reporting ethical concerns
4. External auditing of high-risk systems should be conducted before deployment
5. Ongoing monitoring of deployed systems should be maintained

These guidelines should be regularly reviewed and updated as AI technology and its social implications evolve.
EOL
    
    echo -e "${GREEN}Sample test guideline created successfully${NC}"
fi

# Check if the MCP server is running
echo -e "${BLUE}Checking if MCP server is running...${NC}"
if ! curl -s http://localhost:5001 > /dev/null; then
    echo -e "${YELLOW}MCP server not running. Starting it now...${NC}"
    # Start the server in the background
    python mcp/run_enhanced_mcp_server_with_guidelines.py > mcp_server.log 2>&1 &
    # Save the PID
    MCP_PID=$!
    echo -e "${GREEN}MCP server started with PID: ${MCP_PID}${NC}"
    # Give it a moment to start up
    echo -e "${BLUE}Waiting for server to start...${NC}"
    sleep 5
else
    echo -e "${GREEN}MCP server is already running${NC}"
fi

# Make the test script executable if it isn't already
chmod +x test_guideline_mcp_integration.py

# Run the test script
echo -e "${BLUE}Running guideline MCP integration test...${NC}"
python test_guideline_mcp_integration.py

# Check if we started the server and need to clean up
if [ -n "$MCP_PID" ]; then
    echo -e "${BLUE}Stopping the MCP server (PID: ${MCP_PID})...${NC}"
    kill $MCP_PID
    echo -e "${GREEN}MCP server stopped${NC}"
fi

echo -e "${GREEN}Test completed${NC}"
