#!/usr/bin/env python
"""
Fix script to improve the section embedding processing to handle duplicate sections.

This script specifically addresses the problem of duplicate section IDs when processing
section embeddings from different URI formats (e.g., when case_22_8 and case_236 both 
have 'facts' sections that create a unique constraint violation).

To apply this fix:
1. Run this script with python fix_section_embedding_duplicates.py
2. The script will modify the section_embedding_service.py file
3. Restart the Flask application

"""
import os
import re
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the file before modifying it."""
    backup_path = f"{file_path}.bak"
    logger.info(f"Creating backup of {file_path} to {backup_path}")
    shutil.copy2(file_path, backup_path)
    return backup_path

def fix_section_embedding_service():
    """Fix the section_embedding_service.py file to handle duplicate section ids."""
    file_path = "app/services/section_embedding_service.py"
    
    # Make a backup
    backup_path = backup_file(file_path)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix 1: Improve section metadata extraction with deduplication
        pattern1 = r"# Strategy 2: Try to get from section_embeddings_metadata\s+elif 'section_embeddings_metadata' in doc_metadata and doc_metadata\['section_embeddings_metadata'\]:\s+logger\.info\(f\"Found sections in section_embeddings_metadata\"\)\s+section_metadata = doc_metadata\['section_embeddings_metadata'\]\s+"
        replacement1 = """# Strategy 2: Try to get from section_embeddings_metadata
            elif 'section_embeddings_metadata' in doc_metadata and doc_metadata['section_embeddings_metadata']:
                logger.info(f"Found sections in section_embeddings_metadata")
                section_metadata_dict = {}
                seen_section_ids = set()  # Track section IDs we've already processed
                
                # Process and deduplicate sections
                for section_uri, data in doc_metadata['section_embeddings_metadata'].items():
                    section_id = section_uri.split('/')[-1]
                    
                    # Skip if we already processed this section ID to avoid duplicates
                    if section_id in seen_section_ids:
                        logger.warning(f"Skipping duplicate section ID: {section_id} from URI {section_uri}")
                        continue
                    
                    # Mark this section ID as processed
                    seen_section_ids.add(section_id)
                    
                    # Use current case's URI format consistently
                    normalized_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                    section_metadata_dict[normalized_uri] = data.copy()
                    
                # Use the deduplicated dictionary
                section_metadata = section_metadata_dict
                
                """
        
        # Fix 2: Improve section addition with better error handling
        pattern2 = r"# Process each section\s+for section_uri, embedding in section_embeddings\.items\(\):\s+# Extract section_id from URI\s+section_id = section_uri\.split\('/'\)\[-1\]\s+"
        replacement2 = """# Process each section
                # First, deduplicate sections to avoid unique constraint violations
                processed_section_ids = set()
                deduplicated_embeddings = {}
                
                for section_uri, embedding in section_embeddings.items():
                    # Extract section_id from URI
                    section_id = section_uri.split('/')[-1]
                    
                    # Skip if we've already processed this section ID
                    if section_id in processed_section_ids:
                        logger.warning(f"Skipping duplicate section ID: {section_id} from URI {section_uri}")
                        continue
                        
                    # Use normalized URI with current document ID
                    normalized_uri = f"http://proethica.org/document/case_{document_id}/{section_id}"
                    deduplicated_embeddings[normalized_uri] = embedding
                    processed_section_ids.add(section_id)
                
                # Process each deduplicated section
                for section_uri, embedding in deduplicated_embeddings.items():
                    # Extract section_id from URI
                    section_id = section_uri.split('/')[-1]
                    
                """
        
        # Apply the fixes
        modified_content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)
        modified_content = re.sub(pattern2, replacement2, modified_content, flags=re.DOTALL)
        
        # Write the modified content
        with open(file_path, 'w') as f:
            f.write(modified_content)
            
        logger.info(f"Successfully updated {file_path}")
        logger.info(f"Backup saved to {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating {file_path}: {e}")
        # Restore from backup
        shutil.copy2(backup_path, file_path)
        logger.info(f"Restored original file from backup")
        return False

def main():
    logger.info("Starting section embedding duplicate fix")
    success = fix_section_embedding_service()
    if success:
        logger.info("Fix applied successfully")
        logger.info("To apply the changes, restart the Flask application")
    else:
        logger.error("Fix failed, original files restored")
    
if __name__ == "__main__":
    main()
