#!/usr/bin/env python3
"""
Plan for organizing root directory files into proper structure.
"""

import os
import shutil
from pathlib import Path

def create_cleanup_plan():
    """Create a plan for organizing root directory files."""
    
    # Files that should STAY in root (essential)
    keep_in_root = {
        # Core application files
        'run.py',           # Main Flask entry point
        'wsgi.py',          # WSGI entry point
        'config.py',        # Main config file
        'requirements.txt', # Python dependencies
        'consolidated_requirements.txt', # Alternative requirements
        'requirements-mcp.txt', # MCP requirements
        'package.json',     # Node.js dependencies
        'pytest.ini',      # Test configuration
        '.env',            # Environment variables (if exists)
        '.env.example',    # Environment template
        
        # Docker/deployment
        'docker-compose.yml',
        'postgres.Dockerfile',
        'deploy.sh',
        
        # Documentation (core)
        'README.md',
        'LICENSE', 
        'CLAUDE.md',       # Project instructions
        
        # Directories that are properly organized
        'app/',
        'config/', 
        'docs/',
        'tests/',
        'archive/',
        'pending_delete/',
        'tmp/',
        'scratch/',
        'venv/',
        'logs/',
        'migrations/',
        'ontologies/',
        'backups/'
    }
    
    # Files to move to specific locations
    move_plan = {
        # Documentation files
        'ENHANCED_SCENARIO_QUICK_START.md': 'docs/',
        'ONTOLOGY_VALIDATION_REPORT.md': 'docs/',
        'ontology_comparison_report.md': 'docs/',
        
        # Database/SQL files  
        'init-pgvector.sql': 'sql/',
        'database_backup_working_concept_saving_20250720_050236.sql': 'backups/',
        'restore_working_concept_saving_backup.sh': 'backups/',
        
        # Script files
        'check_db_ontologies.py': 'scripts/',
        'detailed_ontology_check.py': 'scripts/',
        'ontology_validation.py': 'scripts/',
        'setup_project.py': 'scripts/',
        'update_scenario_decisions.py': 'scripts/',
        'run_with_dashboard.py': 'scripts/',
        
        # Log files
        'anthropic_api_compatibility_issues.log': 'logs/archive_20250815/',
        
        # JAR files
        'neosemantics-5.20.0.jar': 'archive/jars/',
        
        # Directories that should be moved/reorganized
        'demo/': 'app/templates/demo/',  # Demo templates
        'templates/': 'archive/unused_root_20250815/',  # Appears to be unused root templates
        'sql/': None,  # Already exists, keep as is
        'data/': None,  # Already exists, keep as is  
        'deployments/': None, # Already exists, keep as is
        'docker/': None, # Already exists, keep as is
        'mclaren/': None, # Already exists, keep as is
        'mcp/': None, # Already exists, keep as is
        'nspe-pipeline/': None, # Already exists, keep as is
        'ontology_data/': None, # Already exists, keep as is
        'ontology_editor/': None, # Already exists, keep as is
        'realm/': None, # Already exists, keep as is
        'run/': None, # Already exists, keep as is
        'screenshots/': None, # Already exists, keep as is
        'scripts/': None, # Already exists, keep as is
        'server_config/': None, # Already exists, keep as is
        'ttl_triple_association/': None, # Already exists, keep as is
        'utils/': None # Already exists, keep as is
    }
    
    return keep_in_root, move_plan

def preview_cleanup():
    """Preview what the cleanup would do."""
    keep_in_root, move_plan = create_cleanup_plan()
    
    print("🧹 ROOT DIRECTORY CLEANUP PLAN")
    print("=" * 50)
    
    print("\n✅ Files/Directories to KEEP in root:")
    for item in sorted(keep_in_root):
        print(f"   {item}")
    
    print("\n📁 Files to MOVE:")
    for source, destination in sorted(move_plan.items()):
        if destination:
            print(f"   {source} → {destination}")
        else:
            print(f"   {source} (keep as-is)")
    
    print(f"\n📊 Summary:")
    print(f"   Files to keep in root: {len(keep_in_root)}")
    print(f"   Files to move: {len([d for d in move_plan.values() if d])}")
    
    return move_plan

if __name__ == "__main__":
    preview_cleanup()