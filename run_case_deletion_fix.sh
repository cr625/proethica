#!/bin/bash
# Script to test and run case deletion fixes

# Set up environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export PYTHONPATH=/workspaces/ai-ethical-dm

# Make the script executable
chmod +x cleanup_cases_with_sections.py

# Function to handle errors
handle_error() {
  echo "ERROR: $1"
  exit 1
}

# Check if cases 238 and 239 exist
echo "Checking if cases 238 and 239 exist..."
python -c "
from sqlalchemy import create_engine, text
import os
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
engine = create_engine(db_url)
with engine.connect() as conn:
    for case_id in [238, 239]:
        result = conn.execute(text('SELECT id, title FROM documents WHERE id = :id'), {'id': case_id})
        row = result.fetchone()
        if row:
            print(f'Case {case_id} exists: {row.title}')
        else:
            print(f'Case {case_id} does not exist')
" || handle_error "Failed to check cases"

# First run in dry-run mode to see what would happen
echo
echo "Running in dry-run mode first..."
./cleanup_cases_with_sections.py 238 239 --dry-run || handle_error "Dry run failed"

# Prompt for confirmation
echo
echo "The above was just a simulation. Do you want to proceed with actual deletion? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Proceeding with deletion..."
    ./cleanup_cases_with_sections.py 238 239 || handle_error "Deletion failed"
    echo "Deletion completed successfully!"
else
    echo "Deletion cancelled."
    exit 0
fi

# Verify that the model update works by attempting to delete another case with sections
echo
echo "Would you like to test the model update with another case? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Please enter a case ID to test deletion with the updated model:"
    read -r test_case_id
    
    if [ -z "$test_case_id" ]; then
        echo "No case ID entered. Skipping test."
    else
        echo "Testing deletion with updated model..."
        echo "Starting Flask shell to test deletion..."
        
        python -c "
from app import db, create_app
from app.models.document import Document
app = create_app()
with app.app_context():
    # Check if case exists
    case = Document.query.get($test_case_id)
    if case:
        print(f'Found case {test_case_id}: {case.title}')
        print(f'This case has {len(case.document_sections)} document sections')
        print('Attempting to delete...')
        try:
            db.session.delete(case)
            db.session.commit()
            print(f'Successfully deleted case {test_case_id} and its sections')
        except Exception as e:
            print(f'Error deleting case: {str(e)}')
            db.session.rollback()
    else:
        print(f'Case {test_case_id} does not exist')
" || handle_error "Model test failed"
    fi
else
    echo "Skipping model test."
fi

echo
echo "Case deletion fix complete."
