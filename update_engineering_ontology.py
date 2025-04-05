#!/usr/bin/env python3
"""
Script to extend the engineering ethics ontology with new concepts needed for NSPE cases.
This script analyzes the NSPE cases and adds new role types, condition types, ethical dilemmas,
and decision types to the engineering ethics ontology.
"""

import sys
import os
import json
import re
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, DC

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Constants
NSPE_CASES_FILE = "data/modern_nspe_cases.json"
ENGINEERING_ONTOLOGY_FILE = "mcp/ontology/engineering-ethics-nspe-extended.ttl"
OUTPUT_ONTOLOGY_FILE = "mcp/ontology/engineering-ethics-nspe-extended.ttl"

# Define namespaces
ENG = Namespace("http://proethica.org/ontology/engineering-ethics#")
OWL_NS = Namespace("http://www.w3.org/2002/07/owl#")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
XML_NS = Namespace("http://www.w3.org/XML/1998/namespace")
XSD_NS = Namespace("http://www.w3.org/2001/XMLSchema#")
DC_NS = Namespace("http://purl.org/dc/elements/1.1/")
BFO_NS = Namespace("http://purl.obolibrary.org/obo/")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
NSPE = Namespace("http://proethica.org/nspe/")

def load_ontology(file_path):
    """
    Load the engineering ethics ontology from a TTL file.
    """
    graph = Graph()
    try:
        graph.parse(file_path, format="turtle")
        print(f"Successfully loaded ontology from {file_path}")
        return graph
    except Exception as e:
        print(f"Error loading ontology: {str(e)}")
        return None

def save_ontology(graph, file_path):
    """
    Save the modified ontology to a TTL file.
    """
    try:
        graph.serialize(destination=file_path, format="turtle")
        print(f"Successfully saved ontology to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving ontology: {str(e)}")
        return False

def load_nspe_cases(file_path):
    """
    Load NSPE cases from the specified JSON file.
    """
    try:
        with open(file_path, 'r') as f:
            cases = json.load(f)
            print(f"Successfully loaded {len(cases)} cases from {file_path}")
            return cases
    except Exception as e:
        print(f"Error loading cases file: {str(e)}")
        return []

def extract_concepts_from_cases(cases):
    """
    Extract potential new concepts from NSPE cases.
    """
    # Containers for different concepts
    roles = set()
    conditions = set()
    dilemmas = set()
    resources = set()
    principles = set()
    actions = set()
    
    # Analyze each case
    for case in cases:
        title = case.get('title', '').lower()
        full_text = case.get('full_text', '').lower()
        
        # Extract concepts from title and text
        
        # Extract roles
        if 'city engineer' in title or 'city engineer' in full_text:
            roles.add('CityEngineerRole')
        if 'peer reviewer' in title or 'peer review' in full_text:
            roles.add('PeerReviewerRole')
        if 'licensure board' in title or 'licensure board' in full_text:
            roles.add('LicensureBoardMemberRole')
        if 'consultant' in title or 'consultant' in full_text:
            roles.add('ConsultantRole')
        
        # Extract conditions
        if 'climate change' in title or 'climate change' in full_text:
            conditions.add('ClimateChangeCondition')
        if 'stormwater' in title or 'stormwater' in full_text:
            conditions.add('StormwaterManagementCondition')
        if 'water quality' in title or 'drinking water' in full_text:
            conditions.add('WaterQualityCondition')
        if 'conflict of interest' in title or 'conflict of interest' in full_text:
            conditions.add('ConflictOfInterestCondition')
        if 'impaired' in title or 'impaired' in full_text:
            conditions.add('ImpairedEngineeringCondition')
        if 'post-employment' in title or 'post-public employment' in full_text:
            conditions.add('PostEmploymentConflictCondition')
        if 'rolling blackout' in title or 'rolling blackout' in full_text:
            conditions.add('PowerOutageCondition')
        
        # Extract dilemmas
        if ('public service' in title and 'private practice' in title) or ('public service' in full_text and 'private practice' in full_text):
            dilemmas.add('PublicServiceVsPrivatePracticeDilemma')
        if ('competence' in title and 'client need' in title) or ('competence' in full_text and 'client need' in full_text):
            dilemmas.add('CompetenceVsClientNeedsDilemma')
        if 'gift' in title or 'gift' in full_text:
            dilemmas.add('GiftAcceptanceDilemma')
        if 'reduced fee' in title or 'free service' in full_text:
            dilemmas.add('ReducedFeeServiceDilemma')
        
        # Extract resources
        if 'plan' in title or 'plan' in full_text:
            resources.add('EngineeringPlans')
        if 'as-built' in title or 'built drawing' in full_text:
            resources.add('AsBuiltDrawings')
        if 'certification' in title or 'certification' in full_text:
            resources.add('DesignCertification')
        if 'stamping' in title or 'seal' in full_text:
            resources.add('EngineeringStamp')
        
        # Extract principles from metadata
        metadata = case.get('metadata', {})
        if 'principles' in metadata:
            for principle in metadata.get('principles', []):
                if principle:
                    # Convert to CamelCase
                    principle_name = ''.join(word.capitalize() for word in principle.split())
                    principles.add(f"{principle_name}Principle")
    
    return {
        'roles': roles,
        'conditions': conditions,
        'dilemmas': dilemmas,
        'resources': resources,
        'principles': principles,
        'actions': actions
    }

def add_engineering_roles(graph, roles):
    """
    Add new engineering role types to the ontology.
    """
    role_count = 0
    
    for role_name in roles:
        role_uri = ENG[role_name]
        
        # Check if role already exists
        if (role_uri, RDF.type, OWL.Class) in graph:
            print(f"Role {role_name} already exists, skipping")
            continue
        
        # Add the role class
        graph.add((role_uri, RDF.type, OWL.Class))
        graph.add((role_uri, RDF.type, PROETH.EntityType))
        graph.add((role_uri, RDF.type, PROETH.Role))
        graph.add((role_uri, RDFS.subClassOf, ENG.EngineeringRole))
        
        # Add label and comment
        label = ' '.join(re.findall('[A-Z][a-z]*', role_name))
        graph.add((role_uri, RDFS.label, Literal(f"{label} Role", lang="en")))
        graph.add((role_uri, RDFS.comment, Literal(f"The role of a {label.lower()} in engineering practice", lang="en")))
        
        # Add capabilities based on role type
        if 'Reviewer' in role_name:
            graph.add((role_uri, PROETH.hasCapability, ENG.SafetyAssessmentCapability))
            graph.add((role_uri, PROETH.hasCapability, ENG.TechnicalReportingCapability))
        elif 'Engineer' in role_name:
            graph.add((role_uri, PROETH.hasCapability, ENG.EngineeringConsultationCapability))
            graph.add((role_uri, PROETH.hasCapability, ENG.TechnicalReportingCapability))
            graph.add((role_uri, PROETH.hasCapability, ENG.RegulatoryComplianceCapability))
        
        role_count += 1
    
    print(f"Added {role_count} new engineering roles")
    return role_count

def add_engineering_conditions(graph, conditions):
    """
    Add new condition types to the ontology.
    """
    condition_count = 0
    
    for condition_name in conditions:
        condition_uri = ENG[condition_name]
        
        # Check if condition already exists
        if (condition_uri, RDF.type, OWL.Class) in graph:
            print(f"Condition {condition_name} already exists, skipping")
            continue
        
        # Add the condition class
        graph.add((condition_uri, RDF.type, OWL.Class))
        graph.add((condition_uri, RDF.type, PROETH.EntityType))
        graph.add((condition_uri, RDF.type, PROETH.ConditionType))
        graph.add((condition_uri, RDFS.subClassOf, ENG.EngineeringCondition))
        
        # Add label and comment
        label = ' '.join(re.findall('[A-Z][a-z]*', condition_name))
        graph.add((condition_uri, RDFS.label, Literal(f"{label}", lang="en")))
        graph.add((condition_uri, RDFS.comment, Literal(f"A condition involving {label.lower()} in engineering practice", lang="en")))
        
        condition_count += 1
    
    print(f"Added {condition_count} new engineering conditions")
    return condition_count

def add_ethical_dilemmas(graph, dilemmas):
    """
    Add new ethical dilemma types to the ontology.
    """
    dilemma_count = 0
    
    for dilemma_name in dilemmas:
        dilemma_uri = ENG[dilemma_name]
        
        # Check if dilemma already exists
        if (dilemma_uri, RDF.type, OWL.Class) in graph:
            print(f"Dilemma {dilemma_name} already exists, skipping")
            continue
        
        # Add the dilemma class
        graph.add((dilemma_uri, RDF.type, OWL.Class))
        graph.add((dilemma_uri, RDF.type, PROETH.EntityType))
        graph.add((dilemma_uri, RDF.type, PROETH.ConditionType))
        graph.add((dilemma_uri, RDFS.subClassOf, ENG.EngineeringEthicalDilemma))
        
        # Add label and comment
        label = ' '.join(re.findall('[A-Z][a-z]*', dilemma_name))
        graph.add((dilemma_uri, RDFS.label, Literal(f"{label}", lang="en")))
        graph.add((dilemma_uri, RDFS.comment, Literal(f"A dilemma involving {label.lower()} in engineering practice", lang="en")))
        
        dilemma_count += 1
    
    print(f"Added {dilemma_count} new ethical dilemmas")
    return dilemma_count

def add_engineering_resources(graph, resources):
    """
    Add new resource types to the ontology.
    """
    resource_count = 0
    
    for resource_name in resources:
        resource_uri = ENG[resource_name]
        
        # Check if resource already exists
        if (resource_uri, RDF.type, OWL.Class) in graph:
            print(f"Resource {resource_name} already exists, skipping")
            continue
        
        # Add the resource class
        graph.add((resource_uri, RDF.type, OWL.Class))
        graph.add((resource_uri, RDF.type, PROETH.EntityType))
        graph.add((resource_uri, RDF.type, PROETH.ResourceType))
        graph.add((resource_uri, RDFS.subClassOf, ENG.EngineeringResource))
        
        # Add label and comment
        label = ' '.join(re.findall('[A-Z][a-z]*', resource_name))
        graph.add((resource_uri, RDFS.label, Literal(f"{label}", lang="en")))
        graph.add((resource_uri, RDFS.comment, Literal(f"A resource involving {label.lower()} in engineering practice", lang="en")))
        
        resource_count += 1
    
    print(f"Added {resource_count} new engineering resources")
    return resource_count

def add_ethical_principles(graph, principles):
    """
    Add new ethical principle types to the ontology.
    """
    principle_count = 0
    
    for principle_name in principles:
        principle_uri = ENG[principle_name]
        
        # Check if principle already exists
        if (principle_uri, RDF.type, OWL.Class) in graph:
            print(f"Principle {principle_name} already exists, skipping")
            continue
        
        # Add the principle class
        graph.add((principle_uri, RDF.type, OWL.Class))
        graph.add((principle_uri, RDF.type, PROETH.EntityType))
        graph.add((principle_uri, RDF.type, PROETH.ConditionType))
        graph.add((principle_uri, RDFS.subClassOf, ENG.EngineeringEthicalPrinciple))
        
        # Add label and comment
        label = ' '.join(re.findall('[A-Z][a-z]*', principle_name))
        graph.add((principle_uri, RDFS.label, Literal(f"{label}", lang="en")))
        graph.add((principle_uri, RDFS.comment, Literal(f"The principle of {label.lower()} in engineering ethics", lang="en")))
        
        principle_count += 1
    
    print(f"Added {principle_count} new ethical principles")
    return principle_count

def update_ontology_date(graph):
    """
    Update the ontology date to the current date.
    """
    # Get the ontology URI
    ontology_uri = URIRef("http://proethica.org/ontology/engineering-ethics")
    
    # Remove existing date
    for date_triple in graph.triples((ontology_uri, DC_NS.date, None)):
        graph.remove(date_triple)
    
    # Add current date
    import datetime
    today = datetime.date.today()
    graph.add((ontology_uri, DC_NS.date, Literal(today.isoformat(), datatype=XSD.date)))
    
    print(f"Updated ontology date to {today.isoformat()}")
    return True

def add_missing_concepts_to_ontology(base_ontology_file, cases_file, output_file):
    """
    Add missing concepts to the engineering ethics ontology based on NSPE cases.
    """
    # Load ontology
    graph = load_ontology(base_ontology_file)
    if not graph:
        return False
    
    # Bind namespaces
    graph.bind("", ENG)
    graph.bind("owl", OWL_NS)
    graph.bind("rdf", RDF_NS)
    graph.bind("rdfs", RDFS_NS)
    graph.bind("xml", XML_NS)
    graph.bind("xsd", XSD_NS)
    graph.bind("dc", DC_NS)
    graph.bind("bfo", BFO_NS)
    graph.bind("proeth", PROETH)
    graph.bind("nspe", NSPE)
    
    # Load NSPE cases
    cases = load_nspe_cases(cases_file)
    if not cases:
        return False
    
    # Extract concepts from cases
    concepts = extract_concepts_from_cases(cases)
    
    # Add new concepts to ontology
    roles_added = add_engineering_roles(graph, concepts['roles'])
    conditions_added = add_engineering_conditions(graph, concepts['conditions'])
    dilemmas_added = add_ethical_dilemmas(graph, concepts['dilemmas'])
    resources_added = add_engineering_resources(graph, concepts['resources'])
    principles_added = add_ethical_principles(graph, concepts['principles'])
    
    # Update ontology date
    update_ontology_date(graph)
    
    # Save modified ontology
    return save_ontology(graph, output_file)

def main():
    """
    Main function to update the engineering ethics ontology with new concepts.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Update engineering ethics ontology with new concepts')
    parser.add_argument('--base', type=str, default=ENGINEERING_ONTOLOGY_FILE,
                        help=f'Base ontology file path (default: {ENGINEERING_ONTOLOGY_FILE})')
    parser.add_argument('--cases', type=str, default=NSPE_CASES_FILE,
                        help=f'NSPE cases file path (default: {NSPE_CASES_FILE})')
    parser.add_argument('--output', type=str, default=OUTPUT_ONTOLOGY_FILE,
                        help=f'Output ontology file path (default: {OUTPUT_ONTOLOGY_FILE})')
    args = parser.parse_args()
    
    print("===== Updating Engineering Ethics Ontology =====")
    result = add_missing_concepts_to_ontology(args.base, args.cases, args.output)
    
    if result:
        print("\nEngineering ethics ontology successfully updated with new concepts")
    else:
        print("\nFailed to update engineering ethics ontology")

if __name__ == "__main__":
    main()
