#!/usr/bin/env python3
"""
Update Claude Model References

This script finds and updates all Claude model references in MCP module files
to ensure they use the latest model version: claude-3-7-sonnet-20250219.
"""

import os
import re
import sys
import logging
from typing import List, Dict, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Target directories with Python files that might contain model references
SEARCH_PATHS = [
    "mcp/modules",
    "mcp",
    "app/services",
    "app/agent_module"
]

# Old model versions to replace
OLD_MODEL_PATTERNS = [
    r'claude-3-opus-20240229',
    r'claude-3-sonnet-20240229',
    r'claude-3-opus-[0-9]+',
    r'claude-3-sonnet-[0-9]+'
]

# New model to use as replacement
NEW_MODEL = "claude-3-7-sonnet-20250219"

def find_python_files(paths: List[str]) -> List[str]:
    """Find all Python files in the given paths."""
    python_files = []
    
    for path in paths:
        if not os.path.exists(path):
            logger.warning(f"Path {path} does not exist, skipping")
            continue
            
        if os.path.isfile(path) and path.endswith('.py'):
            python_files.append(path)
        elif os.path.isdir(path):
            # Walk through directory recursively
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith('.py'):
                        python_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(python_files)} Python files to scan")
    return python_files

def check_for_model_references(file_path: str) -> List[Tuple[str, int]]:
    """Check a file for Claude model references and return matching lines and line numbers."""
    matches = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            # Check if line contains any of the old model patterns
            for pattern in OLD_MODEL_PATTERNS:
                if re.search(pattern, line):
                    matches.append((line.strip(), i + 1))
                    break
        
        return matches
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return []

def update_file(file_path: str) -> Tuple[int, bool]:
    """Update Claude model references in a file. Returns number of replacements and success boolean."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create backup of file before modifying
        backup_path = f"{file_path}.bak"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        replacement_count = 0
        
        # Replace old model references with new model
        for pattern in OLD_MODEL_PATTERNS:
            new_content, count = re.subn(pattern, NEW_MODEL, content)
            replacement_count += count
            content = new_content
        
        if replacement_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Updated {replacement_count} model references in {file_path}")
            return replacement_count, True
        else:
            # Remove backup if no changes were made
            os.remove(backup_path)
            return 0, True
            
    except Exception as e:
        logger.error(f"Error updating file {file_path}: {e}")
        return 0, False

def main() -> int:
    """Main function to update Claude model references."""
    logger.info("Starting Claude model reference update")
    
    # Find Python files
    python_files = find_python_files(SEARCH_PATHS)
    
    # Track statistics
    files_with_references = 0
    files_updated = 0
    total_replacements = 0
    error_files = 0
    
    # Check each file for references
    for file_path in python_files:
        references = check_for_model_references(file_path)
        
        if references:
            files_with_references += 1
            
            logger.info(f"Found {len(references)} model references in {file_path}:")
            for line, line_num in references:
                logger.info(f"  Line {line_num}: {line}")
            
            # Update the file
            replacements, success = update_file(file_path)
            
            if success:
                if replacements > 0:
                    files_updated += 1
                    total_replacements += replacements
            else:
                error_files += 1
    
    # Print summary
    logger.info("\nUpdate Summary:")
    logger.info(f"Scanned {len(python_files)} Python files")
    logger.info(f"Found {files_with_references} files with Claude model references")
    logger.info(f"Updated {files_updated} files with {total_replacements} replacements")
    logger.info(f"Errors encountered in {error_files} files")
    
    if error_files > 0:
        logger.warning("Completed with some errors, check the log above")
        return 1
    else:
        logger.info("Update completed successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
