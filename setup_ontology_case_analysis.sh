#!/bin/bash

# This script sets up the database tables for McLaren's extensional definition analysis
# and processes the NSPE cases using McLaren's approach.

echo "Setting up case analysis tables..."
python scripts/database_migrations/create_extensional_definition_tables.py

echo "Processing NSPE cases..."
python scripts/process_nspe_cases_mclaren.py --cases-file data/nspe_cases.json

echo "Processing modern NSPE cases..."
python scripts/process_nspe_cases_mclaren.py --cases-file data/modern_nspe_cases.json

echo "Done! Case data has been extracted and stored in the database."
