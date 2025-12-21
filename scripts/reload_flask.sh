#!/bin/bash
# Trigger Flask reload by touching run.py
# Use this after making Python code changes when Flask auto-reload is off

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Touch run.py to trigger reload
touch "$PROJECT_DIR/run.py"

echo "Touched run.py to trigger Flask reload"
echo "Note: If Flask is not in debug mode or auto-reload is disabled,"
echo "you may need to restart the server manually:"
echo "  pkill -f 'python run.py' && cd $PROJECT_DIR && python run.py"
