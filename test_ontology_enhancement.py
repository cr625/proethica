#!/usr/bin/env python3
"""
Test script to verify the ontology enhancements and demonstrate how they can be used
for improved section-triple associations.
"""
import sys
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS

def load_ontologies():
    """
    Load both ontologies and verify they can be parsed correctly.
    """
    print("Loading ontologies...")
    
    # Load engineering ethics ontology
    eng_ethics = Graph()
    eng_ethics.parse("ontologies/engineering-ethics.ttl", format="turtle")
    print(f"  ✓ Loaded engineering-ethics.ttl with {len(eng_ethics)} triples")
    
    # Load proethica intermediate ontology
    proeth_int = Graph()
    proeth_int.parse("ontologies/proethica-intermediate.ttl", format="turtle")
    print(f"  ✓ Loaded proethica-intermediate.ttl with {len(proeth_int)} triples")
    
    return eng_ethics, proeth_int

def count_classes_with_semantic_properties(graph):
    """
    Count how many classes have semantic matching properties.
    """
    proeth = URIRef("http://proethica.org/ontology/intermediate#")
    has_category = URIRef(proeth + "hasCategory")
    has_matching_term = URIRef(proeth + "hasMatchingTerm")
    has_text_reference = URIRef(proeth + "hasTextReference")
    has_relevance_score = URIRef(proeth + "hasRelevanceScore")
    
    # Get classes with hasCategory
    query_has_category = """
    SELECT DISTINCT ?class WHERE {
        ?class <http://proethica.org/ontology/intermediate#hasCategory> ?category .
    }
    """
    
    # Get classes with hasMatchingTerm
    query_has_matching_term = """
    SELECT DISTINCT ?class WHERE {
        ?class <http://proethica.org/ontology/intermediate#hasMatchingTerm> ?term .
    }
    """
    
    # Get classes with hasTextReference
    query_has_text_reference = """
    SELECT DISTINCT ?class WHERE {
        ?class <http://proethica.org/ontology/intermediate#hasTextReference> ?text .
    }
    """
    
    # Get classes with hasRelevanceScore
    query_has_relevance_score = """
    SELECT DISTINCT ?class WHERE {
        ?class <http://proethica.org/ontology/intermediate#hasRelevanceScore> ?score .
    }
    """
    
    classes_with_category = set([str(row[0]) for row in graph.query(query_has_category)])
    classes_with_term = set([str(row[0]) for row in graph.query(query_has_matching_term)])
    classes_with_text = set([str(row[0]) for row in graph.query(query_has_text_reference)])
    classes_with_score = set([str(row[0]) for row in graph.query(query_has_relevance_score)])
    
    all_classes_with_semantic = classes_with_category.union(classes_with_term, classes_with_text, classes_with_score)
    
    print("\nClasses with semantic matching properties:")
    print(f"  - Classes with hasCategory: {len(classes_with_category)}")
    print(f"  - Classes with hasMatchingTerm: {len(classes_with_term)}")
    print(f"  - Classes with hasTextReference: {len(classes_with_text)}")
    print(f"  - Classes with hasRelevanceScore: {len(classes_with_score)}")
    print(f"  - Total classes with at least one semantic property: {len(all_classes_with_semantic)}")
    
    return all_classes_with_semantic

def print_principle_examples(graph):
    """
    Print examples of the new principle classes with their semantic properties.
    """
    print("\nExamples of enhanced ethical principles:")
    
    query = """
    SELECT DISTINCT ?principle ?label ?comment 
    WHERE {
        ?principle a owl:Class ;
            rdfs:label ?label ;
            rdfs:comment ?comment ;
            rdfs:subClassOf+ <http://proethica.org/ontology/engineering-ethics#Principle> .
        ?principle <http://proethica.org/ontology/intermediate#hasMatchingTerm> ?term .
    }
    LIMIT 5
    """
    
    results = graph.query(query, initNs={
        "rdfs": RDFS,
        "owl": URIRef("http://www.w3.org/2002/07/owl#")
    })
    
    for i, (principle, label, comment) in enumerate(results, 1):
        print(f"\n{i}. {label}")
        print(f"   URI: {principle}")
        print(f"   Description: {comment}")
        
        # Fetch categories separately
        categories_query = f"""
        SELECT ?category
        WHERE {{
            <{principle}> <http://proethica.org/ontology/intermediate#hasCategory> ?category .
        }}
        """
        categories_results = graph.query(categories_query)
        categories = [str(row[0]) for row in categories_results]
        if categories:
            print(f"   Categories: {', '.join(categories)}")
        
        # Fetch matching terms separately
        terms_query = f"""
        SELECT ?term
        WHERE {{
            <{principle}> <http://proethica.org/ontology/intermediate#hasMatchingTerm> ?term .
        }}
        """
        terms_results = graph.query(terms_query)
        terms = [str(row[0]) for row in terms_results]
        if terms:
            print(f"   Matching terms: {', '.join(terms)}")
        
        # Fetch relevance score separately
        score_query = f"""
        SELECT ?score
        WHERE {{
            <{principle}> <http://proethica.org/ontology/intermediate#hasRelevanceScore> ?score .
        }}
        """
        score_results = graph.query(score_query)
        scores = [str(row[0]) for row in score_results]
        if scores:
            print(f"   Relevance score: {', '.join(scores)}")

def main():
    # Load ontologies
    eng_ethics, proeth_int = load_ontologies()
    
    # Count classes with semantic properties
    semantic_classes = count_classes_with_semantic_properties(eng_ethics)
    
    # Print examples of new principles
    print_principle_examples(eng_ethics)
    
    print("\nTest completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
