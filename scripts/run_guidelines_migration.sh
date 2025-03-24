#!/bin/bash
# Script to migrate guidelines from World model to Document model

echo "Starting guidelines migration process..."

# Step 1: Migrate existing guidelines to Document records
echo "Step 1: Migrating existing guidelines to Document records..."
python scripts/migrate_guidelines_to_documents.py

# Check if the migration was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to migrate guidelines to Document records."
    exit 1
fi

echo "Successfully migrated guidelines to Document records."

# Step 2: Remove guidelines_url and guidelines_text fields from World model
echo "Step 2: Removing guidelines fields from World model..."
python scripts/remove_guidelines_fields.py

# Check if the field removal was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to remove guidelines fields from World model."
    exit 1
fi

echo "Successfully removed guidelines fields from World model."

echo "Guidelines migration completed successfully!"
