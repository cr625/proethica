#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker &>/dev/null; then
  echo "Docker is required on the server. Aborting." >&2
  exit 1
fi

branch=${1:-main}

echo "[deploy] switching to branch: $branch"
if [ -d .git ]; then
  git fetch --all
  git checkout "$branch"
  git pull --ff-only origin "$branch"
else
  echo "[deploy] not a git repo; skipping pull"
fi

echo "[deploy] building images..."
docker compose build

echo "[deploy] starting/updating stack..."
docker compose up -d

echo "[deploy] ensuring pgvector extension..."
docker compose exec -T db psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;" || true

echo "[deploy] recent app logs:"
docker compose logs --since=5m app | tail -n 200
