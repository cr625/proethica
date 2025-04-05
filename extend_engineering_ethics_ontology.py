#!/usr/bin/env python3
"""
Script to extend the engineering ethics ontology with additional concepts
needed for the NSPE cases.
"""

import json
import sys
import os
import re
from collections import defaultdict

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Constants
NSPE_CASES_FILE = "data/modern_nspe_cases.json"
ENGINEERING_ETHICS_ONTOLOGY = "mcp/ontology/engineering-ethics-enhanced.ttl"
NSPE_ENGINEERING_ETHICS = "mcp/ontology/nspe-engineering-ethics.ttl"
OUTPUT_ONTOLOGY = "mcp/ontology/engineering-ethics-nspe-extended.ttl"

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

def load_ontology(file_path):
    """
    Load ontology from the specified TTL file.
    """
    try:
        with open(file_path, 'r') as f:
            ontology = f.read()
            print(f"Successfully loaded ontology from {file_path}")
            return ontology
    except Exception as e:
        print(f"Error loading ontology file: {str(e)}")
        return ""

def extract_concepts_from_ontology(ontology_text):
    """
    Extract concepts (classes) from ontology text.
    """
    concepts = set()
    
    # Extract class declarations - this is a simple regex approach
    class_pattern = r'([A-Za-z0-9]+)\s+rdf:type\s+owl:Class'
    for match in re.finditer(class_pattern, ontology_text):
        concept = match.group(1)
        if concept and not concept.startswith(':'):
            concept = ':' + concept
        concepts.add(concept)
    
    # Extract subclass declarations
    subclass_pattern = r'([A-Za-z0-9]+)\s+rdfs:subClassOf'
    for match in re.finditer(subclass_pattern, ontology_text):
        concept = match.group(1)
        if concept and not concept.startswith(':'):
            concept = ':' + concept
        concepts.add(concept)
    
    return concepts

def extract_concepts_from_cases(cases):
    """
    Extract potential ontology concepts from cases.
    """
    concepts = defaultdict(int)
    
    # Keywords likely to be concepts
    engineering_keywords = [
        "structural", "electrical", "mechanical", "civil", "environmental", 
        "inspection", "design", "consulting", "project management",
        "certification", "building", "construction", "code", "standard",
        "safety", "integrity", "hazard", "risk", "violation", "deficiency"
    ]
    
    ethics_keywords = [
        "confidentiality", "conflict of interest", "competence", "honesty",
        "integrity", "transparency", "disclosure", "whistleblowing", "obligation",
        "responsibility", "duty", "principle", "code of ethics", "dilemma"
    ]
    
    role_keywords = [
        "engineer", "consultant", "inspector", "client", "owner", "authority",
        "building official", "regulatory official", "contractor", "stakeholder"
    ]
    
    # Combine all keywords
    keywords = engineering_keywords + ethics_keywords + role_keywords
    
    # Check case texts for these keywords
    for case in cases:
        text = case.get('full_text', '') or case.get('html_content', '')
        # Convert HTML content to plain text
        if '<' in text and '>' in text:
            text = re.sub('<[^<]+?>', ' ', text)
        
        # Check for keywords
        for keyword in keywords:
            if keyword.lower() in text.lower():
                concepts[keyword] += 1
        
        # Also check metadata
        metadata = case.get('metadata', {})
        for principle in metadata.get('principles', []):
            concepts[principle] += 1
        
        for code in metadata.get('codes_cited', []):
            concepts[code] += 1
    
    return dict(concepts)

def sanitize_concept_name(name):
    """
    Convert a concept name to a valid ontology class name.
    """
    # Replace spaces and special characters with underscore
    name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    # Ensure first character is a letter and capitalized
    if name and not name[0].isalpha():
        name = 'C_' + name
    # Capitalize first letter
    name = name[0].upper() + name[1:]
    return name

def generate_ontology_extension(concepts_to_add, existing_concepts):
    """
    Generate TTL content for extending the ontology with new concepts.
    """
    extension = []
    
    # Add header
    extension.append("\n#################################################################")
    extension.append("#    Additional NSPE Case Concepts")
    extension.append("#################################################################\n")
    
    # Role concepts
    role_concepts = [concept for concept in concepts_to_add if "engineer" in concept.lower() or 
                    "consultant" in concept.lower() or "inspector" in concept.lower() or
                    "official" in concept.lower() or "client" in concept.lower()]
    
    if role_concepts:
        extension.append("\n# Additional Role Types")
        for concept in role_concepts:
            concept_name = sanitize_concept_name(concept)
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name}Role rdf:type owl:Class ;")
                extension.append(f"    rdf:type :EntityType ;")
                extension.append(f"    rdf:type :Role ;")
                extension.append(f"    rdfs:subClassOf :EngineeringRole ;")
                extension.append(f"    rdfs:label \"{concept} Role\"@en ;")
                extension.append(f"    rdfs:comment \"The role of {concept.lower()} in engineering practice\"@en .")
                extension.append("")
    
    # Ethical principle concepts
    principle_concepts = [concept for concept in concepts_to_add if "integrity" in concept.lower() or 
                         "honesty" in concept.lower() or "conflict" in concept.lower() or
                         "responsibility" in concept.lower() or "obligation" in concept.lower() or
                         "duty" in concept.lower() or "principle" in concept.lower()]
    
    if principle_concepts:
        extension.append("\n# Additional Ethical Principles")
        for concept in principle_concepts:
            concept_name = sanitize_concept_name(concept)
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name}Principle rdf:type owl:Class ;")
                extension.append(f"    rdf:type :EntityType ;")
                extension.append(f"    rdf:type :ConditionType ;")
                extension.append(f"    rdfs:subClassOf :EngineeringEthicalPrinciple ;")
                extension.append(f"    rdfs:label \"{concept} Principle\"@en ;")
                extension.append(f"    rdfs:comment \"The principle of {concept.lower()} in engineering ethics\"@en .")
                extension.append("")
    
    # Dilemma concepts
    dilemma_concepts = [concept for concept in concepts_to_add if "dilemma" in concept.lower() or 
                       "conflict" in concept.lower() or "vs" in concept.lower() or
                       "versus" in concept.lower()]
    
    if dilemma_concepts:
        extension.append("\n# Additional Ethical Dilemmas")
        for concept in dilemma_concepts:
            concept_name = sanitize_concept_name(concept)
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name}Dilemma rdf:type owl:Class ;")
                extension.append(f"    rdf:type :EntityType ;")
                extension.append(f"    rdf:type :ConditionType ;")
                extension.append(f"    rdfs:subClassOf :EngineeringEthicalDilemma ;")
                extension.append(f"    rdfs:label \"{concept} Dilemma\"@en ;")
                extension.append(f"    rdfs:comment \"A dilemma involving {concept.lower()} in engineering practice\"@en .")
                extension.append("")
    
    # Engineering condition concepts
    condition_concepts = [concept for concept in concepts_to_add if "hazard" in concept.lower() or 
                         "risk" in concept.lower() or "violation" in concept.lower() or
                         "deficiency" in concept.lower() or "safety" in concept.lower()]
    
    if condition_concepts:
        extension.append("\n# Additional Engineering Conditions")
        for concept in condition_concepts:
            concept_name = sanitize_concept_name(concept)
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name} rdf:type owl:Class ;")
                extension.append(f"    rdf:type :EntityType ;")
                extension.append(f"    rdf:type :ConditionType ;")
                extension.append(f"    rdfs:subClassOf :EngineeringCondition ;")
                extension.append(f"    rdfs:label \"{concept}\"@en ;")
                extension.append(f"    rdfs:comment \"A condition involving {concept.lower()} in engineering practice\"@en .")
                extension.append("")
    
    # Resource concepts
    resource_concepts = [concept for concept in concepts_to_add if "document" in concept.lower() or 
                        "report" in concept.lower() or "drawing" in concept.lower() or
                        "specification" in concept.lower() or "code" in concept.lower() or
                        "standard" in concept.lower()]
    
    if resource_concepts:
        extension.append("\n# Additional Engineering Resources")
        for concept in resource_concepts:
            concept_name = sanitize_concept_name(concept)
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name} rdf:type owl:Class ;")
                extension.append(f"    rdf:type :EntityType ;")
                extension.append(f"    rdf:type :ResourceType ;")
                extension.append(f"    rdfs:subClassOf :EngineeringResource ;")
                extension.append(f"    rdfs:label \"{concept}\"@en ;")
                extension.append(f"    rdfs:comment \"A resource involving {concept.lower()} in engineering practice\"@en .")
                extension.append("")
    
    # NSPE-specific code concepts
    code_concepts = [concept for concept in concepts_to_add if "Code" in concept]
    
    if code_concepts:
        extension.append("\n# NSPE Code Sections")
        for concept in code_concepts:
            concept_name = concept.replace('.', '_').replace(' ', '_')
            if f":{concept_name}" not in existing_concepts:
                extension.append(f":{concept_name} rdf:type owl:Class ;")
                extension.append(f"    rdfs:subClassOf :NSPECodeSection ;")
                extension.append(f"    rdfs:label \"{concept}\"@en ;")
                extension.append(f"    rdfs:comment \"Section {concept} of the NSPE Code of Ethics\"@en .")
                extension.append("")
    
    return "\n".join(extension)

def extend_ontology(base_ontology_file, nspe_cases_file, output_file):
    """
    Extend the ontology with concepts from NSPE cases.
    """
    # Load the cases
    cases = load_nspe_cases(nspe_cases_file)
    if not cases:
        print("No cases found. Exiting.")
        return False
    
    # Load the base ontology
    base_ontology = load_ontology(base_ontology_file)
    if not base_ontology:
        print("Base ontology not found. Exiting.")
        return False
    
    # Also load NSPE engineering ethics ontology if it exists
    nspe_ontology = ""
    nspe_ontology_file = "mcp/ontology/nspe-engineering-ethics.ttl"
    if os.path.exists(nspe_ontology_file):
        nspe_ontology = load_ontology(nspe_ontology_file)
    
    # Extract existing concepts
    existing_concepts = extract_concepts_from_ontology(base_ontology)
    if nspe_ontology:
        existing_concepts.update(extract_concepts_from_ontology(nspe_ontology))
    
    # Extract concepts from cases
    case_concepts = extract_concepts_from_cases(cases)
    
    # Identify concepts to add
    concepts_to_add = [concept for concept, count in case_concepts.items() 
                      if count >= 2 and f":{sanitize_concept_name(concept)}" not in existing_concepts]
    
    print(f"Found {len(existing_concepts)} existing concepts")
    print(f"Found {len(case_concepts)} potential concepts in cases")
    print(f"Will add {len(concepts_to_add)} new concepts to the ontology")
    
    # Generate ontology extension
    extension = generate_ontology_extension(concepts_to_add, existing_concepts)
    
    # Merge with base ontology and write to output file
    with open(output_file, 'w') as f:
        f.write(base_ontology)
        f.write("\n")
        f.write(extension)
    
    print(f"Extended ontology written to {output_file}")
    return True

def main():
    """
    Main function to extend the engineering ethics ontology.
    """
    print("===== Extending Engineering Ethics Ontology =====")
    
    # Default file paths
    base_ontology = ENGINEERING_ETHICS_ONTOLOGY
    nspe_cases = NSPE_CASES_FILE
    output_file = OUTPUT_ONTOLOGY
    
    # Process command line arguments
    if len(sys.argv) > 1:
        base_ontology = sys.argv[1]
    if len(sys.argv) > 2:
        nspe_cases = sys.argv[2]
    if len(sys.argv) > 3:
        output_file = sys.argv[3]
    
    # Extend the ontology
    if extend_ontology(base_ontology, nspe_cases, output_file):
        print("Ontology extension completed successfully.")
    else:
        print("Failed to extend ontology.")

if __name__ == "__main__":
    main()
