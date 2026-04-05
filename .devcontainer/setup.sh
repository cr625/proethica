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

# Install system dependencies
echo "Installing system dependencies (Redis, netcat)..."
sudo apt-get update -qq
sudo apt-get install -y -qq redis-server netcat-openbsd

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

# Download required NLTK data
echo "Downloading NLTK resources..."
/workspaces/venv/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')" -q

# Configure git for both repos so you can commit and push
git config --global --add safe.directory /workspaces/proethica
git config --global --add safe.directory /workspaces/OntServe

# Apply codespace-specific patches (not committed to git)
echo "Applying codespace-specific patches..."

# Patch 1: OntServe web/app.py — add sys.path insert so it finds OntServe root
# regardless of working directory when launched
python3 -c "
import re
path = '$ONTSERVE_DIR/web/app.py'
content = open(path).read()
if '_ontserve_root' not in content:
    insert = '''
import sys
from pathlib import Path

# Ensure OntServe root is on the path regardless of how this script is invoked
_ontserve_root = str(Path(__file__).resolve().parent.parent)
if _ontserve_root not in sys.path:
    sys.path.insert(0, _ontserve_root)
'''
    content = content.replace('import os\n', 'import os\n' + insert, 1)
    open(path, 'w').write(content)
    print('  Patched OntServe web/app.py')
else:
    print('  OntServe web/app.py already patched')
"

# Patch 2: scripts/start_all.sh — add PYTHONPATH to MCP launch, add OntServe Web
# service (Codespaces only), install netcat check
python3 -c "
path = '/workspaces/proethica/scripts/start_all.sh'
content = open(path).read()

if 'start_ontserve_web' not in content:
    # Fix MCP launch to include PYTHONPATH
    content = content.replace(
        'nohup \"\$ONTSERVE_VENV/bin/python\" servers/mcp_server.py',
        'PYTHONPATH=\"\$ONTSERVE_DIR:\$PYTHONPATH\" nohup \"\$ONTSERVE_VENV/bin/python\" servers/mcp_server.py'
    )

    # Add OntServe web functions before check_celery
    web_funcs = '''
check_ontserve_web() {
    nc -z localhost 5003 2>/dev/null
    return \$?
}

start_ontserve_web() {
    log_info \"Checking OntServe Web server...\"
    if check_ontserve_web; then
        log_info \"OntServe Web server is already running on port 5003\"
        return 0
    fi

    log_info \"Starting OntServe Web server...\"
    cd \"\$ONTSERVE_DIR/web\"
    nohup \"\$ONTSERVE_VENV/bin/python\" -c \"
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(\\\"web/app.py\\\"))))
from app import create_app
app = create_app()
app.run(host=\\\"0.0.0.0\\\", port=5003, debug=True, use_reloader=False)
\" > \"\$PID_DIR/ontserve_web.log\" 2>&1 &
    ONTSERVE_WEB_PID=\$!
    echo \$ONTSERVE_WEB_PID > \"\$PID_DIR/ontserve_web.pid\"

    for i in {1..15}; do
        if check_ontserve_web; then
            log_info \"OntServe Web server started (PID: \$ONTSERVE_WEB_PID)\"
            return 0
        fi
        sleep 1
    done

    log_error \"OntServe Web server failed to start (check \$PID_DIR/ontserve_web.log)\"
    return 1
}

'''
    content = content.replace('check_celery() {', web_funcs + 'check_celery() {', 1)

    # Add start call in start/prod-test (after start_mcp)
    content = content.replace(
        '        start_mcp || exit 1\n        start_celery || exit 1',
        '        start_mcp || exit 1\n        [ \"\${CODESPACES}\" = \"true\" ] && { start_ontserve_web || exit 1; }\n        start_celery || exit 1'
    )

    # Add status display
    content = content.replace(
        '    if check_celery; then\n        echo -e \"  Celery:     \${GREEN}RUNNING\${NC}\"\n    else\n        echo -e \"  Celery:     \${RED}STOPPED\${NC}\"\n    fi\n\n    echo \"======================================\"',
        '    if [ \"\${CODESPACES}\" = \"true\" ]; then\n        if check_ontserve_web; then\n            echo -e \"  OntServe Web: \${GREEN}RUNNING\${NC} (port 5003)\"\n        else\n            echo -e \"  OntServe Web: \${RED}STOPPED\${NC}\"\n        fi\n    fi\n\n    if check_celery; then\n        echo -e \"  Celery:     \${GREEN}RUNNING\${NC}\"\n    else\n        echo -e \"  Celery:     \${RED}STOPPED\${NC}\"\n    fi\n\n    echo \"======================================\"'
    )

    # Add stop block
    content = content.replace(
        '    log_info \"Services stopped (Redis left running)\"',
        '    if [ \"\${CODESPACES}\" = \"true\" ] && [ -f \"\$PID_DIR/ontserve_web.pid\" ]; then\n        ONTSERVE_WEB_PID=\$(cat \"\$PID_DIR/ontserve_web.pid\")\n        if kill -0 \$ONTSERVE_WEB_PID 2>/dev/null; then\n            kill \$ONTSERVE_WEB_PID 2>/dev/null\n            log_info \"Stopped OntServe Web (PID: \$ONTSERVE_WEB_PID)\"\n        fi\n        rm -f \"\$PID_DIR/ontserve_web.pid\"\n    fi\n\n    log_info \"Services stopped (Redis left running)\"'
    )

    open(path, 'w').write(content)
    print('  Patched scripts/start_all.sh')
else:
    print('  scripts/start_all.sh already patched')
"

# Hide patched files from git — changes are codespace-only
cd "$ONTSERVE_DIR" && git update-index --assume-unchanged web/app.py
cd /workspaces/proethica && git update-index --assume-unchanged scripts/start_all.sh

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
