#!/bin/bash

# This script sets up the database tables for McLaren's extensional definition analysis
# and processes the NSPE cases using McLaren's approach.
# This is a fixed version that works around the SQLAlchemy URL parsing issue.

echo "Setting up case analysis tables..."
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
python -c "
import sys
import os
from sqlalchemy import create_engine, text
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('create_tables')

# Use direct database URL without going through Flask-SQLAlchemy
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
engine = create_engine(db_url)

try:
    # Create principle_instantiations table
    with engine.connect() as conn:
        conn.execute(text(\"\"\"
            CREATE TABLE IF NOT EXISTS principle_instantiations (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                principle_uri TEXT NOT NULL,
                principle_label TEXT,
                fact_text TEXT NOT NULL,
                fact_context TEXT,
                technique_type TEXT,
                confidence FLOAT DEFAULT 0.5,
                is_negative BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS principle_instantiations_case_id_idx ON principle_instantiations (case_id);
            CREATE INDEX IF NOT EXISTS principle_instantiations_principle_uri_idx ON principle_instantiations (principle_uri);
        \"\"\"))
        
        logger.info('Created principle_instantiations table')
        
        # Create principle_conflicts table
        conn.execute(text(\"\"\"
            CREATE TABLE IF NOT EXISTS principle_conflicts (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                principle1_uri TEXT NOT NULL,
                principle2_uri TEXT NOT NULL,
                principle1_label TEXT,
                principle2_label TEXT,
                resolution_type TEXT,
                override_direction INTEGER DEFAULT 0,
                context TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS principle_conflicts_case_id_idx ON principle_conflicts (case_id);
            CREATE INDEX IF NOT EXISTS principle_conflicts_principle1_uri_idx ON principle_conflicts (principle1_uri);
            CREATE INDEX IF NOT EXISTS principle_conflicts_principle2_uri_idx ON principle_conflicts (principle2_uri);
        \"\"\"))
        
        logger.info('Created principle_conflicts table')
        
        # Create case_operationalization table
        conn.execute(text(\"\"\"
            CREATE TABLE IF NOT EXISTS case_operationalization (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                technique_name TEXT NOT NULL,
                technique_matches JSONB,
                confidence FLOAT DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS case_operationalization_case_id_idx ON case_operationalization (case_id);
            CREATE INDEX IF NOT EXISTS case_operationalization_technique_name_idx ON case_operationalization (technique_name);
        \"\"\"))
        
        logger.info('Created case_operationalization table')
        
        # Create case_triples table
        conn.execute(text(\"\"\"
            CREATE TABLE IF NOT EXISTS case_triples (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                triples TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS case_triples_case_id_idx ON case_triples (case_id);
        \"\"\"))
        
        logger.info('Created case_triples table')
        
        # Check if document table exists
        result = conn.execute(text(\"SELECT to_regclass('public.document')\")).fetchone()
        
        if result[0]:
            conn.execute(text(\"\"\"
                ALTER TABLE principle_instantiations 
                ADD CONSTRAINT IF NOT EXISTS fk_principle_instantiations_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE principle_conflicts 
                ADD CONSTRAINT IF NOT EXISTS fk_principle_conflicts_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE case_operationalization 
                ADD CONSTRAINT IF NOT EXISTS fk_case_operationalization_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE case_triples 
                ADD CONSTRAINT IF NOT EXISTS fk_case_triples_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
            \"\"\"))
            
            logger.info('Added foreign key constraints')
        else:
            logger.warning('Document table not found. Foreign key constraints not added.')
        
        # Add triggers for updated_at timestamps
        conn.execute(text(\"\"\"
            CREATE OR REPLACE FUNCTION update_modified_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE 'plpgsql';
            
            DROP TRIGGER IF EXISTS update_principle_instantiations_timestamp ON principle_instantiations;
            CREATE TRIGGER update_principle_instantiations_timestamp
            BEFORE UPDATE ON principle_instantiations
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
            
            DROP TRIGGER IF EXISTS update_principle_conflicts_timestamp ON principle_conflicts;
            CREATE TRIGGER update_principle_conflicts_timestamp
            BEFORE UPDATE ON principle_conflicts
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
            
            DROP TRIGGER IF EXISTS update_case_operationalization_timestamp ON case_operationalization;
            CREATE TRIGGER update_case_operationalization_timestamp
            BEFORE UPDATE ON case_operationalization
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
            
            DROP TRIGGER IF EXISTS update_case_triples_timestamp ON case_triples;
            CREATE TRIGGER update_case_triples_timestamp
            BEFORE UPDATE ON case_triples
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
        \"\"\"))
        
        logger.info('Added timestamp triggers')
        
        # Commit changes
        conn.commit()
        logger.info('Successfully created all tables for McLaren\'s extensional definition analysis')
        
except Exception as e:
    logger.error(f'Error creating tables: {str(e)}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info('Database tables created successfully')
"

echo "Processing NSPE cases..."
# TODO: Create a direct-to-database version of the case processor script that doesn't rely on Flask
# For now, we'll skip this step and focus on fixing the database connection issues

echo "NSPE case processing was skipped due to SQLAlchemy URL parsing issue"

echo "Processing modern NSPE cases skipped for the same reason"

echo "Done! Database tables have been created, but case analysis is pending a fix for the SQLAlchemy URL parsing issue."
echo "To fix the issue, the URL parsing code in app/__init__.py needs to be updated to handle the escape sequences properly."
