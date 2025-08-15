Legacy tests migrated from repo root on 2025-08-15
-------------------------------------------------

These files were one-off scripts or ad-hoc tests kept for reference. They may rely on:
- A running local Postgres (see docker-compose.yml)
- Real LLM access (set FORCE_MOCK_LLM=false) or mock mode for fast runs
- Project environment vars (see tasks in .vscode or README)

Recommended:
- Keep them out of CI by default
- Run locally when troubleshooting historical behaviors

To run a single file (example):

  PYTHONPATH=. SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm \
  USE_DB_VECTOR_SEARCH=true FORCE_MOCK_LLM=true \
  python tests/legacy_root_20250815/test_role_matching.py
