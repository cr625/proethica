#!/bin/bash
# Process an example NSPE case with full ontology enrichment
# This script demonstrates world entity integration and McLaren extensional definitions

# Set up environment
echo "Setting up environment..."
source .env 2>/dev/null || echo "No .env file found, using default environment"

# Check if we have a world ID to use
if [ "$#" -eq 1 ]; then
    WORLD_ID=$1
    echo "Using provided world ID: $WORLD_ID"
else
    # Default world ID - you may need to change this to match an existing world in your system
    WORLD_ID=1
    echo "Using default world ID: $WORLD_ID. Override by passing a world ID as parameter."
fi

# Define the example case URL
CASE_URL="https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design"
echo "Processing case: Acknowledging Errors in Design"
echo "URL: $CASE_URL"

# Run the processing pipeline with world integration
echo "Running processing pipeline with world entity integration and McLaren extensional definitions..."
cd nspe-pipeline || exit

# World integration and McLaren triples are enabled by default now
python process_nspe_case.py "$CASE_URL" --world-id="$WORLD_ID"

# Processing complete
echo ""
echo "Processing complete. Check the output above for integration results."
echo "To view the case, start the application and navigate to the URL shown above."
echo ""
echo "The case now includes:"
echo "1. Regular semantic triples from the case content"
echo "2. World entity integration triples linking to ontology"
echo "3. McLaren extensional definition triples for principles"
echo ""
echo "To compare world entities before and after integration:"
echo "1. Visit http://localhost:5000/worlds/$WORLD_ID before running this script"
echo "2. Take a screenshot or note the entities"
echo "3. Run this script"
echo "4. Visit http://localhost:5000/worlds/$WORLD_ID again to see new entities"
