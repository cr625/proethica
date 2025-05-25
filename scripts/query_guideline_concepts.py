#!/usr/bin/env python3
"""
Query utility to check guideline concepts stored in the ontology database.
This helps verify that concepts are correctly extracted and saved.
"""

import os
import sys
from pathlib import Path
import json
import argparse
import logging
from sqlalchemy import create_engine, MetaData, Table, text, inspect, select, func, and_
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_url():
    """Get database URL from environment or use default."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default for local development
        db_url = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        logger.info(f"No DATABASE_URL found, using default: {db_url}")
    return db_url

def format_triple(triple):
    """Format a triple for display in a more readable way."""
    subject_label = triple.subject_label or triple.subject.split('/')[-1]
    predicate_label = triple.predicate_label or triple.predicate.split('/')[-1]
    
    if triple.is_literal:
        object_display = triple.object_literal
        if object_display and len(object_display) > 50:
            object_display = object_display[:50] + "..."
    else:
        object_display = triple.object_label or triple.object_uri.split('/')[-1] if triple.object_uri else "None"
    
    return f"{subject_label} → {predicate_label} → {object_display}"

def query_guideline_concepts(args):
    """Query guideline concepts from the database."""
    try:
        # Connect to database
        engine = create_engine(get_db_url())
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if tables exist
        inspector = inspect(engine)
        if 'guidelines' not in inspector.get_table_names():
            logger.error("Guidelines table doesn't exist in the database!")
            return
        
        if 'entity_triples' not in inspector.get_table_names():
            logger.error("Entity triples table doesn't exist in the database!")
            return
        
        # Reflect metadata
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        # Get table objects
        guidelines = metadata.tables['guidelines']
        entity_triples = metadata.tables['entity_triples']
        
        # Count total guidelines
        guideline_count = session.query(func.count()).select_from(guidelines).scalar()
        logger.info(f"Found {guideline_count} guidelines in the database")
        
        # Count guideline concept triples
        triple_count = session.query(func.count()).select_from(entity_triples).filter(
            entity_triples.c.entity_type == 'guideline_concept'
        ).scalar() or 0
        logger.info(f"Found {triple_count} guideline concept triples in the database")
        
        # No data found
        if guideline_count == 0:
            logger.warning("No guidelines found in the database")
            return
        
        # List guidelines
        query = select([
            guidelines.c.id, 
            guidelines.c.title,
            guidelines.c.created_at,
            func.count(entity_triples.c.id).label('triple_count')
        ]).select_from(
            guidelines.outerjoin(entity_triples, and_(
                guidelines.c.id == entity_triples.c.guideline_id,
                entity_triples.c.entity_type == 'guideline_concept'
            ))
        ).group_by(
            guidelines.c.id, guidelines.c.title, guidelines.c.created_at
        ).order_by(guidelines.c.id)
        
        results = session.execute(query)
        
        print("\n=== GUIDELINES WITH CONCEPT COUNT ===")
        for row in results:
            guideline_id = row.id
            title = row.title
            triple_count = row.triple_count
            created_at = row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else "N/A"
            print(f"ID: {guideline_id}, Title: {title}, Triples: {triple_count}, Created: {created_at}")
            
        # If a specific guideline is specified, show its concepts
        if args.guideline_id:
            guideline_id = args.guideline_id
            print(f"\n=== CONCEPTS FOR GUIDELINE ID {guideline_id} ===")
            
            # First check if guideline exists
            guideline = session.execute(
                select([guidelines]).where(guidelines.c.id == guideline_id)
            ).first()
            
            if not guideline:
                logger.error(f"Guideline with ID {guideline_id} not found!")
                return
                
            guideline_title = guideline.title
            print(f"Guideline: {guideline_title}")
            
            # Query for triples related to this guideline
            triples_query = select([
                entity_triples
            ]).where(
                and_(
                    entity_triples.c.guideline_id == guideline_id,
                    entity_triples.c.entity_type == 'guideline_concept'
                )
            ).order_by(entity_triples.c.subject_label, entity_triples.c.predicate_label)
            
            triples = session.execute(triples_query)
            
            # Group by subject to organize output by concept
            concept_triples = {}
            for triple in triples:
                subject = triple.subject
                subject_label = triple.subject_label or subject.split('/')[-1]
                
                if subject not in concept_triples:
                    concept_triples[subject] = {
                        'label': subject_label,
                        'triples': []
                    }
                
                concept_triples[subject]['triples'].append(triple)
            
            # Output concepts and their triples
            print(f"\nFound {len(concept_triples)} unique concepts:")
            for subject, data in concept_triples.items():
                print(f"\n--- Concept: {data['label']} ---")
                for triple in data['triples']:
                    print(f"  • {format_triple(triple)}")
            
            # Summarize concept types
            print("\n=== CONCEPT TYPES SUMMARY ===")
            type_query = select([
                entity_triples.c.object_label,
                func.count().label('count')
            ]).where(
                and_(
                    entity_triples.c.guideline_id == guideline_id,
                    entity_triples.c.entity_type == 'guideline_concept',
                    entity_triples.c.predicate.like('%type%')
                )
            ).group_by(entity_triples.c.object_label).order_by(text('count DESC'))
            
            type_results = session.execute(type_query)
            for row in type_results:
                print(f"{row.object_label}: {row.count} concepts")
                
        # If export flag is set, export all guideline concepts to JSON
        if args.export:
            export_file = args.export
            print(f"\nExporting guideline concepts to {export_file}...")
            
            # Query all guidelines and their triples
            all_guidelines_query = select([guidelines])
            all_guidelines = session.execute(all_guidelines_query)
            
            export_data = []
            for guideline in all_guidelines:
                guideline_id = guideline.id
                
                # Get triples for this guideline
                guideline_triples_query = select([entity_triples]).where(
                    and_(
                        entity_triples.c.guideline_id == guideline_id,
                        entity_triples.c.entity_type == 'guideline_concept'
                    )
                )
                
                triples = []
                for triple in session.execute(guideline_triples_query):
                    triples.append({
                        'subject': triple.subject,
                        'subject_label': triple.subject_label,
                        'predicate': triple.predicate,
                        'predicate_label': triple.predicate_label,
                        'object': triple.object_literal if triple.is_literal else triple.object_uri,
                        'object_label': triple.object_label,
                        'is_literal': triple.is_literal
                    })
                
                export_data.append({
                    'guideline_id': guideline_id,
                    'title': guideline.title,
                    'created_at': guideline.created_at.isoformat() if guideline.created_at else None,
                    'triple_count': len(triples),
                    'triples': triples
                })
            
            # Write to file
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            print(f"Exported {len(export_data)} guidelines with their concepts to {export_file}")
            
    except Exception as e:
        logger.exception(f"Error querying guideline concepts: {str(e)}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Query guideline concepts from the database")
    parser.add_argument('--guideline-id', '-g', type=int, help="ID of a specific guideline to query")
    parser.add_argument('--export', '-e', help="Export all guideline concepts to a JSON file")
    args = parser.parse_args()
    
    query_guideline_concepts(args)

if __name__ == '__main__':
    main()
