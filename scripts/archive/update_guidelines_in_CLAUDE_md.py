#!/usr/bin/env python3
"""
Update CLAUDE.md with Guidelines Integration Progress

This script updates the CLAUDE.md file with information about the latest
guidelines integration work done with the MCP server and triples extraction.
"""

import os
import re
import sys
import logging
import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to the CLAUDE.md file
CLAUDE_MD_PATH = "CLAUDE.md"

def read_file(file_path: str) -> Optional[str]:
    """Read a file and return its contents as a string."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None

def write_file(file_path: str, content: str) -> bool:
    """Write content to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return False

def backup_file(file_path: str) -> Optional[str]:
    """Create a backup of a file."""
    backup_path = f"{file_path}.bak"
    try:
        content = read_file(file_path)
        if content is None:
            return None
        
        if write_file(backup_path, content):
            logger.info(f"Created backup at {backup_path}")
            return backup_path
        else:
            return None
    except Exception as e:
        logger.error(f"Error creating backup of {file_path}: {e}")
        return None

def update_claude_md() -> bool:
    """Update the CLAUDE.md file with guidelines integration progress."""
    # Check if the file exists
    if not os.path.exists(CLAUDE_MD_PATH):
        logger.error(f"CLAUDE.md file not found: {CLAUDE_MD_PATH}")
        return False
    
    # Create a backup
    backup_path = backup_file(CLAUDE_MD_PATH)
    if backup_path is None:
        logger.error("Failed to create backup, aborting")
        return False
    
    # Read the file
    content = read_file(CLAUDE_MD_PATH)
    if content is None:
        return False
    
    # Get current date
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Update or add guidelines section
    guidelines_section = f"""
## Guidelines Integration with MCP Server (Updated: {current_date})

The guidelines integration with the MCP server and triples extraction process has been successfully implemented. This integration enables the extraction of concepts from ethical guidelines, matching them to ontology entities, and generating RDF triples to represent the relationships.

### Key Components

1. **Enhanced Ontology Server**:
   - Integration with `GuidelineAnalysisModule` for processing guidelines
   - JSON-RPC endpoint for reliable client-server communication
   - Updated to use the latest Claude model (`claude-3-7-sonnet-20250219`)

2. **MCP Client Improvements**:
   - Updated to use JSON-RPC endpoints instead of deprecated API endpoints
   - Fixed model references for consistency across the system
   - Added comprehensive error handling for connection failures

3. **Pipeline Tools**:
   - `test_mcp_jsonrpc_connection.py`: Tests server connectivity via JSON-RPC
   - `fix_mcp_client.py`: Updates client to use JSON-RPC communications
   - `update_claude_models_in_mcp_server.py`: Ensures consistent model usage
   - `run_guidelines_mcp_pipeline.sh`: End-to-end testing pipeline

4. **Documentation**:
   - `RUN_WEBAPP_WITH_GUIDELINES.md`: Instructions for running the web app
   - `README_GUIDELINES_TESTING.md`: Testing procedures and troubleshooting
   - `guidelines_progress.md`: Tracking document for progress and next steps

### Running the Application

To run ProEthica with guidelines support:

```bash
./start_with_enhanced_ontology_server.sh
```

This script handles all necessary setup, including:
- Starting the enhanced ontology server
- Updating MCP client configuration
- Ensuring proper model usage
- Starting the Flask web application

### Testing Guidelines Integration

Guidelines integration can be tested using:

```bash
# Test the MCP server connection
./test_mcp_jsonrpc_connection.py --verbose

# Run the full pipeline test
./run_guidelines_mcp_pipeline.sh
```

### Next Steps

1. **Web Interface Enhancements**:
   - Improve concept visualization in the web UI
   - Add better management of guideline triples
   - Implement batch processing for multiple guidelines

2. **Integration with Existing Ontologies**:
   - Connect guideline concepts with engineering ethics ontology
   - Map to existing case analysis frameworks
   - Establish links to the McLaren model

3. **Performance Optimization**:
   - Add caching for extracted concepts
   - Implement parallel processing for large guidelines
   - Optimize triple generation algorithms
"""
    
    # Check if there's already a Guidelines Integration section
    guidelines_section_pattern = r'## Guidelines Integration.*?\n.*?(?=\n## |$)'
    if re.search(guidelines_section_pattern, content, re.DOTALL):
        # Replace existing section
        updated_content = re.sub(guidelines_section_pattern, guidelines_section, content, flags=re.DOTALL)
    else:
        # Add new section at the end
        updated_content = content + guidelines_section
    
    # Write the updated content back to the file
    if write_file(CLAUDE_MD_PATH, updated_content):
        logger.info(f"Successfully updated {CLAUDE_MD_PATH} with guidelines integration progress")
        return True
    else:
        # Restore from backup if the write failed
        logger.warning(f"Failed to update {CLAUDE_MD_PATH}, restoring from backup {backup_path}")
        restore_content = read_file(backup_path)
        if restore_content and write_file(CLAUDE_MD_PATH, restore_content):
            logger.info(f"Restored from backup {backup_path}")
        else:
            logger.error(f"Failed to restore from backup {backup_path}")
        return False

def main() -> int:
    """Main function."""
    logger.info("Starting CLAUDE.md update")
    
    if update_claude_md():
        logger.info("CLAUDE.md update completed successfully")
        return 0
    else:
        logger.error("CLAUDE.md update failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
