#!/bin/bash
# Push internal docs and non-tracked files to OneDrive for cross-machine sync
# Usage: ./scripts/docs_push.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ONEDRIVE_SYNC="/mnt/c/Users/Chris/OneDrive/onto/proethica-sync"

echo "=== ProEthica Docs Push ==="
echo "Project: $PROJECT_DIR"
echo "OneDrive: $ONEDRIVE_SYNC"
echo ""

# Create OneDrive sync directory if it doesn't exist
mkdir -p "$ONEDRIVE_SYNC"

# Sync docs-internal (internal documentation and sensitive scripts)
echo "Syncing docs-internal..."
rsync -av --delete "$PROJECT_DIR/docs-internal/" "$ONEDRIVE_SYNC/docs-internal/"

# Sync .claude directory (agents and commands - not tracked in git)
echo "Syncing .claude..."
rsync -av --delete "$PROJECT_DIR/.claude/" "$ONEDRIVE_SYNC/.claude/"

# Sync database_backups (contains sensitive restore scripts)
echo "Syncing database_backups..."
rsync -av --delete "$PROJECT_DIR/database_backups/" "$ONEDRIVE_SYNC/database_backups/"

# Sync CLAUDE.md and PROGRESS.md (project-specific AI context)
echo "Syncing project markdown files..."
[ -f "$PROJECT_DIR/CLAUDE.md" ] && cp "$PROJECT_DIR/CLAUDE.md" "$ONEDRIVE_SYNC/"
[ -f "$PROJECT_DIR/PROGRESS.md" ] && cp "$PROJECT_DIR/PROGRESS.md" "$ONEDRIVE_SYNC/"

echo ""
echo "=== Push complete ==="
echo "Files synced to: $ONEDRIVE_SYNC"
