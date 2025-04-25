"""
Ontology validator service.

This module provides functionality to validate ontology files
using RDFLib and other validation methods.
"""

import re
from typing import Dict, Any
from rdflib import Graph
from rdflib.exceptions import ParserError

def validate_ontology(content: str) -> Dict[str, Any]:
    """
    Validate an ontology file.
    
    Args:
        content: Content of the ontology file to validate
        
    Returns:
        Validation results dictionary with keys:
        - is_valid: Boolean indicating if the ontology is valid
        - errors: List of error messages if any
        - warnings: List of warning messages if any
    """
    results = {
        'is_valid': False,
        'errors': [],
        'warnings': []
    }
    
    # Basic content checks
    if not content or not content.strip():
        results['errors'].append('Ontology content is empty')
        return results
    
    # Check for required namespaces
    required_namespaces = [
        '@prefix rdfs:',
        '@prefix rdf:',
        '@prefix owl:'
    ]
    
    for namespace in required_namespaces:
        if namespace not in content:
            results['warnings'].append(f'Missing recommended namespace: {namespace}')
    
    # Check for syntax errors using RDFLib
    g = Graph()
    try:
        g.parse(data=content, format='turtle')
    except ParserError as e:
        # Extract the error message
        error_message = str(e)
        
        # Try to extract line number from error message
        line_match = re.search(r'line (\d+)', error_message)
        if line_match:
            line_number = line_match.group(1)
            results['errors'].append(f'Syntax error at line {line_number}: {error_message}')
        else:
            results['errors'].append(f'Syntax error: {error_message}')
        
        return results
    except Exception as e:
        results['errors'].append(f'Error parsing ontology: {str(e)}')
        return results
    
    # If we made it this far, the ontology is valid
    results['is_valid'] = True
    
    # Additional checks could be added here
    # For example, checking for recommended classes, properties, etc.
    
    return results
