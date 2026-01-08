# ProEthica

**Live Demo:** https://proethica.org

**Documentation:** https://proethica.org/docs

## Overview

ProEthica extracts and analyzes ethical concepts from professional ethics case studies using a 9-concept formal methodology (Roles, Principles, Obligations, Sanctions, Responses, Actions, Events, Causes, Consequences). The system generates structured scenarios with decision points, arguments, and outcome analysis.

## Requirements

- Python 3.11+
- PostgreSQL 14+
- Redis (for async task queue)
- Celery (background workers)
- [OntServe](https://github.com/cr625/OntServe) MCP server (port 8082) - ontology management

## Deployment

This application has a complex deployment stack requiring PostgreSQL, Redis, Celery workers, and the OntServe MCP server. A Docker Compose setup is planned for simplified deployment.

For manual deployment, see the installation guide in the documentation.

## Development

```bash
# Clone and setup
git clone https://github.com/cr625/proethica.git
cd proethica
python -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database and API credentials

# Run development server
python run.py
```

## License

GPL-3.0 License - See LICENSE file for details.
