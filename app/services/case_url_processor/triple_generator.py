"""
Triple generator for the Case URL Processor.

This module provides functionality for generating RDF triples from
extracted case data to be stored in the database.
"""

import logging
import re
from typing import Dict, List, Any, Optional
import os
import json

# Set up logging
logger = logging.getLogger(__name__)

class TripleGenerator:
    """
    Generator for RDF triples from case data.
    """
    
    def __init__(self, concept_mappings_path=None):
        """
        Initialize the triple generator.
        
        Args:
            concept_mappings_path: Path to concept mappings file (optional)
        """
        self.concept_mappings = self._load_concept_mappings(concept_mappings_path)
    
    def _load_concept_mappings(self, path=None):
        """
        Load concept mappings from a file if provided, otherwise use defaults.
        
        Args:
            path: Path to concept mappings file (optional)
            
        Returns:
            Dictionary of concept mappings
        """
        # Start with default mappings
        default_mappings = {
            "EthicalPrinciple": {
                "public safety": "http://proethica.org/onto/ethics/PublicSafety",
                "safety": "http://proethica.org/onto/ethics/PublicSafety",
                "public health": "http://proethica.org/onto/ethics/PublicHealth",
                "health": "http://proethica.org/onto/ethics/PublicHealth",
                "welfare": "http://proethica.org/onto/ethics/PublicWelfare",
                "confidentiality": "http://proethica.org/onto/ethics/Confidentiality",
                "competency": "http://proethica.org/onto/ethics/ProfessionalCompetence",
                "competence": "http://proethica.org/onto/ethics/ProfessionalCompetence",
                "honesty": "http://proethica.org/onto/ethics/HonestyAndIntegrity",
                "integrity": "http://proethica.org/onto/ethics/HonestyAndIntegrity",
                "professional responsibility": "http://proethica.org/onto/ethics/ProfessionalResponsibility",
                "objectivity": "http://proethica.org/onto/ethics/Objectivity",
                "disclosure": "http://proethica.org/onto/ethics/Disclosure",
                "conflict of interest": "http://proethica.org/onto/ethics/ConflictOfInterest"
            },
            "EngineeringDiscipline": {
                "civil engineering": "http://proethica.org/onto/eng/CivilEngineering",
                "mechanical engineering": "http://proethica.org/onto/eng/MechanicalEngineering",
                "electrical engineering": "http://proethica.org/onto/eng/ElectricalEngineering",
                "environmental engineering": "http://proethica.org/onto/eng/EnvironmentalEngineering",
                "structural engineering": "http://proethica.org/onto/eng/StructuralEngineering"
            },
            "EngineeringRole": {
                "contractor": "http://proethica.org/onto/eng/ContractorRole",
                "consultant": "http://proethica.org/onto/eng/ConsultantRole",
                "city engineer": "http://proethica.org/onto/eng/CityEngineerRole",
                "peer reviewer": "http://proethica.org/onto/eng/PeerReviewerRole",
                "design engineer": "http://proethica.org/onto/eng/DesignEngineerRole",
                "project engineer": "http://proethica.org/onto/eng/ProjectEngineerRole"
            }
        }
        
        # If path is provided, try to load mappings from file
        if path and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    file_mappings = json.load(f)
                
                # Merge with defaults (file mappings take precedence)
                for category, mappings in file_mappings.items():
                    if category in default_mappings:
                        default_mappings[category].update(mappings)
                    else:
                        default_mappings[category] = mappings
                
                logger.info(f"Loaded concept mappings from {path}")
            except Exception as e:
                logger.error(f"Error loading concept mappings from {path}: {str(e)}")
        
        return default_mappings
    
    def generate_triples(self, case_data, world_id=None):
        """
        Generate RDF triples from case data.
        
        Args:
            case_data: Dictionary of case data
            world_id: ID of the world (optional)
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Skip if no data
        if not case_data:
            logger.warning("No case data provided to generate triples")
            return triples
        
        # Get case identifier
        case_uri = self._generate_case_uri(case_data)
        
        # Add basic case metadata triples
        triples.extend(self._generate_basic_triples(case_uri, case_data))
        
        # Add ethical principles
        triples.extend(self._generate_ethical_principle_triples(case_uri, case_data))
        
        # Add engineering disciplines
        triples.extend(self._generate_discipline_triples(case_uri, case_data))
        
        # Add involved parties if available
        triples.extend(self._generate_involved_party_triples(case_uri, case_data))
        
        # Add explicit potential triples if available
        triples.extend(self._process_potential_triples(case_uri, case_data))
        
        return triples
    
    def _generate_case_uri(self, case_data):
        """
        Generate URI for the case.
        
        Args:
            case_data: Dictionary of case data
            
        Returns:
            URI string
        """
        # Use case number if available
        if case_data.get('case_number'):
            # Clean case number to be URI-friendly
            case_id = case_data['case_number'].replace(' ', '_').replace('-', '_')
            return f"http://proethica.org/case/{case_id}"
        
        # Otherwise, use title
        if case_data.get('title'):
            # Clean title to be URI-friendly
            case_id = re.sub(r'[^a-zA-Z0-9]', '_', case_data['title'])
            case_id = re.sub(r'_+', '_', case_id)  # Replace multiple underscores with one
            return f"http://proethica.org/case/{case_id}"
        
        # If neither is available, use a generic identifier
        return "http://proethica.org/case/unnamed_case"
    
    def _generate_basic_triples(self, case_uri, case_data):
        """
        Generate basic metadata triples.
        
        Args:
            case_uri: URI of the case
            case_data: Dictionary of case data
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Add case type triple
        triples.append({
            "subject": case_uri,
            "predicate": "rdf:type",
            "object": "proethica:EngineeringEthicsCase",
            "is_literal": False
        })
        
        # Add title triple if available
        if case_data.get('title'):
            triples.append({
                "subject": case_uri,
                "predicate": "dc:title",
                "object": case_data['title'],
                "is_literal": True
            })
        
        # Add case number if available
        if case_data.get('case_number'):
            triples.append({
                "subject": case_uri,
                "predicate": "proethica:caseNumber",
                "object": case_data['case_number'],
                "is_literal": True
            })
        
        # Add year if available
        if case_data.get('year'):
            triples.append({
                "subject": case_uri,
                "predicate": "proethica:year",
                "object": str(case_data['year']),
                "is_literal": True
            })
        
        # Add summary if available
        if case_data.get('summary'):
            triples.append({
                "subject": case_uri,
                "predicate": "dc:description",
                "object": case_data['summary'],
                "is_literal": True
            })
        
        # Add URL if available
        if case_data.get('url'):
            triples.append({
                "subject": case_uri,
                "predicate": "dc:source",
                "object": case_data['url'],
                "is_literal": True
            })
        
        # Add outcome if available
        if case_data.get('outcome'):
            triples.append({
                "subject": case_uri,
                "predicate": "proethica:outcome",
                "object": case_data['outcome'],
                "is_literal": True
            })
        
        # Add ethical questions if available
        if case_data.get('ethical_questions'):
            for i, question in enumerate(case_data['ethical_questions']):
                triples.append({
                    "subject": case_uri,
                    "predicate": "proethica:raisesQuestion",
                    "object": question,
                    "is_literal": True
                })
        
        return triples
    
    def _generate_ethical_principle_triples(self, case_uri, case_data):
        """
        Generate triples for ethical principles.
        
        Args:
            case_uri: URI of the case
            case_data: Dictionary of case data
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Skip if no principles
        if not case_data.get('ethical_principles') and not case_data.get('principles'):
            return triples
        
        # Get principles from either field name
        principles = case_data.get('ethical_principles', []) or case_data.get('principles', [])
        
        # Ensure it's a list
        if isinstance(principles, str):
            principles = [principles]
        
        for principle in principles:
            # Map to known concept if possible
            concept_uri = self._map_to_concept(principle, "EthicalPrinciple")
            
            triples.append({
                "subject": case_uri,
                "predicate": "proethica:involvesEthicalPrinciple",
                "object": concept_uri,
                "is_literal": False
            })
        
        return triples
    
    def _generate_discipline_triples(self, case_uri, case_data):
        """
        Generate triples for engineering disciplines.
        
        Args:
            case_uri: URI of the case
            case_data: Dictionary of case data
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Skip if no disciplines
        if not case_data.get('engineering_disciplines'):
            return triples
        
        disciplines = case_data.get('engineering_disciplines', [])
        
        # Ensure it's a list
        if isinstance(disciplines, str):
            disciplines = [disciplines]
        
        for discipline in disciplines:
            # Map to known concept if possible
            concept_uri = self._map_to_concept(discipline, "EngineeringDiscipline")
            
            triples.append({
                "subject": case_uri,
                "predicate": "proethica:involvesEngineeringDiscipline",
                "object": concept_uri,
                "is_literal": False
            })
        
        return triples
    
    def _generate_involved_party_triples(self, case_uri, case_data):
        """
        Generate triples for involved parties.
        
        Args:
            case_uri: URI of the case
            case_data: Dictionary of case data
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Skip if no involved parties
        if not case_data.get('involved_parties'):
            return triples
        
        involved_parties = case_data.get('involved_parties', [])
        
        # Ensure it's a list
        if isinstance(involved_parties, str):
            involved_parties = [involved_parties]
        
        for party in involved_parties:
            # Check if this party matches an engineering role
            role_uri = self._map_to_concept(party, "EngineeringRole")
            
            if "http://proethica.org/onto/eng/" in role_uri:
                # This is a recognized role
                triples.append({
                    "subject": case_uri,
                    "predicate": "proethica:involvesRole",
                    "object": role_uri,
                    "is_literal": False
                })
            else:
                # Just a generic party
                triples.append({
                    "subject": case_uri,
                    "predicate": "proethica:involvesParty",
                    "object": party,
                    "is_literal": True
                })
        
        return triples
    
    def _process_potential_triples(self, case_uri, case_data):
        """
        Process and format potential triples identified by LLM.
        
        Args:
            case_uri: URI of the case
            case_data: Dictionary of case data
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        
        # Skip if no potential triples
        if not case_data.get('potential_triples'):
            return triples
        
        potential_triples = case_data.get('potential_triples', [])
        
        # Parse potential triples in various formats
        if isinstance(potential_triples, list):
            for triple_item in potential_triples:
                if isinstance(triple_item, list) and len(triple_item) == 3:
                    # Format: [subject, predicate, object]
                    subject, predicate, obj = triple_item
                    
                    # Create namespace prefixed predicate if it's a simple name
                    if ':' not in predicate:
                        predicate = f"proethica:{predicate}"
                    
                    # Determine if object is a literal or URI
                    is_literal = not (obj.startswith('http://') or ':' in obj or obj.startswith('<'))
                    
                    triples.append({
                        "subject": case_uri if subject in ['case', 'this', 'this case'] else subject,
                        "predicate": predicate,
                        "object": obj,
                        "is_literal": is_literal
                    })
                elif isinstance(triple_item, str):
                    # Try to parse string format like "Subject - Predicate - Object"
                    parts = re.split(r'\s*-\s*|\s*,\s*|\s+>', triple_item)
                    if len(parts) >= 3:
                        subject, predicate = parts[0], parts[1]
                        obj = ' - '.join(parts[2:])  # Join the rest in case object has hyphens
                        
                        # Create namespace prefixed predicate if it's a simple name
                        if ':' not in predicate:
                            predicate = f"proethica:{predicate}"
                        
                        # Determine if object is a literal or URI
                        is_literal = not (obj.startswith('http://') or ':' in obj or obj.startswith('<'))
                        
                        triples.append({
                            "subject": case_uri if subject in ['case', 'this', 'this case'] else subject,
                            "predicate": predicate,
                            "object": obj,
                            "is_literal": is_literal
                        })
        
        return triples
    
    def _map_to_concept(self, text, concept_type):
        """
        Map extracted text to a known ontology concept.
        
        Args:
            text: The text to map
            concept_type: Type of concept to map to
            
        Returns:
            URI for the concept
        """
        if concept_type not in self.concept_mappings:
            # Default to a custom URI based on the text
            return self._create_custom_uri(text, concept_type)
        
        # Convert text to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # First try exact match
        for concept, uri in self.concept_mappings[concept_type].items():
            if concept.lower() == text_lower:
                return uri
        
        # Then try contained matches
        for concept, uri in self.concept_mappings[concept_type].items():
            if concept.lower() in text_lower or text_lower in concept.lower():
                return uri
        
        # If no match, create a custom URI
        return self._create_custom_uri(text, concept_type)
    
    def _create_custom_uri(self, text, concept_type):
        """
        Create a custom URI for a concept.
        
        Args:
            text: The text to create a URI for
            concept_type: Type of concept
            
        Returns:
            Custom URI
        """
        # Clean text to be URI-friendly
        uri_text = re.sub(r'[^a-zA-Z0-9]', '_', text)
        uri_text = re.sub(r'_+', '_', uri_text)  # Replace multiple underscores with one
        
        # Create URI in the appropriate namespace
        if concept_type == "EthicalPrinciple":
            return f"http://proethica.org/onto/ethics/{uri_text}"
        elif concept_type == "EngineeringDiscipline":
            return f"http://proethica.org/onto/eng/{uri_text}"
        elif concept_type == "EngineeringRole":
            return f"http://proethica.org/onto/eng/{uri_text}Role"
        else:
            return f"http://proethica.org/onto/generic/{uri_text}"
