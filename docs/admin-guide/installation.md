# Installation & Deployment

## Prerequisites

- **Python 3.11 or 3.12** (Ubuntu 24.04 LTS default: 3.12)
- **PostgreSQL 16+** with **pgvector extension**
- **Redis** (for pipeline automation)
- **Anthropic API key** (Claude LLM)
- **OntServe** MCP server (port 8082) for ontology management

## 1. Clone and Install

```bash
git clone https://github.com/cr625/proethica.git
cd proethica

python3 -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt
```

## 2. PostgreSQL Setup

### Install PostgreSQL and pgvector

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib postgresql-16-pgvector
sudo service postgresql start
```

Replace `16` with your installed version (`pg_lsclusters` to check).

### Create Database

```sql
-- As postgres user (sudo -u postgres psql):
CREATE DATABASE ai_ethical_dm;
\connect ai_ethical_dm
CREATE EXTENSION IF NOT EXISTS vector;
```

Tables are created automatically by SQLAlchemy on first run.

## 3. Redis Setup

Redis serves as the message broker for Celery background tasks (pipeline automation).

```bash
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

Verify with:

```bash
redis-cli ping
# Should return: PONG
```

ProEthica uses Redis DB 1 (`redis://localhost:6379/1`) to avoid conflicts with other applications.

Redis is optional for basic usage (manual single-case extraction works without it), but required for batch pipeline automation.

## 4. Configuration

Create `.env` in the project root (use `.env.production.example` as a template):

```bash
# Database
SQLALCHEMY_DATABASE_URI=postgresql://<user>:<password>@localhost:5432/ai_ethical_dm

# API Keys
ANTHROPIC_API_KEY=<your-api-key>

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# OntServe Integration
ONTSERVE_MCP_URL=http://localhost:8082
ONTSERVE_WEB_URL=http://localhost:5003
```

See [Settings](settings.md) for the full list of environment variables.

## 5. OntServe Setup

ProEthica requires the OntServe MCP server for ontology management (entity validation, class hierarchy, SPARQL queries).

```bash
# In a separate terminal:
cd /path/to/OntServe
source venv-ontserve/bin/activate
python servers/mcp_server.py
```

OntServe MCP listens on port 8082. See [OntServe repository](https://github.com/cr625/OntServe) for full setup instructions.

ProEthica will start without OntServe but ontology features (class assignment, entity commit) will be unavailable.

## 6. Run

### Start ProEthica

```bash
source venv-proethica/bin/activate
python run.py
```

Access at: http://localhost:5000

### Start Celery Worker (for pipeline automation)

In a separate terminal:

```bash
cd /path/to/proethica
source venv-proethica/bin/activate
celery -A celery_config.celery worker --loglevel=info
```

The worker processes background pipeline tasks (batch extraction, queue management). See [Pipeline Automation](../analysis/pipeline-automation.md) for details.

### Service Dependencies

| Service | Port | Purpose | Required |
|---------|------|---------|----------|
| ProEthica (Flask) | 5000 | Web application | Yes |
| PostgreSQL | 5432 | Data storage | Yes |
| OntServe MCP | 8082 | Ontology integration | For ontology features |
| Redis | 6379 | Task queue | For pipeline automation |
| Celery Worker | - | Background tasks | For pipeline automation |

## 7. Verify Installation

```bash
# Test imports
python -c "
from app import create_app
from app.services.llm import get_llm_manager
print('ProEthica imports successful')
"

# Check services
redis-cli ping                              # Redis
curl -s http://localhost:8082/              # OntServe MCP
curl -s http://localhost:5000/health/ready  # ProEthica health check

# Run test suite
PYTHONPATH=/path/to/parent:$PYTHONPATH pytest tests/ -v
```

## Production Deployment

### Gunicorn

```bash
gunicorn -w 4 -b 127.0.0.1:5000 --max-requests 1000 --max-requests-jitter 50 --timeout 60 wsgi:app
```

- `--max-requests 1000` recycles workers after 1000 requests to prevent memory leaks
- `--max-requests-jitter 50` staggers restarts so all workers don't recycle at once
- `--timeout 60` allows heavy case pages to complete under load (default 30s)

### Systemd Services

Production deployments use systemd for process management. Create service files for each component (ProEthica, OntServe web, OntServe MCP) with appropriate gunicorn settings. Include `--max-requests` and `--timeout` flags for worker recycling.

```bash
sudo systemctl daemon-reload
sudo systemctl restart proethica
```

### Celery in Production

```bash
celery -A celery_config.celery worker --loglevel=info --detach
```

Or configure as a systemd service for automatic restart.

### Nginx Configuration

Nginx serves as a reverse proxy with bot protection. Configure:

- **Reverse proxy** to the gunicorn socket/port
- **Rate limiting** with `limit_req_zone` to prevent abuse
- **Security headers** (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy)
- **TLS** via Let's Encrypt / certbot

Response caching is currently disabled for `location /`; see the Caching section in `production-server.md` for the rationale and the conditions under which it could be reintroduced.

Note: nginx's `add_header` inheritance is per-block. Any `add_header` in a location block suppresses all headers from parent contexts. Include security headers in every location block.

### robots.txt

The file at `app/static/robots.txt` is served at the domain root via nginx `alias`. It controls crawler behavior, including crawl delays and route restrictions. Update locally and deploy with `git pull`; no service restart needed.

### fail2ban

fail2ban auto-bans IPs that repeatedly trigger nginx rate limits. Configure a jail that watches the nginx error log for rate-limit violations and bans offending IPs via iptables.

## Production Instance

The primary ProEthica instance is available at **[proethica.org](https://proethica.org)**, maintained for research and demonstration purposes.

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

ProEthica requires OntServe MCP on port 8082 for ontology features:

```bash
curl -s http://localhost:8082/
```

### Redis connection refused

```bash
sudo systemctl status redis-server
sudo systemctl start redis-server
redis-cli ping  # Should return PONG
```

### Celery worker not processing tasks

```bash
# Check worker status
celery -A celery_config status

# Check active tasks
celery -A celery_config inspect active
```

## Project Structure

```
proethica/
├── app/                    # Main application
│   ├── models/            # SQLAlchemy models
│   ├── routes/            # Flask blueprints (37 registered)
│   ├── services/          # Business logic and extraction
│   │   ├── llm/          # LLM manager
│   │   ├── extraction/   # Entity extraction
│   │   ├── synthesis/    # Step 4 analysis
│   │   └── narrative/    # Narrative generation
│   ├── tasks/            # Celery task definitions
│   └── templates/         # Jinja2 templates
├── scripts/               # Pipeline and analysis scripts
├── tests/                 # Test suite
├── docs/                  # MkDocs documentation source
├── config.py             # Flask configuration
├── celery_config.py      # Celery worker configuration
├── requirements.txt      # Python dependencies
├── run.py               # Development server
└── wsgi.py              # Production WSGI entry point
```

## Related Documentation

- [System Architecture](architecture.md) - Technical architecture overview
- [Settings](settings.md) - Configuration options and environment variables
- [Ontology Integration](ontology-integration.md) - OntServe MCP configuration
- [Pipeline Automation](../analysis/pipeline-automation.md) - Batch processing setup
