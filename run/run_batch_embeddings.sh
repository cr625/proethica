#!/bin/bash

# Script to run the batch embeddings update with proper environment setup

# Source any environment variables from a .env file if it exists
if [ -f .env ]; then
    echo "Loading environment from .env file"
    set -a
    source .env
    set +a
fi

# Explicitly set SQLAlchemy URI from DATABASE_URL
if [ -n "$DATABASE_URL" ]; then
    export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
    echo "Set SQLALCHEMY_DATABASE_URI from DATABASE_URL: $DATABASE_URL"
fi

# Make sure Flask environment variables are set
export FLASK_APP=run.py
export FLASK_ENV=development

echo "Starting batch section embedding generation..."

# Run the batch embeddings update script
# If running in a virtual environment, ensure we're using it
if [ -d "venv" ] && [ -f "venv/bin/python" ]; then
    echo "Using virtual environment Python"
    venv/bin/python batch_update_embeddings.py
else
    python batch_update_embeddings.py
fi

echo "Script execution completed"
