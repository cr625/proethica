"""Coverage for the production health monitor at scripts/monitor.py.

The droplet cron job runs `/opt/proethica/venv/bin/python
/opt/proethica/scripts/monitor.py` every five minutes. The script was
relocated into docs-internal/scripts/ in May 2026, which removed it from
the deployed tree and broke that cron job; it now lives at the
cron-referenced path again.
"""
import importlib.util
import os
from pathlib import Path

import pytest

MONITOR_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'monitor.py'


@pytest.fixture(scope='module')
def monitor():
    os.environ.setdefault('MONITOR_LOG_FILE', '/tmp/proethica_monitor_test.log')
    spec = importlib.util.spec_from_file_location('proethica_monitor', MONITOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_monitor_script_exists_at_cron_path():
    assert MONITOR_PATH.is_file()


def test_parse_db_uri_plain_postgresql(monitor):
    assert monitor._parse_db_uri(
        'postgresql://proethica_user:secret@localhost:5432/ai_ethical_dm'
    ) == ('proethica_user', 'secret', 'ai_ethical_dm', 'localhost')


def test_parse_db_uri_sqlalchemy_psycopg2(monitor):
    assert monitor._parse_db_uri(
        'postgresql+psycopg2://proethica_user:secret@dbhost:5432/ai_ethical_dm'
    ) == ('proethica_user', 'secret', 'ai_ethical_dm', 'dbhost')


def test_parse_db_uri_fallback_defaults(monitor):
    assert monitor._parse_db_uri('') == (
        'postgres', 'PASS', 'ai_ethical_dm', 'localhost')
