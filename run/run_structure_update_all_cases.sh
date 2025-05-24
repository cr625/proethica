#!/bin/bash
# Script to update all case documents with document structure annotations
# Implements Phase 2.4 of the document structure enhancement plan

echo "==============================================="
echo "Document Structure Annotation Update Tool"
echo "Version 1.0 - May 20, 2025"
echo "==============================================="
echo ""
echo "This script will update all case documents in the database"
echo "with document structure annotations based on the ProEthica ontology."
echo ""
echo "The update process:"
echo "  1. Processes all case study documents in the database"
echo "  2. Generates document structure RDF triples for each case"
echo "  3. Prepares section-level embedding metadata"
echo "  4. Updates the doc_metadata in the database"
echo ""
echo "First, performing a dry run to estimate the scope of changes..."
echo ""

# Run in dry-run mode first
python update_document_structure_storage.py --dry-run

echo ""
echo "==============================================="
echo "The above is a DRY RUN and no changes were made to the database."
echo "To proceed with the actual update, press ENTER."
echo "To cancel, press CTRL+C."
echo "==============================================="
read -p "Press ENTER to continue or CTRL+C to cancel... "

echo ""
echo "Starting database update..."
echo ""

# Run the actual update
python update_document_structure_storage.py

echo ""
echo "==============================================="
echo "Update complete. To verify a specific case, use:"
echo "python check_case_structure.py <case_id>"
echo "==============================================="
