"""
Celery Configuration for ProEthica

This module creates and configures Celery for background task processing
of the scenario pipeline (case analysis workflow).

IMPORTANT: This module should only be imported when starting the Celery worker,
not when running the Flask app. This prevents blueprint registration issues.

Usage:
    celery -A celery_config.celery worker --loglevel=info

    Or with explicit PYTHONPATH:
    PYTHONPATH=/home/chris/onto:$PYTHONPATH celery -A celery_config.celery worker --loglevel=info
"""
import sys
from pathlib import Path

# Add parent directory to path for shared module access
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from celery import Celery
from celery.schedules import crontab
import logging
import os
from dotenv import load_dotenv

# Load .env file before anything else (critical for API keys)
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"Loaded environment from {env_path}")

logger = logging.getLogger(__name__)

# Lazy initialization - only create app when needed
_celery_instance = None


def get_celery():
    """
    Get or create Celery instance (lazy initialization).

    This ensures the Flask app is only created when Celery is actually needed,
    preventing blueprint registration issues during Flask startup.

    Returns:
        Celery: Configured Celery instance
    """
    global _celery_instance

    if _celery_instance is None:
        from app import create_app

        app = create_app()

        celery = Celery(
            app.import_name,
            broker='redis://localhost:6379/1',  # Use DB 1 to avoid conflicts with OntExtract
            backend='redis://localhost:6379/1',
            include=['app.tasks.pipeline_tasks']
        )

        # Configure Celery
        celery.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=7200,  # 2 hour hard limit (LLM extraction can be slow)
            task_soft_time_limit=6000,  # 100 minutes soft limit
            worker_prefetch_multiplier=1,  # One task at a time
            worker_max_tasks_per_child=20,  # Restart worker after 20 tasks
            broker_connection_retry_on_startup=True
        )

        # Beat schedule for periodic tasks (monitoring heartbeat)
        healthchecks_url = os.environ.get('HEALTHCHECKS_PING_URL')
        if healthchecks_url:
            celery.conf.beat_schedule = {
                'heartbeat-every-5-minutes': {
                    'task': 'proethica.tasks.heartbeat',
                    'schedule': 300.0,  # Every 5 minutes
                },
            }
            logger.info("Healthchecks.io heartbeat configured")

        # Set Flask app context for all tasks
        class ContextTask(celery.Task):
            """Base task class that runs in Flask app context."""

            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask
        _celery_instance = celery

        logger.info("ProEthica Celery configured successfully")

    return _celery_instance


# For Celery worker command line: celery -A celery_config.celery worker
celery = get_celery()
