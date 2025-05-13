#!/usr/bin/env python3
"""
Update Claude model references in MCP server files.

This script updates the Claude model references in MCP server files
to use the latest Claude 3.7 Sonnet model.
"""

import os
import re
import sys
from datetime import datetime

# Constants
OLD_MODEL_VERSIONS = [
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-haiku-20240307',
    'claude-3-sonnet',
    'claude-3-opus',
    'claude-3-haiku'
]
NEW_MODEL_VERSION = 'claude-3-7-sonnet-20250219'

# Configure directories to search
DIRS_TO_SEARCH = [
    'mcp',
    'app/services',
    'app/agent_module'
]

def backup_file(filepath):
    """Create a backup of a file with timestamp."""
    backup_path = f"{filepath}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        with open(filepath, 'r', encoding='utf-8') as original:
            with open(backup_path, 'w', encoding='utf-8') as backup:
                backup.write(original.read())
        return True
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return False

def update_claude_model_references(filepath):
    """Update Claude model references in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if any old model version is in the content
        found_match = False
        for old_model in OLD_MODEL_VERSIONS:
            if old_model in content:
                found_match = True
                break
        
        if not found_match:
            return False, []
        
        # Create a backup before modifying
        if not backup_file(filepath):
            return False, []
        
        # Track replacements made
        replacements = []
        
        # Replace all occurrences of old models with the new one
        updated_content = content
        for old_model in OLD_MODEL_VERSIONS:
            if old_model in updated_content:
                # Count occurrences
                count = updated_content.count(old_model)
                if count > 0:
                    replacements.append((old_model, NEW_MODEL_VERSION, count))
                
                # Replace the model reference
                updated_content = updated_content.replace(old_model, NEW_MODEL_VERSION)
        
        # Write the updated content back to the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return True, replacements
    
    except Exception as e:
        print(f"Error processing file {filepath}: {str(e)}")
        return False, []

def process_directory(directory):
    """Process all Python files in a directory recursively."""
    modified_files = 0
    total_replacements = 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                modified, replacements = update_claude_model_references(filepath)
                
                if modified:
                    modified_files += 1
                    print(f"Updated {filepath}:")
                    for old_model, new_model, count in replacements:
                        print(f"  - Replaced {count} occurrence(s) of '{old_model}' with '{new_model}'")
                    total_replacements += sum(count for _, _, count in replacements)
    
    return modified_files, total_replacements

def main():
    """Main function to update all model references."""
    print("Updating Claude model references...")
    total_modified_files = 0
    total_replacements = 0
    
    for directory in DIRS_TO_SEARCH:
        if os.path.exists(directory):
            print(f"\nProcessing directory: {directory}")
            modified_files, replacements = process_directory(directory)
            total_modified_files += modified_files
            total_replacements += replacements
        else:
            print(f"Directory not found: {directory}")
    
    print("\nUpdate complete!")
    print(f"Total files modified: {total_modified_files}")
    print(f"Total replacements: {total_replacements}")
    print(f"Model updated to: {NEW_MODEL_VERSION}")
    
    # Check if any files were modified
    if total_modified_files > 0:
        return 0
    else:
        print("No files needed updating.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
