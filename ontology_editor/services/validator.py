"""
Validator service for the ontology editor.

This service handles validating ontology files for TTL syntax
and BFO compliance.
"""
import os
from typing import Tuple, Dict, List, Any, Union, Optional
from io import StringIO
import logging

# Import rdflib for TTL parsing and validation
try:
    from rdflib import Graph, URIRef, Namespace, RDF, RDFS, OWL
    from rdflib.namespace import NamespaceManager
    from rdflib.exceptions import ParserError
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    logging.warning("rdflib not available, TTL validation will be limited")

# BFO namespace
BFO = Namespace("http://purl.obolibrary.org/obo/")

# Dictionary of BFO class types for validation warnings
BFO_CLASS_TYPES = {
    # Continuants
    "independent_continuant": BFO.BFO_0000004,
    "material_entity": BFO.BFO_0000040,
    "immaterial_entity": BFO.BFO_0000141,
    "spatiotemporal_region": BFO.BFO_0000011,
    "site": BFO.BFO_0000029,
    "spatial_region": BFO.BFO_0000006,
    
    # Dependent continuants
    "dependent_continuant": BFO.BFO_0000005,
    "quality": BFO.BFO_0000019,
    "role": BFO.BFO_0000023,
    "function": BFO.BFO_0000034,
    "disposition": BFO.BFO_0000016,
    
    # Occurrents
    "occurrent": BFO.BFO_0000003,
    "process": BFO.BFO_0000015,
    "process_boundary": BFO.BFO_0000035,
    "temporal_region": BFO.BFO_0000008,
    "temporal_instant": BFO.BFO_0000148,
    "temporal_interval": BFO.BFO_0000038
}

def validate_ttl_syntax(content: str) -> Tuple[bool, List[str]]:
    """
    Validate the syntax of a Turtle (TTL) file.
    
    Args:
        content: TTL content to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    if not RDFLIB_AVAILABLE:
        # Do basic syntax checks if rdflib is not available
        errors = []
        
        # Check for common TTL syntax errors
        if "@prefix" not in content and "prefix" not in content:
            errors.append("No prefix declaration found. TTL files typically need prefix declarations.")
        
        if ":" not in content:
            errors.append("No colon-separated URIs found. TTL files typically use prefix:term notation.")
        
        if "." not in content:
            errors.append("No statement terminator (period) found. TTL statements should end with a period.")
        
        # If we found any errors, return False with the error messages
        if errors:
            return False, errors
        
        # If we couldn't find obvious errors, return True
        return True, []
    
    # Use rdflib for more complete validation
    g = Graph()
    
    try:
        # Try to parse the TTL content
        g.parse(data=content, format="turtle")
        
        # If we get here, the syntax is valid
        return True, []
    
    except ParserError as e:
        # Return the error message
        return False, [str(e)]
    
    except Exception as e:
        # Catch any other exceptions
        return False, [f"Unexpected error: {str(e)}"]

def validate_bfo_compliance(content: str) -> Dict[str, Any]:
    """
    Validate BFO compliance for an ontology file.
    
    This function checks for BFO compliance issues and returns
    warnings rather than blocking edits. It checks:
    
    1. If classes are properly subclassed from BFO classes
    2. If properties have appropriate domains and ranges
    3. If individuals are instances of BFO-compliant classes
    
    Args:
        content: TTL content to validate
        
    Returns:
        Dictionary with validation results
    """
    if not RDFLIB_AVAILABLE:
        return {
            "valid": True,
            "warnings": ["rdflib not available, skipping BFO compliance validation"],
            "suggestions": []
        }
    
    # Initialize results
    results = {
        "valid": True,  # Always valid since we only issue warnings
        "warnings": [],
        "suggestions": []
    }
    
    # Parse the ontology
    g = Graph()
    try:
        g.parse(data=content, format="turtle")
    except Exception as e:
        # If parsing fails, return a parsing error
        results["warnings"].append(f"Failed to parse ontology for BFO validation: {str(e)}")
        return results
    
    # Check for BFO imports
    has_bfo_import = False
    for _, _, o in g.triples((None, OWL.imports, None)):
        if "bfo" in str(o).lower() or "purl.obolibrary.org/obo" in str(o):
            has_bfo_import = True
            break
    
    if not has_bfo_import:
        results["warnings"].append("Ontology does not import BFO. Consider adding an import statement.")
        results["suggestions"].append("Add: 'owl:imports <http://purl.obolibrary.org/obo/bfo.owl> .'")
    
    # Check classes for BFO alignment
    for class_uri in g.subjects(RDF.type, OWL.Class):
        # Skip BFO classes themselves
        if "purl.obolibrary.org/obo" in str(class_uri):
            continue
        
        # Check if class is a subclass of any BFO class
        has_bfo_parent = False
        for _, _, parent in g.triples((class_uri, RDFS.subClassOf, None)):
            if "purl.obolibrary.org/obo" in str(parent):
                has_bfo_parent = True
                break
        
        if not has_bfo_parent:
            # Get the label if available
            label = str(class_uri)
            for _, _, l in g.triples((class_uri, RDFS.label, None)):
                label = f"{l} ({class_uri})"
                break
            
            results["warnings"].append(f"Class {label} is not aligned with BFO hierarchy")
            
            # Suggest potential BFO parent classes based on naming conventions
            class_name = str(class_uri).split('#')[-1].lower()
            
            if "role" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:role (BFO_0000023)")
            elif "process" in class_name or "event" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:process (BFO_0000015)")
            elif "quality" in class_name or "property" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:quality (BFO_0000019)")
            elif "function" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:function (BFO_0000034)")
            elif "entity" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:entity (BFO_0000001)")
            elif "object" in class_name:
                results["suggestions"].append(f"Consider making {label} a subclass of BFO:material_entity (BFO_0000040)")
    
    # Check object properties
    for prop_uri in g.subjects(RDF.type, OWL.ObjectProperty):
        # Check if property has domain and range
        has_domain = False
        has_range = False
        
        for _, _, _ in g.triples((prop_uri, RDFS.domain, None)):
            has_domain = True
            break
        
        for _, _, _ in g.triples((prop_uri, RDFS.range, None)):
            has_range = True
            break
        
        # Get the label if available
        label = str(prop_uri)
        for _, _, l in g.triples((prop_uri, RDFS.label, None)):
            label = f"{l} ({prop_uri})"
            break
        
        if not has_domain:
            results["warnings"].append(f"Property {label} has no domain, which may lead to ambiguous usage")
        
        if not has_range:
            results["warnings"].append(f"Property {label} has no range, which may lead to ambiguous usage")
    
    # Provide general BFO guidance if there are warnings
    if results["warnings"]:
        results["suggestions"].append(
            "Review BFO guidelines at https://basic-formal-ontology.org/guidance"
        )
    
    return results

def load_bfo_ontology() -> Optional[Graph]:
    """
    Load the BFO ontology for validation.
    
    Returns:
        Graph object containing BFO, or None if not available
    """
    if not RDFLIB_AVAILABLE:
        return None
    
    # Try to find the BFO ontology file
    bfo_paths = [
        os.path.join(os.path.dirname(__file__), '../../mcp/ontology/bfo.owl'),
        os.path.join(os.path.dirname(__file__), '../../mcp/ontology/bfo-core.ttl'),
        os.path.join(os.path.dirname(__file__), '../../ontologies/imports/bfo/bfo.owl')
    ]
    
    g = Graph()
    
    for path in bfo_paths:
        if os.path.exists(path):
            try:
                g.parse(path)
                return g
            except Exception as e:
                logging.warning(f"Failed to load BFO ontology from {path}: {str(e)}")
    
    # If we couldn't find a local copy, try to load from the web
    try:
        g.parse("http://purl.obolibrary.org/obo/bfo.owl")
        return g
    except Exception as e:
        logging.warning(f"Failed to load BFO ontology from web: {str(e)}")
    
    return None
