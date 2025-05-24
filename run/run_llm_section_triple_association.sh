#!/bin/bash
# Run LLM-based section-triple association from the command line

# Set default values
DOCUMENT_ID=""
SIMILARITY_THRESHOLD=0.5
MAX_MATCHES=10
OUTPUT=""
BATCH_SIZE=5

# Function to display usage
function show_usage {
    echo "Usage: $0 [OPTIONS]"
    echo "Run LLM-based section-triple association for document sections."
    echo
    echo "Options:"
    echo "  --document-id ID      Process all sections in the specified document"
    echo "  --section-ids 'ID ID' Process specific section IDs (space-separated list)"
    echo "  --with-embeddings      Process all sections that have embeddings"
    echo "  --similarity FLOAT    Similarity threshold (0-1, default: 0.5)"
    echo "  --max-matches N       Maximum matches per section (default: 10)"
    echo "  --batch-size N        Batch size for processing (default: 5)"
    echo "  --output FILE         Save results to JSON file"
    echo "  --help                Show this help message"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --document-id)
            DOCUMENT_ID="$2"
            shift 2
            ;;
        --section-ids)
            SECTION_IDS="$2"
            shift 2
            ;;
        --with-embeddings)
            WITH_EMBEDDINGS="--with-embeddings"
            shift
            ;;
        --similarity)
            SIMILARITY_THRESHOLD="$2"
            shift 2
            ;;
        --max-matches)
            MAX_MATCHES="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --output)
            OUTPUT="--output $2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$DOCUMENT_ID" && -z "$SECTION_IDS" && -z "$WITH_EMBEDDINGS" ]]; then
    echo "Error: You must provide one of: --document-id, --section-ids, or --with-embeddings"
    show_usage
    exit 1
fi

# Construct the document ID argument if provided
if [[ ! -z "$DOCUMENT_ID" ]]; then
    DOC_ARG="--document-id $DOCUMENT_ID"
fi

# Construct the section IDs argument if provided
if [[ ! -z "$SECTION_IDS" ]]; then
    SECTION_ARG="--section-ids $SECTION_IDS"
fi

# Print information about what we're doing
echo "Running LLM-based section-triple association with:"
if [[ ! -z "$DOCUMENT_ID" ]]; then
    echo "- Document ID: $DOCUMENT_ID"
elif [[ ! -z "$SECTION_IDS" ]]; then
    echo "- Section IDs: $SECTION_IDS"
else
    echo "- Processing all sections with embeddings"
fi
echo "- Similarity threshold: $SIMILARITY_THRESHOLD"
echo "- Max matches: $MAX_MATCHES"
echo "- Batch size: $BATCH_SIZE"
if [[ ! -z "$OUTPUT" ]]; then
    echo "- Saving output to: ${OUTPUT#--output }"
fi

# Run the CLI script with LLM-based association
echo "Starting LLM-based association process..."
python -m ttl_triple_association.cli $DOC_ARG $SECTION_ARG $WITH_EMBEDDINGS \
    --similarity $SIMILARITY_THRESHOLD \
    --max-matches $MAX_MATCHES \
    --batch-size $BATCH_SIZE \
    --use-llm \
    $OUTPUT

# Check the exit status
if [ $? -eq 0 ]; then
    echo "✅ LLM-based section-triple association completed successfully!"
else
    echo "❌ LLM-based section-triple association failed with exit code $?"
    exit 1
fi
