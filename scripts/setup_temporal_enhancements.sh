#!/bin/bash
# Setup Temporal Enhancements
#
# This script performs all the necessary steps to set up the
# BFO-based temporal enhancements in the ProEthica system:
# 1. Updates the database with temporal fields
# 2. Enhances the MCP server with temporal endpoints
# 3. Runs tests to verify the functionality

set -e  # Exit on any error

# Get the project root directory
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

echo "===================================================="
echo "Setting up temporal enhancements for ProEthica"
echo "===================================================="

# Step 1: Add temporal fields to entity_triples table
echo -e "\n1. Adding temporal fields to database..."
python scripts/add_temporal_fields_to_triples.py

# Step 2: Enhance MCP server with temporal endpoints
echo -e "\n2. Enhancing MCP server with temporal endpoints..."
python mcp/add_temporal_functionality.py

# Step 3: Run tests to verify functionality
echo -e "\n3. Running tests to verify temporal functionality..."
python scripts/test_temporal_functionality.py

echo -e "\n===================================================="
echo "Temporal enhancements setup complete!"
echo "====================================================\n"

echo "To restart the MCP server with temporal functionality:"
echo "  $ ./scripts/restart_mcp_server.sh"
echo ""
echo "To explore timeline data for a scenario, use:"
echo "  http://localhost:5000/api/timeline/<scenario_id>"
echo "  http://localhost:5000/api/temporal_context/<scenario_id>"
echo ""
echo "For testing temporal queries interactively:"
echo "  python scripts/test_temporal_functionality.py"
echo "===================================================="
