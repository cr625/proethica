#!/usr/bin/env python3
"""
Script to update the ProEthica intermediate ontology and guideline analysis service
to use dynamic concept types from the ontology.
"""

import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of a file with timestamp."""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)
        print(f"✅ Backed up {filepath} to {backup_path}")
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
        print(f"✅ Updated MCP copy at {mcp_target}")

def update_service():
    """Update the guideline analysis service to use dynamic types."""
    source = "/home/chris/proethica/app/services/guideline_analysis_service_dynamic.py"
    target = "/home/chris/proethica/app/services/guideline_analysis_service.py"
    
    print("\n🔄 Updating GuidelineAnalysisService...")
    
    # Backup existing service
    backup_file(target)
    
    # Copy new service
    shutil.copy2(source, target)
    print(f"✅ Updated {target}")

def main():
    print("=" * 80)
    print("ProEthica Ontology and Service Update")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Update the intermediate ontology to include GuidelineConceptTypes")
    print("2. Update the GuidelineAnalysisService to dynamically query concept types")
    print("3. Create backups of existing files")
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
        
        print("\n✅ Update completed successfully!")
        print()
        print("Next steps:")
        print("1. Restart the application to load the new ontology")
        print("2. Restart the MCP server if it's running")
        print("3. Test concept extraction with the new dynamic types")
        print()
        print("The system now uses these 8 dynamic GuidelineConceptTypes:")
        print("- Role")
        print("- Principle")
        print("- Obligation") 
        print("- State (replaces Condition)")
        print("- Resource")
        print("- Action")
        print("- Event")
        print("- Capability")
        
    except Exception as e:
        print(f"\n❌ Error during update: {str(e)}")
        print("Please check the error and try again.")

if __name__ == "__main__":
    main()