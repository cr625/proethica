#!/usr/bin/env python3
"""
Final Comprehensive Schema Fix for ProEthica Categories

Recreates all ProEthica 9-category tables with schemas that exactly match
the SQLAlchemy models, including all foreign keys and field names.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_schema():
    """Fix all ProEthica category table schemas to exactly match SQLAlchemy models."""
    
    # Database connection details (using postgres admin user)
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ai_ethical_dm',
        'user': 'postgres',
        'password': 'PASS'
    }
    
    try:
        # Connect to database
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        logger.info("Connected to database, recreating ProEthica category tables with exact schemas...")
        
        # Drop all category tables first
        tables_to_drop = ['principles', 'obligations', 'states', 'capabilities', 'constraints']
        for table in tables_to_drop:
            logger.info(f"Dropping {table} table...")
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        
        # Create Principles table (exact match to model)
        logger.info("Creating principles table...")
        cursor.execute("""
            CREATE TABLE principles (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                principle_type VARCHAR(100),
                source VARCHAR(255),
                bfo_class VARCHAR(255) DEFAULT 'BFO_0000031',
                proethica_category VARCHAR(50) DEFAULT 'principle',
                ontology_uri VARCHAR(500),
                extraction_confidence FLOAT DEFAULT 0.0,
                extraction_method VARCHAR(100) DEFAULT 'llm_enhanced',
                validation_notes TEXT,
                applies_from INTEGER,
                applies_until INTEGER,
                principle_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_principles_scenario ON principles(scenario_id);
            CREATE INDEX idx_principles_type ON principles(principle_type);
            GRANT ALL PRIVILEGES ON TABLE principles TO proethica_user;
            GRANT ALL PRIVILEGES ON SEQUENCE principles_id_seq TO proethica_user;
        """)
        
        # Create Obligations table (exact match to model)
        logger.info("Creating obligations table...")
        cursor.execute("""
            CREATE TABLE obligations (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                obligation_type VARCHAR(100),
                severity VARCHAR(50) DEFAULT 'medium',
                source_principle_id INTEGER REFERENCES principles(id),
                legal_basis VARCHAR(255),
                bfo_class VARCHAR(255) DEFAULT 'BFO_0000017',
                proethica_category VARCHAR(50) DEFAULT 'obligation',
                ontology_uri VARCHAR(500),
                extraction_confidence FLOAT DEFAULT 0.0,
                extraction_method VARCHAR(100) DEFAULT 'llm_enhanced',
                validation_notes TEXT,
                triggered_by_event_id INTEGER,
                fulfilled_by_action_id INTEGER,
                deadline TIMESTAMP,
                obligation_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_obligations_scenario ON obligations(scenario_id);
            CREATE INDEX idx_obligations_type ON obligations(obligation_type);
            CREATE INDEX idx_obligations_severity ON obligations(severity);
            GRANT ALL PRIVILEGES ON TABLE obligations TO proethica_user;
            GRANT ALL PRIVILEGES ON SEQUENCE obligations_id_seq TO proethica_user;
        """)
        
        # Create States table (exact match to model)
        logger.info("Creating states table...")
        cursor.execute("""
            CREATE TABLE states (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                state_type VARCHAR(100),
                entity_affected VARCHAR(255),
                initial_value VARCHAR(255),
                current_value VARCHAR(255),
                change_tracking JSON DEFAULT '{}',
                bfo_class VARCHAR(255) DEFAULT 'BFO_0000020',
                proethica_category VARCHAR(50) DEFAULT 'state',
                ontology_uri VARCHAR(500),
                extraction_confidence FLOAT DEFAULT 0.0,
                extraction_method VARCHAR(100) DEFAULT 'llm_enhanced',
                validation_notes TEXT,
                tracked_from INTEGER,
                tracked_until INTEGER,
                state_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_states_scenario ON states(scenario_id);
            CREATE INDEX idx_states_type ON states(state_type);
            CREATE INDEX idx_states_entity ON states(entity_affected);
            GRANT ALL PRIVILEGES ON TABLE states TO proethica_user;
            GRANT ALL PRIVILEGES ON SEQUENCE states_id_seq TO proethica_user;
        """)
        
        # Create Capabilities table (exact match to model)
        logger.info("Creating capabilities table...")
        cursor.execute("""
            CREATE TABLE capabilities (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                capability_type VARCHAR(100),
                capability_holder VARCHAR(255),
                competency_level VARCHAR(50),
                skill_evolution JSON DEFAULT '{}',
                bfo_class VARCHAR(255) DEFAULT 'BFO_0000016',
                proethica_category VARCHAR(50) DEFAULT 'capability',
                ontology_uri VARCHAR(500),
                extraction_confidence FLOAT DEFAULT 0.0,
                extraction_method VARCHAR(100) DEFAULT 'llm_enhanced',
                validation_notes TEXT,
                develops_from INTEGER,
                develops_until INTEGER,
                capability_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_capabilities_scenario ON capabilities(scenario_id);
            CREATE INDEX idx_capabilities_type ON capabilities(capability_type);
            CREATE INDEX idx_capabilities_holder ON capabilities(capability_holder);
            GRANT ALL PRIVILEGES ON TABLE capabilities TO proethica_user;
            GRANT ALL PRIVILEGES ON SEQUENCE capabilities_id_seq TO proethica_user;
        """)
        
        # Create Constraints table (exact match to model)
        logger.info("Creating constraints table...")
        cursor.execute("""
            CREATE TABLE constraints (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                constraint_type VARCHAR(100),
                constraint_source VARCHAR(255),
                severity_level VARCHAR(50),
                affected_entities JSON DEFAULT '{}',
                bfo_class VARCHAR(255) DEFAULT 'BFO_0000031',
                proethica_category VARCHAR(50) DEFAULT 'constraint',
                ontology_uri VARCHAR(500),
                extraction_confidence FLOAT DEFAULT 0.0,
                extraction_method VARCHAR(100) DEFAULT 'llm_enhanced',
                validation_notes TEXT,
                limits_from INTEGER,
                limits_until INTEGER,
                constraint_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_constraints_scenario ON constraints(scenario_id);
            CREATE INDEX idx_constraints_type ON constraints(constraint_type);
            CREATE INDEX idx_constraints_source ON constraints(constraint_source);
            GRANT ALL PRIVILEGES ON TABLE constraints TO proethica_user;
            GRANT ALL PRIVILEGES ON SEQUENCE constraints_id_seq TO proethica_user;
        """)
        
        # Commit the changes
        conn.commit()
        logger.info("✅ All table schemas fixed successfully")
        
        # Verify the changes
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('principles', 'obligations', 'states', 'capabilities', 'constraints')
            ORDER BY table_name, column_name;
        """)
        
        verification = cursor.fetchall()
        logger.info("Verification - All columns created:")
        for row in verification:
            logger.info(f"  {row[0]}.{row[1]}: {row[2]}")
        
    except Exception as e:
        logger.error(f"Schema fix failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_schema()
