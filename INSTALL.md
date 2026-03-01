# ProEthica Installation Guide

---

## Prerequisites

- **Python 3.11 or 3.12** (Ubuntu 24.04 LTS default: 3.12)
- **PostgreSQL 16+** with **pgvector extension** (localhost:5432)
- **Anthropic API key** (for Claude LLM)
- **OntServe** MCP server running on port 8082

---

## 1. Clone and Install

```bash
git clone https://github.com/cr625/proethica.git
cd proethica

python3 -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt
```

---

## 2. Configuration

Create `.env` file in project root (use `.env.production.example` as a template):

```bash
# Database
DATABASE_URL=postgresql://postgres:PASS@localhost:5432/ai_ethical_dm

# API Keys
ANTHROPIC_API_KEY=sk-ant-...

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# MCP Integration (OntServe)
ONTSERVE_MCP_URL=http://localhost:8082
ONTSERVE_WEB_URL=http://localhost:5003
```

---

## 3. Database Setup

### Install PostgreSQL + pgvector

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib postgresql-16-pgvector
sudo service postgresql start
```

> Replace `16` with your installed version (`pg_lsclusters` to check).

### Create database

```sql
-- In psql as postgres user:
CREATE DATABASE ai_ethical_dm;
\connect ai_ethical_dm
CREATE EXTENSION IF NOT EXISTS vector;
```

Tables are created automatically by SQLAlchemy on first run.

---

## 4. OntServe Setup

ProEthica requires the OntServe MCP server for ontology management.

```bash
# In a separate terminal:
cd /path/to/OntServe
source venv-ontserve/bin/activate
python servers/mcp_server.py
```

OntServe MCP listens on port 8082. See [OntServe](https://github.com/cr625/OntServe) for full setup.

---

## 5. Run

```bash
source venv-proethica/bin/activate
python run.py
```

Access at: http://localhost:5000

Key routes:
- `/cases/` - Case list
- `/scenario_pipeline/<case_id>` - Extraction pipeline
- `/tools/prompts` - Prompt editor
- `/docs/` - Documentation

### Production

```bash
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

---

## 6. Verify Installation

```bash
# Test imports
python -c "
from app import create_app
from app.services.llm import get_llm_manager
print('ProEthica imports successful')
"

# Run test suite
PYTHONPATH=/path/to/onto:$PYTHONPATH pytest tests/ -v
```

---

## Common Issues

### Database connection refused

```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT 1;"
```

### ANTHROPIC_API_KEY not set

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Or add to .env file
```

### OntServe not reachable

ProEthica requires OntServe MCP on port 8082. Check it is running:
```bash
curl -s http://localhost:8082/
```

---

## Project Structure

```
proethica/
├── app/                    # Main application
│   ├── models/            # SQLAlchemy models
│   ├── routes/            # Flask routes
│   ├── services/          # Business logic
│   │   ├── llm/          # LLM manager
│   │   ├── extraction/   # Entity extraction
│   │   ├── synthesis/    # Step 4 analysis
│   │   └── narrative/    # Narrative generation
│   └── templates/         # Jinja2 templates
├── scripts/               # Pipeline and analysis scripts
├── tests/                 # Test suite
├── docs/                  # MkDocs documentation
├── pyproject.toml        # Tool configs (ruff, mypy, pytest)
├── requirements.txt      # Python dependencies
├── run.py               # Development server
└── wsgi.py              # Production WSGI entry point
```

---

## Support

- **Issues**: https://github.com/cr625/proethica/issues
- **Live site**: https://proethica.org
