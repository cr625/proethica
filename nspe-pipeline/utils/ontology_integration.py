"""
Ontology Integration Utilities
--------------------------
Provides utilities to integrate ontology triples with NSPE cases.

This module:
1. Adds relevant engineering world entities to cases
2. Adds McLaren's extensional definition triples
3. Provides a unified way to integrate ontologies with cases
"""

import os
import sys
import logging
import json
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import RDF_TYPE_PREDICATE

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ontology_integration")

# Import database utilities - using absolute imports for compatibility with direct module loading
import sys
import os
# Get the parent directory path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# If this module is loaded directly rather than through a package
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
from utils.database import store_entity_triples, clear_entity_triples, get_case

# Engineering ethics ontology namespace
ENG_ETHICS_NS = "http://proethica.org/engineering-ethics#"

# McLaren extensional definitions namespace
MCLAREN_EXT_NS = "http://proethica.org/mclaren-extensional-definitions#"

def integrate_ontologies_with_case(case_id):
    """
    Integrate both engineering world entities and McLaren's extensional 
    definitions with a case.
    
    Args:
        case_id: The ID of the case to integrate with
        
    Returns:
        tuple: (eng_count, mclaren_count) - The number of triples added from each ontology
    """
    # Get the case data
    case = get_case(case_id=case_id)
    if not case:
        logger.error(f"Failed to get case with ID {case_id}")
        return (0, 0)
    
    logger.info(f"Integrating ontologies with case {case_id}: {case.get('title')}")
    
    # Add engineering world entities
    eng_count = add_engineering_world_entities(case_id, case)
    
    # Add McLaren extensional definitions
    mclaren_count = add_mclaren_extensional_definitions(case_id, case)
    
    logger.info(f"Added {eng_count} engineering world triples and {mclaren_count} McLaren triples")
    
    return (eng_count, mclaren_count)

def add_engineering_world_entities(case_id, case_data):
    """
    Add relevant engineering world entities to a case.
    
    Args:
        case_id: The ID of the case
        case_data: The case data
        
    Returns:
        int: Number of triples added
    """
    logger.info(f"Adding engineering world entities to case {case_id}")
    
    triples = []
    case_uri = f"http://proethica.org/cases/{case_id}"
    
    # Add basic case typing
    triples.append({
        "subject": case_uri,
        "predicate": RDF_TYPE_PREDICATE,
        "object_uri": f"{ENG_ETHICS_NS}EngineeringEthicsCase",
        "is_literal": False,
        "graph": ENG_ETHICS_NS,
        "triple_metadata": {"source": "automatic_ontology_integration"}
    })
    
    # Analyze case content to find references to engineering world entities
    case_text = case_data.get('content', '')
    
    # List of common engineering ethics concepts to detect
    concepts = [
        # Core engineering ethics principles
        {"term": "public safety", "uri": f"{ENG_ETHICS_NS}PublicSafety"},
        {"term": "health and welfare", "uri": f"{ENG_ETHICS_NS}PublicWelfare"},
        {"term": "sustainable development", "uri": f"{ENG_ETHICS_NS}SustainableDevelopment"},
        {"term": "professional competence", "uri": f"{ENG_ETHICS_NS}ProfessionalCompetence"},
        {"term": "avoid conflict of interest", "uri": f"{ENG_ETHICS_NS}ConflictOfInterest"},
        {"term": "confidentiality", "uri": f"{ENG_ETHICS_NS}Confidentiality"},
        {"term": "honesty", "uri": f"{ENG_ETHICS_NS}Honesty"},
        {"term": "errors", "uri": f"{ENG_ETHICS_NS}ErrorHandling"},
        {"term": "licensure", "uri": f"{ENG_ETHICS_NS}LicensureRequirement"},
        
        # Professional roles
        {"term": "engineer", "uri": f"{ENG_ETHICS_NS}Engineer"},
        {"term": "client", "uri": f"{ENG_ETHICS_NS}Client"},
        {"term": "contractor", "uri": f"{ENG_ETHICS_NS}Contractor"},
        {"term": "employer", "uri": f"{ENG_ETHICS_NS}Employer"},
        {"term": "public", "uri": f"{ENG_ETHICS_NS}PublicStakeholder"},
        
        # Engineering contexts
        {"term": "design", "uri": f"{ENG_ETHICS_NS}EngineeringDesign"},
        {"term": "construction", "uri": f"{ENG_ETHICS_NS}Construction"},
        {"term": "inspection", "uri": f"{ENG_ETHICS_NS}Inspection"},
        {"term": "consulting", "uri": f"{ENG_ETHICS_NS}EngineeringConsulting"},
        {"term": "structural", "uri": f"{ENG_ETHICS_NS}StructuralEngineering"}
    ]
    
    # Special handling for case #23-4 (Acknowledging Errors in Design)
    if case_data.get('doc_metadata', {}).get('case_number') == "23-4":
        # This case is specifically about acknowledging errors in design
        triples.append({
            "subject": case_uri,
            "predicate": f"{ENG_ETHICS_NS}involvesEthicalConcept",
            "object_uri": f"{ENG_ETHICS_NS}ErrorHandling",
            "is_literal": False,
            "graph": ENG_ETHICS_NS,
            "triple_metadata": {"source": "automatic_ontology_integration", "confidence": "high"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{ENG_ETHICS_NS}involvesEthicalConcept",
            "object_uri": f"{ENG_ETHICS_NS}EngineeringDesign",
            "is_literal": False,
            "graph": ENG_ETHICS_NS,
            "triple_metadata": {"source": "automatic_ontology_integration", "confidence": "high"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{ENG_ETHICS_NS}involvesEthicalConcept",
            "object_uri": f"{ENG_ETHICS_NS}HonestyInProfessionalReporting",
            "is_literal": False,
            "graph": ENG_ETHICS_NS,
            "triple_metadata": {"source": "automatic_ontology_integration", "confidence": "high"}
        })
    else:
        # For other cases, detect concepts based on text analysis
        for concept in concepts:
            if concept["term"].lower() in case_text.lower():
                triples.append({
                    "subject": case_uri,
                    "predicate": f"{ENG_ETHICS_NS}involvesEthicalConcept",
                    "object_uri": concept["uri"],
                    "is_literal": False,
                    "graph": ENG_ETHICS_NS,
                    "triple_metadata": {"source": "automatic_ontology_integration", "confidence": "medium"}
                })
    
    # Only add the triples if we found any
    if triples:
        success = store_entity_triples(case_id, triples)
        if success:
            return len(triples)
        else:
            logger.error(f"Failed to store engineering world triples for case {case_id}")
            return 0
    else:
        logger.warning(f"No engineering world entities found for case {case_id}")
        return 0

def add_mclaren_extensional_definitions(case_id, case_data):
    """
    Add McLaren's extensional definitions to a case.
    
    Args:
        case_id: The ID of the case
        case_data: The case data
        
    Returns:
        int: Number of triples added
    """
    logger.info(f"Adding McLaren extensional definitions to case {case_id}")
    
    triples = []
    case_uri = f"http://proethica.org/cases/{case_id}"
    
    # Add basic case typing
    triples.append({
        "subject": case_uri,
        "predicate": RDF_TYPE_PREDICATE,
        "object_uri": f"{MCLAREN_EXT_NS}EthicsCase",
        "is_literal": False,
        "graph": MCLAREN_EXT_NS,
        "triple_metadata": {"source": "automatic_mclaren_integration"}
    })
    
    # Specifics for case #23-4 (Acknowledging Errors in Design)
    if case_data.get('doc_metadata', {}).get('case_number') == "23-4":
        # McLaren extensional definitions for the Acknowledging Errors case
        
        # Add the core extensional definition concepts
        triples.append({
            "subject": case_uri,
            "predicate": f"{MCLAREN_EXT_NS}hasCharacter",
            "object_uri": f"{MCLAREN_EXT_NS}ProfessionalEngineer",
            "is_literal": False,
            "graph": MCLAREN_EXT_NS,
            "triple_metadata": {"source": "mclaren_extensional_definition"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{MCLAREN_EXT_NS}involvesVirtue",
            "object_uri": f"{MCLAREN_EXT_NS}Honesty",
            "is_literal": False,
            "graph": MCLAREN_EXT_NS,
            "triple_metadata": {"source": "mclaren_extensional_definition"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{MCLAREN_EXT_NS}involvesVirtue",
            "object_uri": f"{MCLAREN_EXT_NS}Responsibility",
            "is_literal": False,
            "graph": MCLAREN_EXT_NS,
            "triple_metadata": {"source": "mclaren_extensional_definition"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{MCLAREN_EXT_NS}involvesAction",
            "object_uri": f"{MCLAREN_EXT_NS}AcknowledgingErrors",
            "is_literal": False,
            "graph": MCLAREN_EXT_NS,
            "triple_metadata": {"source": "mclaren_extensional_definition"}
        })
        
        triples.append({
            "subject": case_uri,
            "predicate": f"{MCLAREN_EXT_NS}hasEthicalOutcome",
            "object_uri": f"{MCLAREN_EXT_NS}EthicallyAdequate",
            "is_literal": False,
            "graph": MCLAREN_EXT_NS,
            "triple_metadata": {"source": "mclaren_extensional_definition"}
        })
    else:
        # For other cases, we'd need more sophisticated analysis
        # This would be a good place to use the LLM-based analysis in the future
        pass
    
    # Only add the triples if we found any
    if triples:
        success = store_entity_triples(case_id, triples)
        if success:
            return len(triples)
        else:
            logger.error(f"Failed to store McLaren triples for case {case_id}")
            return 0
    else:
        logger.warning(f"No McLaren extensional definitions applied to case {case_id}")
        return 0

def clear_ontology_triples(case_id):
    """
    Clear all ontology triples for a case.
    
    Args:
        case_id: The ID of the case
        
    Returns:
        int: Number of triples removed
    """
    logger.info(f"Clearing ontology triples for case {case_id}")
    return clear_entity_triples(case_id)


if __name__ == "__main__":
    # Test the module when run directly
    import sys
    
    if len(sys.argv) > 1:
        case_id = int(sys.argv[1])
        print(f"Integrating ontologies with case {case_id}")
        
        eng_count, mclaren_count = integrate_ontologies_with_case(case_id)
        
        print(f"Added {eng_count} engineering world triples and {mclaren_count} McLaren triples")
    else:
        print("Usage: python ontology_integration.py <case_id>")
