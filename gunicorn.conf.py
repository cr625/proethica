"""
Gunicorn configuration for ProEthica production deployment.

--preload loads the application once in the master process, then forks workers.
This eliminates cold-start delays during --max-requests worker recycling
(embedding model loaded once, shared via copy-on-write) and reduces restart
downtime from ~25s to ~8s.

The post_fork hook disposes the SQLAlchemy connection pool in each worker
so forked processes get their own database connections instead of sharing
the master's connections (which causes "server closed the connection
unexpectedly" errors).
"""

# --- Server ---
bind = "127.0.0.1:5000"
workers = 4

# --- Preloading ---
preload_app = True

# --- Worker lifecycle ---
max_requests = 1000
max_requests_jitter = 50
timeout = 60
graceful_timeout = 30

# --- Logging ---
accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    """Dispose SQLAlchemy connection pool after fork.

    With preload_app=True, the master process loads the app and opens
    DB connections (test connection, prompt seeding). After fork, each
    worker inherits those file descriptors. Disposing the pool forces
    each worker to establish its own connections.
    """
    from wsgi import app
    from app.models import db
    with app.app_context():
        db.engine.dispose()
