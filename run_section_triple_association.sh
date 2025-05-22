#!/bin/bash
# This script runs the section triple association process
# It creates the section triple association table if needed and
# associates document sections with relevant ontology triples

# Ensure the script exits on any error
set -e

# Set environment variables if not already set
export DATABASE_URL=${DATABASE_URL:-"postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"}

# Print banner
echo "=================================================="
echo "      SECTION TRIPLE ASSOCIATION PROCESSOR        "
echo "=================================================="
echo "Starting at: $(date)"
echo "DATABASE_URL: $DATABASE_URL"
echo ""

# Create a timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="section_triple_association_${TIMESTAMP}.log"

echo "Logging to: $LOGFILE"
echo ""

# Parse command line arguments
PROCESS_ALL=false
WITH_EMBEDDINGS=false
CASE_ID=""
DOCUMENT_ID=""
SECTION_IDS=""
BATCH_SIZE=50
SIM_THRESHOLD=0.6
DRY_RUN=false

# Process command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --all)
      PROCESS_ALL=true
      shift
      ;;
    --with-embeddings)
      WITH_EMBEDDINGS=true
      shift
      ;;
    --case-id)
      CASE_ID="$2"
      shift
      shift
      ;;
    --document-id)
      DOCUMENT_ID="$2"
      shift
      shift
      ;;
    --section-ids)
      SECTION_IDS="$2"
      shift
      shift
      ;;
    --batch-size)
      BATCH_SIZE="$2"
      shift
      shift
      ;;
    --similarity-threshold)
      SIM_THRESHOLD="$2"
      shift
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Build the command
CMD="python batch_process_section_triples.py"

if $PROCESS_ALL; then
  CMD="$CMD --all"
elif $WITH_EMBEDDINGS; then
  CMD="$CMD --with-embeddings"
elif [ -n "$CASE_ID" ]; then
  CMD="$CMD --case-id $CASE_ID"
elif [ -n "$DOCUMENT_ID" ]; then
  CMD="$CMD --document-id $DOCUMENT_ID"
elif [ -n "$SECTION_IDS" ]; then
  CMD="$CMD --section-ids $SECTION_IDS"
else
  echo "ERROR: No section selection method specified."
  echo "Please use one of: --all, --with-embeddings, --case-id, --document-id, or --section-ids"
  exit 1
fi

CMD="$CMD --batch-size $BATCH_SIZE --similarity-threshold $SIM_THRESHOLD"

if $DRY_RUN; then
  CMD="$CMD --dry-run"
fi

# Print the command
echo "Executing command: $CMD"
echo ""

# Run the command and log output
$CMD 2>&1 | tee $LOGFILE

# Print completion message
echo ""
echo "=================================================="
echo "Section Triple Association Process Complete"
echo "Completed at: $(date)"
echo "Log file: $LOGFILE"
echo "=================================================="
