#!/usr/bin/env python3
"""
Run Enhanced MCP Server with Guidelines Support

This script starts the enhanced ontology MCP server with guidelines support.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import enhanced server
from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyServerWithGuidelines, run_server

if __name__ == "__main__":
    # Start the enhanced server
    logger.info("Starting Enhanced Ontology MCP Server with Guidelines Support...")
    asyncio.run(run_server())
