#!/bin/bash
# Setup a cron job to run the fix_document_status.py script periodically
# This will check for and fix any documents that might be stuck in processing state

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$PROJECT_DIR/scripts/fix_document_status.py"
LOG_PATH="$PROJECT_DIR/logs/document_status_fix.log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Check if the script exists and is executable
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found at $SCRIPT_PATH"
    exit 1
fi

if [ ! -x "$SCRIPT_PATH" ]; then
    echo "Making script executable..."
    chmod +x "$SCRIPT_PATH"
fi

# Create a temporary file for the new crontab
TEMP_CRON=$(mktemp)

# Export current crontab
crontab -l > "$TEMP_CRON" 2>/dev/null || echo "# New crontab" > "$TEMP_CRON"

# Check if the cron job already exists
if grep -q "fix_document_status.py" "$TEMP_CRON"; then
    echo "Cron job for document status fix already exists."
else
    # Add the cron job to run every hour
    echo "# Run document status fix script every hour" >> "$TEMP_CRON"
    echo "0 * * * * cd $PROJECT_DIR && $SCRIPT_PATH >> $LOG_PATH 2>&1" >> "$TEMP_CRON"
    
    # Install the new crontab
    crontab "$TEMP_CRON"
    echo "Cron job installed to run every hour."
fi

# Clean up
rm "$TEMP_CRON"

echo "Setup complete. The script will run every hour and log to $LOG_PATH"
echo "To view the current crontab, run: crontab -l"
