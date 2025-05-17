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
from mcp.enhanced_ontology_server_with_guidelines import run_server

if __name__ == "__main__":
    # Check if we're using mock responses or live LLM
    use_mock = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "false").lower() == "true"
    logger.info(f"Starting Enhanced Ontology MCP Server with Guidelines Support...")
    logger.info(f"USE_MOCK_GUIDELINE_RESPONSES: {use_mock}")
    if not use_mock:
        logger.info("LIVE LLM MODE ENABLED - Using actual Claude API for guidelines")
    
    # Check API keys if not using mock mode
    if not use_mock:
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not found in environment - LLM calls may fail")
        else:
            logger.info("ANTHROPIC_API_KEY found in environment")
    
    # Start the server
    asyncio.run(run_server())
