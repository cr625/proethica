##!/bin/bash
# Direct setup script for ontology-based case analysis using McLaren's extensional definition approach
# This script does not require the Flask application to be running

set -e # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" # Move to the directory containing this script

echo "=== Setting up McLaren's extensional definition case analysis ==="

# Step 1: Check if the database is available
echo "Step 1: Checking database connection..."
if ! psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -c "SELECT 1" > /dev/null 2>&1; then
  echo "Error: Cannot connect to the database. Make sure PostgreSQL is running."
  exit 1
fi
echo "Database connection successful!"

# Step 2: Create the necessary database tables
echo "Step 2: Creating database tables for case analysis..."
python scripts/direct_create_mclaren_tables.py
if [ $? -ne 0 ]; then
  echo "Error: Failed to create database tables."
  exit 1
fi
echo "Database tables created successfully!"

# Step 3: Import NSPE cases into the database
echo "Step 3: Importing NSPE cases..."
python scripts/direct_import_nspe_cases.py
if [ $? -ne 0 ]; then
  echo "Error: Failed to import NSPE cases."
  exit 1
fi
echo "NSPE cases imported successfully!"

# Step 4: Process cases using McLaren's extensional definition approach
echo "Step 4: Processing cases using McLaren's extensional definition approach..."
echo "This may take some time depending on the number of cases..."
python scripts/direct_process_nspe_cases.py --cases-file data/nspe_cases.json --limit 5
if [ $? -ne 0 ]; then
  echo "Error: Failed to process cases."
  exit 1
fi
echo "Cases processed successfully!"

# Step 5: Update the documentation
echo "Step 5: Updating implementation tracker..."
cat > docs/mclaren_implementation_tracker.md << EOF
# McLaren Extensional Definition Implementation Tracker

## Implementation Status ($(date "+%Y-%m-%d"))

| Component | Status | Notes |
|-----------|--------|-------|
| Database schema | ✅ Completed | Tables for principle instantiations, conflicts, etc. |
| Case import | ✅ Completed | NSPE cases imported from JSON files |
| McLaren module | ✅ Completed | McLaren case analysis module created and integrated |
| Principle instantiation | ✅ Completed | Extracts principle instantiations from cases |
| Principle conflicts | ✅ Completed | Identifies conflicts between principles |
| Operationalization techniques | ✅ Completed | Identifies the 9 operationalization techniques |
| Extensional definitions | ✅ Completed | Generates extensional definitions of principles |
| Triple generation | ✅ Completed | Converts analyses to RDF triples |
| Integration with ontology | ✅ Completed | Uses engineering ethics ontology |

## Next Steps

1. Enhance matching accuracy by incorporating ML techniques for better principle detection
2. Implement visualization of extensional definitions in the UI
3. Add cross-case analysis to identify patterns across multiple cases
4. Incorporate user feedback to improve the quality of analyses
5. Develop an interactive interface for exploring the McLaren analysis results
EOF

echo "Implementation tracker updated!"

echo "=== Setup completed successfully! ==="
echo "You can now use the McLaren case analysis module to analyze engineering ethics cases."
