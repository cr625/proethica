#!/usr/bin/env python3
"""
Script to help migrate hardcoded model references to use ModelConfig.
This script identifies files that need updating and provides examples.
"""

import os
import re
from pathlib import Path

# Patterns to search for
MODEL_PATTERNS = [
    r'claude-3-7-sonnet-20250219',
    r'claude-3-sonnet-20240229',
    r'claude-3-opus-20240229',
    r'claude-3-haiku-20240307',
    r'model\s*=\s*["\']claude[^"\']+["\']',
    r'CLAUDE_MODEL_VERSION',
    r'ANTHROPIC_MODEL'
]

# Directories to skip
SKIP_DIRS = {'pending_delete', 'archived', 'venv', '.git', '__pycache__'}

def find_files_with_models(root_dir):
    """Find all Python files containing model references."""
    files_with_models = []
    
    for path in Path(root_dir).rglob('*.py'):
        # Skip directories we don't want to process
        if any(skip_dir in str(path) for skip_dir in SKIP_DIRS):
            continue
            
        try:
            content = path.read_text()
            for pattern in MODEL_PATTERNS:
                if re.search(pattern, content):
                    files_with_models.append(str(path))
                    break
        except Exception as e:
            print(f"Error reading {path}: {e}")
    
    return sorted(set(files_with_models))

def generate_migration_examples():
    """Generate example code for common migration patterns."""
    
    examples = """
# Example 1: Simple model reference
# Before:
model = "claude-3-7-sonnet-20250219"

# After:
from config.models import ModelConfig
model = ModelConfig.get_claude_model("default")

# Example 2: Environment variable
# Before:
model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')

# After:
from config.models import ModelConfig
model = ModelConfig.get_default_model()  # Returns claude-sonnet-4-20250514

# Example 3: Service initialization
# Before:
self.model = "claude-3-sonnet-20240229"

# After:
from config.models import ModelConfig
self.model = ModelConfig.get_claude_model("default")  # Returns claude-sonnet-4-20250514

# Example 4: Test file (keep specific versions)
# Before:
test_model = "claude-3-opus-20240229"

# After:
from config.models import ModelConfig
test_model = ModelConfig.CLAUDE_MODELS["legacy_opus"]  # For testing with old models
# Or use new models:
test_model = ModelConfig.CLAUDE_MODELS["opus-4"]  # Returns claude-opus-4-20250514

# Example 5: Use case specific
# Before:
if need_fast_response:
    model = "claude-3-haiku-20240307"
else:
    model = "claude-3-opus-20240229"

# After:
from config.models import ModelConfig
if need_fast_response:
    model = ModelConfig.get_claude_model("fast")
else:
    model = ModelConfig.get_claude_model("powerful")
"""
    return examples

def main():
    """Main function to run the migration helper."""
    root_dir = Path(__file__).parent.parent
    
    print("Finding files with model references...")
    files = find_files_with_models(root_dir)
    
    print(f"\nFound {len(files)} files with model references:\n")
    
    # Group files by directory
    files_by_dir = {}
    for file in files:
        dir_name = os.path.dirname(file).replace(str(root_dir), '.')
        if dir_name not in files_by_dir:
            files_by_dir[dir_name] = []
        files_by_dir[dir_name].append(os.path.basename(file))
    
    # Print grouped files
    for dir_name, file_list in sorted(files_by_dir.items()):
        print(f"\n{dir_name}:")
        for fname in sorted(file_list):
            print(f"  - {fname}")
    
    print("\n" + "="*60)
    print("MIGRATION EXAMPLES")
    print("="*60)
    print(generate_migration_examples())
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Review the files listed above")
    print("2. Update imports to include: from config.models import ModelConfig")
    print("3. Replace hardcoded models with ModelConfig methods")
    print("4. Test the changes")
    print("5. Update .env files in deployment environments")

if __name__ == "__main__":
    main()