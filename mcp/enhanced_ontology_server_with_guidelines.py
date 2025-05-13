#!/usr/bin/env python3
"""
Enhanced Ontology MCP Server with Guidelines Support

This module provides the MCP server functionality with ontology operations
and guideline analysis capabilities.
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union
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

# Import MCP server and modules
from mcp.http_ontology_mcp_server import HTTPOntologyMCPServer
from mcp.modules.guideline_analysis_module import GuidelineAnalysisModule

class EnhancedOntologyServerWithGuidelines(HTTPOntologyMCPServer):
    """
    Enhanced Ontology MCP Server with Guidelines Support
    
    This server extends the HTTP Ontology MCP Server with additional modules
    for guideline analysis and concept extraction.
    """
    
    def __init__(self, host="localhost", port=5001):
        """
        Initialize the server.
        
        Args:
            host: The host to bind to
            port: The port to bind to
        """
        # Call parent constructor
        super().__init__(host, port)
        
        # Update server info
        self.server_info["name"] = "Enhanced Ontology MCP Server with Guidelines"
        self.server_info["version"] = "1.0.0"
        self.server_info["description"] = "MCP server for ontology operations and guideline analysis"
        
        # Set up LLM clients
        self._init_anthropic_client()
        self._init_openai_client()
        
        # Set up embeddings client
        self._init_embeddings_client()
        
        # Register additional modules
        self._register_guideline_analysis_module()
    
    def _init_anthropic_client(self):
        """Initialize the Anthropic client."""
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.anthropic_available = bool(self.anthropic_api_key)
        
        if self.anthropic_available:
            try:
                import anthropic
                self.anthropic_client = anthropic.AsyncClient(api_key=self.anthropic_api_key)
                logger.info("Anthropic client initialized successfully")
            except ImportError:
                logger.warning("Could not import anthropic package. Anthropic client not available.")
                self.anthropic_available = False
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {e}")
                self.anthropic_available = False
        else:
            logger.warning("ANTHROPIC_API_KEY not found in environment. Anthropic client not available.")
    
    def _init_openai_client(self):
        """Initialize the OpenAI client."""
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_available = bool(self.openai_api_key)
        
        if self.openai_available:
            try:
                import openai
                self.openai_client = openai.AsyncClient(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except ImportError:
                logger.warning("Could not import openai package. OpenAI client not available.")
                self.openai_available = False
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
                self.openai_available = False
        else:
            logger.warning("OPENAI_API_KEY not found in environment. OpenAI client not available.")
    
    def _init_embeddings_client(self):
        """Initialize the embeddings client."""
        # This is a simple embeddings client for similarity calculations
        # In a real implementation, this would use a proper embeddings model
        class SimpleEmbeddingsClient:
            async def calculate_similarities(self, texts1, texts2):
                """
                Calculate similarity scores between two sets of texts.
                
                This is a simplified implementation that just returns random scores.
                In a real implementation, this would calculate proper embeddings
                and cosine similarity.
                
                Args:
                    texts1: First set of texts
                    texts2: Second set of texts
                    
                Returns:
                    List of lists of similarity scores
                """
                import random
                
                # Generate random similarity scores
                return [[random.uniform(0.1, 0.9) for _ in texts2] for _ in texts1]
        
        self.embeddings_client = SimpleEmbeddingsClient()
        logger.info("Simple embeddings client initialized")
    
    def _register_guideline_analysis_module(self):
        """Register the guideline analysis module."""
        try:
            # Create the module
            guideline_module = GuidelineAnalysisModule(
                llm_client=self.anthropic_client if self.anthropic_available else None,
                ontology_client=self,
                embedding_client=self.embeddings_client
            )
            
            # Add it to our modules
            self.add_module(guideline_module)
            
            logger.info("Guideline analysis module registered successfully")
        except Exception as e:
            logger.error(f"Error registering guideline analysis module: {e}")
            raise

async def run_server():
    """
    Run the enhanced ontology server with guidelines support.
    
    This function creates and starts the server.
    """
    # Get port from environment or use default
    port = int(os.environ.get("MCP_SERVER_PORT", 5001))
    
    # Create server
    server = EnhancedOntologyServerWithGuidelines(port=port)
    
    # Start server
    await server.start()
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # Shutdown server gracefully
        await server.stop()

if __name__ == "__main__":
    asyncio.run(run_server())
