#!/bin/bash
# Script to synchronize changes from production server back to development environment
# This helps ensure dev and production stay in sync when changes are made directly on the server

set -e # Exit on any error

# Variables
PROD_SERVER="209.38.62.85"
PROD_USER="chris"
PROD_APP_DIR="/home/chris/proethica"
LOCAL_APP_DIR="/home/chris/ai-ethical-dm"

# SSH Key Configuration
SSH_KEY_PATH="server_config/proethica_deployment_key"
SSH_OPTIONS="-i ${SSH_KEY_PATH} -o StrictHostKeyChecking=no"

echo "======================================================"
echo "SYNC FROM PRODUCTION SERVER TO DEV ENVIRONMENT"
echo "======================================================"
echo "This script will pull changes from the production server back to your"
echo "local development environment, helping keep them in sync."
echo ""
echo "Source: ${PROD_USER}@${PROD_SERVER}:${PROD_APP_DIR}"
echo "Destination: ${LOCAL_APP_DIR}"
echo ""

# Ask if this is a selective sync or full sync
echo "Do you want to perform a selective sync (specific files/directories)"
echo "or a full sync (all files except excluded ones)?"
echo "1) Selective sync"
echo "2) Full sync"
read -p "Enter your choice (1 or 2): " SYNC_TYPE

# Check for local uncommitted changes
echo "Checking for uncommitted local changes..."
LOCAL_CHANGES=$(git status --porcelain)
if [ -n "$LOCAL_CHANGES" ]; then
    echo "WARNING: You have uncommitted local changes:"
    echo "$LOCAL_CHANGES"
    echo ""
    echo "It's recommended to commit or stash these changes before syncing"
    echo "to avoid potential conflicts or data loss."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Sync cancelled. Please commit or stash your changes first."
        exit 1
    fi
fi

# Determine EXCLUDED_ITEMS
EXCLUDED_ITEMS=(
    ".git/"
    ".env"
    "*.pyc"
    "__pycache__/"
    "venv/"
    "env/"
    ".DS_Store"
    ".vscode/"
    "*.log"
    "*.dump"
)

if [ "$SYNC_TYPE" == "1" ]; then
    # Selective sync
    echo ""
    echo "Available directories on the production server:"
    ssh ${SSH_OPTIONS} ${PROD_USER}@${PROD_SERVER} "find ${PROD_APP_DIR} -maxdepth 1 -type d | sort"
    echo ""
    echo "Enter the directories or files you want to sync, separated by spaces."
    echo "Examples: 'app/templates app/static scripts/production_specific.py'"
    read -p "Items to sync: " SELECTED_ITEMS
    
    # Create a temporary directory for selective sync
    TEMP_DIR=$(mktemp -d)
    echo "Created temporary directory for sync: ${TEMP_DIR}"
    
    # Process each selected item
    for ITEM in $SELECTED_ITEMS; do
        echo "Syncing ${ITEM}..."
        # Create the directory structure in the temp dir
        ITEM_DIR=$(dirname "${TEMP_DIR}/${ITEM}")
        mkdir -p "${ITEM_DIR}"
        
        # Rsync the specific item from production to temp dir
        rsync -avz ${SSH_OPTIONS} \
            ${PROD_USER}@${PROD_SERVER}:${PROD_APP_DIR}/${ITEM} \
            ${TEMP_DIR}/${ITEM}
    done
    
    # Now rsync from temp dir to local app dir
    echo "Syncing from temp directory to local app directory..."
    rsync -avz ${TEMP_DIR}/ ${LOCAL_APP_DIR}/
    
    # Clean up
    rm -rf ${TEMP_DIR}
    echo "Removed temporary directory."
else
    # Full sync with exclusions
    EXCLUDE_ARGS=""
    for ITEM in "${EXCLUDED_ITEMS[@]}"; do
        EXCLUDE_ARGS="${EXCLUDE_ARGS} --exclude='${ITEM}'"
    done
    
    # Add any custom exclusions
    echo ""
    echo "Enter any additional patterns to exclude, separated by spaces."
    echo "Leave blank for no additional exclusions."
    echo "Examples: 'local_config.py credentials.json'"
    read -p "Additional exclusions: " ADDITIONAL_EXCLUSIONS
    
    for ITEM in $ADDITIONAL_EXCLUSIONS; do
        EXCLUDE_ARGS="${EXCLUDE_ARGS} --exclude='${ITEM}'"
    done
    
    # Perform the full sync with exclusions
    echo ""
    echo "Syncing all files from production to local (with exclusions)..."
    
    # Use eval to properly handle the exclude arguments
    eval "rsync -avz --delete ${EXCLUDE_ARGS} ${SSH_OPTIONS} ${PROD_USER}@${PROD_SERVER}:${PROD_APP_DIR}/ ${LOCAL_APP_DIR}/"
fi

echo ""
echo "======================================================"
echo "SYNC COMPLETED"
echo "======================================================"
echo ""
echo "Changes from production have been synced to your local environment."
echo "You may need to restart your local development server if running."
echo ""
echo "It's recommended to review the changes and commit them if appropriate:"
echo "git status                 # See what changed"
echo "git diff                   # Review specific changes"
echo "git add .                  # Stage all changes"
echo "git commit -m \"Sync changes from production\""
