#!/usr/bin/env python3
"""
Populate the database with existing LangExtract examples from the hardcoded service.

This script extracts examples from the OntologyDrivenLangExtractService and 
stores them in the database for management through the prompt builder.
"""

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import psycopg2
from psycopg2.extras import Json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_example_data():
    """Extract example data from the hardcoded service methods."""
    
    examples = []
    
    # Factual examples
    examples.append({
        'example_type': 'factual',
        'domain': 'engineering_ethics',
        'section_type': 'FactualSection',
        'name': 'Engineering Structural Analysis Case',
        'description': 'Example of factual section analysis for engineering ethics case involving structural modifications',
        'example_text': 'Engineer Smith, a licensed professional engineer with 15 years of experience, was approached by Client Corp to review structural modifications for a 10-story office building constructed in 1985. The proposed changes would remove two load-bearing columns to create an open floor plan. The building currently houses 200 employees daily.',
        'extractions': [{
            'extraction_class': 'factual_analysis',
            'extraction_text': 'structured_facts',
            'attributes': {
                "key_agents": [
                    {"name": "Engineer Smith", "credentials": "licensed professional engineer", "experience": "15 years"}
                ],
                "key_entities": [
                    {"entity": "Client Corp", "role": "client"},
                    {"entity": "10-story office building", "details": "constructed in 1985, houses 200 employees"}
                ],
                "technical_details": [
                    {"detail": "structural modifications", "specifics": "remove two load-bearing columns"},
                    {"detail": "purpose", "specifics": "create open floor plan"}
                ],
                "contextual_factors": [
                    {"factor": "building_occupancy", "value": "200 employees daily"},
                    {"factor": "building_age", "value": "constructed in 1985"}
                ]
            },
            'order_index': 0
        }]
    })
    
    # Question examples  
    examples.append({
        'example_type': 'question',
        'domain': 'engineering_ethics',
        'section_type': 'EthicalQuestionSection',
        'name': 'Engineering Ethics Questions Case',
        'description': 'Example of ethical question identification for engineering cases',
        'example_text': 'Was it ethical for Engineer Smith to proceed with the structural analysis without first conducting a thorough site inspection? Should the engineer have disclosed potential conflicts of interest given that Client Corp had previously hired Smith\'s firm for unrelated projects?',
        'extractions': [{
            'extraction_class': 'ethical_question',
            'extraction_text': 'ethical_concerns',
            'attributes': {
                "primary_questions": [
                    {
                        "question": "Was it ethical to proceed without site inspection?",
                        "ethical_principle": "professional competence",
                        "stakeholders": ["Engineer Smith", "building occupants", "Client Corp"]
                    },
                    {
                        "question": "Should conflicts of interest be disclosed?",
                        "ethical_principle": "honesty and integrity",
                        "stakeholders": ["Engineer Smith", "Client Corp"]
                    }
                ],
                "underlying_concerns": [
                    {"concern": "public safety", "severity": "high"},
                    {"concern": "professional standards", "severity": "medium"},
                    {"concern": "transparency", "severity": "medium"}
                ]
            },
            'order_index': 0
        }]
    })
    
    # Analysis examples
    examples.append({
        'example_type': 'analysis',
        'domain': 'engineering_ethics',
        'section_type': 'AnalysisSection',
        'name': 'Engineering Ethics Analysis Case',
        'description': 'Example of ethical analysis section for engineering cases',
        'example_text': 'The fundamental issue centers on Engineer Smith\'s professional obligation to prioritize public safety. The NSPE Code of Ethics explicitly states that engineers must "hold paramount the safety, health, and welfare of the public." By proceeding without adequate site inspection, Smith potentially compromised this primary duty. Furthermore, the failure to disclose previous business relationships with Client Corp raises questions about professional objectivity and transparency.',
        'extractions': [{
            'extraction_class': 'ethical_analysis',
            'extraction_text': 'ethical_reasoning',
            'attributes': {
                "central_principles": [
                    {
                        "principle": "public safety paramount",
                        "source": "NSPE Code of Ethics",
                        "application": "duty to conduct thorough site inspection"
                    },
                    {
                        "principle": "professional objectivity",
                        "source": "engineering standards",
                        "application": "disclosure of prior business relationships"
                    }
                ],
                "stakeholder_impacts": [
                    {
                        "stakeholder": "building occupants",
                        "impact": "potential safety risk from inadequate structural analysis"
                    },
                    {
                        "stakeholder": "Client Corp",
                        "impact": "may receive substandard professional service"
                    }
                ],
                "ethical_tensions": [
                    {
                        "tension": "efficiency vs thoroughness",
                        "description": "pressure to complete analysis quickly vs duty to be thorough"
                    }
                ]
            },
            'order_index': 0
        }]
    })
    
    return examples

def populate_database():
    """Populate the database with example data."""
    try:
        # Database connection
        conn = psycopg2.connect(
            host="localhost",
            database="ai_ethical_dm",
            user="postgres",
            password="PASS"
        )
        cur = conn.cursor()
        
        examples = get_example_data()
        
        logger.info(f"Populating database with {len(examples)} examples...")
        
        for example in examples:
            # Insert the example
            cur.execute("""
                INSERT INTO langextract_examples 
                (example_type, domain, section_type, name, description, example_text, active, priority, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                example['example_type'],
                example['domain'], 
                example['section_type'],
                example['name'],
                example['description'],
                example['example_text'],
                True,  # active
                1,     # priority
                'system_seed'  # created_by
            ))
            
            example_id = cur.fetchone()[0]
            logger.info(f"Created example '{example['name']}' with ID {example_id}")
            
            # Insert extractions
            for extraction in example['extractions']:
                cur.execute("""
                    INSERT INTO langextract_example_extractions
                    (example_id, extraction_class, extraction_text, attributes, order_index)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    example_id,
                    extraction['extraction_class'],
                    extraction['extraction_text'],
                    Json(extraction['attributes']),
                    extraction['order_index']
                ))
                
                logger.info(f"  - Added extraction: {extraction['extraction_class']}")
        
        conn.commit()
        
        # Verify results
        cur.execute("SELECT COUNT(*) FROM langextract_examples")
        example_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM langextract_example_extractions")  
        extraction_count = cur.fetchone()[0]
        
        logger.info(f"Successfully populated database:")
        logger.info(f"  - {example_count} examples")
        logger.info(f"  - {extraction_count} extractions")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error populating database: {str(e)}")
        return False

if __name__ == "__main__":
    success = populate_database()
    if success:
        print("Database populated successfully with LangExtract examples!")
        sys.exit(0)
    else:
        print("Failed to populate database")
        sys.exit(1)