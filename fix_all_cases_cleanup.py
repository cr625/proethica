#!/usr/bin/env python3
"""
Universal Case Cleanup Script

Cleans up all problematic scenario records for any case that has schema conflicts.
This script safely removes all scenario-related data using direct SQL to avoid
SQLAlchemy schema mismatches.
"""

import psycopg2
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_case_scenarios(case_id=None):
    """Clean up scenario records for a specific case or all cases"""
    print(f"🔧 Cleaning up scenario records{' for case ' + str(case_id) if case_id else ' for all cases'}...")
    
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
        
        # Find problematic scenarios
        if case_id:
            cursor.execute("""
                SELECT id, name, scenario_metadata->>'source_case_id' as source_case_id
                FROM scenarios 
                WHERE scenario_metadata->>'source_case_id' = %s;
            """, (str(case_id),))
        else:
            # Find all scenarios that might have issues
            cursor.execute("""
                SELECT id, name, scenario_metadata->>'source_case_id' as source_case_id
                FROM scenarios 
                WHERE scenario_metadata IS NOT NULL;
            """)
        
        problematic_scenarios = cursor.fetchall()
        print(f"Found {len(problematic_scenarios)} scenario records to clean")
        
        total_cleaned = 0
        for scenario_id, scenario_name, source_case_id in problematic_scenarios:
            print(f"Cleaning scenario {scenario_id}: {scenario_name} (case {source_case_id})")
            
            # Delete ProEthica 9-category records using direct SQL to avoid schema issues
            tables_to_clean = [
                'capabilities', 'constraints', 'states', 'obligations', 'principles',
                'characters', 'resources', 'actions', 'events', 'decisions'
            ]
            
            for table in tables_to_clean:
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE scenario_id = %s;", (scenario_id,))
                    deleted_count = cursor.rowcount
                    if deleted_count > 0:
                        print(f"  ✅ Deleted {deleted_count} {table} records")
                except Exception as e:
                    print(f"  ⚠️  Error deleting {table}: {e}")
            
            # Delete the scenario itself
            try:
                cursor.execute("DELETE FROM scenarios WHERE id = %s;", (scenario_id,))
                if cursor.rowcount > 0:
                    print(f"  ✅ Deleted scenario {scenario_id}")
                    total_cleaned += 1
            except Exception as e:
                print(f"  ❌ Error deleting scenario: {e}")
        
        # Clean up reasoning traces for the specific case or all cases
        if case_id:
            cursor.execute("SELECT id, session_id FROM reasoning_traces WHERE case_id = %s;", (case_id,))
        else:
            cursor.execute("SELECT id, session_id, case_id FROM reasoning_traces;")
        
        reasoning_traces = cursor.fetchall()
        print(f"Found {len(reasoning_traces)} reasoning traces to clean")
        
        trace_count = 0
        for trace_data in reasoning_traces:
            if case_id:
                trace_id, session_id = trace_data
                trace_case_id = case_id
            else:
                trace_id, session_id, trace_case_id = trace_data
                
            print(f"Deleting reasoning trace {trace_id}: {session_id} (case {trace_case_id})")
            
            # Delete steps first, then trace
            cursor.execute("DELETE FROM reasoning_steps WHERE trace_id = %s;", (trace_id,))
            cursor.execute("DELETE FROM reasoning_traces WHERE id = %s;", (trace_id,))
            trace_count += 1
        
        # If cleaning a specific case, also clear its metadata
        if case_id:
            print(f"Clearing metadata for case {case_id}")
            cursor.execute("""
                UPDATE document 
                SET doc_metadata = doc_metadata - 'latest_scenario' - 'scenario_versions' - 'temporal_analysis' 
                    - 'llm_validation_session' - 'reasoning_trace_id' - 'reasoning_session_id'
                WHERE id = %s;
            """, (case_id,))
            
            if cursor.rowcount > 0:
                print(f"  ✅ Cleared metadata for case {case_id}")
        
        # Commit all changes
        conn.commit()
        
        print(f"\n✅ Cleanup completed successfully!")
        print(f"  - Scenarios cleaned: {total_cleaned}")
        print(f"  - Reasoning traces cleaned: {trace_count}")
        if case_id:
            print(f"  - Case {case_id} metadata cleared")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in cleanup: {e}")
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
    """Main function"""
    print("🔧 ProEthica Universal Case Cleanup")
    print("=" * 50)
    
    # Check if a specific case ID was provided
    case_id = None
    if len(sys.argv) > 1:
        try:
            case_id = int(sys.argv[1])
            print(f"Cleaning up case {case_id} specifically")
        except ValueError:
            print("Invalid case ID provided, cleaning all cases")
    
    success = cleanup_case_scenarios(case_id)
    
    if success:
        if case_id:
            print(f"\n✅ Case {case_id} cleanup completed successfully!")
            print(f"Case {case_id} should now be able to generate and clear scenarios properly.")
        else:
            print(f"\n✅ Universal cleanup completed successfully!")
            print(f"All cases should now be able to generate and clear scenarios properly.")
    else:
        print("\n❌ Cleanup failed")
        print("You may need to check database constraints manually")
    
    print(f"\nUsage: python fix_all_cases_cleanup.py [case_id]")
    print(f"  - No arguments: Clean all cases")  
    print(f"  - With case_id: Clean specific case only")

if __name__ == "__main__":
    main()
