#!/bin/bash
# Script to run the TTL-based section-triple association process with common configurations

# Display usage information
function show_usage {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Run the TTL-based section-triple association process."
    echo
    echo "Options:"
    echo "  -d, --document ID    Process a specific document ID"
    echo "  -s, --sections IDs   Process specific section IDs (space-separated)"
    echo "  -e, --embeddings     Process all sections with embeddings"
    echo "  -t, --threshold NUM  Set similarity threshold (default: 0.6)"
    echo "  -m, --max-matches N  Set maximum matches per section (default: 10)"
    echo "  -b, --batch-size N   Set batch processing size (default: 10)"
    echo "  -o, --output FILE    Save results to JSON file"
    echo "  -j, --json           Output in JSON format"
    echo "  -h, --help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --document 252                 # Process document 252"
    echo "  $0 --sections \"123 124 125\"       # Process sections 123, 124, and 125"
    echo "  $0 --embeddings                   # Process all sections with embeddings"
    echo "  $0 -d 252 -t 0.7 -m 5             # Process document 252 with custom settings"
    echo "  $0 -e -o results.json             # Process all sections with embeddings and save results"
    echo
}

# Default parameters
SIMILARITY=0.6
MAX_MATCHES=10
BATCH_SIZE=10
FORMAT="pretty"
OUTPUT=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--document)
            DOCUMENT_ID="$2"
            shift 2
            ;;
        -s|--sections)
            SECTION_IDS="$2"
            shift 2
            ;;
        -e|--embeddings)
            WITH_EMBEDDINGS=true
            shift
            ;;
        -t|--threshold)
            SIMILARITY="$2"
            shift 2
            ;;
        -m|--max-matches)
            MAX_MATCHES="$2"
            shift 2
            ;;
        -b|--batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -j|--json)
            FORMAT="json"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check that one section selection option is provided
if [[ -z "$DOCUMENT_ID" && -z "$SECTION_IDS" && "$WITH_EMBEDDINGS" != "true" ]]; then
    echo "Error: You must specify either a document ID, section IDs, or --embeddings"
    show_usage
    exit 1
fi

# Build command arguments
CMD="python -m ttl_triple_association.cli"

# Add section selection
if [[ -n "$DOCUMENT_ID" ]]; then
    CMD="$CMD --document-id $DOCUMENT_ID"
elif [[ -n "$SECTION_IDS" ]]; then
    CMD="$CMD --section-ids $SECTION_IDS"
elif [[ "$WITH_EMBEDDINGS" == "true" ]]; then
    CMD="$CMD --with-embeddings"
fi

# Add other options
CMD="$CMD --similarity $SIMILARITY --max-matches $MAX_MATCHES --batch-size $BATCH_SIZE --format $FORMAT"

# Add output file if specified
if [[ -n "$OUTPUT" ]]; then
    CMD="$CMD --output $OUTPUT"
fi

# Display the command being run
echo "Running: $CMD"
echo "----------------------------------------------"

# Execute the command
eval $CMD

# Exit with the same status as the command
exit $?
