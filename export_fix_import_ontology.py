#!/usr/bin/env python3
"""
Script to export an ontology from the database, fix its syntax issues,
and re-import it into the database.

This script will:
1. Export the ontology with the specified ID from the database to a file
2. Attempt automatic syntax fixes
3. Use a proper Turtle syntax validator (via rdflib)
4. Allow manual editing of the file
5. Import the fixed ontology back into the database
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from app
from app import create_app, db
from app.models.ontology import Ontology
from rdflib import Graph

def export_ontology(ontology_id, output_file):
    """
    Export ontology from the database to a file.
    
    Args:
        ontology_id: ID of the ontology to export
        output_file: Path to save the exported ontology
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Exporting ontology ID {ontology_id} to {output_file}...")
    
    app = create_app()
    with app.app_context():
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Error: Ontology with ID {ontology_id} not found!")
            return False
        
        print(f"Found ontology: {ontology.name}")
        print(f"Domain ID: {ontology.domain_id}")
        
        if not ontology.content:
            print("Error: Ontology has no content!")
            return False
        
        # Write content to file
        with open(output_file, 'w') as f:
            f.write(ontology.content)
        
        print(f"Ontology exported to {output_file}")
        print(f"Content length: {len(ontology.content)} characters")
        return True

def validate_turtle(ttl_file):
    """
    Validate a Turtle file and report any syntax issues.
    
    Args:
        ttl_file: Path to the Turtle file to validate
    
    Returns:
        tuple: (valid, issues) where valid is a boolean and issues is a list of error messages
    """
    print(f"Validating Turtle syntax in {ttl_file}...")
    
    issues = []
    try:
        g = Graph()
        g.parse(ttl_file, format="turtle")
        print(f"Successfully parsed TTL file. Graph contains {len(g)} triples.")
        return True, []
    except Exception as e:
        error_msg = f"Error parsing TTL: {str(e)}"
        print(error_msg)
        issues.append(error_msg)
        return False, issues

def import_ontology(ontology_id, input_file):
    """
    Import ontology from a file into the database.
    
    Args:
        ontology_id: ID of the ontology to update
        input_file: Path to the fixed ontology file
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Importing ontology from {input_file} into database for ID {ontology_id}...")
    
    try:
        # First validate the file
        valid, issues = validate_turtle(input_file)
        if not valid:
            print("Cannot import ontology with syntax errors:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        
        # Read the fixed content
        with open(input_file, 'r') as f:
            fixed_content = f.read()
        
        # Update the ontology in the database
        app = create_app()
        with app.app_context():
            ontology = Ontology.query.get(ontology_id)
            if not ontology:
                print(f"Error: Ontology with ID {ontology_id} not found!")
                return False
            
            print(f"Updating ontology: {ontology.name}")
            ontology.content = fixed_content
            db.session.commit()
            
            print(f"Ontology updated successfully!")
            return True
    except Exception as e:
        print(f"Error importing ontology: {str(e)}")
        return False

def main():
    # Get ontology ID from command line or use default
    ontology_id = 1  # Default to ID 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid ontology ID: {sys.argv[1]}")
            print(f"Using default ID: {ontology_id}")
    
    # Create temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define file paths
        export_path = os.path.join(temp_dir, f"ontology_{ontology_id}.ttl")
        
        # Export ontology to file
        if not export_ontology(ontology_id, export_path):
            return 1
        
        # Validate the original file
        valid, issues = validate_turtle(export_path)
        if valid:
            print("Ontology already has valid syntax! No fixes needed.")
            return 0
        
        print("\nOntology has syntax issues that need to be fixed.")
        print("Opening in editor for manual fixes...")
        
        # Create a copy for editing
        edit_path = export_path + ".edit"
        with open(export_path, 'r') as src:
            with open(edit_path, 'w') as dst:
                dst.write(src.read())
        
        # Open the file in the default editor and wait for it to close
        editor = os.environ.get('EDITOR', 'nano')  # Default to nano if no EDITOR is set
        subprocess.call([editor, edit_path])
        
        print("\nEditing complete. Validating fixed ontology...")
        valid, issues = validate_turtle(edit_path)
        
        if not valid:
            print("Fixed ontology still has syntax issues:")
            for issue in issues:
                print(f"  - {issue}")
            print("\nPlease fix the issues and try again.")
            print(f"The partially fixed file is at: {edit_path}")
            # Copy to a more permanent location
            fixed_path = os.path.join(os.getcwd(), f"fixed_ontology_{ontology_id}.ttl")
            with open(edit_path, 'r') as src:
                with open(fixed_path, 'w') as dst:
                    dst.write(src.read())
            print(f"A copy has been saved to: {fixed_path}")
            return 1
        
        print("Fixed ontology is valid!")
        
        # Ask for confirmation before importing
        print("\nReady to import the fixed ontology into the database.")
        response = input("Proceed? (y/n): ").strip().lower()
        if response != 'y':
            print("Import cancelled.")
            # Save a copy anyway
            fixed_path = os.path.join(os.getcwd(), f"fixed_ontology_{ontology_id}.ttl")
            with open(edit_path, 'r') as src:
                with open(fixed_path, 'w') as dst:
                    dst.write(src.read())
            print(f"A copy of the fixed ontology has been saved to: {fixed_path}")
            return 0
        
        # Import the fixed ontology
        if not import_ontology(ontology_id, edit_path):
            # Save a copy in case of failure
            fixed_path = os.path.join(os.getcwd(), f"fixed_ontology_{ontology_id}.ttl")
            with open(edit_path, 'r') as src:
                with open(fixed_path, 'w') as dst:
                    dst.write(src.read())
            print(f"A copy of the fixed ontology has been saved to: {fixed_path}")
            return 1
        
    print("\nProcess completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
