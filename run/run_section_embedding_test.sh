#!/bin/bash
# Run the section embedding metadata test script with proper environment

# Set up environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export PYTHONPATH=/workspaces/ai-ethical-dm

# Make the test script executable if it's not already
chmod +x test_section_embedding_metadata.py

# Run the test
echo "Running section embedding metadata test..."
python test_section_embedding_metadata.py

# Check the return code
if [ $? -eq 0 ]; then
    echo "Test completed successfully!"
else
    echo "Test failed with errors"
    exit 1
fi
