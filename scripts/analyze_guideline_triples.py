#!/usr/bin/env python3
"""
Analyze guideline triples for value classification and duplicate detection.
This script helps identify which triples should go into the core ontology,
which should remain in the database, and which might be duplicates.
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.models.document import Document
from app.models.world import World


# Define namespaces
PROETHICA = Namespace("http://proethica.org/ontology/")
ENG_ETHICS = Namespace("http://proethica.org/ontology/engineering-ethics#")


class TripleAnalyzer:
    """Analyze triples for value classification and duplicates."""
    
    def __init__(self):
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Load ontologies
        self.ontology_graph = Graph()
        self.load_ontologies()
        
        # Value classification rules
        self.high_value_predicates = [
            'defines', 'definesRole', 'definesCapability',
            'requires', 'requiresCapability',
            'emphasizes', 'emphasizesObligation',
            'implements', 'implementsPrinciple',
            'alignsWith', 'relatesTo',
            'isPrimaryObligationOf', 'isEthicalRequirementFor'
        ]
        
        self.low_value_predicates = [
            'mentionsTerm', 'mentions term',
            'type', 'rdf:type',  # if not defining new classes
            'label', 'rdfs:label',  # if duplicating URI info
            'hasText', 'hasTextContent'
        ]
    
    def load_ontologies(self):
        """Load core ontology files."""
        ontology_files = [
            'ontologies/engineering-ethics.ttl',
            'ontologies/proethica-intermediate.ttl',
            'ontologies/bfo.ttl'
        ]
        
        for file_path in ontology_files:
            if os.path.exists(file_path):
                try:
                    self.ontology_graph.parse(file_path, format='turtle')
                    print(f"Loaded {file_path}: {len(self.ontology_graph)} triples")
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
    
    def classify_triple_value(self, triple):
        """Classify a triple as high, medium, or low value."""
        predicate = triple.predicate_label or triple.predicate
        
        # Check predicate against classification rules
        for high_pred in self.high_value_predicates:
            if high_pred in predicate.lower():
                return 'high'
        
        for low_pred in self.low_value_predicates:
            if low_pred in predicate.lower():
                # Special case: rdf:type might be high value if defining new classes
                if 'type' in predicate and self.is_new_class_definition(triple):
                    return 'medium'
                return 'low'
        
        # Default to medium
        return 'medium'
    
    def is_new_class_definition(self, triple):
        """Check if a type triple defines a new class not in core ontology."""
        if not triple.object_uri:
            return False
            
        # Check if the class exists in loaded ontologies
        class_uri = URIRef(triple.object_uri)
        return not bool(self.ontology_graph.value(class_uri, RDF.type, None))
    
    def check_duplicate_in_ontology(self, triple):
        """Check if triple exists in loaded ontologies."""
        subject = URIRef(triple.subject)
        predicate = URIRef(triple.predicate)
        
        if triple.is_literal:
            obj = Literal(triple.object_literal)
        else:
            obj = URIRef(triple.object_uri)
        
        return (subject, predicate, obj) in self.ontology_graph
    
    def find_similar_triples(self, triple):
        """Find similar triples that might be duplicates."""
        similar = []
        
        # Find triples with same subject and predicate
        same_sp = EntityTriple.query.filter_by(
            subject=triple.subject,
            predicate=triple.predicate
        ).all()
        
        # Find triples with same predicate and object
        if triple.is_literal:
            same_po = EntityTriple.query.filter_by(
                predicate=triple.predicate,
                object_literal=triple.object_literal,
                is_literal=True
            ).all()
        else:
            same_po = EntityTriple.query.filter_by(
                predicate=triple.predicate,
                object_uri=triple.object_uri,
                is_literal=False
            ).all()
        
        similar.extend(same_sp)
        similar.extend(same_po)
        
        # Remove duplicates and self
        seen = set()
        unique = []
        for t in similar:
            if t.id != triple.id and t.id not in seen:
                seen.add(t.id)
                unique.append(t)
        
        return unique
    
    def analyze_guideline_triples(self, guideline_id):
        """Analyze all triples for a specific guideline."""
        # Get guideline
        guideline = Document.query.get(guideline_id)
        if not guideline:
            print(f"Guideline {guideline_id} not found")
            return
        
        print(f"\nAnalyzing guideline: {guideline.title}")
        print("=" * 80)
        
        # Get actual guideline ID from metadata if available
        actual_guideline_id = None
        if guideline.doc_metadata and 'guideline_id' in guideline.doc_metadata:
            actual_guideline_id = guideline.doc_metadata['guideline_id']
        
        # Get triples
        if actual_guideline_id:
            triples = EntityTriple.query.filter_by(guideline_id=actual_guideline_id).all()
        else:
            triples = EntityTriple.query.filter_by(
                guideline_id=guideline_id,
                entity_type='guideline_concept'
            ).all()
        
        print(f"Found {len(triples)} triples")
        
        # Analyze by value category
        categories = defaultdict(list)
        duplicates_in_ontology = []
        potential_duplicates = defaultdict(list)
        
        for triple in triples:
            # Classify value
            value = self.classify_triple_value(triple)
            categories[value].append(triple)
            
            # Check for duplicates in ontology
            if self.check_duplicate_in_ontology(triple):
                duplicates_in_ontology.append(triple)
            
            # Find similar triples
            similar = self.find_similar_triples(triple)
            if similar:
                potential_duplicates[triple.id] = similar
        
        # Report results
        self.print_analysis_report(categories, duplicates_in_ontology, potential_duplicates)
        
        return {
            'categories': categories,
            'duplicates_in_ontology': duplicates_in_ontology,
            'potential_duplicates': potential_duplicates
        }
    
    def print_analysis_report(self, categories, duplicates_in_ontology, potential_duplicates):
        """Print analysis report."""
        print("\n## Value Classification Summary")
        print(f"High value: {len(categories['high'])} triples")
        print(f"Medium value: {len(categories['medium'])} triples")
        print(f"Low value: {len(categories['low'])} triples")
        
        # Show examples from each category
        for value, triples in categories.items():
            if triples:
                print(f"\n### {value.upper()} Value Examples:")
                for triple in triples[:3]:  # Show first 3
                    self.print_triple(triple)
        
        # Report duplicates
        if duplicates_in_ontology:
            print(f"\n## Duplicates Found in Core Ontology: {len(duplicates_in_ontology)}")
            for triple in duplicates_in_ontology[:5]:
                self.print_triple(triple)
        
        if potential_duplicates:
            print(f"\n## Potential Duplicate Groups: {len(potential_duplicates)}")
            shown = 0
            for triple_id, similar in potential_duplicates.items():
                if shown >= 3:  # Show first 3 groups
                    break
                triple = EntityTriple.query.get(triple_id)
                print(f"\nOriginal triple:")
                self.print_triple(triple)
                print(f"Similar to {len(similar)} other triples")
                shown += 1
    
    def print_triple(self, triple):
        """Print a triple in readable format."""
        subj = triple.subject_label or triple.subject
        pred = triple.predicate_label or triple.predicate
        obj = triple.object_label or triple.object_literal or triple.object_uri
        
        print(f"  {subj} -- {pred} --> {obj}")
    
    def generate_ontology_candidates(self, guideline_id, output_file='ontology_candidates.ttl'):
        """Generate TTL file with high-value triple candidates."""
        analysis = self.analyze_guideline_triples(guideline_id)
        high_value = analysis['categories']['high']
        
        if not high_value:
            print("\nNo high-value triples found")
            return
        
        # Create graph for candidates
        g = Graph()
        g.bind('proethica', PROETHICA)
        g.bind('eng-ethics', ENG_ETHICS)
        
        # Add high-value triples
        for triple in high_value:
            # Skip if already in ontology
            if triple in analysis['duplicates_in_ontology']:
                continue
            
            subject = URIRef(triple.subject)
            predicate = URIRef(triple.predicate)
            
            if triple.is_literal:
                obj = Literal(triple.object_literal)
            else:
                obj = URIRef(triple.object_uri)
            
            g.add((subject, predicate, obj))
            
            # Add labels if available
            if triple.subject_label:
                g.add((subject, RDFS.label, Literal(triple.subject_label)))
        
        # Serialize to file
        g.serialize(destination=output_file, format='turtle')
        print(f"\nGenerated {output_file} with {len(g)} candidate triples")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze guideline triples')
    parser.add_argument('--guideline', type=int, help='Guideline ID to analyze')
    parser.add_argument('--world', type=int, help='Analyze all guidelines in world')
    parser.add_argument('--export', action='store_true', help='Export high-value candidates to TTL')
    
    args = parser.parse_args()
    
    analyzer = TripleAnalyzer()
    
    if args.guideline:
        if args.export:
            analyzer.generate_ontology_candidates(args.guideline)
        else:
            analyzer.analyze_guideline_triples(args.guideline)
    
    elif args.world:
        # Get all guidelines for world
        world = World.query.get(args.world)
        if not world:
            print(f"World {args.world} not found")
            return
        
        guidelines = Document.query.filter_by(
            world_id=args.world,
            document_type='guideline'
        ).all()
        
        print(f"Found {len(guidelines)} guidelines in {world.name}")
        
        for guideline in guidelines:
            analyzer.analyze_guideline_triples(guideline.id)
    
    else:
        # Analyze all guidelines
        guidelines = Document.query.filter_by(document_type='guideline').all()
        print(f"Found {len(guidelines)} total guidelines")
        
        for guideline in guidelines:
            analyzer.analyze_guideline_triples(guideline.id)


if __name__ == '__main__':
    main()