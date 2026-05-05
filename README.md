# ProEthica

**Live:** <https://proethica.org>

**Documentation:** <https://proethica.org/docs>

## Overview

ProEthica extracts and analyzes ethical concepts from professional ethics case studies using a 9-component formal methodology (Roles, Principles, Obligations, States, Resources, Constraints, Capabilities, Actions, Events). The system generates structured scenarios with decision points, arguments, and outcome analysis. The current corpus contains 118 NSPE Board of Ethical Review cases with full extraction.

## Access Modes

ProEthica supports three modes of access, ordered by required infrastructure.

### 1. Browsing the Extracted Corpus

The public deployment at <https://proethica.org> provides:

- Case list and detail views at `/cases/`
- Extracted 9-component entities per case
- Scenario timelines and decision-point analysis at `/scenario_pipeline/<case_id>`
- Precedent retrieval and similarity search
- Validation study participation at `/validation/`

No installation is required for this mode.

### 2. Reproducing the ICCBR 2026 Experiments

Experiment data and scripts are in [`experiments/iccbr-2026/`](experiments/iccbr-2026/). The analysis scripts query pre-computed embeddings and features from the `case_precedent_features` table. They do not call LLMs or modify the database.

```bash
cd proethica
python -m venv venv-proethica
source venv-proethica/bin/activate
pip install flask flask-sqlalchemy flask-login flask-wtf psycopg2-binary \
  pgvector sqlalchemy alembic numpy scipy sentence-transformers

export SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost:5432/ai_ethical_dm
export ANTHROPIC_API_KEY=dummy  # required by app init, not used by experiments

PYTHONPATH=$(pwd) python scripts/analysis/weight_sweep.py
```

See [`experiments/iccbr-2026/README.md`](experiments/iccbr-2026/README.md) for experiment descriptions, results, and the full script list.

### 3. Running the Full Extraction Pipeline

Required for extracting new cases or modifying the extraction logic.

Requirements:

- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- Anthropic API key (Claude)
- [OntServe](https://github.com/cr625/OntServe) MCP server (port 8082)
- Redis and Celery for background extraction jobs

```bash
# Terminal 1: OntServe MCP (required)
cd /path/to/OntServe && source venv-ontserve/bin/activate && python servers/mcp_server.py

# Terminal 2: ProEthica
cd proethica
python -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt
cp .env.production.example .env
# Edit .env with database and API credentials
python run.py
```

Access at <http://localhost:5000>. See the [Installation Guide](https://proethica.org/docs/admin-guide/installation/) for full setup including PostgreSQL, Redis, Celery, and OntServe configuration.

## License

GPL-3.0 License - See LICENSE file for details.
