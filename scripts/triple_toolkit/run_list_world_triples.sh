#!/bin/bash
# Run the list_world_triples.py script with proper Python path setup

# Set root directory (one level up from scripts/triple_toolkit)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Ensure DATABASE_URL is set
if [ -z "$DATABASE_URL" ] && [ -f "$ROOT_DIR/.env" ]; then
    export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
fi

# Default to a standard connection if not set
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
fi

echo "Using DATABASE_URL: $DATABASE_URL"

# Run the script with proper Python path
PYTHONPATH="$ROOT_DIR:$PYTHONPATH" python3 -m scripts.triple_toolkit.list_world_triples "$@"
