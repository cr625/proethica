#!/usr/bin/env python3
"""
Test all ontology files to verify they can be correctly parsed
"""

import os
import sys
import logging
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Ontology Checker')

def test_ontology_file(file_path):
    """Test an ontology file to verify it can be parsed"""
    
    filename = os.path.basename(file_path)
    logger.info(f'Testing ontology file: {filename}')
    
    # Create a new log file for detailed results
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'ontology_data')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"{os.path.splitext(filename)[0]}_check.log")
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    try:
        # Load the graph
        g = Graph()
        g.parse(file_path, format='turtle')
        
        # Count triples, classes, and properties
        triple_count = len(g)
        class_count = len(list(g.subjects(RDF.type, OWL.Class)))
        obj_prop_count = len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
        data_prop_count = len(list(g.subjects(RDF.type, OWL.DatatypeProperty)))
        
        logger.info(f'Ontology statistics:')
        logger.info(f'  - Total triples: {triple_count}')
        logger.info(f'  - Classes: {class_count}')
        logger.info(f'  - Object properties: {obj_prop_count}')
        logger.info(f'  - Datatype properties: {data_prop_count}')
        
        # Get some sample class names
        logger.info(f'Sample classes:')
        classes = list(g.subjects(RDF.type, OWL.Class))
        for i, cls in enumerate(classes[:5]):
            # Get label if available
            labels = list(g.objects(cls, RDFS.label))
            label = str(labels[0]) if labels else None
            if label:
                logger.info(f'  - {cls} (Label: {label})')
            else:
                logger.info(f'  - {cls}')
            
            # Get superclasses
            superclasses = list(g.objects(cls, RDFS.subClassOf))
            if superclasses:
                logger.info(f'    Superclasses: {len(superclasses)}')
                for sc in superclasses[:2]:  # List first 2 superclasses
                    sc_labels = list(g.objects(sc, RDFS.label))
                    sc_label = str(sc_labels[0]) if sc_labels else None
                    if sc_label:
                        logger.info(f'    - {sc} (Label: {sc_label})')
                    else:
                        logger.info(f'    - {sc}')
        
        # Get some sample property names
        logger.info(f'Sample object properties:')
        obj_props = list(g.subjects(RDF.type, OWL.ObjectProperty))
        for i, prop in enumerate(obj_props[:5]):
            # Get label if available
            labels = list(g.objects(prop, RDFS.label))
            label = str(labels[0]) if labels else None
            if label:
                logger.info(f'  - {prop} (Label: {label})')
            else:
                logger.info(f'  - {prop}')
            
            # Get domain and range
            domains = list(g.objects(prop, RDFS.domain))
            ranges = list(g.objects(prop, RDFS.range))
            
            if domains:
                logger.info(f'    Domain: {domains[0]}')
            if ranges:
                logger.info(f'    Range: {ranges[0]}')
        
        logger.info(f'Ontology {filename} parsed successfully!')
        logger.removeHandler(file_handler)
        return True
    except Exception as e:
        logger.error(f'Error parsing ontology {filename}: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        logger.removeHandler(file_handler)
        return False

def check_all_ontologies():
    """Check all ontology files in the ontologies directory"""
    
    # Path to ontologies directory
    ontology_dir = os.path.join(os.path.dirname(__file__), '..', 'ontologies')
    
    if not os.path.exists(ontology_dir):
        logger.error(f'Ontologies directory not found: {ontology_dir}')
        return
    
    # List all .ttl files
    ttl_files = [f for f in os.listdir(ontology_dir) if f.endswith('.ttl')]
    
    if not ttl_files:
        logger.warning(f'No .ttl files found in {ontology_dir}')
        return
    
    # Test each file
    results = {}
    for filename in ttl_files:
        file_path = os.path.join(ontology_dir, filename)
        results[filename] = test_ontology_file(file_path)
    
    # Print summary
    logger.info(f'\nOntology Check Summary:')
    for filename, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f'{status}: {filename}')
    
    # Calculate success rate
    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    if total_count > 0:
        success_rate = (success_count / total_count) * 100
        logger.info(f'\nSuccess rate: {success_rate:.1f}% ({success_count}/{total_count})')

if __name__ == '__main__':
    check_all_ontologies()
