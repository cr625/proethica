#!/usr/bin/env python3
"""
Direct database script to create experiment tables.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection parameters
DB_PARAMS = {
    'host': 'localhost',
    'port': 5433,
    'database': 'ai_ethical_dm',
    'user': 'postgres',
    'password': 'PASS'
}

# SQL statements to create tables
CREATE_TABLES_SQL = """
-- Create experiment_runs table
CREATE TABLE IF NOT EXISTS experiment_runs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    config JSONB,
    status VARCHAR(50)
);

-- Create prediction_targets table
CREATE TABLE IF NOT EXISTS prediction_targets (
    id SERIAL PRIMARY KEY,
    experiment_run_id INTEGER REFERENCES experiment_runs(id),
    name VARCHAR(255) NOT NULL,
    description TEXT
);

-- Create experiment_predictions table
CREATE TABLE IF NOT EXISTS experiment_predictions (
    id SERIAL PRIMARY KEY,
    experiment_run_id INTEGER REFERENCES experiment_runs(id),
    document_id INTEGER,
    condition VARCHAR(50),
    target VARCHAR(50),
    prediction_text TEXT,
    reasoning TEXT,
    prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_info JSONB
);

-- Create experiment_evaluations table
CREATE TABLE IF NOT EXISTS experiment_evaluations (
    id SERIAL PRIMARY KEY,
    experiment_run_id INTEGER REFERENCES experiment_runs(id),
    prediction_id INTEGER REFERENCES experiment_predictions(id),
    evaluator_id VARCHAR(255),
    reasoning_quality INTEGER,
    persuasiveness INTEGER,
    coherence INTEGER,
    accuracy INTEGER,
    agreement INTEGER,
    support_quality INTEGER,
    preference_score INTEGER,
    alignment_score INTEGER,
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_info JSONB
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_predictions_experiment_run ON experiment_predictions(experiment_run_id);
CREATE INDEX IF NOT EXISTS idx_predictions_document ON experiment_predictions(document_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_experiment_run ON experiment_evaluations(experiment_run_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_prediction ON experiment_evaluations(prediction_id);
"""

def create_tables():
    """Create experiment tables in the database."""
    conn = None
    cursor = None
    
    try:
        # Connect to database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Execute the CREATE TABLE statements
        logger.info("Creating experiment tables...")
        cursor.execute(CREATE_TABLES_SQL)
        
        # Commit the changes
        conn.commit()
        logger.info("Tables created successfully!")
        
        # Verify tables
        verify_tables(cursor)
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating tables: {str(e)}")
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def verify_tables(cursor):
    """Verify that tables were created."""
    tables = ['experiment_runs', 'prediction_targets', 'experiment_predictions', 'experiment_evaluations']
    
    for table in tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, (table,))
        
        exists = cursor.fetchone()[0]
        if exists:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"✓ Table '{table}' exists (rows: {count})")
        else:
            logger.error(f"✗ Table '{table}' does not exist")

if __name__ == "__main__":
    logger.info("Starting experiment tables creation...")
    create_tables()
    logger.info("Done!")