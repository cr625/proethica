#!/bin/bash
# Pull internal docs and non-tracked files from OneDrive for cross-machine sync
# Usage: ./scripts/docs_pull.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ONEDRIVE_SYNC="/mnt/c/Users/Chris/OneDrive/onto/proethica-sync"

echo "=== ProEthica Docs Pull ==="
echo "Project: $PROJECT_DIR"
echo "OneDrive: $ONEDRIVE_SYNC"
echo ""

# Check if OneDrive sync directory exists
if [ ! -d "$ONEDRIVE_SYNC" ]; then
    echo "ERROR: OneDrive sync directory not found: $ONEDRIVE_SYNC"
    echo "Run docs_push.sh first to initialize the sync."
    exit 1
fi

# Sync docs-internal (internal documentation and sensitive scripts)
echo "Syncing docs-internal..."
mkdir -p "$PROJECT_DIR/docs-internal"
rsync -av --delete "$ONEDRIVE_SYNC/docs-internal/" "$PROJECT_DIR/docs-internal/"

# Sync .claude directory (agents and commands - not tracked in git)
echo "Syncing .claude..."
mkdir -p "$PROJECT_DIR/.claude"
rsync -av --delete "$ONEDRIVE_SYNC/.claude/" "$PROJECT_DIR/.claude/"

# Sync database_backups (contains sensitive restore scripts)
echo "Syncing database_backups..."
mkdir -p "$PROJECT_DIR/database_backups"
rsync -av --delete "$ONEDRIVE_SYNC/database_backups/" "$PROJECT_DIR/database_backups/"

# Sync CLAUDE.md and PROGRESS.md (project-specific AI context)
echo "Syncing project markdown files..."
[ -f "$ONEDRIVE_SYNC/CLAUDE.md" ] && cp "$ONEDRIVE_SYNC/CLAUDE.md" "$PROJECT_DIR/"
[ -f "$ONEDRIVE_SYNC/PROGRESS.md" ] && cp "$ONEDRIVE_SYNC/PROGRESS.md" "$PROJECT_DIR/"

echo ""
echo "=== Pull complete ==="
echo "Files synced from: $ONEDRIVE_SYNC"
