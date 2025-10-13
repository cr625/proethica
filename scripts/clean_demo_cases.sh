#!/bin/bash

# Clean Demo Cases Script
# Removes all extraction data for specified cases from both ProEthica and OntServe
# to allow fresh analysis from scratch
#
# Usage: ./scripts/clean_demo_cases.sh 8 10 13

set -e  # Exit on error

if [ -z "$1" ]; then
    echo "Usage: $0 <case_id> [case_id...]"
    echo ""
    echo "Example:"
    echo "  ./scripts/clean_demo_cases.sh 8 10 13"
    exit 1
fi

CASES="$@"

echo "================================================"
echo "ProEthica Demo Cases Cleanup Script"
echo "================================================"
echo ""
echo "Cases to clean: $CASES"
echo ""
echo "WARNING: This will DELETE all extraction data for these cases!"
echo "  - ProEthica database (temporary_rdf_storage, extraction_prompts)"
echo "  - OntServe case ontologies (proethica-case-X)"
echo ""
read -p "Continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo ""
    echo "Cleanup cancelled"
    exit 0
fi

echo ""

# Clean each case
for CASE_ID in $CASES; do
    echo "================================================"
    echo "Cleaning Case $CASE_ID"
    echo "================================================"
    echo ""

    # 1. Clean ProEthica database
    echo "[Case $CASE_ID] Cleaning ProEthica database..."

    # Count entities before deletion
    ENTITY_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c \
        "SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id = $CASE_ID;" | xargs)
    PROMPT_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -t -c \
        "SELECT COUNT(*) FROM extraction_prompts WHERE case_id = $CASE_ID;" | xargs)

    echo "  → Found $ENTITY_COUNT entities in temporary_rdf_storage"
    echo "  → Found $PROMPT_COUNT prompts in extraction_prompts"

    # Delete from ProEthica
    PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c \
        "DELETE FROM temporary_rdf_storage WHERE case_id = $CASE_ID;" > /dev/null
    PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c \
        "DELETE FROM extraction_prompts WHERE case_id = $CASE_ID;" > /dev/null

    echo "  ✓ Deleted $ENTITY_COUNT entities from temporary_rdf_storage"
    echo "  ✓ Deleted $PROMPT_COUNT prompts from extraction_prompts"
    echo ""

    # 2. Clean OntServe case ontology (if exists)
    echo "[Case $CASE_ID] Cleaning OntServe case ontology..."

    ONTOLOGY_NAME="proethica-case-$CASE_ID"

    # Check if ontology exists in OntServe
    ONT_EXISTS=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve_db -t -c \
        "SELECT COUNT(*) FROM ontologies WHERE name = '$ONTOLOGY_NAME';" 2>/dev/null | xargs || echo "0")

    if [ "$ONT_EXISTS" -gt 0 ]; then
        # Count entities before deletion
        ONT_ENTITY_COUNT=$(PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve_db -t -c \
            "SELECT COUNT(*) FROM ontology_entities WHERE namespace LIKE '%case-$CASE_ID%';" 2>/dev/null | xargs || echo "0")

        echo "  → Found ontology '$ONTOLOGY_NAME' with $ONT_ENTITY_COUNT entities"

        # Delete ontology entities
        PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve_db -c \
            "DELETE FROM ontology_entities WHERE namespace LIKE '%case-$CASE_ID%';" > /dev/null 2>&1 || true

        # Delete ontology metadata
        PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve_db -c \
            "DELETE FROM ontologies WHERE name = '$ONTOLOGY_NAME';" > /dev/null 2>&1 || true

        echo "  ✓ Deleted case ontology from OntServe"
    else
        echo "  → No case ontology found in OntServe (this is normal)"
    fi

    echo ""
    echo "[Case $CASE_ID] ✓ Cleanup complete"
    echo ""
done

# Summary
echo "================================================"
echo "CLEANUP SUMMARY"
echo "================================================"
echo ""
echo "✓ All specified cases have been cleaned"
echo ""
echo "Cleaned cases: $CASES"
echo ""
echo "Next steps:"
echo "  1. Navigate to ProEthica: http://localhost:5000"
echo "  2. Run fresh analysis for each case:"
for CASE_ID in $CASES; do
    echo "     - Case $CASE_ID Step 1: http://localhost:5000/scenario_pipeline/case/$CASE_ID/step1"
done
echo ""
echo "  3. Follow with Step 2, Step 3, and Step 4 for each case"
echo ""
