#!/usr/bin/env python3
"""
Database migration script for Reasoning Trace tables.

Creates the reasoning_traces and reasoning_steps tables for capturing
complete reasoning chains across all ProEthica processes.
"""

import psycopg2
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_reasoning_trace_tables():
    """Create reasoning trace tables and indexes using direct database connection"""
    print("Creating Reasoning Trace database tables...")
    
    # Database connection details (matching other migrations)
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
        
        print("Connected to database, creating reasoning trace tables...")
        
        # Check which tables already exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('reasoning_traces', 'reasoning_steps');
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"Existing reasoning trace tables: {existing_tables}")
        
        # Create reasoning_traces table
        if 'reasoning_traces' not in existing_tables:
            print("Creating reasoning_traces table...")
            cursor.execute("""
                CREATE TABLE reasoning_traces (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL,
                    feature_type VARCHAR(50) NOT NULL,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    total_steps INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'in_progress',
                    total_llm_calls INTEGER DEFAULT 0,
                    total_ontology_queries INTEGER DEFAULT 0,
                    average_confidence REAL,
                    processing_time REAL
                );
                
                -- Create indexes for reasoning_traces
                CREATE INDEX idx_reasoning_traces_case_id ON reasoning_traces(case_id);
                CREATE INDEX idx_reasoning_traces_feature_type ON reasoning_traces(feature_type);
                CREATE INDEX idx_reasoning_traces_status ON reasoning_traces(status);
                CREATE INDEX idx_reasoning_traces_started_at ON reasoning_traces(started_at);
                CREATE INDEX idx_reasoning_traces_session_id ON reasoning_traces(session_id);
            """)
        else:
            print("reasoning_traces table already exists, skipping")
        
        # Create reasoning_steps table
        if 'reasoning_steps' not in existing_tables:
            print("Creating reasoning_steps table...")
            cursor.execute("""
                CREATE TABLE reasoning_steps (
                    id SERIAL PRIMARY KEY,
                    trace_id INTEGER NOT NULL REFERENCES reasoning_traces(id) ON DELETE CASCADE,
                    step_number INTEGER NOT NULL,
                    phase_name VARCHAR(100) NOT NULL,
                    step_type VARCHAR(50) NOT NULL,
                    input_data JSONB,
                    output_data JSONB,
                    processed_result JSONB,
                    confidence_score REAL,
                    processing_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    error_message TEXT,
                    model_used VARCHAR(100),
                    tokens_used INTEGER,
                    temperature REAL,
                    entity_type VARCHAR(100),
                    query_type VARCHAR(50)
                );
                
                -- Create indexes for reasoning_steps
                CREATE INDEX idx_reasoning_steps_trace_id ON reasoning_steps(trace_id);
                CREATE INDEX idx_reasoning_steps_step_number ON reasoning_steps(step_number);
                CREATE INDEX idx_reasoning_steps_step_type ON reasoning_steps(step_type);
                CREATE INDEX idx_reasoning_steps_timestamp ON reasoning_steps(timestamp);
                CREATE INDEX idx_reasoning_steps_phase_name ON reasoning_steps(phase_name);
            """)
        else:
            print("reasoning_steps table already exists, skipping")
        
        # Commit the changes
        conn.commit()
        print("✅ Reasoning trace tables created successfully")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('reasoning_traces', 'reasoning_steps')
            ORDER BY table_name;
        """)
        
        created_tables = [row[0] for row in cursor.fetchall()]
        print("Verification - Created tables:")
        for table in created_tables:
            print(f"  ✅ {table}")
            
            # Show column count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = '{table}';
            """)
            col_count = cursor.fetchone()[0]
            print(f"     📋 {col_count} columns")
            
            # Show index count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM pg_indexes 
                WHERE tablename = '{table}';
            """)
            idx_count = cursor.fetchone()[0]
            print(f"     🔍 {idx_count} indexes")
        
        return len(created_tables) == 2
        
    except Exception as e:
        print(f"❌ Error creating reasoning trace tables: {e}")
        if 'conn' in locals():
            conn.rollback()
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def test_basic_operations():
    """Test basic operations on the new tables"""
    print("\nTesting basic reasoning trace operations...")
    
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ai_ethical_dm',
        'user': 'postgres',
        'password': 'PASS'
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Test inserting a trace
        cursor.execute("""
            INSERT INTO reasoning_traces (case_id, feature_type, session_id)
            VALUES (1, 'test', 'test_session_001')
            RETURNING id;
        """)
        trace_id = cursor.fetchone()[0]
        
        # Test inserting a step
        cursor.execute("""
            INSERT INTO reasoning_steps (
                trace_id, step_number, phase_name, step_type, 
                input_data, output_data, processing_time, confidence_score, model_used
            ) VALUES (
                %s, 1, 'test_phase', 'llm_call',
                '{"test": "input"}', '{"test": "output"}', 1.5, 0.85, 'test-model'
            );
        """, (trace_id,))
        
        # Test relationships
        cursor.execute("""
            SELECT COUNT(*) FROM reasoning_steps WHERE trace_id = %s;
        """, (trace_id,))
        step_count = cursor.fetchone()[0]
        assert step_count == 1, "Step was not inserted correctly"
        
        # Clean up test data
        cursor.execute("DELETE FROM reasoning_steps WHERE trace_id = %s;", (trace_id,))
        cursor.execute("DELETE FROM reasoning_traces WHERE id = %s;", (trace_id,))
        
        conn.commit()
        print("✅ Basic operations test passed")
        return True
        
    except Exception as e:
        print(f"❌ Basic operations test failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def main():
    """Main migration function"""
    print("🔍 ProEthica Reasoning Trace Database Migration")
    print("=" * 50)
    
    # Create tables
    tables_created = create_reasoning_trace_tables()
    
    if not tables_created:
        print("❌ Migration failed - tables not created")
        sys.exit(1)
    
    # Test basic operations
    basic_test_passed = test_basic_operations()
    
    if not basic_test_passed:
        print("⚠️  Tables created but basic operations test failed")
        print("   You may need to check the schema manually")
        sys.exit(1)
    
    print("\n✅ Reasoning Trace migration completed successfully!")
    print("📋 Tables created: reasoning_traces, reasoning_steps")
    print("🔍 Indexes created for optimal query performance")
    print("✅ Basic functionality validated")
    
    print("\nNext steps:")
    print("1. Implement ReasoningInspector service")
    print("2. Add captures to existing services")
    print("3. Build the inspection UI")


if __name__ == "__main__":
    main()
