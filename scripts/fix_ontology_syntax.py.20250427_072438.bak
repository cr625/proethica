#!/usr/bin/env python3
"""
Script to fix syntax errors in the ontology TTL files.
"""

import os
import re
import sys
from pathlib import Path

def fix_intermediate_ontology():
    """Fix syntax issues in the intermediate ontology file."""
    file_path = 'mcp/ontology/proethica-intermediate.ttl'
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Make a backup
        backup_path = f"{file_path}.bak"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created backup at: {backup_path}")
        
        # Fix common issues
        
        # 1. Add missing periods at the end of triple blocks
        content = re.sub(r'(\.\s*\n*)([a-zA-Z#:])', r'.\n\n\2', content)
        
        # 2. Ensure proper spacing between statements
        content = re.sub(r'(\.)\s*(:)', r'.\n\n\2', content)
        
        # 3. Clean up potential trailing semicolons followed by periods (invalid syntax)
        content = re.sub(r';\s*\.', r'.', content)
        
        # 4. Fix specific issues with action properties that may have errors
        action_duration_pattern = r'(:actionDuration rdf:type owl:DatatypeProperty[^.]*\.)'
        action_duration_match = re.search(action_duration_pattern, content, re.DOTALL)
        
        if action_duration_match:
            fixed_prop = """
:actionDuration rdf:type owl:DatatypeProperty ;
    rdfs:domain :Action ;
    rdfs:range xsd:duration ;
    rdfs:label "action duration"@en ;
    rdfs:comment "Indicates how long an action takes"@en .
"""
            content = content.replace(action_duration_match.group(1), fixed_prop)
        
        # Write the fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Successfully fixed: {file_path}")
        return True
    
    except Exception as e:
        print(f"Error fixing ontology file: {str(e)}")
        return False

def main():
    """Main function to fix ontology files."""
    success = fix_intermediate_ontology()
    
    if success:
        print("\nNext steps:")
        print("1. Restart the MCP server")
        print("2. Verify ontology loading with the test script:")
        print("   python scripts/test_ontology_extraction.py proethica-intermediate.ttl")
    
if __name__ == "__main__":
    main()
