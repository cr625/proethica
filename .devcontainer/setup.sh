#!/bin/bash
set -e

echo "=== ProEthica + OntServe Codespace Setup ==="

# In Docker Compose, the postgres service is reachable at hostname "postgres"
DB_HOST="postgres"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -c "SELECT 1" &>/dev/null; then
    echo "PostgreSQL is ready."
    break
  fi
  if [ $i -eq 30 ]; then
    echo "ERROR: PostgreSQL did not start in time."
    exit 1
  fi
  sleep 1
done

# Download database dumps from the latest GitHub release
echo "Downloading database dumps..."
gh release download codespace-db -R cr625/proethica -p "*.sql.gz" -D /tmp --clobber

# Create databases, enable pgvector, and restore
echo "Restoring ProEthica database (ai_ethical_dm)..."
PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -c "CREATE DATABASE ai_ethical_dm;" 2>/dev/null || true
PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;"
gunzip -c /tmp/ai_ethical_dm.sql.gz | PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -d ai_ethical_dm

echo "Restoring OntServe database..."
PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -c "CREATE DATABASE ontserve;" 2>/dev/null || true
PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -d ontserve -c "CREATE EXTENSION IF NOT EXISTS vector;"
gunzip -c /tmp/ontserve.sql.gz | PGPASSWORD=PASS psql -h "$DB_HOST" -U postgres -d ontserve

rm -f /tmp/*.sql.gz

# Clone OntServe alongside proethica (full checkout on development branch for active development)
ONTSERVE_DIR="/workspaces/OntServe"
if [ ! -d "$ONTSERVE_DIR" ]; then
  echo "Cloning OntServe..."
  git clone -b development https://github.com/cr625/OntServe.git "$ONTSERVE_DIR"
fi

# Generate ProEthica .env with Codespace-appropriate DB hosts
# API keys come from Codespace secrets (ANTHROPIC_API_KEY, OPENAI_API_KEY)
cat > .env <<ENVEOF
# ProEthica Configuration (Codespace)
SECRET_KEY=dev-codespace-secret-key
FLASK_ENV=development
FLASK_DEBUG=1

# Database - uses 'postgres' hostname (Docker Compose service name)
SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@${DB_HOST}:5432/ai_ethical_dm
DATABASE_URL=postgresql://postgres:PASS@${DB_HOST}:5432/ai_ethical_dm

# API Keys - set these as Codespace secrets in GitHub repo settings
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-MISSING_SET_CODESPACE_SECRET}
OPENAI_API_KEY=${OPENAI_API_KEY:-MISSING_SET_CODESPACE_SECRET}

# OntServe Integration - localhost works here because ports are forwarded within the Codespace
ONTSERVE_MCP_URL=http://localhost:8082
ONTSERVE_WEB_URL=http://localhost:5003
ONTSERVE_DB_HOST=${DB_HOST}

# Environment Settings
ENVIRONMENT=development
PROVENANCE_ENVIRONMENT=development

# Feature Flags
USE_DATABASE_LANGEXTRACT_EXAMPLES=true
ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT=true
MOCK_LLM_ENABLED=false
ENVEOF

# OntServe env - just needs the DB URL override
cat > "$ONTSERVE_DIR/.env" <<ENVEOF
ONTSERVE_DB_URL=postgresql://postgres:PASS@${DB_HOST}:5432/ontserve
ENVEOF

# Single shared venv for both projects (saves ~400-500MB disk)
echo "Installing dependencies (shared venv)..."
VENV_DIR="/workspaces/venv"
python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -q -r requirements.txt -r "$ONTSERVE_DIR/requirements.txt"
deactivate

# Configure git for both repos so you can commit and push
git config --global --add safe.directory /workspaces/proethica
git config --global --add safe.directory /workspaces/OntServe

# Check for missing API keys
if [ "$ANTHROPIC_API_KEY" = "" ] || [ "$ANTHROPIC_API_KEY" = "MISSING_SET_CODESPACE_SECRET" ]; then
  echo ""
  echo "WARNING: ANTHROPIC_API_KEY not set."
  echo "  Add it as a Codespace secret at:"
  echo "  https://github.com/settings/codespaces (user-level) or"
  echo "  https://github.com/cr625/proethica/settings/secrets/codespaces (repo-level)"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start services:"
echo "  source /workspaces/venv/bin/activate"
echo ""
echo "  # Terminal 1 - OntServe MCP (start this first):"
echo "  cd $ONTSERVE_DIR && python servers/mcp_server.py"
echo ""
echo "  # Terminal 2 - ProEthica:"
echo "  cd /workspaces/proethica && python run.py"
