#!/usr/bin/env python3
"""
Migration script to move ontologies from files to the database.

This script:
1. Creates the necessary database tables if they don't exist
2. Reads ontology files from the filesystem
3. Creates database records for each ontology
4. Updates world references to point to database records
5. Creates version history in the database
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.world import World
from ontology_editor.services.file_storage_utils import read_ontology_file

def migrate_ontologies():
    """Migrate file-based ontologies to database."""
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        print("Beginning migration of ontologies from files to database...")
        
        # 1. Get all worlds with ontology sources
        worlds = World.query.filter(World.ontology_source.isnot(None)).all()
        print(f"Found {len(worlds)} worlds with ontology sources")
        
        # 2. For each world, create or find ontology record
        for world in worlds:
            if not world.ontology_source:
                continue
                
            print(f"\nProcessing world {world.id}: {world.name}")
            print(f"  Ontology source: {world.ontology_source}")
            
            # Extract domain ID from source (strip .ttl if present)
            source = world.ontology_source
            if source.lower().endswith('.ttl'):
                domain_id = source[:-4]
            else:
                domain_id = source
                
            # Convert dashes to underscores for filesystem access
            fs_domain_id = domain_id.replace('-', '_')
            
            print(f"  Domain ID: {domain_id}, Filesystem ID: {fs_domain_id}")
            
            # Check if ontology already exists in DB
            ontology = Ontology.query.filter_by(domain_id=domain_id).first()
            
            if not ontology:
                print(f"  Creating new ontology record for {domain_id}")
                
                # Read content from file
                content = read_ontology_file(fs_domain_id, 'main/current.ttl')
                
                if content is None:
                    print(f"  WARNING: Could not read content for {domain_id}")
                    # Try to check if file exists
                    base_dir = os.path.join(os.path.dirname(__file__), '../ontologies')
                    filepath = os.path.join(base_dir, 'domains', fs_domain_id, 'main/current.ttl')
                    print(f"  Looking for file at: {filepath}")
                    if os.path.exists(filepath):
                        print(f"  File exists but couldn't be read")
                    else:
                        print(f"  File does not exist")
                    continue
                
                # Create new ontology record
                ontology = Ontology(
                    name=domain_id.replace('-', ' ').replace('_', ' ').title(),
                    description=f"Ontology for {domain_id.replace('-', ' ').replace('_', ' ')}",
                    domain_id=domain_id,
                    content=content
                )
                db.session.add(ontology)
                db.session.flush()  # Get ID without committing
                
                print(f"  Created ontology record with ID: {ontology.id}")
                
                # Create first version
                version = OntologyVersion(
                    ontology_id=ontology.id,
                    version_number=1,
                    content=content,
                    commit_message="Initial migration"
                )
                db.session.add(version)
                print(f"  Created initial version record")
                
                # Check for version history
                try:
                    # Check for version directories
                    base_dir = os.path.join(os.path.dirname(__file__), '../ontologies')
                    versions_dir = os.path.join(base_dir, 'domains', fs_domain_id, 'main/versions')
                    
                    if os.path.exists(versions_dir) and os.path.isdir(versions_dir):
                        print(f"  Found versions directory: {versions_dir}")
                        version_files = [f for f in os.listdir(versions_dir) if f.startswith('v') and f.endswith('.ttl')]
                        
                        if version_files:
                            print(f"  Found {len(version_files)} version files")
                            
                            # Sort by version number
                            version_files.sort(key=lambda f: int(f[1:-4]))
                            
                            # Start from version 2 since we already created version 1
                            for i, vfile in enumerate(version_files, 2):
                                version_content = read_ontology_file(fs_domain_id, f"main/versions/{vfile}")
                                if version_content:
                                    v = OntologyVersion(
                                        ontology_id=ontology.id,
                                        version_number=i,
                                        content=version_content,
                                        commit_message=f"Migrated from {vfile}"
                                    )
                                    db.session.add(v)
                                    print(f"  Added version {i} from {vfile}")
                except Exception as e:
                    print(f"  ERROR processing versions: {str(e)}")
            else:
                print(f"  Ontology record for {domain_id} already exists with ID: {ontology.id}")
            
            # Update world reference
            world.ontology_id = ontology.id
            print(f"  Updated world {world.id} to use ontology ID {ontology.id}")
        
        # Commit all changes
        print("\nCommitting all changes to database...")
        db.session.commit()
        print("Migration complete!")
        
        # Summary
        ontologies = Ontology.query.all()
        versions = OntologyVersion.query.all()
        worlds_updated = World.query.filter(World.ontology_id.isnot(None)).count()
        
        print("\nMigration Summary:")
        print(f"- Created {len(ontologies)} ontology records")
        print(f"- Created {len(versions)} version records")
        print(f"- Updated {worlds_updated} world records")
        
if __name__ == "__main__":
    migrate_ontologies()
