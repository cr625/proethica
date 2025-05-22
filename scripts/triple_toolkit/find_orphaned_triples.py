#!/usr/bin/env python3
"""
Find triples not properly associated with guidelines or worlds.

This utility identifies entity triples that:
1. Don't have a valid world_id
2. Have guideline_id but the guideline doesn't exist
3. Have entity_type='guideline_concept' but no guideline_id
"""

import sys
import argparse
from scripts.triple_toolkit.common import db_utils, formatting, pagination

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Find orphaned triples in the database.')
    parser.add_argument('--interactive', '-i', action='store_true',
                      help='Use interactive mode for navigation')
    parser.add_argument('--check-all', '-a', action='store_true',
                      help='Check all triple types (not just guideline_concept)')
    parser.add_argument('--limit', '-l', type=int, default=100,
                      help='Limit the number of results (default: 100)')
    return parser.parse_args()

def find_triples_without_world():
    """Find triples that don't have a valid world_id."""
    with db_utils.get_app_context():
        try:
            from app.models.entity_triple import EntityTriple
            from app.models.world import World
            from app import db
            
            # Find all world IDs
            world_ids = [w.id for w in World.query.all()]
            
            # Find triples with world_id that doesn't exist
            query = EntityTriple.query.filter(
                (EntityTriple.world_id.is_not(None)) & 
                ~EntityTriple.world_id.in_(world_ids)
            )
            
            return query.all()
        except Exception as e:
            print(f"Error finding triples without valid world: {e}")
            return []

def find_triples_with_invalid_guideline():
    """Find triples with guideline_id that doesn't exist."""
    with db_utils.get_app_context():
        try:
            from app.models.entity_triple import EntityTriple
            from app.models.guideline import Guideline
            from app import db
            
            # Find all guideline IDs
            guideline_ids = [g.id for g in Guideline.query.all()]
            
            # Find triples with guideline_id that doesn't exist
            query = EntityTriple.query.filter(
                (EntityTriple.guideline_id.is_not(None)) & 
                ~EntityTriple.guideline_id.in_(guideline_ids)
            )
            
            return query.all()
        except Exception as e:
            print(f"Error finding triples with invalid guideline: {e}")
            return []

def find_guideline_concepts_without_guideline():
    """Find triples with entity_type='guideline_concept' but no guideline_id."""
    with db_utils.get_app_context():
        try:
            from app.models.entity_triple import EntityTriple
            
            query = EntityTriple.query.filter(
                EntityTriple.entity_type == 'guideline_concept',
                EntityTriple.guideline_id.is_(None)
            )
            
            return query.all()
        except Exception as e:
            print(f"Error finding guideline concepts without guideline: {e}")
            return []

def find_triples_without_entity_association(check_all=False):
    """Find triples without proper entity association."""
    with db_utils.get_app_context():
        try:
            from app.models.entity_triple import EntityTriple
            from sqlalchemy import and_, or_
            
            conditions = []
            
            # For guideline_concept, require guideline_id
            conditions.append(
                and_(
                    EntityTriple.entity_type == 'guideline_concept',
                    EntityTriple.guideline_id.is_(None)
                )
            )
            
            if check_all:
                # For character, require character_id
                conditions.append(
                    and_(
                        EntityTriple.entity_type == 'character',
                        EntityTriple.character_id.is_(None)
                    )
                )
                
                # For scenario, require scenario_id
                conditions.append(
                    and_(
                        EntityTriple.entity_type == 'scenario',
                        EntityTriple.scenario_id.is_(None)
                    )
                )
            
            query = EntityTriple.query.filter(or_(*conditions))
            return query.all()
        except Exception as e:
            print(f"Error finding triples without entity association: {e}")
            return []

def find_all_orphaned_triples(check_all=False, limit=100):
    """Find all types of orphaned triples."""
    orphaned = []
    
    # Find triples without valid world
    triples = find_triples_without_world()
    for triple in triples[:limit]:
        triple.orphan_reason = "Invalid world_id"
        orphaned.append(triple)
    
    # Find triples with invalid guideline
    if len(orphaned) < limit:
        remaining = limit - len(orphaned)
        triples = find_triples_with_invalid_guideline()
        for triple in triples[:remaining]:
            triple.orphan_reason = "Invalid guideline_id"
            orphaned.append(triple)
    
    # Find guideline concepts without guideline
    if len(orphaned) < limit:
        remaining = limit - len(orphaned)
        triples = find_guideline_concepts_without_guideline()
        for triple in triples[:remaining]:
            triple.orphan_reason = "guideline_concept without guideline_id"
            orphaned.append(triple)
    
    # Find triples without proper entity association
    if check_all and len(orphaned) < limit:
        remaining = limit - len(orphaned)
        triples = find_triples_without_entity_association(check_all=True)
        for triple in triples[:remaining]:
            triple.orphan_reason = f"{triple.entity_type} without matching ID"
            orphaned.append(triple)
    
    return orphaned[:limit]

def format_orphaned_triple(triple):
    """Format an orphaned triple for display."""
    labels = {
        'subject_label': triple.subject_label,
        'predicate_label': triple.predicate_label,
        'object_label': triple.object_label
    }
    
    triple_str = formatting.format_triple(
        triple.subject, 
        triple.predicate, 
        triple.object_literal if triple.is_literal else triple.object_uri,
        triple.is_literal,
        labels
    )
    
    # Add orphan reason and IDs
    id_info = (
        f"ID: {triple.id}\n"
        f"Entity Type: {triple.entity_type}\n"
        f"World ID: {triple.world_id}\n"
        f"Guideline ID: {triple.guideline_id}\n"
        f"Orphan Reason: {triple.orphan_reason}"
    )
    
    return f"{triple_str}\n\n{id_info}"

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        orphaned_triples = find_all_orphaned_triples(
            check_all=args.check_all,
            limit=args.limit
        )
        
        if not orphaned_triples:
            print("No orphaned triples found!")
            return 0
        
        title = "ORPHANED TRIPLES"
        if args.interactive:
            pagination.interactive_pager(
                orphaned_triples,
                formatter=format_orphaned_triple,
                title=title
            )
        else:
            formatting.print_header(title)
            print(f"Found {len(orphaned_triples)} orphaned triples:")
            print()
            
            for i, triple in enumerate(orphaned_triples):
                if i > 0:
                    print("\n" + "-" * 40 + "\n")  # Separator between triples
                print(format_orphaned_triple(triple))
            
            if len(orphaned_triples) == args.limit:
                print(f"\nNote: Results limited to {args.limit} triples. Use --limit to change.")
            
            print("\nTip: Use --interactive for better navigation")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
