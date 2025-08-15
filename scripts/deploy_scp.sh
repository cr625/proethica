#!/usr/bin/env bash
# Package the current workspace (excluding heavy/dev files) and deploy to the droplet via scp/ssh.
# Requires an SSH config Host named 'digitalocean'.
set -euo pipefail

REMOTE_HOST=${REMOTE_HOST:-digitalocean}
REMOTE_DIR=${REMOTE_DIR:-/opt/proethica}
BRANCH=${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo workspace)}
STAMP=$(date +%Y%m%d%H%M%S)
PKG_BASENAME=proethica-${BRANCH}-${STAMP}
PKG_TAR=/tmp/${PKG_BASENAME}.tar
PKG_TAR_GZ=${PKG_TAR}.gz

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[deploy-scp] Packaging workspace from: $ROOT_DIR"
# Create a tar (not gzipped yet) so we can append README.md after excluding md files
# Exclusions: VCS, venv, caches, logs, backups, screenshots, node modules, tests, docs, markdowns (we'll add README.md back)
EXCLUDES=(
  --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.vscode'
  --exclude='logs' --exclude='*.log' --exclude='archive' --exclude='backups' --exclude='screenshots'
  --exclude='node_modules' --exclude='dist' --exclude='build'
  --exclude='tests' --exclude='docs'
  --exclude='**/*.md'
)

# Fresh tar
rm -f "$PKG_TAR" "$PKG_TAR_GZ"

tar cf "$PKG_TAR" "${EXCLUDES[@]}" .
# Re-add README.md explicitly if present
if [ -f README.md ]; then
  tar rf "$PKG_TAR" README.md
fi
# Gzip the tar
gzip -9 "$PKG_TAR"

echo "[deploy-scp] Package created: $PKG_TAR_GZ ($(du -h "$PKG_TAR_GZ" | cut -f1))"

# Upload
echo "[deploy-scp] Uploading to $REMOTE_HOST:/tmp/${PKG_BASENAME}.tar.gz"
scp -q "$PKG_TAR_GZ" "$REMOTE_HOST:/tmp/${PKG_BASENAME}.tar.gz"

# Remote install
cat <<'REMOTE_SCRIPT' > /tmp/proethica_remote_install.sh
set -euo pipefail
PKG="$1"
TARGET_DIR="${2:-/opt/proethica}"
STAMP=$(date +%Y%m%d%H%M%S)
if [ -d "$TARGET_DIR" ]; then
  sudo mkdir -p /opt && sudo chown "$USER":"$USER" /opt || true
  echo "[remote] Backing up existing $TARGET_DIR to ${TARGET_DIR}_bak_${STAMP}"
  sudo mv "$TARGET_DIR" "${TARGET_DIR}_bak_${STAMP}" || true
fi
mkdir -p "$TARGET_DIR"

echo "[remote] Extracting package to $TARGET_DIR"
# Extract preserving perms
 tar -xzf "$PKG" -C "$TARGET_DIR"

cd "$TARGET_DIR"

# Ensure Docker is present
if ! command -v docker &>/dev/null; then
  echo "[remote] Docker not found. Installing via get.docker.com..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

# Build and start
echo "[remote] docker compose up -d --build"
docker compose up -d --build

# Ensure pgvector extension exists (init script should handle first-run)
if docker compose ps db >/dev/null 2>&1; then
  docker compose exec -T db psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;" || true
fi

echo "[remote] Done. Recent app logs:"
docker compose logs --since=3m app | tail -n 200 || true
REMOTE_SCRIPT

# Copy and run remote script
scp -q /tmp/proethica_remote_install.sh "$REMOTE_HOST:/tmp/proethica_remote_install.sh"
ssh "$REMOTE_HOST" "bash /tmp/proethica_remote_install.sh /tmp/${PKG_BASENAME}.tar.gz ${REMOTE_DIR}"

echo "[deploy-scp] Complete. Visit http://$(ssh -G "$REMOTE_HOST" | awk '/^hostname /{print $2}')/"
