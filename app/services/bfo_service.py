#!/usr/bin/env python
"""
BFOService: Service for Basic Formal Ontology (BFO) operations.

This service provides functionality for working with BFO concepts,
particularly those related to temporal aspects of entities in the system.
"""

from typing import Dict, List, Optional, Any, Union
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL
import os

# Define BFO and related namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/")
PROETHICA = Namespace("http://proethica.org/ontology/")
PROETHICA_INT = Namespace("http://proethica.org/ontology/intermediate#")


class BFOService:
    """Service for Basic Formal Ontology (BFO) operations."""

    def __init__(self):
        """Initialize the BFO service with ontology graph."""
        self.graph = Graph()
        
        # Load BFO and ProEthica intermediate ontology
        try:
            # Get the base directory of the application
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            
            # Paths to ontology files
            bfo_path = os.path.join(base_dir, "mcp/ontology/bfo.owl")
            intermediate_path = os.path.join(base_dir, "mcp/ontology/proethica-intermediate.ttl")
            
            # Load ontologies if they exist
            if os.path.exists(bfo_path):
                self.graph.parse(bfo_path, format="xml")
                
            if os.path.exists(intermediate_path):
                self.graph.parse(intermediate_path, format="turtle")
                
        except Exception as e:
            print(f"Error loading ontologies: {str(e)}")
            # Continue with an empty graph
    
    def get_temporal_region_types(self) -> Dict[str, URIRef]:
        """
        Get the temporal region types defined in BFO.
        
        Returns:
            Dictionary mapping region type names to URIRefs
        """
        return {
            "temporal_region": BFO.BFO_0000008,  # temporal region
            "zero_dimensional": BFO.BFO_0000148,  # zero-dimensional temporal region (instant)
            "one_dimensional": BFO.BFO_0000038,  # one-dimensional temporal region (interval)
            "temporal_boundary": BFO.BFO_0000011  # temporal boundary
        }
    
    def get_temporal_relation_types(self) -> Dict[str, str]:
        """
        Get the temporal relation types defined in ProEthica ontology.
        
        Returns:
            Dictionary mapping relation type names to descriptions
        """
        return {
            "precedes": "Entity A occurs before Entity B",
            "follows": "Entity A occurs after Entity B",
            "coincidesWith": "Entities occur at the same time",
            "overlaps": "Temporal regions have an overlapping period",
            "necessitates": "An event creates the need for a decision",
            "hasConsequence": "Relates a decision to resulting events",
            "isNecessitatedBy": "Inverse of necessitates",
            "isConsequenceOf": "Inverse of hasConsequence"
        }
    
    def get_granularity_types(self) -> List[str]:
        """
        Get the temporal granularity types.
        
        Returns:
            List of granularity type names
        """
        return [
            "seconds", 
            "minutes", 
            "hours", 
            "days", 
            "weeks", 
            "months", 
            "years"
        ]
    
    def format_temporal_description(self, triple_data: Dict[str, Any]) -> str:
        """
        Format a human-readable description of a temporal triple.
        
        Args:
            triple_data: Dictionary containing temporal triple data
            
        Returns:
            Human-readable description
        """
        description = ""
        
        # Basic triple data
        entity_type = triple_data.get("entity_type", "")
        entity_id = triple_data.get("entity_id")
        
        # Temporal data
        region_type = triple_data.get("temporal_region_type", "")
        start_time = triple_data.get("temporal_start")
        end_time = triple_data.get("temporal_end")
        relation_type = triple_data.get("temporal_relation_type")
        granularity = triple_data.get("temporal_granularity", "")
        
        # Format based on region type
        if region_type == str(BFO.BFO_0000148):  # 0D temporal region
            if start_time:
                description += f"{entity_type.capitalize()} {entity_id} occurs at {start_time}"
        elif region_type == str(BFO.BFO_0000038):  # 1D temporal region
            if start_time and end_time:
                description += f"{entity_type.capitalize()} {entity_id} occurs from {start_time} to {end_time}"
            elif start_time:
                description += f"{entity_type.capitalize()} {entity_id} begins at {start_time}"
        
        # Add relation information if available
        if relation_type:
            relation_descriptions = self.get_temporal_relation_types()
            relation_desc = relation_descriptions.get(relation_type, relation_type)
            description += f" ({relation_desc})"
        
        return description
    
    def enhance_triples_with_bfo_temporal(self, g: Graph, subject_uri: URIRef, 
                                          temporal_data: Dict[str, Any]) -> None:
        """
        Enhance a graph with BFO temporal information.
        
        Args:
            g: RDF graph to enhance
            subject_uri: Subject URI to add statements about
            temporal_data: Dictionary containing temporal data
        """
        region_type = temporal_data.get("temporal_region_type")
        start_time = temporal_data.get("temporal_start")
        end_time = temporal_data.get("temporal_end")
        relation_type = temporal_data.get("temporal_relation_type")
        relation_to = temporal_data.get("temporal_relation_to")
        granularity = temporal_data.get("temporal_granularity")
        
        # Create temporal region
        if region_type and start_time:
            # Create temporal region node
            temp_region = URIRef(f"{subject_uri}/temporal-region")
            
            # Add type statement
            g.add((temp_region, RDF.type, URIRef(region_type)))
            
            # Add statements about the region
            g.add((subject_uri, PROETHICA_INT.hasTemporalRegion, temp_region))
            
            # Add start time
            g.add((temp_region, PROETHICA_INT.hasStartTime, Literal(start_time.isoformat())))
            
            # Add end time if available
            if end_time:
                g.add((temp_region, PROETHICA_INT.hasEndTime, Literal(end_time.isoformat())))
            
            # Add granularity if available
            if granularity:
                g.add((temp_region, PROETHICA_INT.hasGranularity, Literal(granularity)))
        
        # Add relation if available
        if relation_type and relation_to:
            # Create relation predicate URI
            relation_pred = PROETHICA_INT[relation_type]
            
            # Create related entity URI - assuming it follows a pattern
            related_uri = URIRef(f"http://proethica.org/entity/{relation_to}")
            
            # Add relation statement
            g.add((subject_uri, relation_pred, related_uri))
