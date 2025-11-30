"""
Celery Tasks for ProEthica Pipeline Processing

This package contains background tasks for automated case analysis.
Tasks run in separate Celery worker processes with Flask app context.

Usage:
    # Start worker
    celery -A celery_config.celery worker --loglevel=info

    # Queue a case for processing
    from app.tasks.pipeline_tasks import run_full_pipeline_task
    result = run_full_pipeline_task.delay(case_id=7)
"""
