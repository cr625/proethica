#!/usr/bin/env python3
"""
Script to demonstrate integration of BFO ontology with ethical case studies.

This script shows how the Basic Formal Ontology (BFO) concepts can be used to
enhance the representation and querying of ethical cases in the AI-Ethical-DM system.
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import networkx as nx
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
ONTOLOGY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp", "ontology")
BFO_PATH = os.path.join(ONTOLOGY_DIR, "bfo-core.ttl")
ENG_ETHICS_PATH = os.path.join(ONTOLOGY_DIR, "engineering_ethics.ttl")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CASES_PATH = os.path.join(DATA_DIR, "nspe_cases.json")
MODERN_CASES_PATH = os.path.join(DATA_DIR, "modern_nspe_cases.json")

# Namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
ENG = Namespace("http://example.org/engineering-ethics#")
CASES = Namespace("http://example.org/ethics-cases#")


def load_ontologies() -> Graph:
    """
    Load the BFO and Engineering Ethics ontologies.
    
    Returns:
        Combined RDF graph with both ontologies
    """
    logger.info("Loading ontologies...")
    
    # Create a new graph
    g = Graph()
    
    # Load BFO ontology
    logger.info(f"Loading BFO from {BFO_PATH}")
    g.parse(BFO_PATH, format="turtle")
    
    # Load Engineering Ethics ontology
    logger.info(f"Loading Engineering Ethics from {ENG_ETHICS_PATH}")
    g.parse(ENG_ETHICS_PATH, format="turtle")
    
    logger.info(f"Loaded combined graph with {len(g)} triples")
    return g


def load_cases() -> List[Dict[str, Any]]:
    """
    Load both historical and modern ethics cases.
    
    Returns:
        Combined list of case dictionaries
    """
    cases = []
    
    # Load historical cases
    if os.path.exists(CASES_PATH):
        try:
            with open(CASES_PATH, 'r', encoding='utf-8') as f:
                historical_cases = json.load(f)
                logger.info(f"Loaded {len(historical_cases)} historical cases")
                cases.extend(historical_cases)
        except Exception as e:
            logger.error(f"Error loading historical cases: {str(e)}")
    
    # Load modern cases
    if os.path.exists(MODERN_CASES_PATH):
        try:
            with open(MODERN_CASES_PATH, 'r', encoding='utf-8') as f:
                modern_cases = json.load(f)
                logger.info(f"Loaded {len(modern_cases)} modern cases")
                cases.extend(modern_cases)
        except Exception as e:
            logger.error(f"Error loading modern cases: {str(e)}")
    
    return cases


def map_ethics_to_bfo(g: Graph, cases: List[Dict[str, Any]]) -> Graph:
    """
    Create RDF mappings between engineering ethics concepts and BFO concepts,
    and represent cases using BFO categories.
    
    Args:
        g: The combined ontology graph
        cases: List of ethics cases
        
    Returns:
        Updated graph with ethics-to-BFO mappings
    """
    # Add BFO namespace
    g.bind("bfo", BFO)
    g.bind("eng", ENG)
    g.bind("cases", CASES)
    
    # Define mapping of ethical concepts to BFO
    logger.info("Mapping engineering ethics concepts to BFO...")
    
    # Map principles to BFO:generically_dependent_continuant (0000031)
    g.add((ENG.EthicalPrinciple, RDFS.subClassOf, BFO["0000031"]))  # generically_dependent_continuant
    
    # Map ethical dilemmas to BFO:process (0000015)
    g.add((ENG.EthicalDilemma, RDFS.subClassOf, BFO["0000015"]))  # process
    
    # Map professional duties to BFO:role (0000023)
    g.add((ENG.ProfessionalDuty, RDFS.subClassOf, BFO["0000023"]))  # role
    
    # Map conflicts to BFO:process_boundary (0000035)
    g.add((ENG.EthicalConflict, RDFS.subClassOf, BFO["0000035"]))  # process_boundary
    
    # Map outcomes to BFO:process_profile (0000144)
    g.add((ENG.EthicalOutcome, RDFS.subClassOf, BFO["0000144"]))  # process_profile
    
    # Add common engineering ethics principles as instances of EthicalPrinciple
    principles = set()
    for case in cases:
        case_principles = case.get('metadata', {}).get('principles', [])
        for principle in case_principles:
            principles.add(principle.lower())
    
    # Create the principle instances
    for principle in principles:
        principle_uri = ENG[f"principle_{principle.replace(' ', '_')}"]
        g.add((principle_uri, RDF.type, ENG.EthicalPrinciple))
        g.add((principle_uri, RDFS.label, Literal(principle)))
    
    # Add cases
    logger.info("Adding cases using BFO structure...")
    for i, case in enumerate(cases):
        case_number = case.get('case_number', f"case-{i}")
        case_id = case_number.replace(' ', '_').replace('-', '_').lower()
        case_uri = CASES[case_id]
        
        # Case as a process
        g.add((case_uri, RDF.type, ENG.EthicalDilemma))
        g.add((case_uri, RDFS.label, Literal(case.get('title', 'Unknown Title'))))
        
        # Add outcome
        outcome = case.get('metadata', {}).get('outcome', 'unknown')
        outcome_uri = CASES[f"outcome_{case_id}"]
        g.add((outcome_uri, RDF.type, ENG.EthicalOutcome))
        g.add((outcome_uri, RDFS.label, Literal(outcome)))
        g.add((case_uri, ENG.hasOutcome, outcome_uri))
        
        # Add principles
        for principle in case.get('metadata', {}).get('principles', []):
            principle_uri = ENG[f"principle_{principle.lower().replace(' ', '_')}"]
            g.add((case_uri, ENG.involvesEthicalPrinciple, principle_uri))
        
        # If there are conflicting principles, create a conflict node
        if len(case.get('metadata', {}).get('principles', [])) > 1:
            conflict_uri = CASES[f"conflict_{case_id}"]
            g.add((conflict_uri, RDF.type, ENG.EthicalConflict))
            g.add((case_uri, ENG.hasConflict, conflict_uri))
            
            # Connect principles to the conflict
            for principle in case.get('metadata', {}).get('principles', []):
                principle_uri = ENG[f"principle_{principle.lower().replace(' ', '_')}"]
                g.add((conflict_uri, ENG.involvesEthicalPrinciple, principle_uri))
    
    return g


def find_conflicts_involving_principle(g: Graph, principle_name: str) -> List[Dict[str, str]]:
    """
    Find ethical dilemmas involving a specific principle.
    
    Args:
        g: The RDF graph
        principle_name: The name of the principle to search for
        
    Returns:
        List of dilemmas with their details
    """
    principle_uri = ENG[f"principle_{principle_name.lower().replace(' ', '_')}"]
    
    query = """
    PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_>
    PREFIX eng: <http://example.org/engineering-ethics#>
    PREFIX cases: <http://example.org/ethics-cases#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?case ?caseLabel ?outcome
    WHERE {
        ?case rdf:type eng:EthicalDilemma .
        ?case eng:involvesEthicalPrinciple ?principle .
        ?case rdfs:label ?caseLabel .
        ?case eng:hasOutcome ?outcomeNode .
        ?outcomeNode rdfs:label ?outcome .
        FILTER(?principle = ?targetPrinciple)
    }
    """
    
    results = g.query(query, initBindings={'targetPrinciple': principle_uri})
    
    dilemmas = []
    for row in results:
        dilemmas.append({
            'case_uri': str(row.case),
            'case_label': str(row.caseLabel),
            'outcome': str(row.outcome)
        })
    
    return dilemmas


def find_conflicting_principles(g: Graph) -> List[Dict[str, List[str]]]:
    """
    Find principles that often conflict with each other.
    
    Args:
        g: The RDF graph
        
    Returns:
        List of conflicts with principles involved
    """
    query = """
    PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_>
    PREFIX eng: <http://example.org/engineering-ethics#>
    PREFIX cases: <http://example.org/ethics-cases#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?conflict ?case ?caseLabel (GROUP_CONCAT(?principleLabel; separator=", ") as ?principles)
    WHERE {
        ?case rdf:type eng:EthicalDilemma .
        ?case rdfs:label ?caseLabel .
        ?case eng:hasConflict ?conflict .
        ?conflict eng:involvesEthicalPrinciple ?principle .
        ?principle rdfs:label ?principleLabel .
    }
    GROUP BY ?conflict ?case ?caseLabel
    """
    
    results = g.query(query)
    
    conflicts = []
    for row in results:
        conflicts.append({
            'conflict_uri': str(row.conflict),
            'case_uri': str(row.case),
            'case_label': str(row.caseLabel),
            'principles': str(row.principles).split(", ")
        })
    
    return conflicts


def visualize_principle_network(g: Graph, output_file: str = None):
    """
    Create a network visualization of ethical principles and their relationships.
    
    Args:
        g: The RDF graph
        output_file: Optional path to save the visualization
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Get all principles
    query = """
    PREFIX eng: <http://example.org/engineering-ethics#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?principle ?label
    WHERE {
        ?principle rdf:type eng:EthicalPrinciple .
        ?principle rdfs:label ?label .
    }
    """
    
    results = g.query(query)
    
    # Add principle nodes
    for row in results:
        G.add_node(str(row.label), type="principle")
    
    # Find co-occurring principles in cases
    query = """
    PREFIX eng: <http://example.org/engineering-ethics#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?p1Label ?p2Label (COUNT(?case) as ?count)
    WHERE {
        ?case eng:involvesEthicalPrinciple ?p1 .
        ?case eng:involvesEthicalPrinciple ?p2 .
        ?p1 rdfs:label ?p1Label .
        ?p2 rdfs:label ?p2Label .
        FILTER (?p1 != ?p2)
    }
    GROUP BY ?p1Label ?p2Label
    """
    
    results = g.query(query)
    
    # Add edges for co-occurring principles
    for row in results:
        G.add_edge(str(row.p1Label), str(row.p2Label), weight=int(row.count))
    
    # Create visualization
    plt.figure(figsize=(12, 10))
    
    # Set node positions using spring layout
    pos = nx.spring_layout(G, k=0.3, iterations=50)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=800, node_color="lightblue", alpha=0.8)
    
    # Draw edges with width based on weight
    edge_widths = [G[u][v]['weight'] for u, v in G.edges()]
    nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.5, edge_color="gray")
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=10)
    
    plt.title("Network of Co-occurring Ethical Principles in Cases")
    plt.axis("off")
    
    # Save or show the visualization
    if output_file:
        plt.savefig(output_file, format="png", dpi=300, bbox_inches="tight")
        logger.info(f"Saved visualization to {output_file}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='Demonstrate BFO integration with ethics cases')
    parser.add_argument('--principle', type=str, help='Search for cases involving a specific principle')
    parser.add_argument('--conflicts', action='store_true', help='Show conflicting principles')
    parser.add_argument('--visualize', action='store_true', help='Create visualization of principle network')
    parser.add_argument('--output', type=str, help='Output file for visualization')
    
    args = parser.parse_args()
    
    # Load ontologies and cases
    g = load_ontologies()
    cases = load_cases()
    
    # Map ethics concepts to BFO and add cases
    g = map_ethics_to_bfo(g, cases)
    
    # Count triples in the graph
    logger.info(f"Enhanced graph now has {len(g)} triples")
    
    # Search for cases involving a specific principle
    if args.principle:
        logger.info(f"Searching for cases involving '{args.principle}'...")
        dilemmas = find_conflicts_involving_principle(g, args.principle)
        
        print(f"\nFound {len(dilemmas)} dilemmas involving '{args.principle}':")
        for i, dilemma in enumerate(dilemmas, 1):
            print(f"{i}. {dilemma['case_label']} (Outcome: {dilemma['outcome']})")
    
    # Show conflicting principles
    if args.conflicts:
        logger.info("Finding conflicting principles...")
        conflicts = find_conflicting_principles(g)
        
        print(f"\nFound {len(conflicts)} principle conflicts:")
        for i, conflict in enumerate(conflicts, 1):
            print(f"{i}. Case: {conflict['case_label']}")
            print(f"   Principles: {', '.join(conflict['principles'])}")
    
    # Create visualization
    if args.visualize:
        logger.info("Creating network visualization of principles...")
        output_file = args.output if args.output else os.path.join(DATA_DIR, "principle_network.png")
        visualize_principle_network(g, output_file)
    
    # Default action if no specific argument provided
    if not (args.principle or args.conflicts or args.visualize):
        print("\nBFO Integration Demo")
        print("-------------------")
        print("This script demonstrates how BFO concepts can be used to enhance ethical reasoning.")
        print("\nAvailable commands:")
        print("  --principle NAME : Search for cases involving a specific principle")
        print("  --conflicts      : Show conflicting principles")
        print("  --visualize      : Create visualization of principle network")
        print("\nExample usage:")
        print("  python3 bfo_ethics_demo.py --principle \"public safety\"")
        print("  python3 bfo_ethics_demo.py --conflicts")
        print("  python3 bfo_ethics_demo.py --visualize --output principles.png")


if __name__ == "__main__":
    main()
