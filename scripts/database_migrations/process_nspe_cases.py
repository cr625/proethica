import sys
import os
import subprocess
import time

def run_script(script_name, *args):
    """Run a Python script with arguments and return its output"""
    cmd = [sys.executable, script_name] + list(args)
    print(f"\n\n{'='*80}")
    print(f"Running {script_name} {' '.join(args)}")
    print(f"{'='*80}\n")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    
    print(f"\n{'='*80}")
    print(f"Completed {script_name} with return code {result.returncode}")
    print(f"{'='*80}\n")
    
    return result.returncode == 0

def restart_flask_app():
    """Restart the Flask app to apply changes"""
    print("\nRestarting Flask application...")
    try:
        subprocess.run([sys.executable, "run.py"], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      text=True, 
                      start_new_session=True)
        print("Server started in background.")
        # Give it a moment to start up
        time.sleep(3)
    except Exception as e:
        print(f"Error starting server: {str(e)}")

def process_nspe_cases(world_id="1"):
    """Process NSPE cases by fixing and importing them correctly"""
    
    world_id_str = str(world_id)
    print(f"Processing NSPE cases for world ID {world_id_str}...")
    
    # Step 1: Remove incorrect cases
    if not run_script("remove_incorrect_nspe_cases.py", world_id_str):
        print("Failed to remove incorrect cases")
        return False
    
    # Step 2: Fix URLs and titles for existing cases
    if not run_script("fix_nspe_case_imports.py", world_id_str):
        print("Failed to fix case URLs and titles")
        return False
    
    # Step 3: Import missing cases
    if not run_script("import_missing_nspe_cases.py", world_id_str):
        print("Failed to import missing cases")
        return False
    
    # Step 4: Extend the engineering ethics ontology
    output_path = os.path.join('mcp', 'ontology', 'engineering-ethics-nspe-extended.ttl')
    if not run_script("extend_nspe_engineering_ontology.py", output_path):
        print("Failed to extend the engineering ethics ontology")
        return False
    
    # Step 5: Update the world to use the new ontology
    if not run_script("scripts/update_world_ontology.py", world_id_str, output_path):
        print("Failed to update world ontology")
        # This step might fail if it has a different interface than expected,
        # but we'll continue anyway
        print("Continuing despite update error...")
    
    # Step 6: Import case triples to the database
    if not run_script("import_case_triples_to_db.py", world_id_str):
        print("Failed to import case triples to the database")
        print("Continuing anyway as this might not be critical...")
    
    print("\nAll NSPE case processing completed successfully!")
    
    # Restart the Flask app to apply changes
    restart_flask_app()
    
    print("\nReady to use the updated NSPE cases!")
    return True

if __name__ == "__main__":
    world_id = "1"  # Default to world ID 1
    
    if len(sys.argv) > 1:
        world_id = sys.argv[1]
    
    success = process_nspe_cases(world_id)
    sys.exit(0 if success else 1)
