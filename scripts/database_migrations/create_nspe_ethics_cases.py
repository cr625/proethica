#!/usr/bin/env python3
"""
Script to create engineering ethics cases from NSPE Board of Ethical Review cases.
This script processes modern NSPE cases, creates rich RDF triple representations,
and submits them to the ProEthica system.
"""

import json
import sys
import os
import uuid
import datetime
import requests
from collections import defaultdict

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Optional: Import the EntityTripleService if direct DB integration is needed
# from app import create_app, db
# from app.services.entity_triple_service import EntityTripleService

# Constants
NSPE_CASES_FILE = "data/modern_nspe_cases.json"
SERVER_URL = "http://localhost:3333"  # Change to match your server
ENGINEERING_WORLD_ID = 1  # Assuming Engineering Ethics world ID is 1

# RDF Namespace Definitions
NAMESPACES = {
    "Case": "http://proethica.org/case/",
    "NSPE": "http://proethica.org/nspe/",
    "ENG_ETHICS": "http://proethica.org/ontology/engineering-ethics#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "bfo": "http://purl.obolibrary.org/obo/",
    "proeth": "http://proethica.org/ontology/intermediate#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ar": "http://proethica.org/ontology/agent-role#",
    "eng": "http://proethica.org/ontology/engineering-ethics#",
    "nspe": "http://proethica.org/nspe/",
    "rel": "http://proethica.org/relation/"
}

# Common Principles and Codes mapping for easy reference
# This maps principle names to their corresponding ontology terms
PRINCIPLE_MAPPING = {
    "public safety": "ENG_ETHICS:PublicSafetyPrinciple",
    "confidentiality": "ENG_ETHICS:ConfidentialityPrinciple",
    "competency": "ENG_ETHICS:CompetencyPrinciple",
    "honesty": "ENG_ETHICS:HonestyPrinciple",
    "professional responsibility": "ENG_ETHICS:ProfessionalResponsibility",
    "conflicts of interest": "ENG_ETHICS:ConflictOfInterestAvoidanceObligation",
    "objectivity": "ENG_ETHICS:ObjectivityPrinciple",
    "disclosure": "ENG_ETHICS:HonestyPrinciple",
    "integrity": "ENG_ETHICS:ObjectivityPrinciple",
    "professional judgment": "ENG_ETHICS:CompetencyPrinciple"
}

CODE_MAPPING = {
    "Code I.1": "NSPE:NSPECodeI1",
    "Code I.4": "NSPE:NSPECodeI4",
    "Code II.1.a": "NSPE:NSPECodeII1a",
    "Code II.1.b": "NSPE:NSPECodeII1b",
    "Code II.1.c": "NSPE:NSPECodeII1c",
    "Code II.1.e": "NSPE:NSPECodeII1e",
    "Code II.2": "NSPE:NSPECodeII2",
    "Code II.3.a": "NSPE:NSPECodeII3a",
    "Code II.4": "NSPE:NSPECodeII4",
    "Code II.4.a": "NSPE:NSPECodeII4a",
    "Code II.4.b": "NSPE:NSPECodeII4b",
    "Code II.4.d": "NSPE:NSPECodeII4d",
    "Code III.1": "NSPE:NSPECodeIII1",
    "Code III.1.a": "NSPE:NSPECodeIII1a",
    "Code III.1.b": "NSPE:NSPECodeIII1b",
    "Code III.2.b": "NSPE:NSPECodeIII2b",
    "Code III.4": "NSPE:NSPECodeIII4"
}

# Map dilemma types to ontology terms
DILEMMA_MAPPING = {
    "confidentiality vs safety": "ENG_ETHICS:ConfidentialityVsSafetyDilemma",
    "competency vs client wishes": "ENG_ETHICS:CompetencyVsClientWishesDilemma",
    "quality vs budget": "ENG_ETHICS:QualityVsBudgetDilemma",
    "conflicts of interest": "ENG_ETHICS:ConflictOfInterestCondition",
    "whistleblowing": "ENG_ETHICS:WhistleblowingDecision"
}

# Map roles to ontology terms
ROLE_MAPPING = {
    "structural engineer": "ENG_ETHICS:StructuralEngineerRole",
    "electrical engineer": "ENG_ETHICS:ElectricalEngineerRole",
    "mechanical engineer": "ENG_ETHICS:MechanicalEngineerRole",
    "consulting engineer": "ENG_ETHICS:ConsultingEngineerRole",
    "project engineer": "ENG_ETHICS:ProjectEngineerRole",
    "inspection engineer": "ENG_ETHICS:InspectionEngineerRole",
    "client": "ENG_ETHICS:ClientRole",
    "building official": "ENG_ETHICS:BuildingOfficialRole",
    "regulatory official": "ENG_ETHICS:RegulatoryOfficialRole",
    "public stakeholder": "ENG_ETHICS:PublicStakeholderRole"
}

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

def sanitize_id(text):
    """
    Create a sanitized ID from text for use in RDF.
    """
    if not text:
        return f"Case_{uuid.uuid4().hex[:8]}"
    
    # Replace spaces and special characters with underscores
    return ''.join(c if c.isalnum() else '_' for c in text).strip('_')

def identify_dilemma_type(case):
    """
    Identify the type of ethical dilemma in the case.
    """
    principles = case.get('metadata', {}).get('principles', [])
    if "confidentiality" in principles and "public safety" in principles:
        return "confidentiality vs safety"
    elif "competency" in principles and "professional judgment" in principles:
        return "competency vs client wishes"
    elif "conflicts of interest" in principles:
        return "conflicts of interest"
    elif "whistleblowing" in principles or "public safety" in principles:
        return "whistleblowing"
    return "general ethical dilemma"

def extract_roles_from_text(text):
    """
    Extract engineering and stakeholder roles from case text.
    """
    roles = []
    for role_keyword, role_uri in ROLE_MAPPING.items():
        if role_keyword in text.lower():
            roles.append((role_keyword, role_uri))
    return roles

def extract_entities_from_case(case):
    """
    Extract entities (engineers, clients, etc.) from case text.
    """
    entities = []
    text = case.get('full_text', '') or case.get('html_content', '')
    
    # Common patterns for engineers in NSPE cases
    engineer_patterns = [
        r'Engineer ([A-Z])',
        r'engineer ([A-Z])',
        r'Engineer ([A-Z][a-z]+)'
    ]
    
    # Simple extraction based on common case formats
    # A more sophisticated approach would use NLP or regex patterns
    if "Engineer A" in text:
        entities.append(("Engineer A", "main engineer"))
    if "Engineer B" in text:
        entities.append(("Engineer B", "secondary engineer"))
    if "Client X" in text or "Client" in text:
        entities.append(("Client", "client"))
    
    return entities

def generate_case_triples(case):
    """
    Generate RDF triples for a case.
    """
    triples = []
    case_number = case.get('case_number', '').replace('-', '_')
    case_id = f"Case_{case_number}"
    title_id = sanitize_id(case.get('title', ''))
    case_uri = f"Case:{case_id}_{title_id}"
    
    # Basic case information
    triples.append({
        "subject": case_uri,
        "predicate": "rdf:type",
        "object": "owl:NamedIndividual"
    })
    
    triples.append({
        "subject": case_uri,
        "predicate": "rdf:type",
        "object": "proeth:EthicalDilemma"
    })
    
    triples.append({
        "subject": case_uri,
        "predicate": "rdfs:label",
        "object": case.get('title', 'Untitled Case'),
        "is_literal": True
    })
    
    # Add description
    if case.get('full_text'):
        triples.append({
            "subject": case_uri,
            "predicate": "rdfs:comment",
            "object": case.get('full_text', ''),
            "is_literal": True
        })
    
    # Add case number and year
    if case.get('case_number'):
        triples.append({
            "subject": case_uri,
            "predicate": "NSPE:caseNumber",
            "object": case.get('case_number', ''),
            "is_literal": True
        })
    
    if case.get('year'):
        triples.append({
            "subject": case_uri,
            "predicate": "NSPE:caseYear",
            "object": str(case.get('year', '')),
            "is_literal": True
        })
    
    # Add source URL
    if case.get('url'):
        triples.append({
            "subject": case_uri,
            "predicate": "NSPE:sourceUrl",
            "object": case.get('url', ''),
            "is_literal": True
        })
    
    # Identify principles and codes
    metadata = case.get('metadata', {})
    principles = metadata.get('principles', [])
    codes = metadata.get('codes_cited', [])
    
    # Add principles
    for principle in principles:
        principle_uri = PRINCIPLE_MAPPING.get(principle.lower(), f"NSPE:{sanitize_id(principle)}Principle")
        principle_instance = f"{principle_uri}Instance_{case_number}"
        
        # Create principle instance
        triples.append({
            "subject": principle_instance,
            "predicate": "rdf:type",
            "object": "owl:NamedIndividual"
        })
        
        triples.append({
            "subject": principle_instance,
            "predicate": "rdf:type",
            "object": principle_uri
        })
        
        # Link principle to case
        triples.append({
            "subject": case_uri,
            "predicate": "eng:involvesPrinciple",
            "object": principle_instance
        })
    
    # Add codes
    for code in codes:
        code_uri = CODE_MAPPING.get(code, f"NSPE:{sanitize_id(code)}")
        
        triples.append({
            "subject": case_uri,
            "predicate": "rel:references",
            "object": code_uri
        })
    
    # Add dilemma type
    dilemma_type = identify_dilemma_type(case)
    dilemma_uri = DILEMMA_MAPPING.get(dilemma_type, "proeth:EthicalDilemma")
    
    triples.append({
        "subject": case_uri,
        "predicate": "rdf:type",
        "object": dilemma_uri
    })
    
    # Extract and add entities
    entities = extract_entities_from_case(case)
    for i, (entity_name, entity_type) in enumerate(entities):
        entity_id = f"{sanitize_id(entity_name)}_{case_number}"
        
        # Create entity instance
        triples.append({
            "subject": entity_id,
            "predicate": "rdf:type",
            "object": "owl:NamedIndividual"
        })
        
        triples.append({
            "subject": entity_id,
            "predicate": "rdf:type",
            "object": "ar:Character"
        })
        
        triples.append({
            "subject": entity_id,
            "predicate": "rdfs:label",
            "object": entity_name,
            "is_literal": True
        })
        
        # Add entity roles
        if "engineer" in entity_type.lower():
            role_uri = "eng:EngineeringRole"
            if "structural" in entity_type.lower():
                role_uri = "eng:StructuralEngineerRole"
            elif "consulting" in entity_type.lower():
                role_uri = "eng:ConsultingEngineerRole"
            
            role_instance = f"{role_uri}Instance_{entity_id}"
            
            triples.append({
                "subject": role_instance,
                "predicate": "rdf:type",
                "object": "owl:NamedIndividual"
            })
            
            triples.append({
                "subject": role_instance,
                "predicate": "rdf:type",
                "object": role_uri
            })
            
            triples.append({
                "subject": entity_id,
                "predicate": "ar:hasRole",
                "object": role_instance
            })
        elif "client" in entity_type.lower():
            role_uri = "eng:ClientRole"
            role_instance = f"{role_uri}Instance_{entity_id}"
            
            triples.append({
                "subject": role_instance,
                "predicate": "rdf:type",
                "object": "owl:NamedIndividual"
            })
            
            triples.append({
                "subject": role_instance,
                "predicate": "rdf:type",
                "object": role_uri
            })
            
            triples.append({
                "subject": entity_id,
                "predicate": "ar:hasRole",
                "object": role_instance
            })
        
        # Link entity to case
        triples.append({
            "subject": case_uri,
            "predicate": "rel:involves",
            "object": entity_id
        })
    
    # Add outcome
    outcome = metadata.get('outcome', '')
    if outcome:
        decision_id = f"Decision_{case_number}"
        
        triples.append({
            "subject": decision_id,
            "predicate": "rdf:type",
            "object": "owl:NamedIndividual"
        })
        
        triples.append({
            "subject": decision_id,
            "predicate": "rdf:type",
            "object": "eng:EthicalDecision"
        })
        
        decision_label = f"NSPE Board Decision for Case {case.get('case_number', '')}"
        triples.append({
            "subject": decision_id,
            "predicate": "rdfs:label",
            "object": decision_label,
            "is_literal": True
        })
        
        # Add decision outcome detail
        if "unethical" in outcome:
            triples.append({
                "subject": decision_id,
                "predicate": "NSPE:outcome",
                "object": "Unethical",
                "is_literal": True
            })
        elif "ethical" in outcome:
            triples.append({
                "subject": decision_id,
                "predicate": "NSPE:outcome",
                "object": "Ethical",
                "is_literal": True
            })
        else:
            triples.append({
                "subject": decision_id,
                "predicate": "NSPE:outcome",
                "object": outcome,
                "is_literal": True
            })
        
        # Link decision to case
        triples.append({
            "subject": case_uri,
            "predicate": "rel:hasDecision",
            "object": decision_id
        })
    
    # Add board analysis if available
    board_analysis = metadata.get('board_analysis', '')
    if board_analysis:
        triples.append({
            "subject": case_uri,
            "predicate": "NSPE:boardAnalysis",
            "object": board_analysis,
            "is_literal": True
        })
    
    # Add related cases
    related_cases = metadata.get('related_cases', [])
    for related_case in related_cases:
        related_case_id = f"Case_{related_case.replace('-', '_')}"
        triples.append({
            "subject": case_uri,
            "predicate": "rel:relatedTo",
            "object": f"Case:{related_case_id}"
        })
    
    return triples

def create_case_with_triples(case, server_url=SERVER_URL):
    """
    Create a new case in the ProEthica system using the triple-based API.
    """
    # Generate title and description
    title = case.get('title', '')
    if not title and case.get('case_number'):
        title = f"NSPE Case {case.get('case_number')}"
    
    description = case.get('full_text', '')
    if not description and case.get('html_content'):
        # This is a very simple HTML tag removal, might need improvement
        description = case.get('html_content', '').replace('<p>', '\n\n').replace('</p>', '').replace('<h2>', '\n\n').replace('</h2>', '\n').replace('<h3>', '\n\n').replace('</h3>', '\n')
        description = description.replace('<ol>', '\n').replace('</ol>', '').replace('<li>', '\n- ').replace('</li>', '')
        # Remove any remaining HTML tags
        import re
        description = re.sub('<[^<]+?>', '', description)
    
    # Source information
    source = case.get('url', '')
    if not source:
        source = f"NSPE Board of Ethical Review Case {case.get('case_number', '')}, {case.get('year', '')}"
    
    # Generate RDF triples
    triples = generate_case_triples(case)
    
    # Extract namespaces from NAMESPACES dictionary
    prefixes = list(NAMESPACES.keys())
    uris = [NAMESPACES[prefix] for prefix in prefixes]
    
    # Prepare the data for the triple-based API
    form_data = {
        'source_type': 'nspe',
        'title': title,
        'world_id': ENGINEERING_WORLD_ID,
        'description': description,
        'source': source
    }
    
    # Create lists for triples data
    subjects = []
    predicates = []
    objects = []
    is_literals = []
    
    # Add triple data to lists
    for triple in triples:
        subjects.append(triple['subject'])
        predicates.append(triple['predicate'])
        objects.append(triple['object'])
        is_literals.append('true' if triple.get('is_literal', False) else 'false')
    
    # Add lists to form data
    form_data['subjects[]'] = subjects
    form_data['predicates[]'] = predicates
    form_data['objects[]'] = objects
    form_data['is_literals[]'] = is_literals
    form_data['prefixes[]'] = prefixes
    form_data['uris[]'] = uris
    
    # Print the request data for debugging
    print("\nSending the following data to create triple-based case:")
    print(f"Title: {title}")
    print(f"Description: {description[:100]}...")
    print(f"Triples: {len(triples)}")
    print(f"Namespaces: {len(prefixes)}")
    
    # Send POST request to create the case
    try:
        response = requests.post(
            f"{server_url}/cases/triple/new",
            data=form_data
        )
        
        if response.status_code == 200 or response.status_code == 302:
            print("Case created successfully using triple-based approach!")
            # Try to extract the new case ID from the redirect URL
            if response.history and response.history[0].status_code == 302:
                redirect_url = response.history[0].headers.get('Location', '')
                case_id = redirect_url.split('/')[-1]
                print(f"New case ID: {case_id}")
                print(f"View the case at: {server_url}/cases/{case_id}")
            return True
        else:
            print(f"Error creating case. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return False

def create_cases_from_nspe_data(max_cases=20, verbose=True):
    """
    Create cases from the NSPE data up to max_cases.
    """
    # Load cases
    cases = load_nspe_cases(NSPE_CASES_FILE)
    
    # Filter for more recent cases
    cases = sorted(cases, key=lambda case: case.get('year', 0), reverse=True)
    
    # Ensure diversity by categorizing cases by dilemma type
    cases_by_dilemma = defaultdict(list)
    for case in cases:
        dilemma_type = identify_dilemma_type(case)
        cases_by_dilemma[dilemma_type].append(case)
    
    # Create a diverse selection of cases
    selected_cases = []
    
    # First, ensure we have at least one of each dilemma type
    for dilemma_type, dilemma_cases in cases_by_dilemma.items():
        if dilemma_cases:
            selected_cases.append(dilemma_cases[0])
            dilemma_cases.pop(0)
    
    # Then fill remaining slots, ensuring diversity
    remaining_slots = max_cases - len(selected_cases)
    if remaining_slots > 0:
        # Calculate how many cases to take from each category
        cases_per_category = max(1, remaining_slots // len(cases_by_dilemma))
        
        for dilemma_type, dilemma_cases in cases_by_dilemma.items():
            to_take = min(cases_per_category, len(dilemma_cases))
            selected_cases.extend(dilemma_cases[:to_take])
            
            if len(selected_cases) >= max_cases:
                break
    
    # Ensure we don't exceed max_cases
    selected_cases = selected_cases[:max_cases]
    
    print(f"Selected {len(selected_cases)} cases for creation")
    
    # Create cases
    successful_cases = 0
    for i, case in enumerate(selected_cases):
        print(f"\nProcessing case {i+1}/{len(selected_cases)}: {case.get('case_number', '')} - {case.get('title', '')}")
        try:
            # Create case with triple-based approach
            if create_case_with_triples(case):
                successful_cases += 1
            else:
                print(f"Failed to create case: {case.get('case_number', '')} - {case.get('title', '')}")
        except Exception as e:
            print(f"Error processing case: {str(e)}")
    
    print(f"\nCreated {successful_cases} out of {len(selected_cases)} cases successfully")
    return successful_cases

def export_case_triples_to_json(case, output_file=None):
    """
    Export case triples to a JSON file for inspection or manual import.
    """
    # Generate title and description
    title = case.get('title', '')
    if not title and case.get('case_number'):
        title = f"NSPE Case {case.get('case_number')}"
    
    description = case.get('full_text', '')
    if not description and case.get('html_content'):
        # Simple HTML tag removal
        description = case.get('html_content', '').replace('<p>', '\n\n').replace('</p>', '').replace('<h2>', '\n\n').replace('</h2>', '\n').replace('<h3>', '\n\n').replace('</h3>', '\n')
        description = description.replace('<ol>', '\n').replace('</ol>', '').replace('<li>', '\n- ').replace('</li>', '')
        # Remove any remaining HTML tags
        import re
        description = re.sub('<[^<]+?>', '', description)
    
    # Source information
    source = case.get('url', '')
    if not source:
        source = f"NSPE Board of Ethical Review Case {case.get('case_number', '')}, {case.get('year', '')}"
    
    # Generate RDF triples
    triples = generate_case_triples(case)
    
    # Create case data structure
    case_data = {
        "title": title,
        "description": description,
        "source": source,
        "rdf_triples": {
            "triples": triples,
            "namespaces": NAMESPACES
        }
    }
    
    # Add metadata
    if case.get('metadata'):
        case_data["metadata"] = case.get('metadata')
    
    # Save to file if output_file is provided
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(case_data, f, indent=2)
        print(f"Exported case triples to {output_file}")
    
    return case_data

def export_all_case_triples(output_dir="data/case_triples", max_cases=20):
    """
    Export all case triples to individual JSON files for inspection.
    """
    # Load cases
    cases = load_nspe_cases(NSPE_CASES_FILE)
    
    # Filter for more recent cases
    cases = sorted(cases, key=lambda case: case.get('year', 0), reverse=True)
    
    # Ensure directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Export cases
    exported_cases = 0
    for i, case in enumerate(cases[:max_cases]):
        case_number = case.get('case_number', f"unknown_{i}").replace('-', '_')
        output_file = os.path.join(output_dir, f"case_{case_number}.json")
        
        try:
            export_case_triples_to_json(case, output_file)
            exported_cases += 1
        except Exception as e:
            print(f"Error exporting case {case_number}: {str(e)}")
    
    print(f"Exported {exported_cases} cases to {output_dir}")
    return exported_cases

def main():
    """
    Main function to create NSPE ethics cases.
    """
    print("===== Creating NSPE Engineering Ethics Cases =====")
    
    # Process command line arguments
    max_cases = 20
    if len(sys.argv) > 1:
        try:
            max_cases = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number of cases specified: {sys.argv[1]}. Using default: {max_cases}")
    
    # Create the cases
    print(f"Creating up to {max_cases} cases...")
    num_created = create_cases_from_nspe_data(max_cases=max_cases)
    
    print(f"\nCompleted creating {num_created} engineering ethics cases.")

def parse_arguments():
    """
    Parse command line arguments
    """
    import argparse
    parser = argparse.ArgumentParser(description='Create engineering ethics cases from NSPE BER cases')
    parser.add_argument('--max-cases', type=int, default=20,
                        help='Maximum number of cases to create (default: 20)')
    parser.add_argument('--export-only', action='store_true',
                        help='Only export to JSON files, do not try to create in database')
    parser.add_argument('--export-dir', type=str, default='data/case_triples',
                        help='Directory to export case triples to (default: data/case_triples)')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose output')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    print("===== Creating NSPE Engineering Ethics Cases =====")
    
    # If export only, just export the cases
    if args.export_only:
        print(f"Exporting up to {args.max_cases} cases to {args.export_dir}...")
        num_exported = export_all_case_triples(output_dir=args.export_dir, max_cases=args.max_cases)
        print(f"\nCompleted exporting {num_exported} engineering ethics cases.")
    else:
        # Create the cases
        print(f"Creating up to {args.max_cases} cases...")
        num_created = create_cases_from_nspe_data(max_cases=args.max_cases, verbose=args.verbose)
        print(f"\nCompleted creating {num_created} engineering ethics cases.")
