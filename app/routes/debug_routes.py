"""
Debug routes for development.
"""
from flask import Blueprint, jsonify
import sys

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/test-triple-preview', methods=['GET'])
def test_triple_preview():
    """
    Test route to verify the triple preview functionality.
    """
    # Generate sample triples for testing
    sample_triples = [
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            "predicate_label": "type",
            "object": "http://proethica.org/engineering-ethics/principle",
            "object_label": "Principle",
            "is_literal": False
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
            "predicate_label": "label",
            "object": "Safety Critical Design",
            "is_literal": True
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://purl.org/dc/elements/1.1/description",
            "predicate_label": "description",
            "object": "The practice of ensuring safety in systems where failure could cause serious harm",
            "is_literal": True
        }
    ]
    
    # Return platform info and triples
    return jsonify({
        "status": "success",
        "message": "Triple preview test route is functioning",
        "python_version": sys.version,
        "sample_triples": sample_triples,
        "triple_count": len(sample_triples)
    })
