# Settings

This guide covers ProEthica configuration options and environment settings.

## Environment Variables

ProEthica is configured via environment variables in `.env` file.

### Flask Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | development | Environment (development/production) |
| `FLASK_HOST` | 0.0.0.0 | Bind address |
| `FLASK_PORT` | 5000 | Server port |
| `SECRET_KEY` | (required) | Session encryption key |
| `DEBUG` | True | Debug mode |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLALCHEMY_DATABASE_URI` | (required) | PostgreSQL connection string |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | False | Track object modifications |

Example connection string:
```
postgresql://postgres:PASS@localhost:5432/ai_ethical_dm
```

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `CLAUDE_DEFAULT_MODEL` | claude-sonnet-4-20250514 | Default Claude model |
| `CLAUDE_POWERFUL_MODEL` | claude-opus-4-1-20250805 | Powerful model for complex tasks |
| `OPENAI_API_KEY` | (optional) | OpenAI fallback |
| `ENABLE_GEMINI` | false | Enable Google Gemini |
| `GOOGLE_API_KEY` | (optional) | Gemini API key |

### OntServe Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `ONTSERVE_MCP_ENABLED` | auto | Auto-detected on startup |
| `ONTSERVE_MCP_URL` | http://localhost:8082 | MCP server URL |
| `ONTSERVE_MCP_PORT` | 8082 | MCP server port for auto-detection |

### Extraction Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EXTRACTION_MODE` | multi_pass | Extraction mode |
| `MOCK_LLM_ENABLED` | false | Use mock LLM for testing |
| `USE_DATABASE_LANGEXTRACT_EXAMPLES` | true | Load examples from database |

### Pipeline Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | redis://localhost:6379/1 | Celery broker |
| `CELERY_RESULT_BACKEND` | redis://localhost:6379/1 | Result storage |

## Configuration Files

### config.py

Main Flask configuration in `/config.py`:

```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    # ...
```

### celery_config.py

Celery configuration in `/celery_config.py`:

```python
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
task_time_limit = 7200
task_soft_time_limit = 6000
```

## Model Selection

### Claude Models

| Model | Use Case |
|-------|----------|
| `claude-sonnet-4-*` | Default extraction tasks |
| `claude-opus-4-*` | Complex analysis tasks |
| `claude-haiku-*` | Simple, fast tasks |

### Changing Models

Edit environment variables:

```bash
CLAUDE_DEFAULT_MODEL=claude-sonnet-4-20250514
CLAUDE_POWERFUL_MODEL=claude-opus-4-1-20250805
```

Or update at runtime via Admin interface.

## OntServe Configuration

### MCP Server Settings

OntServe MCP must be running for ontology integration:

```bash
# Start OntServe MCP
cd /path/to/OntServe
python servers/mcp_server.py
```

### Connection Validation

ProEthica validates MCP connection at startup:

- Checks server availability
- Logs connection status
- Continues with fallback if unavailable

### Fallback Behavior

If MCP unavailable:

- Available Classes section empty
- Extraction still works
- Entities stored locally
- Manual push to ontology required

## Database Settings

### PostgreSQL

Required PostgreSQL settings:

```
host: localhost
port: 5432
database: ai_ethical_dm
user: postgres
password: (your password)
```

### pgvector Extension

Vector similarity requires pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Test Database

Testing uses separate database:

```
database: ai_ethical_dm_test
```

## Embedding Configuration

### Model

Default embedding model:

```python
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
EMBEDDING_DIMENSION = 384
```

### Performance

Embedding generation settings:

| Setting | Value | Purpose |
|---------|-------|---------|
| Batch size | 32 | Concurrent embeddings |
| Cache | Enabled | Reduce recomputation |

## Logging

### Log Level

Set via environment:

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Log Files

Logs written to:

- Console (stdout)
- `logs/app.log` (if configured)

### LLM Traces

LLM prompts and responses logged for debugging:

- Stored in `extraction_prompts` table
- Accessible via UI
- Include timestamps and model info

## Security Settings

### CSRF Protection

Enabled by default. Token required for forms.

### Session Security

| Setting | Value |
|---------|-------|
| Session type | Server-side |
| Cookie secure | True (production) |
| Cookie httponly | True |

### API Keys

Store API keys securely:

- Use environment variables
- Never commit to repository
- Rotate periodically

## Performance Tuning

### Database Connections

SQLAlchemy pool settings:

```python
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_MAX_OVERFLOW = 20
```

### Celery Workers

Adjust worker count:

```bash
celery -A celery_config worker --concurrency=4
```

### LLM Rate Limits

Built-in retry with exponential backoff:

- Max retries: 3
- Initial delay: 1 second
- Max delay: 30 seconds

## Development vs Production

### Development

```bash
FLASK_ENV=development
DEBUG=True
```

- Auto-reload enabled
- Detailed error pages
- Debug toolbar available

### Production

```bash
FLASK_ENV=production
DEBUG=False
```

- No auto-reload
- Generic error pages
- Gunicorn recommended

## Admin Interface

### Accessing Admin

Navigate to: `/admin` (requires admin role)

### Admin Features

| Feature | Description |
|---------|-------------|
| Prompts | View/edit extraction prompts |
| Models | Configure LLM models |
| Users | Manage user accounts |
| System | View system status |

## Troubleshooting

### Check Configuration

Verify environment loaded:

```bash
python -c "import os; print(os.environ.get('FLASK_ENV'))"
```

### Test Database Connection

```bash
PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT 1"
```

### Test LLM Connection

```bash
python -c "
from app.services.claude_service import ClaudeService
svc = ClaudeService()
print(svc.test_connection())
"
```

## Related Guides

- [Installation & Deployment](../reference/installation.md) - Setup and deployment
- [Pipeline Automation](pipeline-automation.md) - Celery settings
- [Ontology Integration](../reference/ontology-integration.md) - MCP settings
