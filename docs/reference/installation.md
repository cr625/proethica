# Installation & Deployment

Technical installation and deployment documentation for ProEthica.

## Current Status

ProEthica is currently deployed as a research prototype. Public deployment options are under development.

## Production Instance

The primary ProEthica instance is available at:

**[https://proethica.org](https://proethica.org)**

This instance is maintained for research and demonstration purposes. Contact the project maintainers for access.

## Local Development

Local development installation instructions are available in the project repository:

**[https://github.com/cr625/proethica](https://github.com/cr625/proethica)**

### Requirements

- Python 3.11+
- PostgreSQL 14+
- Redis (for pipeline automation)
- OntServe MCP server (for ontology integration)

### Quick Reference

```bash
# Clone repository
git clone https://github.com/cr625/proethica.git
cd proethica

# Create virtual environment
python -m venv venv-proethica
source venv-proethica/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start application
python run.py
```

## Docker Deployment

Docker deployment is planned for a future release. This will provide:

- Single-command deployment
- Pre-configured PostgreSQL and Redis
- OntServe integration
- Production-ready configuration

Check the [GitHub repository](https://github.com/cr625/proethica) for updates.

## Service Dependencies

| Service | Port | Purpose |
|---------|------|---------|
| ProEthica | 5000 | Main application |
| OntServe MCP | 8082 | Ontology validation |
| PostgreSQL | 5432 | Data storage |
| Redis | 6379 | Pipeline automation |

## Related Documentation

- [System Architecture](architecture.md) - Technical architecture overview
- [Ontology Integration](ontology-integration.md) - OntServe configuration
