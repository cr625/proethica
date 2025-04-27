#!/usr/bin/env python3
"""
Script to automatically fix syntax errors in the ontology content stored in the database.
This script applies targeted fixes for known issues and updates the database directly.
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

class OntologySyntaxFixer:
    def __init__(self):
        self.app = create_app()
        self.fixes_applied = []
    
    def get_ontology(self, ontology_id):
        """Get ontology from database."""
        with self.app.app_context():
            ontology = Ontology.query.get(ontology_id)
            if not ontology:
                return None
            return ontology
    
    def save_ontology(self, ontology, content):
        """Save updated content to database."""
        with self.app.app_context():
            ontology.content = content
            db.session.commit()
            return True
    
    def validate_turtle(self, content):
        """Validate Turtle content using rdflib."""
        try:
            # Use a temporary file for validation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                g = Graph()
                g.parse(tmp_path, format="turtle")
                triples_count = len(g)
                return True, triples_count, []
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            return False, 0, [str(e)]
    
    def fix_syntax(self, content):
        """Apply multiple fix strategies to correct Turtle syntax."""
        original_content = content
        
        # Fix 1: Fix missing semicolons after certain patterns
        patterns = [
            # Fix missing semicolon after rdfs:label with English tag
            (r'(rdfs:label "[^"]*"@en)\s*\n', r'\1 ;\n'),
            # Fix missing semicolon after rdfs:comment with English tag
            (r'(rdfs:comment "[^"]*"@en)\s*\n', r'\1 ;\n'),
            # Fix the specific issue with Engineering Capability
            (r'rdfs:label "Engineering Capability"@en\s*\n', r'rdfs:label "Engineering Capability"@en ;\n'),
        ]
        
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                self.fixes_applied.append(f"Fixed missing semicolons in pattern: {pattern}")
                content = new_content
        
        # Fix 2: Fix string literals with newlines
        # This is trickier as we need to join multi-line literals
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            # Look for lines with an opening quote but no closing quote
            # or with a string spanning multiple lines
            if re.search(r'rdfs:label\s+"[^"]*$', line) or re.search(r'rdfs:comment\s+"[^"]*$', line):
                j = i + 1
                while j < len(lines) and '"' not in lines[j]:
                    j += 1
                
                if j < len(lines) and '"' in lines[j]:
                    # Found a multi-line string, join it
                    joined_line = line
                    
                    for k in range(i+1, j+1):
                        joined_line += ' ' + lines[k].strip()
                    
                    # Replace newlines and spaces with a single space
                    joined_line = re.sub(r'\s+', ' ', joined_line)
                    
                    # Update the current line
                    lines[i] = joined_line
                    
                    # Remove the other lines
                    for k in range(i+1, j+1):
                        lines[k] = ''
                    
                    self.fixes_applied.append(f"Fixed multi-line string at line {i+1}")
                
            i += 1
        
        # Rejoin the lines, skipping empty ones
        content = '\n'.join(line for line in lines if line)
        
        # Fix 3: Fix the specific issue with "Engineering Ethics Ontology" that has newline
        content = re.sub(
            r'rdfs:label "Engineering\s*;?\s*\n\s*Ethics Ontology"@en', 
            r'rdfs:label "Engineering Ethics Ontology"@en', 
            content
        )
        
        # Fix 4: Ensure property-value pairs are properly terminated
        # Add semicolons between property-value pairs
        content = re.sub(
            r'([a-zA-Z0-9:]+\s+[^;\.]+)\n\s+([a-zA-Z0-9:]+)', 
            r'\1 ;\n    \2', 
            content
        )
        
        # Fix 5: Fix missing periods at the end of blocks
        content = re.sub(
            r'([^\.;,\s])\s*\n\n', 
            r'\1 .\n\n', 
            content
        )
        
        # Fix 6: Fix rdfs:subClassOf lines that don't end with semicolons
        content = re.sub(
            r'(rdfs:subClassOf [^;\.]+)\s*\n',
            r'\1 ;\n',
            content
        )
        
        # Fix 7: Fix any remaining known issues
        # Add more specific fixes here if validation still fails
        
        if original_content == content:
            self.fixes_applied.append("No syntax issues found or fixed")
            
        return content
    
    def process_ontology(self, ontology_id):
        """Process ontology, applying fixes and updating if valid."""
        print(f"Processing ontology with ID {ontology_id}...")
        
        # Get the ontology from database
        ontology = self.get_ontology(ontology_id)
        if not ontology:
            print(f"Ontology with ID {ontology_id} not found")
            return False
        
        print(f"Ontology name: {ontology.name}")
        print(f"Domain ID: {ontology.domain_id}")
        
        original_content = ontology.content
        if not original_content:
            print("Ontology has no content!")
            return False
        
        # Validate original content
        print("Validating original content...")
        original_valid, original_triples, original_issues = self.validate_turtle(original_content)
        
        if original_valid:
            print("Original ontology is already valid! No fixes needed.")
            print(f"Contains {original_triples} triples.")
            return True
        
        print("Original ontology has syntax issues:")
        for issue in original_issues:
            print(f"  - {issue}")
        
        # Apply fixes
        print("\nApplying automatic fixes...")
        fixed_content = self.fix_syntax(original_content)
        
        # Validate fixed content
        print("Validating fixed ontology...")
        fixed_valid, fixed_triples, fixed_issues = self.validate_turtle(fixed_content)
        
        if not fixed_valid:
            print("Automatic fixes were not sufficient. Issues remain:")
            for issue in fixed_issues:
                print(f"  - {issue}")
            
            # Save the partially fixed content to a file for inspection
            output_file = "partially_fixed_ontology.ttl"
            with open(output_file, "w") as f:
                f.write(fixed_content)
            print(f"\nPartially fixed content saved to {output_file}")
            print("You may need to manually fix the remaining issues.")
            
            return False
        
        print("Ontology fixed successfully!")
        print(f"Contains {fixed_triples} triples.")
        print("\nFixes applied:")
        for fix in self.fixes_applied:
            print(f"  - {fix}")
        
        # Save to database
        print("\nSaving fixed ontology to database...")
        if self.save_ontology(ontology, fixed_content):
            print("Ontology updated successfully in the database.")
            return True
        else:
            print("Failed to update ontology in database.")
            return False

def main():
    fixer = OntologySyntaxFixer()
    
    # Process ontology with ID 1 by default
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print(f"Using default ID: {ontology_id}")
    
    success = fixer.process_ontology(ontology_id)
    
    if success:
        print("\nProcess completed successfully!")
        print("You should now restart the server with: ./restart_server.sh")
    else:
        print("\nProcess completed with issues. See above for details.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
