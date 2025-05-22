#!/bin/bash

# Run the section embedding fix script for all documents or specific document IDs
# This script is used to regenerate embeddings for sections that are missing them

# Load environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

# Set default values
FORCE=false
BATCH_SIZE=20
MODEL="all-MiniLM-L6-v2"
DEVICE=""  # Empty for auto-detection

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --document-id)
            DOCUMENT_ID="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --document-id ID    Process specific document ID (can be specified multiple times)"
            echo "  --force             Force regeneration of all embeddings, even if they exist"
            echo "  --batch-size N      Number of sections to process in each batch (default: 20)"
            echo "  --model NAME        Embedding model to use (default: all-MiniLM-L6-v2)"
            echo "  --device TYPE       Device to use (cpu, cuda, or empty for auto-detection)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build the base command
CMD="python fix_section_embeddings.py --batch-size $BATCH_SIZE --model '$MODEL'"

# Add force flag if needed
if [ "$FORCE" = true ]; then
    CMD="$CMD --force"
fi

# Add device if specified
if [ ! -z "$DEVICE" ]; then
    CMD="$CMD --device $DEVICE"
fi

# If document ID is specified, process just that document
if [ ! -z "$DOCUMENT_ID" ]; then
    echo "Processing document ID: $DOCUMENT_ID"
    $CMD --document-id "$DOCUMENT_ID"
    exit $?
fi

# Otherwise, get a list of all documents that have sections
echo "Fetching list of all documents with sections..."
DOCUMENT_IDS=$(python -c "
import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')

# Connect to database
engine = create_engine(db_url)

try:
    # Get all document IDs that have sections
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT DISTINCT document_id
            FROM document_sections
            ORDER BY document_id
        '''))
        
        # Print document IDs
        for row in result:
            print(row[0])
except Exception as e:
    print(f'Error: {str(e)}', file=sys.stderr)
    sys.exit(1)
")

# Check if we got any document IDs
if [ $? -ne 0 ]; then
    echo "Error fetching document IDs"
    exit 1
fi

if [ -z "$DOCUMENT_IDS" ]; then
    echo "No documents with sections found"
    exit 0
fi

# Process each document
TOTAL_DOCUMENTS=$(echo "$DOCUMENT_IDS" | wc -l)
CURRENT=0
SUCCESS=0
FAILED=0

echo "Found $TOTAL_DOCUMENTS documents with sections"
echo "Processing all documents..."

# Process each document
for DOC_ID in $DOCUMENT_IDS; do
    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$TOTAL_DOCUMENTS] Processing document ID: $DOC_ID"
    
    $CMD --document-id $DOC_ID
    
    if [ $? -eq 0 ]; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAILED=$((FAILED + 1))
        echo "Failed to process document ID: $DOC_ID"
    fi
    
    echo "Progress: $CURRENT/$TOTAL_DOCUMENTS (Success: $SUCCESS, Failed: $FAILED)"
    echo "----------------------------------------"
done

echo "Completed processing all documents"
echo "Total: $TOTAL_DOCUMENTS"
echo "Success: $SUCCESS"
echo "Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
