#!/bin/bash

# restore_database_temp.sh: Temporary restore using Docker-based method
# Usage: bash backups/restore_database_temp.sh <backup_file>

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Use the Docker-based restore script
bash "$(dirname "$0")/docker_restore.sh" "$BACKUP_FILE"
