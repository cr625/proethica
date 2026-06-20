"""Prompt-builder shared helpers (section-type + schema builders)."""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate, SectionPromptInstance, PromptTemplateVersion, LangExtractExample, LangExtractExampleExtraction
from sqlalchemy import func, text
import requests
import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def get_ontology_section_types() -> List[Dict[str, str]]:
    """
    Get section types from the ontology via SPARQL.
    Falls back to hardcoded types if SPARQL fails.
    """
    try:
        query = "PREFIX cases: <http://proethica.org/ontology/cases#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> SELECT DISTINCT ?sectionType ?label ?definition WHERE { ?sectionType rdfs:subClassOf cases:SectionType . OPTIONAL { ?sectionType rdfs:label ?label . } OPTIONAL { ?sectionType skos:definition ?definition . } FILTER(?sectionType != cases:SectionType) } ORDER BY ?sectionType"
        
        from app.services.ontserve.ontserve_config import get_ontserve_mcp_url
        response = requests.post(
            f"{get_ontserve_mcp_url()}/sparql",
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"SPARQL response length: {len(response.text)}")
            logger.info(f"SPARQL response preview: {response.text[:500]}...")
            results = response.json()
            section_types = []
            
            for binding in results.get('results', {}).get('bindings', []):
                section_type_uri = binding['sectionType']['value']
                section_type_name = section_type_uri.split('#')[-1]
                
                section_types.append({
                    'name': section_type_name,
                    'label': binding['label']['value'],
                    'definition': binding.get('definition', {}).get('value', ''),
                    'uri': section_type_uri
                })
            
            return section_types
        
        # If SPARQL failed, fall back to hardcoded section types
        logger.warning(f"SPARQL query failed with status {response.status_code}, using fallback")
        return get_fallback_section_types()
    
    except Exception as e:
        logger.error(f"Error getting ontology section types: {e}")
        # Return hardcoded fallback section types
        return get_fallback_section_types()


def get_fallback_section_types() -> List[Dict[str, str]]:
    """
    Fallback section types when SPARQL is unavailable.
    """
    return [
        {
            'name': 'FactualSection',
            'label': 'Factual Section',
            'definition': 'Section containing factual information and background details',
            'uri': 'http://proethica.org/ontology/cases#FactualSection'
        },
        {
            'name': 'EthicalQuestionSection',
            'label': 'Ethical Question Section', 
            'definition': 'Section containing ethical questions and dilemmas',
            'uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection'
        },
        {
            'name': 'AnalysisSection',
            'label': 'Analysis Section',
            'definition': 'Section containing ethical analysis and reasoning',
            'uri': 'http://proethica.org/ontology/cases#AnalysisSection'
        },
        {
            'name': 'ConclusionSection',
            'label': 'Conclusion Section',
            'definition': 'Section containing conclusions and recommendations',
            'uri': 'http://proethica.org/ontology/cases#ConclusionSection'
        }
    ]


def get_domain_specific_section_types(domain_name: str) -> List[Dict[str, str]]:
    """
    Get section types specific to a domain, including domain-specific extensions.
    """
    # Start with generic section types
    section_types = get_ontology_section_types()
    
    # Add domain-specific logic here
    if domain_name.lower() == 'engineering':
        # Engineering might have additional section types
        section_types.extend([
            {
                'name': 'CodeReferenceSection',
                'label': 'Code Reference Section',
                'definition': 'References to engineering codes and standards',
                'uri': 'http://proethica.org/ontology/cases#CodeReferenceSection'
            },
            {
                'name': 'SafetyAnalysisSection', 
                'label': 'Safety Analysis Section',
                'definition': 'Analysis of safety implications and risk factors',
                'uri': 'http://proethica.org/ontology/cases#SafetyAnalysisSection'
            }
        ])
    
    return section_types




def get_extraction_class_schemas() -> Dict[str, Any]:
    """
    Get schemas for different extraction classes to help with example creation.
    """
    return {
        'factual_analysis': {
            'extraction_text_options': ['structured_facts', 'key_information', 'factual_content'],
            'attribute_schema': {
                'key_agents': {'type': 'array', 'description': 'People involved with their roles and credentials'},
                'key_entities': {'type': 'array', 'description': 'Important entities, organizations, or objects'},
                'technical_details': {'type': 'array', 'description': 'Technical specifications or requirements'},
                'contextual_factors': {'type': 'array', 'description': 'Environmental or situational factors'}
            }
        },
        'ethical_question': {
            'extraction_text_options': ['ethical_concerns', 'questions_identified', 'ethical_issues'],
            'attribute_schema': {
                'primary_questions': {'type': 'array', 'description': 'Main ethical questions raised'},
                'underlying_concerns': {'type': 'array', 'description': 'Deeper ethical concerns'},
                'stakeholders_affected': {'type': 'array', 'description': 'Who is impacted by these questions'}
            }
        },
        'ethical_analysis': {
            'extraction_text_options': ['ethical_reasoning', 'analysis_content', 'ethical_evaluation'],
            'attribute_schema': {
                'central_principles': {'type': 'array', 'description': 'Key ethical principles involved'},
                'stakeholder_impacts': {'type': 'array', 'description': 'How different stakeholders are affected'},
                'ethical_tensions': {'type': 'array', 'description': 'Conflicts between ethical principles'}
            }
        }
    }


def get_template_variable_schemas() -> Dict[str, Any]:
    """
    Get common template variable schemas for autocomplete and validation.
    """
    return {
        'case_domain': {
            'type': 'string',
            'description': 'Professional domain context (e.g., engineering, medical)',
            'examples': ['engineering', 'medical', 'legal', 'business']
        },
        'stakeholder_types': {
            'type': 'array',
            'description': 'Types of stakeholders relevant to the domain',
            'examples': ['engineers', 'public', 'clients', 'regulators']
        },
        'professional_codes': {
            'type': 'array', 
            'description': 'Relevant professional codes of ethics',
            'examples': ['NSPE Code', 'IEEE Code', 'AMA Code']
        },
        'regulatory_context': {
            'type': 'string',
            'description': 'Applicable regulations and oversight bodies',
            'examples': ['OSHA compliance', 'EPA regulations', 'FDA approval']
        },
        'safety_considerations': {
            'type': 'array',
            'description': 'Key safety factors and public welfare concerns',
            'examples': ['public safety', 'environmental impact', 'product safety']
        }
    }
