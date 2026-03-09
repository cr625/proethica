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
postgresql://<user>:<password>@localhost:5432/ai_ethical_dm
```

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `CLAUDE_DEFAULT_MODEL` | claude-sonnet-4-6 | Default Claude model |
| `CLAUDE_POWERFUL_MODEL` | claude-opus-4-6 | Powerful model for complex tasks |
| `CLAUDE_FAST_MODEL` | claude-haiku-4-5-20251001 | Fast model for simple tasks |
| `OPENAI_API_KEY` | (optional) | OpenAI fallback |
| `ENABLE_GEMINI` | false | Enable Google Gemini |
| `GOOGLE_API_KEY` | (optional) | Gemini API key |

### OntServe Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `ONTSERVE_MCP_URL` | http://localhost:8082 | MCP server URL |
| `ONTSERVE_MCP_PORT` | 8082 | Port used by `run.py` for auto-detection at startup |

`ONTSERVE_MCP_ENABLED` is set automatically at runtime by `run.py` based on whether the MCP server responds. It is not a user-configurable setting.

### Extraction Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_LLM_ENABLED` | false | Use mock LLM for testing |
| `USE_DATABASE_LANGEXTRACT_EXAMPLES` | true | Load examples from database |

### Pipeline Settings

Celery uses Redis DB 1 as both broker and result backend. These values are hardcoded in `celery_config.py`:

```python
broker='redis://localhost:6379/1'
backend='redis://localhost:6379/1'
```

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
broker = 'redis://localhost:6379/1'
backend = 'redis://localhost:6379/1'
task_time_limit = 7200       # 2 hour hard limit
task_soft_time_limit = 6000  # 100 minute soft limit
worker_prefetch_multiplier = 1  # One task at a time
```

## Model Selection

### Claude Models

| Model | Use Case |
|-------|----------|
| `claude-sonnet-4-6` | All extraction tasks (Steps 1-4) |
| `claude-opus-4-6` | Complex analysis tasks (reserved for high-stakes operations) |
| `claude-haiku-4-5-20251001` | Simple, fast tasks |

### Changing Models

Edit environment variables:

```bash
CLAUDE_DEFAULT_MODEL=claude-sonnet-4-6
CLAUDE_POWERFUL_MODEL=claude-opus-4-6
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
user: <db-user>
password: <password>
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
psql -h localhost -U <db-user> -d ai_ethical_dm -c "SELECT 1"
```

### Test LLM Connection

```bash
python -c "
from app.services.llm import get_llm_manager
mgr = get_llm_manager()
print(f'LLM manager loaded, default model: {mgr.default_model}')
"
```

## Related Guides

- [Installation & Deployment](installation.md) - Setup and deployment
- [Pipeline Management](pipeline-management.md) - Celery settings
- [Ontology Integration](ontology-integration.md) - MCP settings
