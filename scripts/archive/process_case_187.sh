#!/bin/bash
# Process case 187 with full ontology enrichment directly
# This script adds McLaren extensional definitions directly for case 187

# Set up environment
echo "Setting up environment..."
source .env 2>/dev/null || echo "No .env file found, using default environment"

echo "Processing Case 187: Acknowledging Errors in Design"
echo "Adding McLaren extensional definition triples..."
echo ""

# Instead of relying on the scraper, we'll directly add McLaren extensional triples
echo "Generating Python script to add McLaren extensional triples..."
cat > add_mclaren_triples.py << 'EOF'
#!/usr/bin/env python3
"""
Add McLaren extensional definition triples to case 187
"""

import sys
import os
import logging

# Add parent directory to path to import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import Flask app to create application context
from app import create_app

# Create app instance
app = create_app()

# Import the McLaren extensions module
from nspe_pipeline.utils.mclaren_extensions import add_mclaren_extensional_triples
from app.services.application_context_service import ApplicationContextService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("add_mclaren_triples")

def main():
    """Add McLaren extensional triples to case 187."""
    case_id = 187
    
    logger.info(f"Adding McLaren extensional definition triples to case {case_id}")
    
    # Use application context to interact with the database
    with app.app_context():
        app_context = ApplicationContextService()
        result = add_mclaren_extensional_triples(case_id, app_context)
        
    if result['success']:
        logger.info(f"Successfully added {result['triple_count']} McLaren extensional definition triples to case {case_id}")
        return 0
    else:
        logger.error(f"Failed to add McLaren extensional triples: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF

# Make the script executable
chmod +x add_mclaren_triples.py

# Run the script to add McLaren triples
python add_mclaren_triples.py

# Clean up temporary file
rm add_mclaren_triples.py

echo ""
echo "Process completed!"
echo "The case now includes McLaren extensional definition triples for principles"
echo ""
echo "You can view the case at: http://localhost:5000/cases/187"
