#!/usr/bin/env python3
"""
Migration script to move TemporaryConcept records to OntServe draft ontologies.

This script will:
1. Read all TemporaryConcept records from ProEthica database
2. Group them by document/world combinations 
3. Create corresponding draft ontologies in OntServe
4. Optionally remove the old TemporaryConcept records after successful migration
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_proethica_app():
    """Create ProEthica Flask app with proper configuration."""
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
    
    # Set required environment variables
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['SECRET_KEY'] = 'migration-script-key'
    os.environ['WTF_CSRF_ENABLED'] = 'false'  # Disable CSRF for migration
    os.environ['FLASK_ENV'] = 'development'
    
    # Try different approaches to create the app
    from app import create_app
    from flask import Flask
    
    try:
        # Try the standard way first
        app = create_app()
    except Exception as e:
        logger.warning(f"Standard app creation failed: {e}")
        # Create app directly using Flask and minimal config
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'migration-script-key'
        
        # Initialize SQLAlchemy
        from app.models import db
        db.init_app(app)
    
    # Ensure database URI is set
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    
    return app

async def migrate_temporary_concepts():
    """Main migration function."""
    logger.info("🔄 Starting migration from TemporaryConcept to OntServe draft ontologies...")
    
    # Create ProEthica app and get data
    try:
        app = create_proethica_app()
        
        with app.app_context():
            from app.models.temporary_concept import TemporaryConcept
            from app.models.document import Document
            from app.models.world import World
            from app.services.draft_ontology_service import DraftOntologyService
            
            # Get all temporary concepts
            concepts = TemporaryConcept.query.all()
            logger.info(f"Found {len(concepts)} TemporaryConcept records to migrate")
            
            if not concepts:
                logger.info("✅ No TemporaryConcept records found - migration not needed")
                return True
            
            # Group by document/world combinations
            groups = {}
            for concept in concepts:
                key = (concept.document_id, concept.world_id, concept.session_id)
                if key not in groups:
                    groups[key] = []
                groups[key].append(concept)
            
            logger.info(f"Found {len(groups)} document/world/session combinations to migrate")
            
            # Migrate each group
            migrated_count = 0
            failed_count = 0
            
            for (doc_id, world_id, session_id), group in groups.items():
                try:
                    # Get document and world info
                    doc = Document.query.get(doc_id)
                    world = World.query.get(world_id)
                    
                    doc_title = doc.title if doc else f"Document {doc_id}"
                    world_name = world.name if world else f"World {world_id}"
                    
                    logger.info(f"Migrating {len(group)} concepts from '{doc_title}' in '{world_name}' (session {session_id})")
                    
                    # Convert concepts to draft ontology format
                    draft_concepts = []
                    extraction_method = None
                    created_by = None
                    
                    for temp_concept in group:
                        if extraction_method is None:
                            extraction_method = temp_concept.extraction_method or 'llm'
                        if created_by is None:
                            created_by = temp_concept.created_by or 'ProEthica Migration'
                        
                        # Convert concept data to draft format
                        concept_data = temp_concept.concept_data or {}
                        
                        draft_concept = {
                            "uri": concept_data.get("uri", concept_data.get("id", f"migrated_concept_{temp_concept.id}")),
                            "label": concept_data.get("label", concept_data.get("name", "Migrated Concept")),
                            "type": concept_data.get("type", concept_data.get("category", "concept")),
                            "description": concept_data.get("description", concept_data.get("comment", "")),
                            "metadata": {
                                "migrated_from_temp_concept": True,
                                "original_temp_concept_id": temp_concept.id,
                                "original_session_id": session_id,
                                "original_status": temp_concept.status,
                                "original_extraction_timestamp": temp_concept.extraction_timestamp.isoformat() if temp_concept.extraction_timestamp else None,
                                "document_id": doc_id,
                                "world_id": world_id,
                                "extraction_method": extraction_method,
                                "created_by": created_by,
                                "migrated_at": datetime.utcnow().isoformat(),
                                "original_data": concept_data  # Preserve full original data
                            }
                        }
                        
                        # Add any additional properties from original concept
                        for key, value in concept_data.items():
                            if key not in ["uri", "label", "type", "description", "id", "name", "category", "comment"]:
                                draft_concept[key] = value
                        
                        draft_concepts.append(draft_concept)
                    
                    # Create unique draft ontology name
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    draft_name = f"migrated_doc{doc_id}_world{world_id}_{timestamp}"
                    
                    # Store in OntServe as draft ontology
                    result = await DraftOntologyService.store_concepts(
                        concepts=draft_concepts,
                        document_id=doc_id,
                        world_id=world_id,
                        draft_name=draft_name,
                        extraction_method=extraction_method,
                        created_by=created_by + " (Migration)",
                        base_imports=["prov-o-base"]
                    )
                    
                    if result:
                        logger.info(f"✅ Successfully migrated {len(draft_concepts)} concepts to draft ontology: {result}")
                        migrated_count += len(draft_concepts)
                        
                        # TODO: Optionally mark original concepts as migrated or delete them
                        # For now, we'll leave them in place for safety
                        
                    else:
                        logger.error(f"❌ Failed to migrate concepts from session {session_id}")
                        failed_count += len(draft_concepts)
                    
                except Exception as e:
                    logger.error(f"❌ Error migrating session {session_id}: {e}")
                    failed_count += len(group)
                    continue
            
            logger.info(f"🎉 Migration completed!")
            logger.info(f"✅ Successfully migrated: {migrated_count} concepts")
            logger.info(f"❌ Failed to migrate: {failed_count} concepts")
            
            return failed_count == 0
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def cleanup_temporary_concepts():
    """Optional cleanup of migrated TemporaryConcept records."""
    logger.warning("🧹 Cleanup of TemporaryConcept records not implemented yet")
    logger.warning("   Original TemporaryConcept records left in place for safety")
    logger.warning("   Consider manual cleanup after verifying migration success")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate TemporaryConcept records to OntServe draft ontologies')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without actually doing it')
    parser.add_argument('--cleanup', action='store_true', help='Clean up original TemporaryConcept records after migration')
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No actual migration will be performed")
        # TODO: Implement dry run logic
        logger.warning("Dry run mode not implemented yet")
        return
    
    # Ensure OntServe is available
    ontserve_url = os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
    logger.info(f"Using OntServe at: {ontserve_url}")
    
    try:
        # Run the migration
        success = asyncio.run(migrate_temporary_concepts())
        
        if success:
            logger.info("🎉 Migration completed successfully!")
            
            if args.cleanup:
                cleanup_temporary_concepts()
        else:
            logger.error("❌ Migration failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()