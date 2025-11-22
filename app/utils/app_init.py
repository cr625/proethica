"""Helpers for initializing the Flask application."""

import os
from sqlalchemy import create_engine


def smoke_test_db_connection(app):
    """Perform a lightweight database connection test."""
    with app.app_context():
        try:
            engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
            connection = engine.connect()
            connection.close()

            if os.environ.get('DEBUG', '').lower() == 'true':
                print("Database connection successful.")
        except Exception as e:
            print(f"Warning: Database connection error: {str(e)}")
            print("The application may not function correctly without database access.")


def init_csrf_exemptions(app):
    """Apply CSRF exemptions for routes that require it."""
    from app.routes.api_document_annotations import init_csrf_exemption
    from app.routes.cases import init_cases_csrf_exemption
    from app.routes.scenario_pipeline.interactive_builder import init_csrf_exemption as init_scenario_csrf_exemption
    from app.routes.scenario_pipeline.step1 import init_step1_csrf_exemption
    from app.routes.scenario_pipeline.step2 import init_step2_csrf_exemption
    from app.routes.scenario_pipeline.step3 import init_step3_csrf_exemption
    from app.routes.scenario_pipeline.step4 import init_step4_csrf_exemption
    from app.routes.scenario_pipeline.step5 import init_step5_csrf_exemption

    init_csrf_exemption(app)
    init_scenario_csrf_exemption(app)
    init_cases_csrf_exemption(app)
    init_step1_csrf_exemption(app)
    init_step2_csrf_exemption(app)
    init_step3_csrf_exemption(app)
    init_step4_csrf_exemption(app)
    init_step5_csrf_exemption(app)
