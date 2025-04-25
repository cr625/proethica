#!/usr/bin/env python3
"""
Script to fix syntax errors in the ontology TTL content stored in the database.
This script identifies and repairs common syntax errors in Turtle RDF syntax.
"""
import os
import sys
import re
from rdflib import Graph

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from app
from app import create_app, db
from app.models.ontology import Ontology

def fix_ttl_syntax(ttl_content):
    """
    Fix common syntax errors in Turtle RDF content.
    
    Args:
        ttl_content (str): Original TTL content with potential syntax errors
        
    Returns:
        str: Fixed TTL content
    """
    # Make a copy of the content
    fixed_content = ttl_content
    
    # Fix specific syntax issues based on what we've seen
    
    # Fix 1: Fix missing dots at the end of statements
    # This is the error we saw: "expected '.' or '}' or ']' at end of statement"
    fixed_content = re.sub(r'rdfs:label "Engineering Capability"@en \s*\n', 
                          r'rdfs:label "Engineering Capability"@en ;\n', 
                          fixed_content)
    
    # Fix 2: Fix broken string literals with newlines
    # This specifically fixes the "Engineering ;\n Ethics Ontology" issue
    fixed_content = re.sub(r'rdfs:label "Engineering ;\s*\n\s*Ethics Ontology"@en', 
                          r'rdfs:label "Engineering Ethics Ontology"@en', 
                          fixed_content)
    
    # Fix 3: Make sure all subject-predicate-object statements are properly terminated
    lines = fixed_content.split("\n")
    result_lines = []
    
    # Process each line
    for i, line in enumerate(lines):
        # Skip empty lines or lines that are just comments
        if not line.strip() or line.strip().startswith('#'):
            result_lines.append(line)
            continue
            
        # Skip lines that already end with proper terminators
        if line.strip().endswith('.') or line.strip().endswith(';') or line.strip().endswith(','):
            result_lines.append(line)
            continue
            
        # Check if this is the last line of a block that should end with a period
        if i < len(lines) - 1 and not lines[i+1].strip().startswith((' ', '\t')):
            # This is the last line of a statement block - should end with a period
            result_lines.append(line + ' .')
        elif i < len(lines) - 1 and lines[i+1].strip() and not line.strip().endswith(':'):
            # This is a continued statement - should end with a semicolon
            result_lines.append(line + ' ;')
        else:
            result_lines.append(line)
    
    fixed_content = '\n'.join(result_lines)
    
    # Fix 4: Fix misplaced quotes or other common Turtle syntax errors
    # Look for lines with ^ syntax errors
    fixed_content = re.sub(r'\s+\^\s*([a-zA-Z])', r' ;\n    \1', fixed_content)
    
    # Fix 5: Fix misplaced quotes that appear in string literals
    # Look for patterns like "string"string" or "string\" and fix them
    fixed_content = re.sub(r'"([^"]*)"([^"]*)"', r'"\1\2"', fixed_content)
    
    return fixed_content

def fix_ontology_syntax():
    """
    Fix syntax in all ontologies or a specific one by ID.
    """
    print("Starting ontology syntax repair")
    
    app = create_app()
    with app.app_context():
        # Get the ontology with ID 1
        ontology = Ontology.query.get(1)
        if not ontology:
            print("Ontology with ID 1 not found!")
            return
            
        print(f"Processing ontology: {ontology.name}")
        print(f"Domain ID: {ontology.domain_id}")
        print(f"Original content length: {len(ontology.content) if ontology.content else 'None'}")
        
        if not ontology.content:
            print("No content to fix!")
            return
        
        # Try to parse the original content to identify errors
        print("Validating original content...")
        original_issues = validate_ttl(ontology.content)
        
        if not original_issues:
            print("Original content already valid! No fixes needed.")
            return
        
        print("Original content has syntax issues.")
        print("Attempting to fix...")
        
        # Fix the content
        fixed_content = fix_ttl_syntax(ontology.content)
        
        # Validate the fixed content
        print("Validating fixed content...")
        fixed_issues = validate_ttl(fixed_content)
        
        if not fixed_issues:
            print("Syntax fixes were successful! Content is now valid.")
            print(f"Fixed content length: {len(fixed_content)}")
            
            # Save the fixed content
            print("Saving fixed content to database...")
            ontology.content = fixed_content
            db.session.commit()
            print("Fixed content saved.")
            
            return True
        else:
            print("Syntax issues still exist after attempted fix.")
            print("You may need to manually edit the ontology content.")
            
            # Show the remaining issues
            print("Issues found:")
            for issue in fixed_issues:
                print(f"  - {issue}")
            
            return False

def validate_ttl(ttl_content):
    """
    Validate TTL content and return a list of issues found.
    
    Args:
        ttl_content: TTL content to validate
        
    Returns:
        list: List of validation error messages, or empty list if valid
    """
    issues = []
    
    try:
        g = Graph()
        g.parse(data=ttl_content, format="turtle")
        print(f"Successfully parsed TTL content. Graph contains {len(g)} triples.")
    except Exception as e:
        print(f"Error parsing TTL: {str(e)}")
        issues.append(str(e))
    
    return issues

if __name__ == "__main__":
    fixed = fix_ontology_syntax()
    if fixed:
        print("Ontology syntax fixed successfully!")
    else:
        print("Ontology syntax repairs were not fully successful. Manual editing may be required.")
