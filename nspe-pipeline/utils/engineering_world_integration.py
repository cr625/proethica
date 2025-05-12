#!/usr/bin/env python3
"""
Engineering World Ontology Integration Module
--------------------------------------------
This module provides functions to integrate NSPE cases with the engineering world ontology,
creating proper RDF triples with subject-predicate-object structure that correctly represent
the engineering ethical concepts in the case.
"""

import os
import sys
import logging
import psycopg2
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("engineering_world_integration")

# Path adjustment to import from parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import database utility
from utils.database import get_db_connection, get_case

# Engineering ethics ontology namespace
ENGINEERING_ETHICS_NS = "http://proethica.org/ontology/engineering-ethics#"

def get_case_properties(case_id: int) -> Dict[str, Any]:
    """
    Retrieve case properties from the database
    
    Args:
        case_id (int): The ID of the case
        
    Returns:
        Dict[str, Any]: Case properties
    """
    try:
        # Make db connection directly as get_db_connection may not use the right settings
        conn = psycopg2.connect(
            host="localhost",
            database="ai_ethical_dm",
            user="postgres",
            password="PASS",
            port=5433
        )
        cursor = conn.cursor()
        
        # Query the documents table instead of entities
        cursor.execute("""
            SELECT id, title, 'document' as entity_type 
            FROM documents
            WHERE id = %s
        """, (case_id,))
        
        case = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if case:
            return {
                'id': case[0],
                'title': case[1],
                'entity_type': case[2]
            }
        
        return {}
    except Exception as e:
        logger.error(f"Error retrieving case properties: {e}")
        return {}

def identify_engineering_concepts(case_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Identify engineering concepts from case data based on content analysis
    
    Args:
        case_data (Dict): Case data including title, content sections, etc.
        
    Returns:
        Dict: Dictionary of identified concepts grouped by category
    """
    # Initialize empty concept categories
    concepts = {
        'roles': [],
        'actions': [],
        'conditions': [],
        'dilemmas': [],
        'principles': []
    }
    
    # Extract key text for analysis
    title = case_data.get('title', '')
    content = []
    for section in case_data.get('sections', {}).values():
        content.append(section.get('content', ''))
    full_content = ' '.join(content).lower()
    
    # Identify roles based on keywords
    role_keywords = {
        'StructuralEngineerRole': ['structural engineer', 'structural design', 'structures'],
        'ConsultingEngineerRole': ['consulting', 'consultant', 'consultancy'],
        'ProjectEngineerRole': ['project engineer', 'project management'],
        'ElectricalEngineerRole': ['electrical engineer', 'electrical system'],
        'MechanicalEngineerRole': ['mechanical engineer', 'mechanical system'],
        'InspectionEngineerRole': ['inspection', 'inspector'],
        'ClientRole': ['client', 'employer'],
        'RegulatoryOfficialRole': ['regulatory', 'regulator', 'official']
    }
    
    # Identify actions based on keywords
    action_keywords = {
        'DesignAction': ['design', 'designing', 'redesign'],
        'ReviewAction': ['review', 'assessment', 'evaluate'],
        'ConsultationAction': ['consult', 'advise', 'counsel'],
        'ReportAction': ['report', 'document', 'reporting'],
        'ApprovalAction': ['approve', 'approve', 'sign off'],
        'DesignRevisionAction': ['revise', 'modify', 'update design'],
        'HazardReportingAction': ['report hazard', 'safety report']
    }
    
    # Identify conditions based on keywords
    condition_keywords = {
        'SafetyHazard': ['hazard', 'danger', 'unsafe', 'safety risk'],
        'StructuralDeficiency': ['structural defect', 'deficiency', 'structural failure'],
        'ElectricalSystemDeficiency': ['electrical defect', 'wiring issue'],
        'MechanicalSystemDeficiency': ['mechanical defect', 'mechanical issue'],
        'BuildingSystemDeficiency': ['building defect', 'construction defect'],
        'ConflictOfInterestCondition': ['conflict of interest', 'competing interest']
    }
    
    # Identify dilemmas based on keywords
    dilemma_keywords = {
        'EngineeringEthicalDilemma': ['ethical dilemma', 'ethical issue', 'ethical question', 'ethics'],
        'ConfidentialityVsSafetyDilemma': ['confidentiality', 'confidential information', 'disclose', 'disclosure'],
        'ProfessionalResponsibilityDilemma': ['professional responsibility', 'duty', 'obligation'],
        'CompetenceVsClientWishesDilemma': ['competence', 'qualification', 'client wishes'],
        'QualityVsBudgetDilemma': ['quality', 'budget', 'cost'],
        'RegulationVsPublicSafetyDilemma': ['regulation', 'code', 'public safety'],
        'ConflictOfInterestDilemma': ['conflict of interest', 'competing interest']
    }
    
    # Identify principles based on keywords
    principle_keywords = {
        'HonestyPrinciple': ['honesty', 'truthful', 'full disclosure'],
        'CompetencyPrinciple': ['competence', 'competency', 'qualified'],
        'ObjectivityPrinciple': ['objectivity', 'objective', 'impartial'],
        'PublicSafetyPrinciple': ['public safety', 'safety', 'welfare'],
        'ConfidentialityPrinciple': ['confidentiality', 'confidential'],
        'DisclosurePrinciple': ['disclosure', 'disclose', 'reveal'],
        'FutureImpactsPrinciple': ['future impacts', 'long-term']
    }
    
    # Search for roles
    for role, keywords in role_keywords.items():
        if any(keyword in full_content for keyword in keywords):
            concepts['roles'].append(role)
    
    # Search for actions
    for action, keywords in action_keywords.items():
        if any(keyword in full_content for keyword in keywords):
            concepts['actions'].append(action)
    
    # Search for conditions
    for condition, keywords in condition_keywords.items():
        if any(keyword in full_content for keyword in keywords):
            concepts['conditions'].append(condition)
    
    # Search for dilemmas
    for dilemma, keywords in dilemma_keywords.items():
        if any(keyword in full_content for keyword in keywords):
            concepts['dilemmas'].append(dilemma)
    
    # Search for principles
    for principle, keywords in principle_keywords.items():
        if any(keyword in full_content for keyword in keywords):
            concepts['principles'].append(principle)
    
    # Special handling for NSPE-specific content
    if 'nspe code' in full_content or 'nspe ethics' in full_content:
        if 'principles' not in concepts:
            concepts['principles'] = []
        concepts['principles'].extend(['NSPEPrinciple', 'NSPEPublicSafetyPrinciple'])
    
    return concepts

def create_engineering_world_triples(case_id: int, concepts: Dict[str, List[str]], entity_type: str = 'document') -> Tuple[bool, int]:
    """
    Create engineering world ontology triples for a case
    
    Args:
        case_id (int): The ID of the case
        concepts (Dict): Dictionary of identified concepts grouped by category
        entity_type (str): The entity type to use for the triples
        
    Returns:
        Tuple[bool, int]: Success status and number of triples added
    """
    try:
        # Make db connection directly with proper settings
        conn = psycopg2.connect(
            host="localhost",
            database="ai_ethical_dm",
            user="postgres",
            password="PASS",
            port=5433
        )
        cursor = conn.cursor()
        
        # Get the document URI to use as subject for all triples
        document_uri = f"http://proethica.org/entity/document_{case_id}"
        
        triples = []
        
        # Add roles
        for role in concepts.get('roles', []):
            role_uri = f"{ENGINEERING_ETHICS_NS}{role}"
            triples.append({
                'subject': document_uri,
                'predicate': f"{ENGINEERING_ETHICS_NS}hasRole",
                'object_uri': role_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "engineering-ethics",
                'entity_type': entity_type,
                'entity_id': case_id,
                'triple_metadata': {
                    'triple_type': 'engineering_ethics',
                    'display_label': f"has role: {role}",
                    'name': role
                }
            })
        
        # Add actions
        for action in concepts.get('actions', []):
            action_uri = f"{ENGINEERING_ETHICS_NS}{action}"
            triples.append({
                'subject': document_uri,
                'predicate': f"{ENGINEERING_ETHICS_NS}involvesAction",
                'object_uri': action_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "engineering-ethics",
                'entity_type': entity_type,
                'entity_id': case_id,
                'triple_metadata': {
                    'triple_type': 'engineering_ethics',
                    'display_label': f"involves action: {action}",
                    'name': action
                }
            })
        
        # Add conditions
        for condition in concepts.get('conditions', []):
            condition_uri = f"{ENGINEERING_ETHICS_NS}{condition}"
            triples.append({
                'subject': document_uri,
                'predicate': f"{ENGINEERING_ETHICS_NS}involvesCondition",
                'object_uri': condition_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "engineering-ethics",
                'entity_type': entity_type,
                'entity_id': case_id,
                'triple_metadata': {
                    'triple_type': 'engineering_ethics',
                    'display_label': f"involves condition: {condition}",
                    'name': condition
                }
            })
        
        # Add dilemmas
        for dilemma in concepts.get('dilemmas', []):
            dilemma_uri = f"{ENGINEERING_ETHICS_NS}{dilemma}"
            triples.append({
                'subject': document_uri,
                'predicate': f"{ENGINEERING_ETHICS_NS}presentsDilemma",
                'object_uri': dilemma_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "engineering-ethics",
                'entity_type': entity_type,
                'entity_id': case_id,
                'triple_metadata': {
                    'triple_type': 'engineering_ethics',
                    'display_label': f"presents dilemma: {dilemma}",
                    'name': dilemma
                }
            })
        
        # Add principles
        for principle in concepts.get('principles', []):
            principle_uri = f"{ENGINEERING_ETHICS_NS}{principle}"
            triples.append({
                'subject': document_uri,
                'predicate': f"{ENGINEERING_ETHICS_NS}involvesPrinciple",
                'object_uri': principle_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "engineering-ethics",
                'entity_type': entity_type,
                'entity_id': case_id,
                'triple_metadata': {
                    'triple_type': 'engineering_ethics',
                    'display_label': f"involves principle: {principle}",
                    'name': principle
                }
            })
        
        # Insert the triples into the entity_triples table
        for triple in triples:
            cursor.execute("""
                INSERT INTO entity_triples 
                (subject, predicate, object_uri, object_literal, is_literal, graph, entity_type, entity_id, triple_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                triple['subject'],
                triple['predicate'],
                triple['object_uri'],
                triple['object_literal'],
                triple['is_literal'],
                triple['graph'],
                triple['entity_type'],
                triple['entity_id'],
                triple['triple_metadata']
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, len(triples)
    except Exception as e:
        logger.error(f"Error creating engineering world triples: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False, 0

def add_engineering_world_triples(case_id: int, entity_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Add engineering world ontology triples to a case
    
    Args:
        case_id (int): The ID of the case
        entity_type (str, optional): Override the entity type
        
    Returns:
        Dict: Result of the operation
    """
    try:
        logger.info(f"Adding engineering world ontology triples to case {case_id}")
        
        # Get case properties
        case_props = get_case_properties(case_id)
        if not case_props:
            return {
                'success': False,
                'message': f"Case {case_id} not found",
                'case_id': case_id
            }
        
        # Use provided entity_type or the one from the case
        if not entity_type:
            entity_type = case_props.get('entity_type', 'document')
        
        # Get the full case data
        case_data = get_case(case_id)
        if not case_data:
            return {
                'success': False,
                'message': f"Failed to retrieve case data for {case_id}",
                'case_id': case_id
            }
        
        # Identify engineering concepts from case data
        concepts = identify_engineering_concepts(case_data)
        logger.info(f"Identified engineering concepts from case {case_id}: {concepts}")
        
        # Create engineering world triples
        success, triple_count = create_engineering_world_triples(case_id, concepts, entity_type)
        
        if success:
            return {
                'success': True,
                'message': f"Successfully added {triple_count} engineering world triples to case {case_id}",
                'case_id': case_id,
                'triple_count': triple_count,
                'concepts': concepts
            }
        else:
            return {
                'success': False,
                'message': "Failed to add engineering world triples",
                'case_id': case_id
            }
    except Exception as e:
        logger.error(f"Error adding engineering world triples: {e}")
        return {
            'success': False,
            'message': f"Error: {str(e)}",
            'case_id': case_id
        }
