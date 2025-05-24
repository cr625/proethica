#!/bin/bash
# Run the section embeddings metadata migration script with proper environment

# Set up environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
export PYTHONPATH=/workspaces/ai-ethical-dm

# Check if dry run flag is provided
DRY_RUN=""
if [ "$1" == "--dry-run" ]; then
    DRY_RUN="--dry-run"
    echo "Running in DRY RUN mode - no changes will be made to the database"
fi

# Run the migration script
echo "Starting section embeddings metadata migration..."
python migrate_section_embeddings_metadata.py $DRY_RUN

# Check the return code
if [ $? -eq 0 ]; then
    echo "Migration completed successfully"
else
    echo "Migration failed with errors"
    exit 1
fi

echo "Done"
