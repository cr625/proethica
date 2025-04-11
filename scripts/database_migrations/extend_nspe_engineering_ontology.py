#!/usr/bin/env python3
"""
Script to extend the NSPE engineering ethics ontology with specific concepts
needed for the newly added cases.
"""

import sys
import os
import re

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Constants
INPUT_ONTOLOGY = "mcp/ontology/engineering-ethics-enhanced.ttl"
OUTPUT_ONTOLOGY = "mcp/ontology/engineering-ethics-nspe-extended.ttl"

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
    class_pattern = r':([A-Za-z0-9]+)\s+a\s+owl:Class'
    for match in re.finditer(class_pattern, ontology_text):
        concept = ':' + match.group(1)
        concepts.add(concept)
    
    # Also check for rdf:type owl:Class pattern
    type_pattern = r':([A-Za-z0-9]+)\s+rdf:type\s+owl:Class'
    for match in re.finditer(type_pattern, ontology_text):
        concept = ':' + match.group(1)
        concepts.add(concept)
    
    return concepts

def generate_ontology_extension():
    """
    Generate specific additions to the ontology based on the new NSPE cases.
    """
    extension = []
    
    # Add header
    extension.append("\n#################################################################")
    extension.append("#    Additional NSPE Case Concepts")
    extension.append("#################################################################\n")
    
    # Add new role concepts
    extension.append("\n# New Engineering Roles")
    
    # PeerReviewerRole already exists in the ontology
    extension.append("""
:RegulatoryEngineerRole a proeth:EntityType,
        proeth:Role,
        owl:Class ;
    rdfs:label "Regulatory Engineer Role"@en ;
    rdfs:comment "The role of an engineer who works for a regulatory agency or in regulatory compliance"@en ;
    rdfs:subClassOf :EngineeringRole .""")
    
    # Add new condition concepts
    extension.append("\n\n# New Engineering Conditions")
    
    # WaterQualityCondition and ClimateChangeCondition already exist in the ontology
    extension.append("""
:PublicHealthCondition a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Public Health Condition"@en ;
    rdfs:comment "A condition related to public health that requires engineering assessment or intervention"@en ;
    rdfs:subClassOf :EngineeringCondition .""")
    
    # Add new resource concepts
    extension.append("\n\n# New Engineering Resources")
    
    # AsBuiltDrawings already exists in the ontology
    extension.append("""
:DesignDrawings a proeth:EntityType,
        proeth:ResourceType,
        owl:Class ;
    rdfs:label "Design Drawings"@en ;
    rdfs:comment "Engineering drawings showing design specifications"@en ;
    rdfs:subClassOf :EngineeringDocument .""")
    
    # Add new ethical principles
    extension.append("\n\n# New Ethical Principles")
    
    extension.append("""
:DisclosurePrinciple a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Disclosure Principle"@en ;
    rdfs:comment "The principle that engineers should disclose relevant information to affected parties"@en ;
    rdfs:subClassOf :EngineeringEthicalPrinciple .

:ObjectivityPrinciple a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Objectivity Principle"@en ;
    rdfs:comment "The principle that engineers should maintain objectivity in their professional judgments"@en ;
    rdfs:subClassOf :EngineeringEthicalPrinciple .

:FutureImpactsPrinciple a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Future Impacts Principle"@en ;
    rdfs:comment "The principle that engineers should consider future impacts of their work beyond immediate requirements"@en ;
    rdfs:subClassOf :EngineeringEthicalPrinciple .""")
    
    # Add new dilemmas
    extension.append("\n\n# New Ethical Dilemmas")
    
    extension.append("""
:ConflictOfInterestDilemma a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Conflict of Interest Dilemma"@en ;
    rdfs:comment "A dilemma where an engineer must navigate conflicting interests in professional practice"@en ;
    rdfs:subClassOf :EngineeringEthicalDilemma .

:RegulationVsPublicSafetyDilemma a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Regulation vs Public Safety Dilemma"@en ;
    rdfs:comment "A dilemma where existing regulations conflict with broader public safety considerations"@en ;
    rdfs:subClassOf :EngineeringEthicalDilemma .

:ProfessionalResponsibilityDilemma a proeth:ConditionType,
        proeth:EntityType,
        owl:Class ;
    rdfs:label "Professional Responsibility Dilemma"@en ;
    rdfs:comment "A dilemma where an engineer must determine the extent of their professional responsibility"@en ;
    rdfs:subClassOf :EngineeringEthicalDilemma .""")
    
    return "\n".join(extension)

def extend_ontology(input_file, output_file):
    """
    Extend the ontology with specific NSPE case concepts.
    """
    # Load the base ontology
    base_ontology = load_ontology(input_file)
    if not base_ontology:
        print("Base ontology not found. Exiting.")
        return False
    
    # Extract existing concepts
    existing_concepts = extract_concepts_from_ontology(base_ontology)
    print(f"Found {len(existing_concepts)} existing concepts in the ontology")
    
    # Generate specific extensions
    extension = generate_ontology_extension()
    
    # Merge with base ontology and write to output file
    with open(output_file, 'w') as f:
        f.write(base_ontology)
        f.write("\n")
        f.write(extension)
    
    print(f"Extended ontology written to {output_file}")
    print("Added the following concept types:")
    print("- 1 engineering role")
    print("- 1 engineering condition")
    print("- 1 engineering resource")
    print("- 3 ethical principles")
    print("- 3 ethical dilemmas")
    return True

def main():
    """
    Main function to extend the engineering ethics ontology.
    """
    print("===== Extending NSPE Engineering Ethics Ontology =====")
    
    # Default file paths
    input_file = INPUT_ONTOLOGY
    output_file = OUTPUT_ONTOLOGY
    
    # Process command line arguments
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    # Extend the ontology
    if extend_ontology(input_file, output_file):
        print("Ontology extension completed successfully.")
    else:
        print("Failed to extend ontology.")

if __name__ == "__main__":
    main()
