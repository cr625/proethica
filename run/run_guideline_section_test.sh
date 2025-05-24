#!/bin/bash
# Script to test the GuidelineSectionService with database connection

# Set environment variables
export FLASK_APP=app
export FLASK_ENV=development
export SQLALCHEMY_DATABASE_URI="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export PYTHONPATH="/workspaces/ai-ethical-dm"

echo "Running test for GuidelineSectionService..."
python test_guideline_section_service.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ TEST PASSED: GuidelineSectionService works correctly"
    echo "The implementation is successful!"
else
    echo "❌ TEST FAILED: GuidelineSectionService test failed"
    echo "Please check the logs for more information."
fi
