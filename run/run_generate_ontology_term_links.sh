#!/bin/bash

# Generate Ontology Term Links - Helper Script
# 
# This script runs the ontology term link generation with common configurations.
# It processes existing documents to identify individual words/phrases that match
# ontology terms and creates linkable annotations.

echo "=== Ontology Term Link Generation ==="
echo "Timestamp: $(date)"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

cd "$(dirname "$0")/.."

# Run with different options based on arguments
case "${1:-help}" in
    "test")
        echo "TEST MODE: Processing first 5 documents only"
        python scripts/generate_ontology_term_links.py --limit 5 --dry-run
        ;;
    "single")
        if [ -z "$2" ]; then
            echo "Error: Please provide document ID"
            echo "Usage: $0 single <document_id>"
            exit 1
        fi
        echo "Processing single document ID: $2"
        python scripts/generate_ontology_term_links.py --document-id "$2"
        ;;
    "world")
        if [ -z "$2" ]; then
            echo "Error: Please provide world ID"
            echo "Usage: $0 world <world_id>"
            exit 1
        fi
        echo "Processing documents from world ID: $2"
        python scripts/generate_ontology_term_links.py --world-id "$2"
        ;;
    "force")
        echo "FORCE MODE: Regenerating all existing term links"
        python scripts/generate_ontology_term_links.py --force
        ;;
    "all")
        echo "Processing all case documents..."
        python scripts/generate_ontology_term_links.py
        ;;
    "help"|*)
        echo "Usage: $0 <mode> [options]"
        echo ""
        echo "Modes:"
        echo "  test              - Dry run on first 5 documents"
        echo "  single <doc_id>   - Process single document"
        echo "  world <world_id>  - Process documents from specific world"
        echo "  force             - Force regeneration of existing links"
        echo "  all               - Process all case documents"
        echo "  help              - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 test                    # Test run"
        echo "  $0 single 18               # Process document ID 18"
        echo "  $0 world 1                 # Process Engineering Ethics world"
        echo "  $0 force                   # Regenerate all links"
        echo "  $0 all                     # Process all documents"
        ;;
esac

echo ""
echo "=== Term Link Generation Complete ==="