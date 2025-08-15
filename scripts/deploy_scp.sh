#!/usr/bin/env bash
# Package the current workspace (excluding heavy/dev files) and deploy to the droplet via scp/ssh.
# Requires an SSH config Host named 'digitalocean'.
set -euo pipefail

REMOTE_HOST=${REMOTE_HOST:-digitalocean}
REMOTE_DIR=${REMOTE_DIR:-~/proethica}
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
TARGET_DIR="${2:-$HOME/proethica}"
# Expand ~ if provided
if [ "${TARGET_DIR:0:1}" = "~" ]; then
  TARGET_DIR="${HOME}${TARGET_DIR#~}"
fi
STAMP=$(date +%Y%m%d%H%M%S)

# Ensure base directory exists and is writable (handles first-time deploy)
BASE_DIR=$(dirname "$TARGET_DIR")
if [ ! -d "$BASE_DIR" ]; then
  echo "[remote] Creating base directory $BASE_DIR"
  mkdir -p "$BASE_DIR" 2>/dev/null || sudo mkdir -p "$BASE_DIR" || true
fi
chown "$USER":"$USER" "$BASE_DIR" 2>/dev/null || sudo chown "$USER":"$USER" "$BASE_DIR" 2>/dev/null || true

# Backup existing install if present
if [ -d "$TARGET_DIR" ]; then
  echo "[remote] Backing up existing $TARGET_DIR to ${TARGET_DIR}_bak_${STAMP}"
  mv "$TARGET_DIR" "${TARGET_DIR}_bak_${STAMP}" 2>/dev/null || sudo mv "$TARGET_DIR" "${TARGET_DIR}_bak_${STAMP}" || true
fi
# Create target dir (use sudo if needed) and ensure ownership
mkdir -p "$TARGET_DIR" 2>/dev/null || sudo mkdir -p "$TARGET_DIR" || true
chown -R "$USER":"$USER" "$TARGET_DIR" 2>/dev/null || sudo chown -R "$USER":"$USER" "$TARGET_DIR" 2>/dev/null || true

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

# Write a known-good docker-compose.yml to avoid indentation issues
cat > docker-compose.yml <<'COMPOSE_YML'
version: '3.9'

services:
  db:
    image: pgvector/pgvector:pg17
    container_name: proethica-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: PASS
      POSTGRES_DB: ai_ethical_dm
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init-pgvector.sql:/docker-entrypoint-initdb.d/init-pgvector.sql:ro

  mcp:
    build:
      context: .
      dockerfile: docker/mcp.Dockerfile
    environment:
      MCP_SERVER_PORT: 5001
      MCP_HOST: 0.0.0.0
    expose:
      - "5001"
    restart: unless-stopped

  app:
    build:
      context: .
      dockerfile: docker/app.Dockerfile
    environment:
      ENVIRONMENT: production
      SQLALCHEMY_DATABASE_URI: postgresql://postgres:PASS@db:5432/ai_ethical_dm
      MCP_SERVER_URL: http://mcp:5001
      USE_DB_VECTOR_SEARCH: "true"
    env_file:
      - .env
    depends_on:
      - db
      - mcp
    ports:
      - "8080:8000"
    restart: unless-stopped

volumes:
  pgdata:
COMPOSE_YML

# Ensure Docker Compose is available (prefer v2 plugin)
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "[remote] Docker Compose not found. Installing plugin to user home..."
  mkdir -p "$HOME/.docker/cli-plugins"
  OS=$(uname -s)
  ARCH=$(uname -m)
  # Normalize ARCH
  case "$ARCH" in
    x86_64|amd64) ARCH=amd64;;
    aarch64|arm64) ARCH=arm64;;
  esac
  COMPOSE_VERSION="v2.29.2"
  URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-${OS}-${ARCH}"
  curl -fsSL "$URL" -o "$HOME/.docker/cli-plugins/docker-compose"
  chmod +x "$HOME/.docker/cli-plugins/docker-compose"
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    echo "[remote] Failed to install Docker Compose. Please install it manually." >&2
    exit 1
  fi
fi

# Build and start
echo "[remote] Pre-clean existing stack (down + remove stale containers)"
${COMPOSE_CMD} down || true
docker rm -f proethica-postgres 2>/dev/null || true
echo "[remote] ${COMPOSE_CMD} up -d --build"
HOST_HTTP_PORT=${HOST_HTTP_PORT:-8080} ${COMPOSE_CMD} up -d --build

# Ensure pgvector extension exists (init script should handle first-run)
if ${COMPOSE_CMD} ps db >/dev/null 2>&1; then
  HOST_HTTP_PORT=${HOST_HTTP_PORT:-8080} ${COMPOSE_CMD} exec -T db psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;" || true
fi

echo "[remote] Done. Recent app logs:"
HOST_HTTP_PORT=${HOST_HTTP_PORT:-8080} ${COMPOSE_CMD} logs --since=3m app | tail -n 200 || true
REMOTE_SCRIPT

# Copy and run remote script
scp -q /tmp/proethica_remote_install.sh "$REMOTE_HOST:/tmp/proethica_remote_install.sh"
ssh "$REMOTE_HOST" "bash /tmp/proethica_remote_install.sh /tmp/${PKG_BASENAME}.tar.gz ${REMOTE_DIR}"

echo "[deploy-scp] Complete. Visit http://$(ssh -G "$REMOTE_HOST" | awk '/^hostname /{print $2}')/"
