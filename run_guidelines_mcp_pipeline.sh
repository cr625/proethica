#!/bin/bash
# Run Guidelines MCP Pipeline
# This script runs the complete pipeline for testing the guidelines MCP integration

# Set up error handling
set -e
echo "Starting Guidelines MCP Pipeline..."

# Check if test_guideline.txt exists
if [ ! -f "test_guideline.txt" ]; then
  echo "Error: test_guideline.txt not found"
  echo "Creating a sample test guideline file..."
  cat > test_guideline.txt << 'EOT'
# Engineering Ethics Guidelines

## Professional Obligations

Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.

Engineers shall perform services only in areas of their competence.

Engineers shall issue public statements only in an objective and truthful manner.

Engineers shall act for each employer or client as faithful agents or trustees.

Engineers shall avoid deceptive acts.

## Professional Conduct

Engineers shall act in such a manner as to uphold and enhance the honor, integrity, and dignity of the engineering profession.

Engineers shall treat all persons with dignity, respect, fairness and without discrimination.

Engineers shall strive to serve the public interest.

## Professional Development

Engineers shall continue their professional development throughout their careers and shall provide opportunities for the professional development of those engineers under their supervision.

## Confidentiality

Engineers shall not disclose, without consent, confidential information concerning the business affairs or technical processes of any present or former client or employer.

## Conflicts of Interest

Engineers shall avoid all known conflicts of interest with their employers or clients and shall promptly inform their employers or clients of any business association, interests, or circumstances which could influence their judgment or the quality of their services.

## Whistleblowing

When engineers have knowledge or reason to believe that another person or firm may be in violation of any of the provisions of these Guidelines, they shall present such information to the proper authority in writing and shall cooperate with the proper authority in furnishing such further information or assistance as may be required.
EOT
  echo "Sample test guideline created."
fi

# Start the MCP server in the background
echo "Starting MCP server..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > mcp_server_log.txt 2>&1 &
SERVER_PID=$!

# Give the server time to start up
echo "Waiting for server to initialize..."
sleep 5

# Fix the client if needed
echo "Making sure the client is using the correct endpoint..."
python fix_test_guideline_mcp_client.py

# Run the client
echo "Running test client..."
python test_guideline_mcp_client.py

# Check if files were created
if [ -f "guideline_concepts.json" ] && [ -f "guideline_triples.json" ]; then
  echo "Pipeline completed successfully!"
  echo "Output files created:"
  echo "- guideline_concepts.json"
  echo "- guideline_matches.json"
  echo "- guideline_triples.json"
  echo "- guideline_triples.ttl"
else
  echo "Pipeline completed but some output files are missing."
fi

# Shutdown the server
echo "Shutting down MCP server..."
kill $SERVER_PID

echo "Done."
