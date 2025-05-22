#!/bin/bash
# Run the list_guidelines.py script with database configuration

# Ensure we're in the right directory
cd "$(dirname "$0")/../.."

# Set environment variables if needed
if [ -f .env ]; then
  source .env
fi

# Make sure DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
  # Default database URL for development
  export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
  echo "Using default DATABASE_URL. Set this in .env for production use."
fi

echo "Using DATABASE_URL: $DATABASE_URL"

# Run the script
python -m scripts.triple_toolkit.list_guidelines "$@"
