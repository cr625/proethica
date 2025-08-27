#!/usr/bin/env python3
"""
Script to add unified atomic splitting to all extractors that don't already have it.

This script modifies extractors in place to use the unified atomic splitting framework,
providing a consistent approach across all 9 concept types.
"""

import os
import re
import shutil
from pathlib import Path

# Define the extractors and their concept types
EXTRACTORS = {
    'actions.py': 'action',
    'capabilities.py': 'capability',
    'constraints.py': 'constraint', 
    'events.py': 'event',
    'obligations.py': 'obligation',
    'principles.py': 'principle',  # Already has it
    'resources.py': 'resource',
    'roles.py': 'role',
    'states.py': 'state'
}

EXTRACTION_DIR = Path("app/services/extraction")

def backup_file(file_path: Path) -> Path:
    """Create a backup of the original file."""
    backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
    shutil.copy2(file_path, backup_path)
    print(f"✅ Backed up {file_path} to {backup_path}")
    return backup_path

def has_unified_splitting(content: str) -> bool:
    """Check if file already has unified splitting."""
    return ('ENABLE_CONCEPT_SPLITTING' in content or 
            'split_concepts_for_extractor' in content or
            'AtomicExtractionMixin' in content)

def get_extractor_class_name(content: str) -> str:
    """Extract the extractor class name from the content."""
    match = re.search(r'class (\w+Extractor)', content)
    return match.group(1) if match else None

def add_atomic_mixin_import(content: str) -> str:
    """Add the AtomicExtractionMixin import."""
    # Look for existing base imports
    base_import_pattern = r'from \.base import (.+)'
    match = re.search(base_import_pattern, content)
    
    if match:
        # Add AtomicExtractionMixin to existing import
        imports = match.group(1)
        if 'AtomicExtractionMixin' not in imports:
            new_imports = imports + ', AtomicExtractionMixin' if not imports.endswith('\\') else imports + ',\\n    AtomicExtractionMixin'
            content = re.sub(base_import_pattern, f'from .base import {new_imports}', content)
            # Also add the mixin import
            content = re.sub(
                r'(from \.base import [^\\n]+\\n)',
                r'\\1from .atomic_extraction_mixin import AtomicExtractionMixin\n',
                content
            )
    else:
        # Add new import line
        pattern = r'(from \.base import ConceptCandidate[^\\n]*\\n)'
        replacement = r'\\1from .atomic_extraction_mixin import AtomicExtractionMixin\n'
        content = re.sub(pattern, replacement, content)
    
    return content

def add_mixin_to_class(content: str, class_name: str) -> str:
    """Add AtomicExtractionMixin to the extractor class."""
    # Pattern to match class definition
    class_pattern = f'class {class_name}\\(Extractor\\):'
    replacement = f'class {class_name}(Extractor, AtomicExtractionMixin):'
    
    if class_pattern in content:
        content = content.replace(class_pattern, replacement)
    
    return content

def add_concept_type_property(content: str, concept_type: str) -> str:
    """Add the concept_type property to the class."""
    # Find the end of __init__ method to insert the property
    init_pattern = r'(def __init__\(self[^}]+?\n        [^\\n]*\\n)'
    
    property_code = f'''
    @property
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        return '{concept_type}'
'''
    
    # Insert after __init__ method
    def replacement(match):
        return match.group(1) + property_code
    
    content = re.sub(init_pattern, replacement, content, flags=re.DOTALL)
    return content

def add_atomic_splitting_to_extract_method(content: str, concept_type: str) -> str:
    """Modify the extract method to use atomic splitting."""
    
    # Find the extract method
    extract_pattern = r'(def extract\\(self, text: str[^}]*?\\) -> List\\[ConceptCandidate\\]:.*?\\n)(.*?)(?=\\n    def |\\n\\nclass |\\n\\n\\n|\\Z)'
    
    def replacement(match):
        method_signature = match.group(1)
        method_body = match.group(2)
        
        # Check if it already has atomic splitting
        if 'apply_atomic_splitting' in method_body or 'split_concepts_for_extractor' in method_body:
            return match.group(0)  # Already has it
        
        # Create new method body with atomic splitting
        new_body = f'''        \"\"\"
        Extract {concept_type} concepts with unified atomic splitting.
        \"\"\"
        if not text:
            return []

        # Step 1: Initial extraction (preserve original logic)
        initial_candidates = self._extract_initial_concepts(text, world_id=world_id, guideline_id=guideline_id)
        
        # Step 2: Apply unified atomic splitting  
        return self._apply_atomic_splitting(initial_candidates)

    def _extract_initial_concepts(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        \"\"\"
        Initial {concept_type} extraction without atomic splitting.
        
        This preserves the original extraction logic.
        \"\"\"
{method_body}'''
        
        return method_signature + new_body
    
    content = re.sub(extract_pattern, replacement, content, flags=re.DOTALL)
    return content

def update_extractor_file(file_path: Path, concept_type: str) -> bool:
    """Update a single extractor file with unified atomic splitting."""
    
    print(f"\\n🔄 Processing {file_path.name} ({concept_type})...")
    
    # Read current content
    content = file_path.read_text(encoding='utf-8')
    
    # Check if already has unified splitting
    if has_unified_splitting(content):
        print(f"  ✅ Already has unified splitting - skipping")
        return False
    
    # Get class name
    class_name = get_extractor_class_name(content)
    if not class_name:
        print(f"  ❌ Could not find extractor class - skipping")
        return False
    
    print(f"  📝 Found class: {class_name}")
    
    # Make backup
    backup_file(file_path)
    
    try:
        # Apply transformations
        content = add_atomic_mixin_import(content)
        content = add_mixin_to_class(content, class_name)
        content = add_concept_type_property(content, concept_type)
        content = add_atomic_splitting_to_extract_method(content, concept_type)
        
        # Write updated content
        file_path.write_text(content, encoding='utf-8')
        print(f"  ✅ Successfully updated {file_path.name}")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to update {file_path.name}: {e}")
        # Restore from backup
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        if backup_path.exists():
            shutil.copy2(backup_path, file_path)
            print(f"  🔄 Restored from backup")
        return False

def update_all_extractors():
    """Update all extractors with unified atomic splitting."""
    
    print("🚀 Adding Unified Atomic Splitting to All Extractors")
    print("=" * 60)
    
    updated_count = 0
    total_count = 0
    
    for filename, concept_type in EXTRACTORS.items():
        file_path = EXTRACTION_DIR / filename
        
        if not file_path.exists():
            print(f"❌ {filename} not found - skipping")
            continue
            
        total_count += 1
        
        if update_extractor_file(file_path, concept_type):
            updated_count += 1
    
    print(f"\\n📊 Summary:")
    print(f"  Total extractors: {total_count}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {total_count - updated_count}")
    
    if updated_count > 0:
        print(f"\\n🎉 Successfully added unified atomic splitting to {updated_count} extractors!")
        print("\\n📝 Next steps:")
        print("  1. Set ENABLE_CONCEPT_SPLITTING=true to activate")
        print("  2. Test extraction with updated extractors")
        print("  3. Verify atomic concept output")
    else:
        print("\\n✅ All extractors already have unified splitting enabled!")

if __name__ == "__main__":
    # Change to project root
    os.chdir(Path(__file__).parent.parent)
    update_all_extractors()