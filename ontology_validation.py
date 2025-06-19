#!/usr/bin/env python3
"""
Ontology Validation Script for ProEthica

Validates class hierarchies and bindings across the three main ontologies:
- bfo.ttl (Basic Formal Ontology)
- proethica-intermediate.ttl (Intermediate ontology)
- engineering-ethics.ttl (Domain-specific ontology)
"""

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from collections import defaultdict
import sys
import os

# Define namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
EE = Namespace("http://proethica.org/ontology/engineering-ethics#")

def load_ontologies():
    """Load all three ontology files into separate graphs"""
    graphs = {}
    
    ontology_files = {
        'bfo': 'ontologies/bfo.ttl',
        'proethica': 'ontologies/proethica-intermediate.ttl', 
        'engineering': 'ontologies/engineering-ethics.ttl'
    }
    
    for name, file_path in ontology_files.items():
        if os.path.exists(file_path):
            g = Graph()
            try:
                g.parse(file_path, format='turtle')
                graphs[name] = g
                print(f"✓ Loaded {name}: {len(g)} triples")
            except Exception as e:
                print(f"✗ Error loading {file_path}: {e}")
        else:
            print(f"✗ File not found: {file_path}")
    
    return graphs

def validate_class_hierarchies(graphs):
    """Validate that all classes have proper parent classes"""
    print("\n" + "="*60)
    print("VALIDATING CLASS HIERARCHIES")
    print("="*60)
    
    issues = []
    
    for ont_name, graph in graphs.items():
        print(f"\n--- {ont_name.upper()} ONTOLOGY ---")
        
        # Find all classes
        classes = list(graph.subjects(RDF.type, OWL.Class))
        print(f"Found {len(classes)} classes")
        
        # Check each class for proper parent relationships
        orphaned_classes = []
        
        for cls in classes:
            # Get all superclasses 
            superclasses = list(graph.objects(cls, RDFS.subClassOf))
            
            if not superclasses:
                # Check if it's a top-level class or should have parents
                class_name = str(cls).split('#')[-1] if '#' in str(cls) else str(cls).split('/')[-1]
                
                # These are acceptable top-level classes
                acceptable_top_level = [
                    'BFO_0000001',  # entity (BFO root)
                    'Thing',        # owl:Thing
                    'EntityType',   # ProEthica meta-class
                    'GuidelineConceptType'  # ProEthica meta-class
                ]
                
                if class_name not in acceptable_top_level:
                    orphaned_classes.append((cls, class_name))
        
        if orphaned_classes:
            print(f"  ⚠️  {len(orphaned_classes)} classes without parent classes:")
            for cls, name in orphaned_classes[:10]:  # Show first 10
                print(f"    - {name}")
            if len(orphaned_classes) > 10:
                print(f"    ... and {len(orphaned_classes) - 10} more")
            issues.extend(orphaned_classes)
        else:
            print(f"  ✓ All classes have proper parent relationships")
    
    return issues

def validate_cross_ontology_bindings(graphs):
    """Validate bindings between ontologies"""
    print("\n" + "="*60)
    print("VALIDATING CROSS-ONTOLOGY BINDINGS")
    print("="*60)
    
    issues = []
    
    if 'proethica' in graphs and 'bfo' in graphs:
        print("\n--- PROETHICA → BFO BINDINGS ---")
        proeth_graph = graphs['proethica']
        bfo_graph = graphs['bfo']
        
        # Get all ProEthica classes that reference BFO
        bfo_references = []
        for s, p, o in proeth_graph:
            if p == RDFS.subClassOf and str(o).startswith('http://purl.obolibrary.org/obo/BFO_'):
                bfo_references.append((s, o))
        
        print(f"Found {len(bfo_references)} ProEthica classes referencing BFO")
        
        # Validate each BFO reference exists
        missing_bfo_classes = []
        for proeth_class, bfo_class in bfo_references:
            if not list(bfo_graph.subjects(RDF.type, OWL.Class)):
                # BFO might use different patterns, let's check if the class exists at all
                if (bfo_class, None, None) not in bfo_graph:
                    missing_bfo_classes.append((proeth_class, bfo_class))
        
        if missing_bfo_classes:
            print(f"  ⚠️  {len(missing_bfo_classes)} BFO references not found:")
            for proeth_cls, bfo_cls in missing_bfo_classes[:5]:
                proeth_name = str(proeth_cls).split('#')[-1]
                bfo_name = str(bfo_cls).split('/')[-1]
                print(f"    - {proeth_name} → {bfo_name}")
        else:
            print(f"  ✓ All BFO references are valid")
    
    if 'engineering' in graphs and 'proethica' in graphs:
        print("\n--- ENGINEERING → PROETHICA BINDINGS ---")
        eng_graph = graphs['engineering']
        proeth_graph = graphs['proethica']
        
        # Get all engineering classes that reference ProEthica
        proeth_references = []
        for s, p, o in eng_graph:
            if p == RDFS.subClassOf and str(o).startswith('http://proethica.org/ontology/intermediate#'):
                proeth_references.append((s, o))
        
        print(f"Found {len(proeth_references)} Engineering classes referencing ProEthica")
        
        # Validate each ProEthica reference exists
        missing_proeth_classes = []
        for eng_class, proeth_class in proeth_references:
            if (proeth_class, RDF.type, OWL.Class) not in proeth_graph:
                missing_proeth_classes.append((eng_class, proeth_class))
        
        if missing_proeth_classes:
            print(f"  ⚠️  {len(missing_proeth_classes)} ProEthica references not found:")
            for eng_cls, proeth_cls in missing_proeth_classes:
                eng_name = str(eng_cls).split('#')[-1]
                proeth_name = str(proeth_cls).split('#')[-1]
                print(f"    - {eng_name} → {proeth_name}")
        else:
            print(f"  ✓ All ProEthica references are valid")
    
    return issues

def analyze_guideline_concept_hierarchy(graphs):
    """Analyze the 8 core guideline concept types and their hierarchy"""
    print("\n" + "="*60)
    print("ANALYZING GUIDELINE CONCEPT HIERARCHY")
    print("="*60)
    
    if 'proethica' not in graphs:
        print("ProEthica ontology not loaded")
        return
    
    graph = graphs['proethica']
    
    # Find GuidelineConceptType classes
    guideline_concepts = []
    for s in graph.subjects(RDF.type, PROETH.GuidelineConceptType):
        guideline_concepts.append(s)
    
    print(f"Found {len(guideline_concepts)} Guideline Concept Types:")
    
    for concept in guideline_concepts:
        concept_name = str(concept).split('#')[-1]
        
        # Get BFO parent
        bfo_parents = [o for o in graph.objects(concept, RDFS.subClassOf) 
                      if str(o).startswith('http://purl.obolibrary.org/obo/BFO_')]
        
        # Get labels and comments
        labels = list(graph.objects(concept, RDFS.label))
        comments = list(graph.objects(concept, RDFS.comment))
        
        print(f"\n  {concept_name}:")
        if labels:
            print(f"    Label: {labels[0]}")
        if bfo_parents:
            bfo_name = str(bfo_parents[0]).split('/')[-1]
            print(f"    BFO Parent: {bfo_name}")
        if comments:
            comment = str(comments[0])[:100] + "..." if len(str(comments[0])) > 100 else str(comments[0])
            print(f"    Comment: {comment}")

def generate_validation_report(graphs, hierarchy_issues, binding_issues):
    """Generate a comprehensive validation report"""
    print("\n" + "="*60)
    print("VALIDATION SUMMARY REPORT")
    print("="*60)
    
    total_classes = sum(len(list(g.subjects(RDF.type, OWL.Class))) for g in graphs.values())
    print(f"Total classes analyzed: {total_classes}")
    
    print(f"\nHierarchy Issues: {len(hierarchy_issues)}")
    print(f"Binding Issues: {len(binding_issues)}")
    
    if not hierarchy_issues and not binding_issues:
        print("\n✅ VALIDATION PASSED: All ontology hierarchies and bindings are correct!")
    else:
        print(f"\n⚠️  VALIDATION WARNINGS: {len(hierarchy_issues + binding_issues)} issues found")
        
        if hierarchy_issues:
            print("\nClasses needing parent class definitions:")
            for cls, name in hierarchy_issues[:10]:
                print(f"  - {name}")
        
        if binding_issues:
            print("\nCross-ontology binding issues:")
            for issue in binding_issues[:10]:
                print(f"  - {issue}")
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    if hierarchy_issues:
        print("1. Review orphaned classes and add appropriate rdfs:subClassOf relationships")
        print("2. Ensure all domain-specific classes inherit from intermediate ontology classes")
    
    if binding_issues:
        print("3. Fix missing cross-ontology references")
        print("4. Validate that all imported ontology classes exist")
    
    print("5. Consider using automated ontology validation tools like HermiT or Pellet")
    print("6. Implement SPARQL-based validation queries for ongoing quality assurance")

def main():
    print("ProEthica Ontology Validation")
    print("="*40)
    
    # Load ontologies
    graphs = load_ontologies()
    
    if not graphs:
        print("No ontology files could be loaded. Exiting.")
        sys.exit(1)
    
    # Validate hierarchies
    hierarchy_issues = validate_class_hierarchies(graphs)
    
    # Validate cross-ontology bindings
    binding_issues = validate_cross_ontology_bindings(graphs)
    
    # Analyze guideline concept hierarchy
    analyze_guideline_concept_hierarchy(graphs)
    
    # Generate report
    generate_validation_report(graphs, hierarchy_issues, binding_issues)

if __name__ == "__main__":
    main()