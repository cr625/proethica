#!/usr/bin/env python3
"""
Manual Cleanup for Problematic Scenario Records

Directly removes scenario records that are causing schema conflicts
during the clear scenario operation.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def manual_cleanup_scenarios():
    """Manually delete problematic scenario records"""
    print("🔧 Manual cleanup of problematic scenario records...")
    
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
        
        # Find scenarios for case 8 that are causing issues
        cursor.execute("""
            SELECT id, name FROM scenarios 
            WHERE scenario_metadata->>'source_case_id' = '8' 
            OR id IN (33, 34);
        """)
        
        problematic_scenarios = cursor.fetchall()
        print(f"Found problematic scenarios: {problematic_scenarios}")
        
        for scenario_id, scenario_name in problematic_scenarios:
            print(f"Manually deleting scenario {scenario_id}: {scenario_name}")
            
            # Delete in order to avoid foreign key constraints
            
            # Delete capabilities first (this is causing the schema error)
            try:
                cursor.execute("DELETE FROM capabilities WHERE scenario_id = %s;", (scenario_id,))
                print(f"  ✅ Deleted capabilities for scenario {scenario_id}")
            except Exception as e:
                print(f"  ⚠️  Error deleting capabilities: {e}")
            
            # Delete other ProEthica 9-category records
            tables_to_clean = [
                'constraints', 'states', 'obligations', 'principles',
                'characters', 'resources', 'actions', 'events', 'decisions'
            ]
            
            for table in tables_to_clean:
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE scenario_id = %s;", (scenario_id,))
                    print(f"  ✅ Deleted {table} for scenario {scenario_id}")
                except Exception as e:
                    print(f"  ⚠️  Error deleting {table}: {e}")
            
            # Finally delete the scenario itself
            try:
                cursor.execute("DELETE FROM scenarios WHERE id = %s;", (scenario_id,))
                print(f"  ✅ Deleted scenario {scenario_id}")
            except Exception as e:
                print(f"  ❌ Error deleting scenario: {e}")
        
        # Also clean up any reasoning traces for case 8
        cursor.execute("SELECT id, session_id FROM reasoning_traces WHERE case_id = 8;")
        reasoning_traces = cursor.fetchall()
        
        for trace_id, session_id in reasoning_traces:
            print(f"Deleting reasoning trace {trace_id}: {session_id}")
            cursor.execute("DELETE FROM reasoning_steps WHERE trace_id = %s;", (trace_id,))
            cursor.execute("DELETE FROM reasoning_traces WHERE id = %s;", (trace_id,))
            print(f"  ✅ Deleted reasoning trace {trace_id}")
        
        # Commit all changes
        conn.commit()
        
        print("✅ Manual cleanup completed successfully!")
        
        # Verify cleanup
        cursor.execute("""
            SELECT COUNT(*) FROM scenarios 
            WHERE scenario_metadata->>'source_case_id' = '8' 
            OR id IN (33, 34);
        """)
        remaining_scenarios = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reasoning_traces WHERE case_id = 8;")
        remaining_traces = cursor.fetchone()[0]
        
        print(f"Verification:")
        print(f"  - Remaining problematic scenarios: {remaining_scenarios}")
        print(f"  - Remaining reasoning traces: {remaining_traces}")
        
        return remaining_scenarios == 0 and remaining_traces == 0
        
    except Exception as e:
        print(f"❌ Error in manual cleanup: {e}")
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
    print("🔧 ProEthica Manual Scenario Cleanup")
    print("=" * 50)
    
    success = manual_cleanup_scenarios()
    
    if success:
        print("\n✅ Manual cleanup completed successfully!")
        print("📋 Problematic scenario records removed")
        print("🗑️ Reasoning traces cleared")
        print("\nCase 8 should now be able to generate scenarios and clear properly.")
    else:
        print("\n❌ Manual cleanup failed")
        print("You may need to check database constraints manually")

if __name__ == "__main__":
    main()
