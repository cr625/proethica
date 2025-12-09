# Installation

This guide covers setting up ProEthica for local development and production deployment.

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- Redis (for pipeline automation)
- OntServe MCP server (for ontology integration)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/cr625/proethica.git
cd proethica
```

### 2. Create Virtual Environment

```bash
python -m venv venv-proethica
source venv-proethica/bin/activate  # Linux/Mac
# or
venv-proethica\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Flask
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
SECRET_KEY=your-secret-key

# Database
SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@localhost:5432/ai_ethical_dm

# LLM (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...

# OntServe MCP
ONTSERVE_MCP_ENABLED=true
ONTSERVE_MCP_URL=http://localhost:8082

# Extraction
EXTRACTION_MODE=multi_pass
```

### 5. Initialize Database

Create the PostgreSQL database:

```bash
createdb ai_ethical_dm
```

Run migrations:

```bash
cd db_migration
psql -h localhost -U postgres -d ai_ethical_dm -f 001_initial_schema.sql
# Run additional migrations in order
```

### 6. Start OntServe MCP (Required)

ProEthica requires OntServe MCP server for ontology validation:

```bash
cd /path/to/OntServe
source venv-ontserve/bin/activate
python servers/mcp_server.py
```

### 7. Start ProEthica

```bash
cd /path/to/proethica
source venv-proethica/bin/activate
python run.py
```

Access at: http://localhost:5000

## Service Dependencies

| Service | Port | Required | Purpose |
|---------|------|----------|---------|
| ProEthica | 5000 | Yes | Main application |
| OntServe MCP | 8082 | Yes | Ontology validation |
| PostgreSQL | 5432 | Yes | Data storage |
| Redis | 6379 | Optional | Pipeline automation |
| Celery Worker | - | Optional | Background tasks |

## Pipeline Automation (Optional)

For batch case processing, enable Celery:

### Start Redis

```bash
redis-server
```

### Start Celery Worker

```bash
PYTHONPATH=/path/to/parent:$PYTHONPATH celery -A celery_config worker --loglevel=info
```

### Start ProEthica with Full Stack

Use the convenience script:

```bash
./scripts/start_all.sh start
```

## Production Deployment

For production deployment to DigitalOcean or similar:

1. Configure systemd services for OntServe MCP
2. Set up nginx reverse proxy
3. Configure SSL certificates
4. Set `FLASK_ENV=production`
5. Use gunicorn instead of Flask development server

See [Deployment Checklist](../reference/architecture.md) for details.

## Verifying Installation

After starting all services:

1. Visit http://localhost:5000
2. Navigate to Cases page
3. Verify OntServe connection indicator shows green
4. Try uploading a test case

## Troubleshooting

### Database Connection Failed

Verify PostgreSQL is running and credentials match `.env`:

```bash
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT 1"
```

### OntServe MCP Not Available

Check MCP server is running on port 8082:

```bash
curl -X POST http://localhost:8082 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_tools","id":1}'
```

### LLM API Errors

Verify API key is set and has credits:

```bash
echo $ANTHROPIC_API_KEY
```

## Next Steps

- [First Login](first-login.md) - Interface overview
- [Upload Cases](../how-to/upload-cases.md) - Add cases for analysis
