#!/bin/bash
# Script to run the pgvector section embedding migration and tests

set -e  # Exit on any error

echo "=== Starting pgvector section embedding migration and tests ==="
echo ""

# 1. Create document_sections table
echo "Step 1: Creating document_sections table with pgvector support..."
python migration_document_sections.py
echo "✓ Document sections table created successfully"
echo ""

# 2. Migrate existing data
echo "Step 2: Migrating existing section data to document_sections table..."
python migrate_section_data.py
echo "✓ Data migration completed successfully"
echo ""

# 3. Run tests to verify implementation
echo "Step 3: Running tests to verify pgvector section embedding implementation..."
python test_pgvector_section_embeddings.py
echo "✓ Tests completed successfully"
echo ""

echo "=== pgvector section embedding migration completed successfully ==="
echo ""
echo "The system now uses pgvector for more efficient section embeddings and similarity search."
echo "Section data is stored in the document_sections table, and metadata in document.doc_metadata has been updated with storage_type: 'pgvector'."
