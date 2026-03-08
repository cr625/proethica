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
SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@localhost:5432/ai_ethical_dm

# API Keys
ANTHROPIC_API_KEY=sk-ant-...

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

### All Services at Once

```bash
./scripts/start_all.sh start
```

This starts OntServe MCP, Redis, Celery worker, and Flask in the correct order.

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

Production deployments use systemd for process management. Service files are at `/etc/systemd/system/`:

- `proethica.service` -- 4 gunicorn workers on port 5000
- `ontserve-web.service` -- 2 gunicorn workers on port 5003 (reduced from 3; each worker uses ~850MB)
- `ontserve-mcp.service` -- MCP server on port 8082

Both gunicorn services include `--max-requests` and `--timeout` flags. After editing service files:

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

Nginx serves as a reverse proxy with caching and bot protection.

**Main config** (`/etc/nginx/nginx.conf`) -- add to the `http` block:

```nginx
# Proxy cache for ProEthica
proxy_cache_path /var/cache/nginx/proethica
    levels=1:2
    keys_zone=proethica_cache:10m
    max_size=200m
    inactive=60m
    use_temp_path=off;

# Per-IP rate limiting (2 requests/sec)
limit_req_zone $binary_remote_addr zone=bot_limit:10m rate=2r/s;
```

**Site config** (`/etc/nginx/sites-enabled/proethica.org`):

```nginx
server {
    server_name proethica.org www.proethica.org;

    # Block known aggressive crawlers by IP
    # deny 1.2.3.4;

    # Serve robots.txt directly (no proxy)
    location = /robots.txt {
        alias /opt/proethica/app/static/robots.txt;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Rate limiting -- burst allows short spikes, nodelay returns 429 immediately
        limit_req zone=bot_limit burst=10 nodelay;
        limit_req_status 429;

        # Response cache
        proxy_cache proethica_cache;
        proxy_cache_valid 200 30m;
        proxy_cache_valid 404 1m;
        proxy_cache_methods GET HEAD;
        proxy_cache_key "$scheme$request_method$host$request_uri";
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_background_update on;
        proxy_cache_lock on;
        proxy_ignore_headers Set-Cookie Vary;

        # Headers (must all be in same block -- nginx add_header inheritance)
        add_header X-Cache-Status $upstream_cache_status;
        include /etc/nginx/conf.d/security-headers.conf;
    }

    # SSL managed by Certbot
}
```

Each `location` block must `include /etc/nginx/conf.d/security-headers.conf` because nginx's `add_header` inheritance is per-block: any `add_header` in a location block suppresses all headers from parent contexts.

### Security Headers

Global security headers in `/etc/nginx/conf.d/security-headers.conf`, included from each location block:

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

**Cache management:**

```bash
# Check cache status header on a response
curl -sI https://proethica.org/ | grep X-Cache-Status
# HIT = served from cache, MISS = fetched from gunicorn

# Purge all cached responses
sudo rm -rf /var/cache/nginx/proethica/*
sudo systemctl reload nginx
```

### robots.txt

The file at `app/static/robots.txt` is served at the domain root via nginx `alias`. It controls crawler behavior:

- Turnitin is fully blocked (aggressive scraping caused OOM kills in March 2026)
- Other bots get a 2-second crawl delay
- Pipeline and API routes are disallowed; case listing and detail pages are allowed

Update the file locally and deploy with `git pull`; no service restart needed.

### fail2ban

fail2ban auto-bans IPs that repeatedly trigger nginx rate limits.

**Filter** (`/etc/fail2ban/filter.d/nginx-limit-req.conf`):

```ini
[Definition]
failregex = limiting requests, excess: .* by zone .*, client: <HOST>
ignoreregex =
```

**Jail** (`/etc/fail2ban/jail.d/nginx-limit-req.conf`):

```ini
[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 10
findtime = 60
bantime = 600
action = iptables-multiport[name=nginx-limit-req, port="http,https", protocol=tcp]
```

This bans any IP at the firewall level for 10 minutes after 10 rate-limit violations within 60 seconds.

```bash
# Check jail status
sudo fail2ban-client status nginx-limit-req

# Manually unban an IP
sudo fail2ban-client set nginx-limit-req unbanip 1.2.3.4
```

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
│   ├── routes/            # Flask blueprints (42 registered)
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
