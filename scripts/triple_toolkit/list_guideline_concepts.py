#!/usr/bin/env python3
"""
List concepts associated with guidelines.

This utility displays concepts (subjects) from entity triples associated with guidelines,
showing their predicates and properties.
"""

import sys
import argparse
from scripts.triple_toolkit.common import db_utils, formatting, pagination

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='List concepts associated with guidelines.')
    parser.add_argument('--world-id', '-w', type=int, default=1,
                      help='World ID (default: 1)')
    parser.add_argument('--guideline-id', '-g', type=int,
                      help='Guideline ID (if not specified, will list concepts from all guidelines in the world)')
    parser.add_argument('--interactive', '-i', action='store_true',
                      help='Use interactive mode for navigation')
    parser.add_argument('--format', '-f', choices=['simple', 'detailed', 'triples'], default='simple',
                      help='Output format (default: simple)')
    return parser.parse_args()

def get_world(world_id):
    """Retrieve a world from the database by ID."""
    with db_utils.get_app_context():
        try:
            from app.models.world import World
            
            world = World.query.get(world_id)
            return world
        except Exception as e:
            print(f"Error retrieving world: {e}")
            return None

def get_guideline(guideline_id):
    """Retrieve a guideline from the database by ID."""
    with db_utils.get_app_context():
        try:
            from app.models.guideline import Guideline
            
            guideline = Guideline.query.get(guideline_id)
            return guideline
        except Exception as e:
            print(f"Error retrieving guideline: {e}")
            return None

def get_guidelines_for_world(world_id):
    """Retrieve all guidelines for a world."""
    with db_utils.get_app_context():
        try:
            from app.models.guideline import Guideline
            
            guidelines = Guideline.query.filter_by(world_id=world_id).all()
            return guidelines
        except Exception as e:
            print(f"Error retrieving guidelines: {e}")
            return []

def get_concepts_for_guideline(guideline_id):
    """Get concepts (subjects) associated with a guideline."""
    with db_utils.get_app_context():
        try:
            from app.models.guideline import Guideline
            
            guideline = Guideline.query.get(guideline_id)
            if not guideline:
                print(f"Guideline with ID {guideline_id} not found.")
                return []
            
            # This uses the concepts property defined in the Guideline model
            return guideline.concepts
        except Exception as e:
            print(f"Error retrieving concepts: {e}")
            return []

def get_triples_for_guideline(guideline_id):
    """Get all triples associated with a guideline."""
    with db_utils.get_app_context():
        try:
            from app.models.entity_triple import EntityTriple
            
            triples = EntityTriple.query.filter_by(
                guideline_id=guideline_id,
                entity_type='guideline_concept'
            ).all()
            return triples
        except Exception as e:
            print(f"Error retrieving triples: {e}")
            return []

def get_unique_concepts_for_world(world_id):
    """Get unique concepts across all guidelines in a world."""
    # Get all guidelines for the world
    guidelines = get_guidelines_for_world(world_id)
    
    # Collect all concepts
    all_concepts = []
    for guideline in guidelines:
        concepts = get_concepts_for_guideline(guideline.id)
        all_concepts.extend(concepts)
    
    # Deduplicate by subject URI
    unique_subjects = set()
    unique_concepts = []
    
    for concept in all_concepts:
        if concept.subject not in unique_subjects:
            unique_subjects.add(concept.subject)
            unique_concepts.append(concept)
    
    return unique_concepts

def format_concept_simple(concept):
    """Format a concept for simple display."""
    return f"{concept.subject_label or concept.subject}"

def format_concept_detailed(concept):
    """Format a concept for detailed display."""
    result = f"Concept: {concept.subject_label or concept.subject}\n"
    result += f"  URI: {concept.subject}\n"
    
    # Add type if available
    if hasattr(concept, 'type_label') and concept.type_label:
        result += f"  Type: {concept.type_label}\n"
    
    # Add description if available
    if hasattr(concept, 'description') and concept.description:
        result += f"  Description: {concept.description}\n"
    
    # Add predicates
    if hasattr(concept, 'predicates') and concept.predicates:
        result += f"  Predicates: {concept.predicates}"
    
    return result

def format_triple(triple):
    """Format a triple for display."""
    labels = {
        'subject_label': triple.subject_label,
        'predicate_label': triple.predicate_label,
        'object_label': triple.object_label
    }
    
    return formatting.format_triple(
        triple.subject, 
        triple.predicate, 
        triple.object_literal if triple.is_literal else triple.object_uri,
        triple.is_literal,
        labels
    )

def list_concepts_for_guideline(guideline_id, format_type='simple', interactive=False):
    """List concepts for a specific guideline."""
    guideline = get_guideline(guideline_id)
    if not guideline:
        print(f"Guideline with ID {guideline_id} not found.")
        return
    
    if format_type == 'triples':
        triples = get_triples_for_guideline(guideline_id)
        if not triples:
            print(f"No triples found for guideline '{guideline.title}' (ID: {guideline_id}).")
            return
        
        if interactive:
            pagination.interactive_pager(
                triples,
                formatter=format_triple,
                title=f"TRIPLES FOR GUIDELINE: {guideline.title}"
            )
        else:
            formatting.print_header(f"TRIPLES FOR GUIDELINE: {guideline.title}")
            for triple in triples:
                print(format_triple(triple))
                print()  # Add spacing between triples
    else:
        concepts = get_concepts_for_guideline(guideline_id)
        if not concepts:
            print(f"No concepts found for guideline '{guideline.title}' (ID: {guideline_id}).")
            return
        
        formatter = format_concept_detailed if format_type == 'detailed' else format_concept_simple
        
        if interactive:
            pagination.interactive_pager(
                concepts,
                formatter=formatter,
                title=f"CONCEPTS FOR GUIDELINE: {guideline.title}"
            )
        else:
            formatting.print_header(f"CONCEPTS FOR GUIDELINE: {guideline.title}")
            for concept in concepts:
                print(formatter(concept))
                if format_type == 'detailed':
                    print()  # Add spacing between detailed concepts

def list_concepts_for_world(world_id, format_type='simple', interactive=False):
    """List concepts for all guidelines in a world."""
    world = get_world(world_id)
    if not world:
        print(f"World with ID {world_id} not found.")
        return
    
    concepts = get_unique_concepts_for_world(world_id)
    if not concepts:
        print(f"No concepts found for world '{world.name}' (ID: {world_id}).")
        return
    
    formatter = format_concept_detailed if format_type == 'detailed' else format_concept_simple
    
    if interactive:
        pagination.interactive_pager(
            concepts,
            formatter=formatter,
            title=f"CONCEPTS FOR WORLD: {world.name}"
        )
    else:
        formatting.print_header(f"CONCEPTS FOR WORLD: {world.name}")
        for concept in concepts:
            print(formatter(concept))
            if format_type == 'detailed':
                print()  # Add spacing between detailed concepts

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        if args.guideline_id:
            list_concepts_for_guideline(
                args.guideline_id,
                format_type=args.format,
                interactive=args.interactive
            )
        else:
            list_concepts_for_world(
                args.world_id,
                format_type=args.format,
                interactive=args.interactive
            )
            
        if not args.interactive and args.format == 'simple':
            print("\nTips: Use --format detailed for more information or --interactive for navigation")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
