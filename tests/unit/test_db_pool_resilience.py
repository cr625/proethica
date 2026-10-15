"""Database pool resilience against server-side connection loss.

Regression coverage for the production 500s of 2026-10-15 06:56/07:00 UTC.
An unattended operating-system upgrade restarted PostgreSQL on the droplet;
each gunicorn worker then handed its idle pooled connection -- already
closed by the server -- to the next request, raising
``psycopg2.OperationalError: SSL connection has been closed unexpectedly``
on the first query (observed on /cases/133/structure and other routes).
The same failure was recorded for 2026-10-09 in the ROADMAP.

The pool must discard a dead connection at checkout (pool_pre_ping) and
retire connections on a bounded lifetime (pool_recycle), so a PostgreSQL
restart is a transparent reconnect rather than a user-visible 500.
"""
from sqlalchemy import create_engine, text


def test_engine_options_enable_pre_ping_and_recycle():
    """The base configuration carries the pool resilience options.

    Development, production, and testing configurations all inherit from
    Config, so asserting the base class covers every deployment.
    """
    from config import Config

    options = Config.SQLALCHEMY_ENGINE_OPTIONS
    assert options['pool_pre_ping'] is True
    assert options['pool_recycle'] == 300


def test_engine_pool_applies_pre_ping_and_recycle(app):
    """Flask-SQLAlchemy builds the request engine with those options."""
    from app.models import db

    with app.app_context():
        pool = db.engine.pool
        assert pool._pre_ping is True
        assert pool._recycle == 300


def test_dead_pooled_connection_is_discarded_at_checkout(app):
    """A connection killed server-side while idle must not fail the next query.

    Reproduces the incident mechanics: check out a connection, return it
    idle to the pool, terminate its backend from a separate connection
    (the PostgreSQL restart), then run the first query of the next request.
    """
    from app.models import db

    with app.app_context():
        with db.engine.connect() as conn:
            backend_pid = conn.execute(text("SELECT pg_backend_pid()")).scalar()

        admin_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        try:
            with admin_engine.connect() as admin_conn:
                terminated = admin_conn.execute(
                    text("SELECT pg_terminate_backend(:pid)"),
                    {'pid': backend_pid},
                ).scalar()
                admin_conn.commit()
        finally:
            admin_engine.dispose()
        assert terminated is True

        # First query of the next request: pre-fix this raised
        # OperationalError (SSL connection has been closed unexpectedly).
        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar() == 1
