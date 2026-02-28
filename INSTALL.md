# ProEthica Installation Guide

Quick installation guide for ProEthica.

---

## Prerequisites

- **Python 3.11 or 3.12** (Ubuntu 24.04 LTS default: 3.12)
- **PostgreSQL 16+** with **pgvector extension** (localhost:5432)
- **Anthropic API key** (for Claude LLM)

---

## Installation Methods

### Option 1: Using pip (Traditional)

```bash
# Clone repository
cd /home/user/proethica

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies (production + development)
pip install -r requirements.txt
```

### Option 2: Using uv (Recommended - 10-100x faster)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
cd /home/user/proethica

# Install dependencies (creates .venv automatically)
uv sync

# Activate environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

---

## Configuration

### 1. Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql://postgres:PASS@localhost:5432/ai_ethical_dm

# API Keys
ANTHROPIC_API_KEY=sk-ant-...  # Your Anthropic API key
# OPENAI_API_KEY=sk-...       # Optional: OpenAI fallback

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# MCP Integration (OntServe)
ONTSERVE_MCP_URL=http://localhost:8082
ONTSERVE_WEB_URL=http://localhost:5003
```

### 2. Database Setup

#### Install PostgreSQL + pgvector

On Ubuntu/Debian (including GitHub Codespaces):

```bash
sudo apt-get update
sudo apt-get install -y --allow-unauthenticated postgresql postgresql-contrib
sudo apt-get install -y --allow-unauthenticated postgresql-16-pgvector
sudo service postgresql start
```

> **Note:** Replace `16` with your installed PostgreSQL version (`pg_lsclusters` to check).

#### Create database user and database

In GitHub Codespaces, `sudo -u postgres psql` may prompt for the codespace
user password. If you don't know it, set a password for the postgres OS user
first, then use `su`:

```bash
sudo passwd postgres   # set a password
su - postgres          # switch to postgres user
psql                   # open psql prompt
```

Then run each command **one at a time** inside psql:

```sql
CREATE USER proethica_user WITH PASSWORD 'ProEthicaSecure2025';
CREATE DATABASE ai_ethical_dm OWNER proethica_user;
GRANT ALL PRIVILEGES ON DATABASE ai_ethical_dm TO proethica_user;
```

```sql
\connect ai_ethical_dm
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

```sql
\dx
```

You should see `vector` listed under installed extensions. Exit with `\q`.

> **Important:** Run `\connect ai_ethical_dm` and `CREATE EXTENSION ...`
> as separate commands — pasting them together causes a psql parse error.

#### Apply migrations

```bash
psql -h localhost -U postgres -d ai_ethical_dm -f db_migration/*.sql
```

---

### 3. Redis Setup

```bash
sudo apt-get install -y --allow-unauthenticated redis-server
sudo service redis-server start
redis-cli ping  # should return PONG
```

---

## Running ProEthica

### Development Server

```bash
# Activate environment
source venv/bin/activate  # or: source .venv/bin/activate

# Run Flask development server
python run.py
```

Access at: http://localhost:5000

### Production Server

```bash
# Using gunicorn (included in requirements.txt)
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

# Or with production config
gunicorn -c config/gunicorn.py wsgi:app
```

---

## Verify Installation

### Quick Test

```bash
# Test imports
python -c "
from app import create_app
from app.services.llm import get_llm_manager
print('✅ ProEthica imports successful')
"

# Run test suite
pytest tests/ -v

# Check database connection
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    from app.models import Document
    count = Document.query.count()
    print(f'✅ Database connected: {count} cases found')
"
```

---

## Common Issues

### Issue: ModuleNotFoundError

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or: source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Database connection refused

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start if needed
sudo systemctl start postgresql

# Verify connection
psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT 1;"
```

### Issue: ANTHROPIC_API_KEY not set

```bash
# Export temporarily
export ANTHROPIC_API_KEY="sk-ant-your-key-here"

# Or add to .env file (recommended)
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

---

## Development Tools

### Code Quality

```bash
# Lint code with ruff
ruff check .

# Format code
ruff format .

# Type check with mypy
mypy app/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_llm_manager.py -v

# Run integration tests only
pytest -m integration
```

---

## Project Structure

```
proethica/
├── app/                    # Main application
│   ├── models/            # Database models
│   ├── routes/            # Flask routes
│   ├── services/          # Business logic
│   │   ├── llm/          # LLM manager (Week 1)
│   │   └── scenario_generation/  # Scenario features
│   └── templates/         # HTML templates
├── db_migration/          # SQL migrations
├── tests/                 # Test suite
├── docs/                  # Documentation
├── pyproject.toml        # Modern Python config
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── run.py               # Development server
└── wsgi.py              # Production WSGI entry point
```

---

## Next Steps

1. **Apply database migrations**: See `db_migration/` directory
2. **Load NSPE cases**: See `nspe-pipeline/` directory
3. **Test scenario generation**: http://localhost:5000/scenario_pipeline/case/8/generate
4. **Read docs**: See `docs/CASE_ANALYSIS_IMPLEMENTATION_PLAN.md`

---

## Documentation

- **Testing**: `docs/TESTING_PARTICIPANT_MAPPING.md`
- **Architecture**: `docs/LLM_MANAGER_DESIGN.md`
- **Implementation**: `docs/CASE_ANALYSIS_IMPLEMENTATION_PLAN.md`
- **Project Status**: `CLAUDE.md`

---

## Support

- **Issues**: https://github.com/cr625/proethica/issues
- **Docs**: https://proethica.org
- **OntServe Integration**: See `docs/MCP_INTEGRATION_GUIDE.md`

**Installation complete!** 🎉
