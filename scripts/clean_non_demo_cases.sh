#!/bin/bash

# Clean Non-Demo Cases Script
# Removes all extraction data for cases OTHER than the specified demo cases
# This leaves only the demo cases with analysis data
#
# Usage: ./scripts/clean_non_demo_cases.sh

set -e  # Exit on error

KEEP_CASES="8, 10, 13"

echo "================================================"
echo "ProEthica Non-Demo Cases Cleanup Script"
echo "================================================"
echo ""
echo "This will DELETE extraction data from ALL cases EXCEPT:"
echo "  Cases: $KEEP_CASES"
echo ""

# Get list of cases that will be cleaned
echo "Checking which cases will be cleaned..."
echo ""

CASES_TO_CLEAN=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "
SELECT DISTINCT case_id
FROM temporary_rdf_storage
WHERE case_id NOT IN ($KEEP_CASES)
ORDER BY case_id;
" | xargs)

if [ -z "$CASES_TO_CLEAN" ]; then
    echo "✓ No non-demo cases found with extraction data"
    echo "  Only demo cases ($KEEP_CASES) have data"
    exit 0
fi

echo "Cases to be cleaned: $CASES_TO_CLEAN"
echo ""

# Show details of what will be deleted
echo "Details:"
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT
    t.case_id,
    d.title,
    COUNT(DISTINCT t.id) as entities,
    COUNT(DISTINCT ep.id) as prompts
FROM temporary_rdf_storage t
LEFT JOIN documents d ON t.case_id = d.id
LEFT JOIN extraction_prompts ep ON t.case_id = ep.case_id
WHERE t.case_id NOT IN ($KEEP_CASES)
GROUP BY t.case_id, d.title
ORDER BY t.case_id;
"

echo ""
echo "WARNING: This action cannot be undone!"
read -p "Continue with cleanup? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo ""
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo "Cleaning non-demo cases..."
echo ""

# Delete from temporary_rdf_storage
ENTITY_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "
SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id NOT IN ($KEEP_CASES);
" | xargs)

PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
DELETE FROM temporary_rdf_storage WHERE case_id NOT IN ($KEEP_CASES);
" > /dev/null

echo "✓ Deleted $ENTITY_COUNT entities from temporary_rdf_storage"

# Delete from extraction_prompts
PROMPT_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c "
SELECT COUNT(*) FROM extraction_prompts WHERE case_id NOT IN ($KEEP_CASES);
" | xargs)

PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
DELETE FROM extraction_prompts WHERE case_id NOT IN ($KEEP_CASES);
" > /dev/null

echo "✓ Deleted $PROMPT_COUNT prompts from extraction_prompts"

echo ""
echo "================================================"
echo "CLEANUP COMPLETE"
echo "================================================"
echo ""
echo "✓ Removed extraction data from cases: $CASES_TO_CLEAN"
echo "✓ Preserved demo cases: $KEEP_CASES"
echo ""

# Show remaining cases with data
echo "Remaining cases with extraction data:"
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "
SELECT
    t.case_id,
    d.title,
    COUNT(DISTINCT t.id) as entities,
    COUNT(DISTINCT ep.id) as prompts
FROM temporary_rdf_storage t
LEFT JOIN documents d ON t.case_id = d.id
LEFT JOIN extraction_prompts ep ON t.case_id = ep.case_id
GROUP BY t.case_id, d.title
ORDER BY t.case_id;
"

echo ""
echo "Next steps:"
echo "  1. Verify demo cases look good: http://localhost:5000"
echo "  2. Create database backup: ./scripts/backup_demo_database.sh"
echo "  3. Deploy to production"
echo ""
