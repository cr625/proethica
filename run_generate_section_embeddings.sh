#!/bin/bash
# Run the section embedding generation script for a specific document

if [ $# -eq 0 ]; then
    echo "Usage: $0 <document_id>"
    echo "Example: $0 252"
    exit 1
fi

document_id=$1

echo "Generating embeddings for document $document_id..."
python generate_section_embeddings.py --document-id $document_id

# Check if the command succeeded
if [ $? -eq 0 ]; then
    echo "Embedding generation completed successfully."
    echo "You can now run the section-triple association process:"
    echo "bash run_ttl_section_triple_association.sh --document $document_id --threshold 0.3 --max-matches 10"
else
    echo "Embedding generation failed."
    exit 1
fi
