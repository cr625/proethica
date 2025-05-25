#!/usr/bin/env python3
"""
Validate the syntax and check for circular references in the ontology files.
"""
import rdflib
import sys

def validate_turtle_file(file_path):
    """
    Validate the Turtle syntax of a file.
    """
    print(f"Validating {file_path}...")
    try:
        g = rdflib.Graph()
        g.parse(file_path, format="turtle")
        triple_count = len(g)
        print(f"  ✓ Valid Turtle syntax with {triple_count} triples")
        return g
    except Exception as e:
        print(f"  ✗ Invalid Turtle syntax: {str(e)}")
        return None

def check_circular_references(g, file_path):
    """
    Check for classes that reference themselves in rdfs:subClassOf.
    """
    circular_refs = []
    
    # SPARQL query to find classes that reference themselves
    query = """
    SELECT ?class WHERE {
        ?class rdfs:subClassOf ?class .
    }
    """
    
    results = g.query(query, initNs={"rdfs": rdflib.RDFS})
    
    for row in results:
        circular_refs.append(str(row[0]))
    
    if circular_refs:
        print(f"  ✗ Found {len(circular_refs)} circular references:")
        for ref in circular_refs:
            print(f"    - {ref}")
    else:
        print(f"  ✓ No circular references found")
    
    return circular_refs

def check_property_completeness(g, file_path):
    """
    Check if all classes have required properties.
    """
    # Query for classes that don't have rdfs:label
    query_no_label = """
    SELECT ?class WHERE {
        ?class a owl:Class .
        FILTER NOT EXISTS { ?class rdfs:label ?label }
    }
    """
    
    # Query for classes that don't have rdfs:comment
    query_no_comment = """
    SELECT ?class WHERE {
        ?class a owl:Class .
        FILTER NOT EXISTS { ?class rdfs:comment ?comment }
    }
    """
    
    results_no_label = g.query(query_no_label, initNs={"owl": rdflib.OWL, "rdfs": rdflib.RDFS})
    results_no_comment = g.query(query_no_comment, initNs={"owl": rdflib.OWL, "rdfs": rdflib.RDFS})
    
    classes_no_label = [str(row[0]) for row in results_no_label]
    classes_no_comment = [str(row[0]) for row in results_no_comment]
    
    print(f"  Property completeness check:")
    if classes_no_label:
        print(f"    ✗ {len(classes_no_label)} classes missing rdfs:label")
    else:
        print(f"    ✓ All classes have rdfs:label")
    
    if classes_no_comment:
        print(f"    ✗ {len(classes_no_comment)} classes missing rdfs:comment")
    else:
        print(f"    ✓ All classes have rdfs:comment")
    
    return classes_no_label, classes_no_comment

def check_reference_integrity(g_eng, g_proeth):
    """
    Check if all references between ontologies are valid.
    """
    # Extract all URIs from both ontologies
    eng_uris = set([str(s) for s in g_eng.subjects()] + [str(o) for o in g_eng.objects()])
    proeth_uris = set([str(s) for s in g_proeth.subjects()] + [str(o) for o in g_proeth.objects()])
    
    # Find references to proethica in engineering-ethics
    query_proeth_refs = """
    SELECT ?s ?p ?o WHERE {
        ?s ?p ?o .
        FILTER(STRSTARTS(STR(?o), "http://proethica.org/ontology/intermediate#"))
    }
    """
    
    results = g_eng.query(query_proeth_refs)
    invalid_refs = []
    
    for row in results:
        obj = str(row[2])
        if obj not in proeth_uris:
            invalid_refs.append(obj)
    
    print(f"  Reference integrity check:")
    if invalid_refs:
        print(f"    ✗ Found {len(invalid_refs)} references to non-existent proethica URIs:")
        for ref in invalid_refs[:5]:  # Show at most 5 examples
            print(f"      - {ref}")
        if len(invalid_refs) > 5:
            print(f"      - ... and {len(invalid_refs) - 5} more")
    else:
        print(f"    ✓ All references to proethica URIs are valid")
    
    return invalid_refs

def main():
    eng_ethics_path = "ontologies/engineering-ethics.ttl"
    proeth_interm_path = "ontologies/proethica-intermediate.ttl"
    
    # Validate Turtle syntax
    g_eng = validate_turtle_file(eng_ethics_path)
    g_proeth = validate_turtle_file(proeth_interm_path)
    
    if not g_eng or not g_proeth:
        print("Syntax validation failed. Exiting.")
        sys.exit(1)
    
    # Check for circular references
    print("\nChecking for circular references:")
    eng_circular = check_circular_references(g_eng, eng_ethics_path)
    proeth_circular = check_circular_references(g_proeth, proeth_interm_path)
    
    # Check property completeness
    print("\nChecking property completeness:")
    print(f"Engineering ethics ontology:")
    eng_no_label, eng_no_comment = check_property_completeness(g_eng, eng_ethics_path)
    print(f"Proethica intermediate ontology:")
    proeth_no_label, proeth_no_comment = check_property_completeness(g_proeth, proeth_interm_path)
    
    # Check reference integrity
    print("\nChecking reference integrity:")
    invalid_refs = check_reference_integrity(g_eng, g_proeth)
    
    # Summarize issues
    issues = len(eng_circular) + len(proeth_circular) + len(eng_no_label) + len(eng_no_comment) + len(proeth_no_label) + len(proeth_no_comment) + len(invalid_refs)
    
    print("\nValidation summary:")
    if issues == 0:
        print("✓ No issues found! Ontologies are valid and consistent.")
    else:
        print(f"✗ Found {issues} issues that need to be fixed.")
    
    return issues

if __name__ == "__main__":
    sys.exit(main())
