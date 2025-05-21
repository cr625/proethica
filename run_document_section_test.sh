#!/bin/bash
# Script to test the document section cascade delete fix

# Set environment variables
export FLASK_APP=app
export FLASK_ENV=development
export SQLALCHEMY_DATABASE_URI="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export PYTHONPATH="/workspaces/ai-ethical-dm"

echo "Running test for cascade deletion of document sections..."
python test_delete_document_241.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ TEST PASSED: Document section cascade delete works correctly"
    echo "The relationship fix was successful!"
else
    echo "❌ TEST FAILED: Document section cascade delete is not working"
    echo "Further debugging may be required."
fi
