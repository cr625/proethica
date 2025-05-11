#!/usr/bin/env python3
"""
Clean TTL files by removing unexpected characters
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TTL Cleaner')

def clean_ttl_file(file_path):
    """Clean a TTL file by removing unexpected characters"""
    
    logger.info(f'Cleaning file: {file_path}')
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Make a backup of the original file
        backup_path = f'{file_path}.bak'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f'Created backup at: {backup_path}')
        
        # Remove '+' characters at the end of lines
        cleaned_content = re.sub(r'\+\s*$', '', content, flags=re.MULTILINE)
        
        # Remove any other non-standard characters that might cause parsing issues
        # This includes control characters, null bytes, etc.
        cleaned_content = re.sub(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F]', '', cleaned_content)
        
        # Write the cleaned content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        logger.info(f'Successfully cleaned file: {file_path}')
        return True
    except Exception as e:
        logger.error(f'Error cleaning file {file_path}: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return False

def clean_all_ttl_files():
    """Clean all TTL files in the ontologies directory"""
    
    # Path to ontologies directory
    ontology_dir = os.path.join(os.path.dirname(__file__), '..', 'ontologies')
    
    success_count = 0
    failure_count = 0
    
    # Process each TTL file
    for file_name in os.listdir(ontology_dir):
        if file_name.endswith('.ttl'):
            file_path = os.path.join(ontology_dir, file_name)
            
            if clean_ttl_file(file_path):
                success_count += 1
            else:
                failure_count += 1
    
    logger.info(f'Cleaning completed. Success: {success_count}, Failures: {failure_count}')

if __name__ == '__main__':
    clean_all_ttl_files()
