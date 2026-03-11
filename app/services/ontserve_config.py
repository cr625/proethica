"""Centralized OntServe connection configuration.

Reads from environment variables (same source as Flask config).
No Flask app context required -- safe to use at module level and
in constructors.
"""

import os
from pathlib import Path


def get_ontserve_db_config() -> dict:
    """Return psycopg2-compatible connection dict for OntServe DB."""
    return {
        'dbname': os.environ.get('ONTSERVE_DB_NAME', 'ontserve'),
        'user': os.environ.get('ONTSERVE_DB_USER', 'postgres'),
        'password': os.environ.get('ONTSERVE_DB_PASSWORD', 'PASS'),
        'host': os.environ.get('ONTSERVE_DB_HOST', 'localhost'),
        'port': int(os.environ.get('ONTSERVE_DB_PORT', '5432')),
    }


def get_ontserve_db_url() -> str:
    """Return SQLAlchemy-compatible connection URL for OntServe DB."""
    c = get_ontserve_db_config()
    return f"postgresql://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['dbname']}"


def get_ontserve_base_path() -> Path:
    """Return filesystem path to OntServe project root."""
    return Path(os.environ.get(
        'ONTSERVE_BASE_PATH',
        str(Path(__file__).resolve().parent.parent.parent.parent / 'OntServe')
    ))


def get_ontserve_mcp_url() -> str:
    """Return OntServe MCP server URL."""
    return os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')


def get_ontserve_web_url() -> str:
    """Return OntServe web interface URL."""
    return os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
