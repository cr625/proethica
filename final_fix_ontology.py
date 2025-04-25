#!/usr/bin/env python3
"""
Script to fix specific syntax errors in the ontology TTL content stored in the database.
This script targets known issues in the engineering-ethics-nspe-extended ontology.
"""
import os
import sys
import re
import tempfile
from rdflib import Graph

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from app
from app import create_app, db
from app.models.ontology import Ontology

def fix_ontology_in_db(ontology_id=1):
    """
    Fix the ontology syntax in the database.
    
    Args:
        ontology_id: ID of the ontology to fix (default: 1)
        
    Returns:
        bool: True if fixed successfully, False otherwise
    """
    app = create_app()
    with app.app_context():
        # Get the ontology from the database
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Error: Ontology with ID {ontology_id} not found!")
            return False
        
        print(f"Found ontology: {ontology.name}")
        print(f"Domain ID: {ontology.domain_id}")
        
        # Validate original content
        print("Validating original content...")
        is_valid, error = validate_turtle_content(ontology.content)
        if is_valid:
            print("Original content is already valid! No fixes needed.")
            return True
        
        print(f"Original content has syntax errors: {error}")
        
        # Apply targeted fixes
        print("Applying fixes...")
        fixed_content = apply_specific_fixes(ontology.content)
        
        # Validate fixed content
        print("Validating fixed content...")
        is_valid, error = validate_turtle_content(fixed_content)
        if not is_valid:
            print(f"Failed to fix all syntax errors: {error}")
            
            # Save the partially fixed content to a file for debugging
            with open("failed_ontology_fix.ttl", "w") as f:
                f.write(fixed_content)
            
            print("Partially fixed content saved to failed_ontology_fix.ttl")
            return False
        
        # Save the fixed content to the database
        print("Syntax fixes successful! Saving to database...")
        ontology.content = fixed_content
        db.session.commit()
        print("Fixed ontology saved to database.")
        
        return True

def validate_turtle_content(content):
    """
    Validate Turtle content using rdflib.
    
    Args:
        content: Turtle content to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Create a temporary file for validation
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Parse the content with rdflib
            g = Graph()
            g.parse(tmp_path, format="turtle")
            triples_count = len(g)
            print(f"Successfully parsed content. Graph contains {triples_count} triples.")
            return True, None
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        return False, str(e)

def apply_specific_fixes(content):
    """
    Apply specific fixes to the ontology content based on the known issues.
    
    Args:
        content: Original ontology content
        
    Returns:
        str: Fixed ontology content
    """
    # Fix 1: Fix missing semicolon after rdfs:label "Engineering Capability"@en
    content = content.replace(
        'rdfs:label "Engineering Capability"@en \n',
        'rdfs:label "Engineering Capability"@en ;\n'
    )
    
    # Fix 2: Fix newline in "Engineering Ethics Ontology" string
    content = re.sub(
        r'rdfs:label "Engineering\s*;?\s*\n\s*Ethics Ontology"@en',
        r'rdfs:label "Engineering Ethics Ontology"@en',
        content
    )
    
    # Fix 3: Fix issues with New Engineering Roles section at line 508
    # Replace problematic role declarations
    role_pattern = r':RegulatoryEngineerRole a proeth:EntityType,\s*\n\s*proeth:Role, ;'
    fixed_role = ':RegulatoryEngineerRole rdf:type proeth:EntityType, proeth:Role ;'
    content = re.sub(role_pattern, fixed_role, content)
    
    # Fix similar patterns for other roles in that section
    content = re.sub(
        r'(:PublicHealthCondition|:DesignDrawings|:DisclosurePrinciple|:ObjectivityPrinciple|'
        r':FutureImpactsPrinciple|:ConflictOfInterestDilemma|:RegulationVsPublicSafetyDilemma|'
        r':ProfessionalResponsibilityDilemma) a (proeth:[A-Za-z]+),\s*\n\s*(proeth:[A-Za-z]+), ;',
        r'\1 rdf:type \2, \3 ;',
        content
    )
    
    # Fix 4: Add missing periods at the end of statement blocks
    lines = content.split('\n')
    result = []
    for i in range(len(lines)):
        line = lines[i]
        result.append(line)
        
        # If this is the last line of a block that's not properly terminated
        if (i < len(lines) - 1 and 
            line.strip() and not line.strip().endswith(('.', ';', ',')) and
            (not lines[i+1].strip() or not lines[i+1].strip()[0].isspace())):
            # Add a period
            result[-1] = result[-1] + ' .'
    
    content = '\n'.join(result)
    
    # Fix 5: Fix any remaining rdf:type vs 'a' inconsistencies in properties
    # This standardizes on using rdf:type instead of 'a' to avoid confusion
    content = re.sub(r'\sa\s+([a-zA-Z0-9:]+)', r' rdf:type \1', content)
    
    return content

if __name__ == "__main__":
    # Get ontology ID from command line or use default
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print(f"Using default ID: {ontology_id}")
    
    # Fix the ontology
    if fix_ontology_in_db(ontology_id):
        print("\nSuccess! The ontology has been fixed.")
        print("You should now restart the server with: ./restart_server.sh")
    else:
        print("\nFailed to fix all ontology syntax issues.")
        print("Please check the error messages and manually fix any remaining issues.")
