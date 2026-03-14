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

## ICCBR 2026 Experiments

Experiment data and results for the ICCBR 2026 paper are in [`experiments/iccbr-2026/`](experiments/iccbr-2026/). The experiments evaluate component-aware case retrieval against expert citation ground truth across 119 NSPE Board of Ethical Review cases.

To reproduce the experiments without the full system (no OntServe, no LLM keys, no Celery/Redis):

```bash
# 1. Install minimal dependencies
cd proethica
python -m venv venv-proethica
source venv-proethica/bin/activate
pip install flask flask-sqlalchemy flask-login flask-wtf psycopg2-binary \
  pgvector sqlalchemy alembic numpy scipy sentence-transformers

# 2. Configure database access
export DATABASE_URL=postgresql://user:pass@localhost:5432/ai_ethical_dm
export ANTHROPIC_API_KEY=dummy  # not used by experiments, but required by app init

# 3. Run any experiment
PYTHONPATH=$(pwd) python scripts/analysis/weight_sweep.py
```

The analysis scripts query pre-computed embeddings and features from the `case_precedent_features` table. They do not call LLMs or modify the database. See [`experiments/iccbr-2026/README.md`](experiments/iccbr-2026/README.md) for experiment descriptions, results, and the full script list.

## CBR Retrieval Component

The precedent retrieval system can run independently of the extraction pipeline. It requires Flask, PostgreSQL with pgvector, and the sentence-transformers embedding model (all-MiniLM-L6-v2, downloaded automatically on first use).

```bash
# Start with retrieval only (no OntServe, no Celery)
export ANTHROPIC_API_KEY=dummy
PYTHONPATH=$(pwd) python run.py
```

The web interface at http://localhost:5000 provides case browsing, similarity search, and precedent discovery. Extraction features require the full setup (LLM keys, OntServe, Celery).

## License

GPL-3.0 License - See LICENSE file for details.
