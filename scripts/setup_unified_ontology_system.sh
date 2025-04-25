#!/bin/bash
# Setup script for the unified ontology system
# This script sets up the database tables, imports base ontologies,
# and processes domain ontology imports.

set -e  # Exit on error

echo "Setting up unified ontology system..."

# Change to the project root directory
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/.."

# 1. Create database tables
echo "Step 1: Creating ontology_imports table and new columns..."
python scripts/standalone_create_tables.py
if [ $? -ne 0 ]; then
    echo "Failed to create necessary database tables. Aborting."
    exit 1
fi
echo "Database tables created successfully."

# 2. Import base ontologies
echo "Step 2: Importing base ontologies (BFO, ProEthica Intermediate)..."
python scripts/standalone_import_base_ontologies.py
if [ $? -ne 0 ]; then
    echo "Failed to import base ontologies. Aborting."
    exit 1
fi
echo "Base ontologies imported successfully."

# 3. Process domain ontology imports
echo "Step 3: Processing domain ontology imports..."
python scripts/standalone_process_domain_imports.py
if [ $? -ne 0 ]; then
    echo "Warning: Some issues occurred during domain ontology import processing."
    # Don't exit - this step might have partial success
fi
echo "Domain ontology imports processed."

echo "Unified ontology system setup complete!"
echo "You may now restart the server to apply the changes."
