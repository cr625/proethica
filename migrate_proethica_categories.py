#!/usr/bin/env python3
"""
Migration: Create ProEthica 9-Category Database Tables

Creates the database tables for all 9 ProEthica categories that were implemented
as first-class database models in Phase 4E:
- principles, obligations, states, capabilities, constraints

These tables are needed for the Enhanced Scenario Generation with proper
9-category database modeling instead of JSON metadata.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the ProEthica 9-category tables migration."""
    
    # Database connection details
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
        
        logger.info("Connected to database, creating ProEthica 9-category tables...")
        
        # Check which tables already exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('principles', 'obligations', 'states', 'capabilities', 'constraints');
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Existing ProEthica category tables: {existing_tables}")
        
        # Create Principles table
        if 'principles' not in existing_tables:
            logger.info("Creating principles table...")
            cursor.execute("""
                CREATE TABLE principles (
                    id SERIAL PRIMARY KEY,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    principle_type VARCHAR(50),
                    source_reference VARCHAR(255),
                    ethical_framework VARCHAR(100),
                    priority_level INTEGER DEFAULT 1,
                    applicability_conditions JSON,
                    bfo_class VARCHAR(100),
                    proethica_category VARCHAR(50) DEFAULT 'principle',
                    ontology_uri VARCHAR(500),
                    extraction_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_principles_scenario ON principles(scenario_id);
                CREATE INDEX idx_principles_type ON principles(principle_type);
            """)
        else:
            logger.info("Principles table already exists, skipping")
        
        # Create Obligations table
        if 'obligations' not in existing_tables:
            logger.info("Creating obligations table...")
            cursor.execute("""
                CREATE TABLE obligations (
                    id SERIAL PRIMARY KEY,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    obligation_type VARCHAR(50),
                    duty_bearer VARCHAR(255),
                    duty_recipient VARCHAR(255),
                    obligation_source VARCHAR(255),
                    priority_level INTEGER DEFAULT 1,
                    temporal_scope VARCHAR(50),
                    fulfillment_conditions JSON,
                    bfo_class VARCHAR(100),
                    proethica_category VARCHAR(50) DEFAULT 'obligation',
                    ontology_uri VARCHAR(500),
                    extraction_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_obligations_scenario ON obligations(scenario_id);
                CREATE INDEX idx_obligations_type ON obligations(obligation_type);
                CREATE INDEX idx_obligations_bearer ON obligations(duty_bearer);
            """)
        else:
            logger.info("Obligations table already exists, skipping")
        
        # Create States table
        if 'states' not in existing_tables:
            logger.info("Creating states table...")
            cursor.execute("""
                CREATE TABLE states (
                    id SERIAL PRIMARY KEY,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    state_type VARCHAR(50),
                    entity_affected VARCHAR(255),
                    initial_value VARCHAR(255),
                    current_value VARCHAR(255),
                    change_indicators JSON,
                    temporal_context VARCHAR(100),
                    bfo_class VARCHAR(100),
                    proethica_category VARCHAR(50) DEFAULT 'state',
                    ontology_uri VARCHAR(500),
                    extraction_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_states_scenario ON states(scenario_id);
                CREATE INDEX idx_states_type ON states(state_type);
                CREATE INDEX idx_states_entity ON states(entity_affected);
            """)
        else:
            logger.info("States table already exists, skipping")
        
        # Create Capabilities table
        if 'capabilities' not in existing_tables:
            logger.info("Creating capabilities table...")
            cursor.execute("""
                CREATE TABLE capabilities (
                    id SERIAL PRIMARY KEY,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    capability_type VARCHAR(50),
                    capability_holder VARCHAR(255),
                    skill_category VARCHAR(100),
                    competency_level VARCHAR(50),
                    authority_scope VARCHAR(255),
                    development_context TEXT,
                    evolution_indicators JSON,
                    bfo_class VARCHAR(100),
                    proethica_category VARCHAR(50) DEFAULT 'capability',
                    ontology_uri VARCHAR(500),
                    extraction_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_capabilities_scenario ON capabilities(scenario_id);
                CREATE INDEX idx_capabilities_type ON capabilities(capability_type);
                CREATE INDEX idx_capabilities_holder ON capabilities(capability_holder);
            """)
        else:
            logger.info("Capabilities table already exists, skipping")
        
        # Create Constraints table
        if 'constraints' not in existing_tables:
            logger.info("Creating constraints table...")
            cursor.execute("""
                CREATE TABLE constraints (
                    id SERIAL PRIMARY KEY,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    constraint_type VARCHAR(50),
                    constraining_factor VARCHAR(255),
                    constrained_entity VARCHAR(255),
                    severity_level VARCHAR(50),
                    temporal_applicability VARCHAR(100),
                    constraint_source VARCHAR(255),
                    workaround_possibilities JSON,
                    relationships JSON,
                    bfo_class VARCHAR(100),
                    proethica_category VARCHAR(50) DEFAULT 'constraint',
                    ontology_uri VARCHAR(500),
                    extraction_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_constraints_scenario ON constraints(scenario_id);
                CREATE INDEX idx_constraints_type ON constraints(constraint_type);
                CREATE INDEX idx_constraints_factor ON constraints(constraining_factor);
            """)
        else:
            logger.info("Constraints table already exists, skipping")
        
        # Commit the changes
        conn.commit()
        logger.info("✅ ProEthica 9-category tables migration completed successfully")
        
        # Verify the changes
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('principles', 'obligations', 'states', 'capabilities', 'constraints')
            ORDER BY table_name;
        """)
        
        verification = cursor.fetchall()
        logger.info("Verification - Created tables:")
        for row in verification:
            logger.info(f"  ✅ {row[0]}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migration()
