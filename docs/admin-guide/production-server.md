# Production Server Setup -- ProEthica

Reference for the production server infrastructure. Covers setup steps and architecture details. For routine deployments, see `.claude/agents/git-deployment-sync.md`.

## Server Overview

| Item | Value |
|------|-------|
| Provider | DigitalOcean droplet |
| OS | Ubuntu 24.04 LTS |
| Domain | proethica.org |

## Systemd Service

The application runs as a systemd service with gunicorn workers behind an nginx reverse proxy.

- Auto-restarts on failure
- Environment loaded from `.env`
- Security hardening enabled

## PostgreSQL

**Extension required**: `pgvector` (for embedding similarity search).

```bash
# Install extension (one-time):
sudo apt install postgresql-17-pgvector

# Enable in database (required after DROP/CREATE DATABASE):
sudo -u postgres psql -d ai_ethical_dm -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

All embedding columns use `vector(384)` type (384 dimensions from `all-MiniLM-L6-v2`).

## Python Dependencies

### Standard packages

```bash
pip install -r requirements.txt
```

### Embedding model (sentence-transformers)

Required for similarity search and the precedent network. Without it, the service falls back to OpenAI embeddings (1536D) which mismatch the stored 384D vectors.

```bash
# Install CPU-only PyTorch (no CUDA needed):
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install sentence-transformers:
pip install sentence-transformers
```

The `all-MiniLM-L6-v2` model downloads automatically on first use (~90MB).

### NLTK data

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

## Nginx

Reverse proxy on ports 80/443 with TLS (Let's Encrypt).

### Caching

Nginx response caching is currently disabled. The `proxy_cache_path` zone is still declared in `/etc/nginx/nginx.conf` for `proethica.org`, but no `location` block in the active site configuration references it. The `/var/cache/nginx/proethica` directory exists but stays empty.

**Why the cache was removed.** Flask's session signing produces a fresh `Set-Cookie: session=...` on every response and sets `Vary: Cookie` to advertise that fact. Honoring those signals correctly yields near-zero cache hit rate. Ignoring them with `proxy_ignore_headers Set-Cookie Vary` causes every visitor to share a single signed Flask session cookie, which defeats CSRF protection and clobbers authenticated session cookies on the GET that follows login. Both states are net negatives, so the cache was removed from `location /` on 2026-05-04.

A `proeth_auth` cookie is still set by Flask on login (and cleared on logout). Its original purpose was to drive `proxy_cache_bypass` so authenticated users skipped the anonymous cache. With the cache removed, the cookie is vestigial. The Flask code is retained harmlessly in case a correctly designed response cache is reintroduced later.

**Reintroducing response caching.** If response caching is reintroduced for the main app, change the Flask side first to issue session cookies only on first visit and on auth events, not on every response. Then `Vary: Cookie` works correctly and anonymous visitors share cache entries while authenticated users skip the cache. Until that change ships, do not add `proxy_cache` directives to `location /`.

Static assets, `/demo` (alias-served files, no cookies), and OntServe endpoints (port 5003, separate site) remain safe candidates for caching in dedicated `location` blocks.

Gzip is enabled for all text content types at compression level 6.

See `docs-internal/production-server-ops.md` for the authoritative ops reference.

## Offline Data Scripts

These scripts run one-time or after data changes. They are NOT part of routine deployments.

### Similarity cache (precedent network graph)

Pre-computes pairwise similarity scores for the precedent network. Required after adding new cases or updating extraction data.

```bash
python scripts/populate_similarity_cache.py --all
# Or for specific cases:
python scripts/populate_similarity_cache.py --cases 73,74,75
```

### Section embeddings

Generates 384D embeddings for document sections. Normally populated via the web UI **Generate Embeddings** button on the case structure page, but can be batch-run:

```bash
python scripts/populate_section_embeddings.py --all
```

### Component embeddings

Generates per-component (R, P, O, S, Rs, A, E, Ca, Cs) and combined embeddings from extracted entities:

```bash
python scripts/populate_component_embeddings.py --all
```

### Precedent features

Extracts structural features for precedent matching:

```bash
python scripts/populate_precedent_features.py
```

## Environment Variables

Key variables in `.env`:

```
ENVIRONMENT=production
ANTHROPIC_API_KEY=<api-key>
OPENAI_API_KEY=<api-key>
ONTSERVE_MCP_URL=http://localhost:8082
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/ai_ethical_dm
EMBEDDING_PROVIDER_PRIORITY=local,openai,anthropic,google
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
DISABLE_LOCAL_EMBEDDINGS=false
```

## TLS Certificates

Managed by Let's Encrypt / certbot. Auto-renewal via systemd timer.

## Directory Layout

```
/opt/proethica/
  .env                  # Environment variables
  wsgi.py               # Gunicorn entry point
  venv/                 # Python virtual environment
  app/                  # Application code
  site/                 # MkDocs compiled documentation (served at /docs/)
  scripts/              # Offline data scripts
```

## Setup From Scratch Checklist

1. Provision Ubuntu 24.04 droplet
2. Install system packages: `postgresql`, `postgresql-17-pgvector`, `nginx`, `python3.12-venv`, `certbot`
3. Create database, enable `vector` extension
4. Create database user
5. Clone repo, create venv, install requirements
6. Install embedding model: CPU-only torch + sentence-transformers
7. Install NLTK data
8. Configure `.env` with API keys and database credentials
9. Install systemd service file, enable and start
10. Configure nginx site with TLS (certbot)
11. Configure sudoers entries
12. Restore database from dev dump
13. Run offline data scripts (embeddings, similarity cache)
