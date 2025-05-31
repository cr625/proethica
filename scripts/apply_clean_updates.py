#!/usr/bin/env python3
"""
Apply clean updates: ontology and service without backward compatibility.
"""

import os
import shutil
import subprocess
from datetime import datetime

def backup_file(filepath):
    """Create a backup of a file with timestamp."""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)
        print(f"✅ Backed up {filepath}")
        return backup_path
    return None

def update_ontology():
    """Update the intermediate ontology with GuidelineConceptTypes."""
    source = "/home/chris/proethica/ontologies/proethica-intermediate-updated.ttl"
    target = "/home/chris/proethica/ontologies/proethica-intermediate.ttl"
    
    print("🔄 Updating ProEthica intermediate ontology...")
    
    # Backup existing ontology
    backup_file(target)
    
    # Copy new ontology
    shutil.copy2(source, target)
    print(f"✅ Updated {target}")
    
    # Also update the MCP ontology directory
    mcp_target = "/home/chris/proethica/mcp/ontology/proethica-intermediate.ttl"
    if os.path.exists(os.path.dirname(mcp_target)):
        backup_file(mcp_target)
        shutil.copy2(source, mcp_target)
        print(f"✅ Updated MCP copy")

def update_service():
    """Update the guideline analysis service with clean version."""
    source = "/home/chris/proethica/app/services/guideline_analysis_service_clean.py"
    target = "/home/chris/proethica/app/services/guideline_analysis_service.py"
    
    print("\n🔄 Updating GuidelineAnalysisService...")
    
    # Backup existing service
    backup_file(target)
    
    # Copy new service
    shutil.copy2(source, target)
    print(f"✅ Updated {target}")

def reset_database():
    """Reset guideline data in database."""
    print("\n🔄 Resetting database...")
    
    sql_file = "/home/chris/proethica/sql/reset_guidelines.sql"
    cmd = [
        'docker', 'exec', '-i', 'proethica-postgres',
        'psql', '-U', 'postgres', '-d', 'ai_ethical_dm', '-f', '-'
    ]
    
    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        result = subprocess.run(cmd, input=sql_content, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Database reset successfully")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"❌ Database reset failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error resetting database: {str(e)}")
        return False
    
    return True

def main():
    print("=" * 80)
    print("ProEthica Clean Update")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Update the intermediate ontology with GuidelineConceptTypes")
    print("2. Install the clean GuidelineAnalysisService (no backward compatibility)")
    print("3. Reset the database (delete existing guideline)")
    print()
    print("Changes:")
    print("- 'Condition' replaced with 'State'")
    print("- Strict type validation (no fallbacks)")
    print("- Requires ontology to define all 8 concept types")
    print()
    
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Update cancelled.")
        return
    
    print()
    
    try:
        # Update ontology
        update_ontology()
        
        # Update service
        update_service()
        
        # Reset database
        if reset_database():
            print("\n✅ All updates completed successfully!")
            print()
            print("The system now uses these 8 GuidelineConceptTypes:")
            print("1. Role - Professional positions")
            print("2. Principle - Ethical values")
            print("3. Obligation - Professional duties") 
            print("4. State - Conditions and contexts")
            print("5. Resource - Physical/informational entities")
            print("6. Action - Intentional activities")
            print("7. Event - Occurrences")
            print("8. Capability - Skills and abilities")
            print()
            print("Next steps:")
            print("1. Restart the application")
            print("2. Restart the MCP server")
            print("3. Add your guideline again (will get ID = 1)")
            print("4. Extract concepts with the new system")
        else:
            print("\n⚠️  Updates applied but database reset had issues")
            print("You may need to manually clean the database")
        
    except Exception as e:
        print(f"\n❌ Error during update: {str(e)}")
        print("Please check the error and try again.")

if __name__ == "__main__":
    main()