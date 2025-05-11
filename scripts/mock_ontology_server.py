#!/usr/bin/env python3
"""
Mock Ontology Server for standalone use of McLaren Case Analysis Module.
This provides the minimum interface needed for the McLaren module to function
without requiring the full Flask application.
"""

import os
import logging
from rdflib import Graph, URIRef, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

logger = logging.getLogger("mock_ontology_server")

class MockOntologyServer:
    """
    Simple mock server that provides the minimal interface required by the McLaren module.
    """
    
    def __init__(self):
        """Initialize the mock server."""
        self.app = None
        self.ontology_path = os.path.join(os.getcwd(), "ontologies")
        self.cached_graphs = {}
        
    def _load_graph_from_file(self, ontology_source):
        """
        Load an RDF graph from a TTL file.
        
        Args:
            ontology_source: Name of the ontology file (without .ttl extension)
            
        Returns:
            rdflib.Graph: The loaded RDF graph
        """
        if ontology_source in self.cached_graphs:
            return self.cached_graphs[ontology_source]
            
        try:
            file_path = os.path.join(self.ontology_path, f"{ontology_source}.ttl")
            if not os.path.exists(file_path):
                logger.error(f"Ontology file not found: {file_path}")
                return Graph()
                
            g = Graph()
            g.parse(file_path, format="turtle")
            
            # Cache the graph for future use
            self.cached_graphs[ontology_source] = g
            
            logger.info(f"Loaded ontology from {file_path} with {len(g)} triples")
            return g
        except Exception as e:
            logger.error(f"Error loading ontology {ontology_source}: {str(e)}")
            return Graph()
