#!/usr/bin/env python3
"""
Fix unmapped concept types - process rdf:type triples that should have type mappings
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
from app.models.entity_triple import EntityTriple
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper
from sqlalchemy import text

def extract_concept_name(subject_uri):
    """Extract human-readable concept name from URI."""
    if not subject_uri:
        return ""
    
    name = subject_uri.split('/')[-1]
    # Convert kebab-case to space-separated
    name = name.replace('-', ' ').replace('_', ' ')
    return name

def main():
    """Process unmapped rdf:type triples through the type mapping system."""
    app = create_app('config')
    
    with app.app_context():
        print("Processing unmapped concept types...")
        
        # Initialize the type mapper
        mapper = GuidelineConceptTypeMapper()
        
        # Get unmapped rdf:type triples
        unmapped_concepts = db.session.execute(text('''
            SELECT id, subject, object_literal, original_llm_type
            FROM entity_triples 
            WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
            AND object_literal IS NULL
            ORDER BY id
        ''')).fetchall()
        
        print(f"Found {len(unmapped_concepts)} unmapped concept types")
        
        updated_count = 0
        
        for concept_row in unmapped_concepts:
            concept_id, subject_uri, current_type, llm_type = concept_row
            
            # Extract concept name from URI
            concept_name = extract_concept_name(subject_uri)
            
            # Use LLM type if available, otherwise use concept name
            type_to_map = llm_type or concept_name
            
            if not type_to_map:
                print(f"⚠️  Skipping concept {concept_id}: no type or name available")
                continue
            
            # Map the type
            result = mapper.map_concept_type(
                llm_type=type_to_map,
                concept_description="",
                concept_name=concept_name
            )
            
            try:
                # Get the concept and update it
                concept = EntityTriple.query.get(concept_id)
                if concept:
                    concept.object_literal = result.mapped_type
                    concept.original_llm_type = type_to_map
                    concept.type_mapping_confidence = result.confidence
                    concept.mapping_justification = result.justification
                    concept.needs_type_review = result.needs_review
                    
                    status = "⚠️  NEEDS REVIEW" if result.needs_review else "✅"
                    print(f"{status} {concept_name}: '{type_to_map}' → {result.mapped_type} ({result.confidence*100:.0f}%)")
                    
                    updated_count += 1
                else:
                    print(f"❌ Concept {concept_id} not found in database")
                    
            except Exception as e:
                print(f"❌ Error updating concept {concept_id} ({concept_name}): {e}")
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n🎉 Successfully mapped {updated_count} concept types!")
            
            # Show updated statistics
            total_mapped = db.session.execute(text('''
                SELECT COUNT(*) FROM entity_triples 
                WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
                AND object_literal IS NOT NULL
            ''')).scalar()
            
            still_unmapped = db.session.execute(text('''
                SELECT COUNT(*) FROM entity_triples 
                WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
                AND object_literal IS NULL
            ''')).scalar()
            
            needs_review = db.session.execute(text('''
                SELECT COUNT(*) FROM entity_triples 
                WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
                AND needs_type_review = true
            ''')).scalar()
            
            print(f"📊 Total mapped concept types: {total_mapped}")
            print(f"📊 Still unmapped: {still_unmapped}")
            print(f"📊 Needing review: {needs_review}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise

if __name__ == '__main__':
    main()