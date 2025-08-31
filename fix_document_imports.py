#!/usr/bin/env python3
"""
Fix incorrect Document imports throughout the application.
Changes 'from app.models.document import Document' to 'from app.models import Document'
"""

import os
import re

def fix_imports_in_file(filepath):
    """Fix Document imports in a single file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Pattern to match the incorrect import
        pattern = r'from app\.models\.document import (Document[^,\n]*)'
        
        # Check if file has the incorrect import
        if re.search(pattern, content):
            # Replace with correct import
            new_content = re.sub(
                r'from app\.models\.document import Document\b',
                'from app.models import Document',
                content
            )
            
            # Handle DocumentChunk and other imports
            new_content = re.sub(
                r'from app\.models\.document import Document, DocumentChunk',
                'from app.models import Document, DocumentChunk',
                new_content
            )
            
            # Handle imports with PROCESSING_STATUS
            new_content = re.sub(
                r'from app\.models\.document import Document, PROCESSING_STATUS',
                'from app.models import Document\nfrom app.models.document import PROCESSING_STATUS',
                new_content
            )
            
            new_content = re.sub(
                r'from app\.models\.document import Document, DocumentChunk, PROCESSING_STATUS',
                'from app.models import Document, DocumentChunk\nfrom app.models.document import PROCESSING_STATUS',
                new_content
            )
            
            new_content = re.sub(
                r'from app\.models\.document import Document, PROCESSING_STATUS, PROCESSING_PHASES',
                'from app.models import Document\nfrom app.models.document import PROCESSING_STATUS, PROCESSING_PHASES',
                new_content
            )
            
            # Write back if changed
            if new_content != content:
                with open(filepath, 'w') as f:
                    f.write(new_content)
                return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False
    return False

def main():
    """Fix all Document imports in the app directory."""
    fixed_files = []
    
    # Walk through app directory
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_imports_in_file(filepath):
                    fixed_files.append(filepath)
                    print(f"Fixed: {filepath}")
    
    print(f"\nTotal files fixed: {len(fixed_files)}")
    
    if fixed_files:
        print("\nFixed files:")
        for f in sorted(fixed_files):
            print(f"  - {f}")

if __name__ == "__main__":
    main()
