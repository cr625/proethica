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
    
    def extract_temporal_boundaries(self, events: List[Dict[str, Any]], case_content: str) -> List[Dict[str, Any]]:
        """
        Extract temporal boundaries from events using BFO concepts.
        
        Args:
            events: List of events from scenario generation
            case_content: Original case text for context
            
        Returns:
            List of temporal boundary dictionaries
        """
        boundaries = []
        
        # Find decision points as temporal boundaries (BFO_0000011)
        for i, event in enumerate(events):
            if event.get('kind') == 'decision':
                boundary = {
                    'boundary_id': f"bfo_boundary_{i+1}",
                    'bfo_class': 'BFO_0000011',  # temporal boundary
                    'event_id': event.get('id'),
                    'boundary_type': 'decision_point',
                    'description': event.get('text', f"Decision boundary {i+1}"),
                    'ethical_significance': self._calculate_boundary_significance(event, case_content)
                }
                boundaries.append(boundary)
        
        return boundaries
    
    def calculate_temporal_relations(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate BFO-based temporal relations between events.
        
        Args:
            events: List of events with temporal information
            
        Returns:
            List of temporal relation dictionaries
        """
        relations = []
        
        # Simple precedence relations for now
        sorted_events = sorted(events, key=lambda e: e.get('sequence_number', 0))
        
        for i in range(len(sorted_events) - 1):
            current = sorted_events[i]
            next_event = sorted_events[i + 1]
            
            relation = {
                'source_id': current.get('id'),
                'target_id': next_event.get('id'),
                'relation_type': 'precedes',
                'bfo_class': 'BFO_0000057',  # temporal relation
                'confidence': 0.8
            }
            relations.append(relation)
        
        return relations
    
    def build_process_profile(self, case_id: int, events: List[Dict[str, Any]], case_content: str) -> Dict[str, Any]:
        """
        Build a BFO process profile for the complete case.
        
        Args:
            case_id: Database ID of the case
            events: List of events from scenario generation
            case_content: Original case text
            
        Returns:
            Process profile dictionary
        """
        boundaries = self.extract_temporal_boundaries(events, case_content)
        relations = self.calculate_temporal_relations(events)
        
        profile = {
            'process_id': f"bfo_process_{case_id}",
            'bfo_class': 'BFO_0000015',  # process
            'case_id': case_id,
            'temporal_boundaries': boundaries,
            'temporal_relations': relations,
            'process_phases': self._identify_bfo_phases(events, boundaries),
            'critical_path': self._extract_critical_path(events, boundaries)
        }
        
        return profile
    
    def _calculate_boundary_significance(self, event: Dict[str, Any], case_content: str) -> float:
        """Calculate ethical significance of a temporal boundary."""
        significance = 0.5
        
        if event.get('kind') == 'decision':
            significance += 0.3
        
        # Look for ethical keywords
        text = event.get('text', '').lower()
        ethical_terms = ['safety', 'public', 'disclosure', 'ethical', 'responsibility']
        
        for term in ethical_terms:
            if term in text:
                significance += 0.1
        
        return min(significance, 1.0)
    
    def _identify_bfo_phases(self, events: List[Dict[str, Any]], boundaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify process phases using BFO concepts."""
        phases = []
        
        # Simple phase identification based on decision points
        decision_boundaries = [b for b in boundaries if b.get('boundary_type') == 'decision_point']
        
        for i, boundary in enumerate(decision_boundaries):
            phase = {
                'phase_id': f"bfo_phase_{i+1}",
                'phase_name': f"Phase {i+1}",
                'bfo_class': 'BFO_0000144',  # process boundary
                'start_boundary': boundary['boundary_id'],
                'events_in_phase': []
            }
            phases.append(phase)
        
        return phases
    
    def _extract_critical_path(self, events: List[Dict[str, Any]], boundaries: List[Dict[str, Any]]) -> List[str]:
        """Extract critical path through the process."""
        # Return IDs of high-significance boundaries and decision events
        critical = []
        
        for boundary in boundaries:
            if boundary.get('ethical_significance', 0) > 0.7:
                critical.append(boundary['boundary_id'])
        
        for event in events:
            if event.get('kind') == 'decision':
                critical.append(event.get('id'))
        
        return critical
