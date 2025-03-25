#!/bin/bash
# Run the application with Gunicorn for better stability
# Usage: ./run_with_gunicorn.sh

# Set the number of worker processes
WORKERS=4

# Set the timeout (in seconds)
# This is increased from the default 30 seconds to accommodate longer processing times
TIMEOUT=120

# Run Gunicorn with the specified settings
echo "Starting AI Ethical DM with Gunicorn ($WORKERS workers, $TIMEOUT second timeout)..."
gunicorn -w $WORKERS -t $TIMEOUT "app:create_app()" --bind 127.0.0.1:8000
