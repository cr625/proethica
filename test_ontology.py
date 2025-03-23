#!/usr/bin/env python3
from mcp.ontology_mcp_server import OntologyMCPServer
import asyncio
import json

async def test():
    server = OntologyMCPServer()
    
    # Test engineering_ethics.ttl
    print('Loading engineering_ethics.ttl...')
    g = server._load_graph_from_file('engineering_ethics.ttl')
    print('Graph loaded, detecting namespace...')
    namespace = server._detect_namespace(g)
    print(f'Detected namespace: {namespace}')
    print('Extracting entities...')
    entities = server._extract_entities(g, 'all')
    print('Entities extracted:')
    for entity_type, entities_list in entities.items():
        print(f'{entity_type}: {len(entities_list)} entities found')
        if entities_list:
            print(f'Sample {entity_type}:')
            print(json.dumps(entities_list[0], indent=2))
            print()
    
    # Print all triples in the engineering_ethics.ttl file
    print('\nPrinting all triples in engineering_ethics.ttl related to Client and BridgeDesign1...')
    from rdflib import RDF, RDFS
    
    # Look for Client class
    print("\nLooking for Client class...")
    for s, p, o in g.triples((None, RDF.type, None)):
        if 'Client' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for Client1 instance
    print("\nLooking for Client1 instance...")
    for s, p, o in g.triples((None, None, None)):
        if 'Client1' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for BridgeDesign1 instance
    print("\nLooking for BridgeDesign1 instance...")
    for s, p, o in g.triples((None, None, None)):
        if 'BridgeDesign1' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for actionForClient property
    print("\nLooking for actionForClient property...")
    for s, p, o in g.triples((None, None, None)):
        if 'actionForClient' in str(p):
            print(f"Found: {s} {p} {o}")
    
    # Test tccc.ttl
    print('\nLoading tccc.ttl...')
    g = server._load_graph_from_file('tccc.ttl')
    print('Graph loaded, detecting namespace...')
    namespace = server._detect_namespace(g)
    print(f'Detected namespace: {namespace}')
    print('Extracting entities...')
    entities = server._extract_entities(g, 'all')
    print('Entities extracted:')
    for entity_type, entities_list in entities.items():
        print(f'{entity_type}: {len(entities_list)} entities found')
    
    # Print all triples in the tccc.ttl file
    print('\nPrinting all triples in tccc.ttl related to Patient and TourniquetApplication1...')
    
    # Look for Patient class
    print("\nLooking for Patient class...")
    for s, p, o in g.triples((None, RDF.type, None)):
        if 'Patient' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for Patient1 instance
    print("\nLooking for Patient1 instance...")
    for s, p, o in g.triples((None, None, None)):
        if 'Patient1' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for TourniquetApplication1 instance
    print("\nLooking for TourniquetApplication1 instance...")
    for s, p, o in g.triples((None, None, None)):
        if 'TourniquetApplication1' in str(s):
            print(f"Found: {s} {p} {o}")
    
    # Look for actionForPatient property
    print("\nLooking for actionForPatient property...")
    for s, p, o in g.triples((None, None, None)):
        if 'actionForPatient' in str(p):
            print(f"Found: {s} {p} {o}")

if __name__ == "__main__":
    asyncio.run(test())
