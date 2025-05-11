#!/usr/bin/env python3
"""
Test if the BFO ontology file can be parsed by RDFLib
"""

import os
import sys
import logging
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BFO Test')

def test_bfo_file():
    """Test if the BFO ontology file can be parsed by RDFLib"""
    
    # Path to the BFO ontology file
    file_path = os.path.join(os.path.dirname(__file__), '..', 'ontologies', 'bfo.ttl')
    
    # Log file path
    log_file_path = os.path.join(os.path.dirname(__file__), '..', 'ontology_data', 'bfo_test_results.log')
    
    # Create ontology_data directory if it doesn't exist
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'ontology_data'), exist_ok=True)
    
    # File handler for log
    file_handler = logging.FileHandler(log_file_path, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info(f'Testing file: {file_path}')
    
    # Test loading the file
    try:
        g = Graph()
        g.parse(file_path, format='turtle')
        
        # Count triples
        triple_count = len(g)
        logger.info(f'Successfully parsed file. Triple count: {triple_count}')
        
        # Count classes
        class_count = len(list(g.subjects(RDF.type, OWL.Class)))
        logger.info(f'Class count: {class_count}')
        
        # Count properties
        obj_prop_count = len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
        data_prop_count = len(list(g.subjects(RDF.type, OWL.DatatypeProperty)))
        logger.info(f'Property count: {obj_prop_count + data_prop_count} (Object: {obj_prop_count}, Data: {data_prop_count})')
        
        # Sample some triples
        logger.info('Sample triples:')
        for i, (s, p, o) in enumerate(g):
            if i >= 10:
                break
            logger.info(f'  {s} {p} {o}')
        
        # Test specific queries
        # Find all OWL classes
        classes = list(g.subjects(RDF.type, OWL.Class))
        logger.info(f'Found {len(classes)} OWL classes')
        
        # Sample some classes
        if classes:
            logger.info('Sample classes:')
            for i, cls in enumerate(classes[:5]):
                # Get label if available
                labels = list(g.objects(cls, RDFS.label))
                label = str(labels[0]) if labels else str(cls).split('/')[-1].split('#')[-1]
                logger.info(f'  Class {i+1}: {cls} (Label: {label})')
        
        # Find all object properties
        obj_props = list(g.subjects(RDF.type, OWL.ObjectProperty))
        logger.info(f'Found {len(obj_props)} object properties')
        
        # Sample some object properties
        if obj_props:
            logger.info('Sample object properties:')
            for i, prop in enumerate(obj_props[:5]):
                # Get label if available
                labels = list(g.objects(prop, RDFS.label))
                label = str(labels[0]) if labels else str(prop).split('/')[-1].split('#')[-1]
                logger.info(f'  Property {i+1}: {prop} (Label: {label})')
        
        logger.info('Test completed successfully')
        return True
    except Exception as e:
        logger.error(f'Error parsing file: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == '__main__':
    test_bfo_file()
    print("Test complete. Check ontology_data/bfo_test_results.log for results.")
