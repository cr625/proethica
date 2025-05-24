#!/bin/bash
# Script to run the cascade delete test with proper environment setup

# Set up environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export SQLALCHEMY_DATABASE_URI="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"  
export PYTHONPATH=/workspaces/ai-ethical-dm

# Make the test script executable if it's not already
chmod +x test_cascade_delete.py

# Run the test
echo "Running cascade delete test..."
python test_cascade_delete.py

# Check the return code
if [ $? -eq 0 ]; then
    echo "Cascade delete test completed successfully!"
else
    echo "Cascade delete test failed"
    exit 1
fi
