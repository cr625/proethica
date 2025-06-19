#!/usr/bin/env python3
"""
Refined Ontology Analysis for ProEthica

Focus on real validation issues, filtering out OWL constructs and blank nodes.
"""

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL, BNode
from collections import defaultdict
import sys
import os

# Define namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
EE = Namespace("http://proethica.org/ontology/engineering-ethics#")

def analyze_proethica_meta_classes():
    """Analyze the ProEthica meta-classes that were flagged as orphaned"""
    print("\n" + "="*60)
    print("ANALYZING PROETHICA META-CLASSES")
    print("="*60)
    
    g = Graph()
    g.parse('ontologies/proethica-intermediate.ttl', format='turtle')
    
    meta_classes = [
        "ResourceType", "EventType", "ActionType", "CapabilityType", "ConditionType"
    ]
    
    for class_name in meta_classes:
        class_uri = PROETH[class_name]
        
        # Check if it exists
        if (class_uri, RDF.type, OWL.Class) in g:
            print(f"\n{class_name}:")
            
            # Get label and comment
            labels = list(g.objects(class_uri, RDFS.label))
            comments = list(g.objects(class_uri, RDFS.comment))
            
            # Check for subclass relationships
            parents = list(g.objects(class_uri, RDFS.subClassOf))
            
            if labels:
                print(f"  Label: {labels[0]}")
            if comments:
                print(f"  Comment: {comments[0]}")
            if parents:
                print(f"  Parents: {[str(p) for p in parents]}")
            else:
                print(f"  ⚠️  No parent class defined")
                
            # Check deprecation status
            deprecated = list(g.objects(class_uri, OWL.deprecated))
            if deprecated and str(deprecated[0]).lower() == 'true':
                print(f"  📋 Status: DEPRECATED")

def validate_bfo_hierarchy():
    """Validate BFO hierarchy, filtering out blank nodes and OWL constructs"""
    print("\n" + "="*60)
    print("VALIDATING BFO HIERARCHY (Named Classes Only)")
    print("="*60)
    
    g = Graph()
    g.parse('ontologies/bfo.ttl', format='turtle')
    
    # Get only named BFO classes (not blank nodes)
    bfo_classes = []
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, BNode):
            continue  # Skip blank nodes
        if str(s).startswith('http://purl.obolibrary.org/obo/BFO_'):
            bfo_classes.append(s)
    
    print(f"Found {len(bfo_classes)} named BFO classes")
    
    # Find the root entity
    entity_class = BFO.BFO_0000001
    if entity_class in bfo_classes:
        print(f"✓ Root entity class found: {entity_class}")
    
    # Check hierarchy
    orphaned = []
    for cls in bfo_classes:
        parents = list(g.objects(cls, RDFS.subClassOf))
        # Filter out restriction-based parents (blank nodes)
        named_parents = [p for p in parents if not isinstance(p, BNode)]
        
        if not named_parents and cls != entity_class:
            class_id = str(cls).split('/')[-1]
            orphaned.append((cls, class_id))
    
    print(f"Classes without named parent classes: {len(orphaned)}")
    if orphaned:
        for cls, class_id in orphaned[:5]:
            print(f"  - {class_id}")

def check_engineering_ethics_completeness():
    """Check completeness of engineering ethics ontology"""
    print("\n" + "="*60)
    print("ENGINEERING ETHICS ONTOLOGY COMPLETENESS")
    print("="*60)
    
    g = Graph()
    g.parse('ontologies/engineering-ethics.ttl', format='turtle')
    
    # Analyze different types of classes
    roles = list(g.subjects(RDFS.subClassOf, PROETH.EngineerRole))
    resources = list(g.subjects(RDFS.subClassOf, PROETH.Resource))
    capabilities = list(g.subjects(RDFS.subClassOf, PROETH.TechnicalCapability))
    
    print(f"Engineer Roles: {len(roles)}")
    for role in roles:
        role_name = str(role).split('#')[-1]
        print(f"  - {role_name}")
    
    print(f"\nResource Types: {len(resources)}")
    for resource in resources:
        if str(resource).startswith('http://proethica.org/ontology/engineering-ethics#'):
            resource_name = str(resource).split('#')[-1]
            print(f"  - {resource_name}")
    
    print(f"\nTechnical Capabilities: {len(capabilities)}")
    for capability in capabilities:
        cap_name = str(capability).split('#')[-1]
        print(f"  - {cap_name}")

def suggest_improvements():
    """Suggest specific improvements based on analysis"""
    print("\n" + "="*60)
    print("IMPROVEMENT SUGGESTIONS")
    print("="*60)
    
    print("1. PROETHICA META-CLASSES:")
    print("   - ResourceType, EventType, ActionType, CapabilityType should inherit from EntityType")
    print("   - Consider removing deprecated ConditionType class")
    
    print("\n2. MISSING GUIDELINE CONCEPT IMPLEMENTATIONS:")
    print("   - Add more engineering-specific Principles (e.g., Safety, Sustainability)")
    print("   - Define engineering-specific Obligations (e.g., PublicSafetyObligation)")
    print("   - Add engineering States (e.g., ProjectConstraint, BudgetLimitation)")
    
    print("\n3. VALIDATION TOOLS:")
    print("   - Consider implementing SHACL shapes for validation")
    print("   - Add OWL reasoner integration (HermiT, Pellet)")
    print("   - Implement SPARQL-based validation queries")
    
    print("\n4. NEO4J INTEGRATION:")
    print("   - Load ontologies into Neo4j for graph analysis")
    print("   - Create Cypher queries for hierarchy validation")
    print("   - Visualize class hierarchies using Neo4j Browser")

def create_fixed_meta_classes():
    """Create fixes for the ProEthica meta-class hierarchy"""
    print("\n" + "="*60)
    print("PROPOSED FIXES FOR META-CLASSES")
    print("="*60)
    
    fixes = """
# Add to proethica-intermediate.ttl after EntityType definition:

:ResourceType rdf:type owl:Class ;
    rdfs:subClassOf :EntityType ;
    rdfs:label "Resource Type"@en ;
    rdfs:comment "Meta-class for specific resource types recognized by the ProEthica system"@en .

:EventType rdf:type owl:Class ;
    rdfs:subClassOf :EntityType ;
    rdfs:label "Event Type"@en ;
    rdfs:comment "Meta-class for specific event types recognized by the ProEthica system"@en .

:ActionType rdf:type owl:Class ;
    rdfs:subClassOf :EntityType ;
    rdfs:label "Action Type"@en ;
    rdfs:comment "Meta-class for specific action types recognized by the ProEthica system"@en .

:CapabilityType rdf:type owl:Class ;
    rdfs:subClassOf :EntityType ;
    rdfs:label "Capability Type"@en ;
    rdfs:comment "Meta-class for specific capability types recognized by the ProEthica system"@en .

# ConditionType is already marked as deprecated - consider removing
"""
    
    print(fixes)

def check_neo4j_integration():
    """Check if we can integrate with Neo4j for validation"""
    print("\n" + "="*60)
    print("NEO4J INTEGRATION CHECK")
    print("="*60)
    
    try:
        from neo4j import GraphDatabase
        print("✓ Neo4j Python driver available")
        
        # Check if Neo4j is running
        try:
            driver = GraphDatabase.driver("bolt://localhost:7687")
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record:
                    print("✓ Neo4j instance is running and accessible")
                    
                    # Check if there's already ontology data
                    result = session.run("MATCH (n) RETURN count(n) as nodeCount")
                    count = result.single()["nodeCount"]
                    print(f"✓ Neo4j database has {count} nodes")
                    
            driver.close()
            return True
        except Exception as e:
            print(f"⚠️  Neo4j connection failed: {e}")
            return False
            
    except ImportError:
        print("✗ Neo4j Python driver not available")
        return False

def main():
    print("ProEthica Ontology Refined Analysis")
    print("="*50)
    
    # Analyze ProEthica meta-classes
    analyze_proethica_meta_classes()
    
    # Validate BFO hierarchy (named classes only)
    validate_bfo_hierarchy()
    
    # Check engineering ethics completeness
    check_engineering_ethics_completeness()
    
    # Check Neo4j integration
    neo4j_available = check_neo4j_integration()
    
    # Suggest improvements
    suggest_improvements()
    
    # Show proposed fixes
    create_fixed_meta_classes()

if __name__ == "__main__":
    main()