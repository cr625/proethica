#!/usr/bin/env python3
"""
Test script for ProEthica experiment implementation.

This script starts a Flask development server to test the experiment interface,
allowing us to interactively test the experiment creation, case selection,
prediction generation, and evaluation workflows.
"""

import os
import sys
import logging
from app import create_app

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_test_server(host='127.0.0.1', port=5050):
    """Run a Flask development server for testing the experiment interface."""
    try:
        # Create app without configuration
        app = create_app()
        
        # Set required configuration directly in app.config
        app.config['ENVIRONMENT'] = 'codespace'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['DEBUG'] = True
        app.config['FLASK_DEBUG'] = True
        
        # Reinitialize database with new configuration
        from app.models import db
        db.init_app(app)
        
        # Specify host and port
        logger.info(f"Starting test server at http://{host}:{port}/experiment/")
        logger.info("Press CTRL+C to stop the server")
        
        # Run the app
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        logger.exception(f"Error running test server: {str(e)}")
        sys.exit(1)

def create_sample_experiment():
    """Create a sample experiment for testing."""
    try:
        # Use direct SQLAlchemy approach instead of Flask app context
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, declarative_base
        import json
        
        # Database connection settings
        DB_HOST = 'localhost'
        DB_PORT = '5433'
        DB_USER = 'postgres'
        DB_PASS = 'PASS'
        DB_NAME = 'ai_ethical_dm'
        
        # Create SQLAlchemy engine and session
        db_uri = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        logger.info(f"Connecting to database with URI: {db_uri}")
        
        engine = create_engine(db_uri)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Import necessary SQLAlchemy components
        from sqlalchemy import Column, Integer, String, Text, DateTime, func
        from sqlalchemy.dialects.postgresql import JSONB
        
        # Create a minimal ExperimentRun class for this operation
        Base = declarative_base()
        
        class ExperimentRun(Base):
            __tablename__ = 'experiment_runs'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(255), nullable=False)
            description = Column(Text)
            created_at = Column(DateTime, default=func.now())
            updated_at = Column(DateTime, default=func.now())
            created_by = Column(String(255))
            config = Column(JSONB)
            status = Column(String(50), default='created')
            
        # Check if test experiment already exists
        from sqlalchemy import text
        result = session.execute(text("SELECT id FROM experiment_runs WHERE name = 'Test Experiment'"))
        existing = result.first()
        
        if existing:
            logger.info(f"Test experiment already exists with ID {existing[0]}")
            return
        
        # Create a new experiment with JSONB config
        config_json = {
            'leave_out_conclusion': True,
            'use_ontology': True,
            'evaluation_metrics': ['reasoning_quality', 'persuasiveness', 'coherence']
        }
        
        # Insert directly using SQL to avoid ORM complications
        from sqlalchemy import text
        insert_stmt = text("""
            INSERT INTO experiment_runs 
            (name, description, created_by, config, status) 
            VALUES (:name, :description, :created_by, :config, :status)
            RETURNING id
        """)
        
        result = session.execute(
            insert_stmt, 
            {
                'name': 'Test Experiment',
                'description': 'This is a test experiment for the ProEthica experiment interface',
                'created_by': 'test_user',
                'config': json.dumps(config_json),
                'status': 'created'
            }
        )
        
        experiment_id = result.scalar()
        session.commit()
        
        logger.info(f"Created test experiment with ID {experiment_id}")
            
    except Exception as e:
        logger.exception(f"Error creating sample experiment: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--create-sample':
        logger.info("Creating sample experiment for testing")
        create_sample_experiment()
    else:
        logger.info("Starting experiment test server")
        run_test_server()
