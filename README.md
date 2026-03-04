# ProEthica

**Live:** https://proethica.org

**Documentation:** https://proethica.org/docs

## Overview

ProEthica extracts and analyzes ethical concepts from professional ethics case studies using a 9-component formal methodology (Roles, Principles, Obligations, States, Resources, Constraints, Capabilities, Actions, Events). The system generates structured scenarios with decision points, arguments, and outcome analysis.

## Requirements

- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- Anthropic API key (Claude)
- [OntServe](https://github.com/cr625/OntServe) MCP server (port 8082) for ontology management

## Quick Start

```bash
# Terminal 1: OntServe MCP (required)
cd /path/to/OntServe && source venv-ontserve/bin/activate && python servers/mcp_server.py

# Terminal 2: ProEthica
cd proethica
python -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt
cp .env.production.example .env
# Edit .env with your database and API credentials
python run.py
```

Access at: http://localhost:5000

See the [Installation Guide](https://proethica.org/docs/admin-guide/installation/) for full setup instructions including PostgreSQL, Redis, Celery, and OntServe configuration.

## License

GPL-3.0 License - See LICENSE file for details.
