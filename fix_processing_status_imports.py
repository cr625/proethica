#!/usr/bin/env python3
"""
Fix all PROCESSING_STATUS import issues in the codebase.
"""

import os
import re

def fix_processing_status_imports():
    """Fix all imports of PROCESSING_STATUS from app.models to app.models.document"""
    
    # Files to fix (based on grep results)
    files_to_fix = [
        'app/routes/worlds.py',
        'app/routes/cases.py',
        'app/routes/cases_triple.py',
        'app/routes/cases_structure_update.py',
        'app/services/embedding_service.py'
    ]
    
    fixed_files = []
    skipped_files = []
    
    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            skipped_files.append(file_path)
            continue
            
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Pattern to match the problematic import
            pattern = r'from app\.models import ([^,\n]*,\s*)?PROCESSING_STATUS'
            
            # Check if the file has the problematic import
            if re.search(pattern, content):
                # Replace the import
                # Handle cases with just PROCESSING_STATUS
                content = re.sub(
                    r'from app\.models import PROCESSING_STATUS\b',
                    'from app.models.document import PROCESSING_STATUS',
                    content
                )
                
                # Handle cases with Document, PROCESSING_STATUS
                content = re.sub(
                    r'from app\.models import Document,\s*PROCESSING_STATUS\b',
                    'from app.models import Document\nfrom app.models.document import PROCESSING_STATUS',
                    content
                )
                
                # Handle cases with other imports before PROCESSING_STATUS
                content = re.sub(
                    r'from app\.models import ([^,\n]+),\s*PROCESSING_STATUS\b',
                    r'from app.models import \1\nfrom app.models.document import PROCESSING_STATUS',
                    content
                )
                
                # Write the fixed content back
                with open(file_path, 'w') as f:
                    f.write(content)
                
                print(f"✅ Fixed: {file_path}")
                fixed_files.append(file_path)
            else:
                print(f"ℹ️  No changes needed: {file_path}")
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            skipped_files.append(file_path)
    
    print("\n" + "="*50)
    print(f"Summary: Fixed {len(fixed_files)} files")
    if skipped_files:
        print(f"Skipped {len(skipped_files)} files: {', '.join(skipped_files)}")
    
    return len(fixed_files)

if __name__ == "__main__":
    print("Fixing PROCESSING_STATUS import issues...")
    print("="*50)
    
    num_fixed = fix_processing_status_imports()
    
    if num_fixed > 0:
        print(f"\n✅ Successfully fixed {num_fixed} files!")
        print("The application should now start without PROCESSING_STATUS import errors.")
    else:
        print("\n✅ No files needed fixing.")
