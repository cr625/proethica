#!/usr/bin/env python3
"""
Update existing term links with correct entity types from the ontology
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app import create_app, db
from app.models.section_term_link import SectionTermLink
from app.services.ontology_term_recognition_service import OntologyTermRecognitionService

def main():
    """Update existing term links with entity types from ontology."""
    app = create_app('config')
    
    with app.app_context():
        print("Updating existing term links with entity types...")
        
        # Initialize the ontology service to get entity type mappings
        print("Loading ontology terms...")
        recognition_service = OntologyTermRecognitionService()
        
        if not recognition_service.ontology_terms:
            print("❌ No ontology terms loaded!")
            return
        
        print(f"✅ Loaded {len(recognition_service.ontology_terms)} ontology terms")
        
        # Get all term links that need updating
        term_links = SectionTermLink.query.filter_by(entity_type='unknown').all()
        print(f"Found {len(term_links)} term links to update")
        
        updated_count = 0
        
        for link in term_links:
            # Find the entity type for this ontology URI
            entity_type = None
            
            # Look through the ontology terms to find the entity type
            for term_key, term_info in recognition_service.ontology_terms.items():
                if term_info['uri'] == link.ontology_uri:
                    entity_type = term_info.get('entity_type', 'unknown')
                    break
            
            if entity_type and entity_type != 'unknown':
                link.entity_type = entity_type
                updated_count += 1
                
                if updated_count % 50 == 0:
                    print(f"Updated {updated_count} term links...")
        
        # Commit the changes
        try:
            db.session.commit()
            print(f"✅ Successfully updated {updated_count} term links with entity types!")
            
            # Show statistics by entity type
            from sqlalchemy import text
            result = db.session.execute(text("""
                SELECT entity_type, COUNT(*) as count
                FROM section_term_links 
                GROUP BY entity_type 
                ORDER BY count DESC
            """))
            
            print("\n📊 Entity type distribution:")
            for row in result:
                print(f"   {row[0]}: {row[1]} links")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {str(e)}")
            raise

if __name__ == '__main__':
    main()