"""
External MCP Client - Connects to OntServe MCP server via ngrok tunnel.
Enables direct LLM-ontology interaction for enhanced concept extraction.
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional
import time

logger = logging.getLogger(__name__)

class ExternalMCPClient:
    """Client for connecting to external OntServe MCP server via ngrok."""
    
    def __init__(self, server_url: str = None):
        """
        Initialize external MCP client.
        
        Args:
            server_url: URL of the external MCP server (defaults to EXTERNAL_MCP_URL env var)
        """
        import os
        if server_url is None:
            server_url = os.environ.get('EXTERNAL_MCP_URL', 'http://localhost:8083')
        self.server_url = server_url.rstrip('/')
        self.request_id = 0
        self.timeout = 30
        self.session = requests.Session()
        
        # Configure session for ngrok
        self.session.headers.update({
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
        })
        
        logger.info(f"External MCP client initialized for: {self.server_url}")
    
    def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "list_tools",
                "params": {}
            }
            
            response = self.session.post(
                self.server_url, 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result:
                    tools = result['result'].get('tools', [])
                    logger.info(f"Listed {len(tools)} MCP tools")
                    return {'success': True, 'tools': tools}
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    logger.error(f"MCP list_tools failed: {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                logger.error(f"HTTP error {response.status_code}: {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return {'success': False, 'error': str(e)}
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Dict with tool result or error
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "call_tool",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            logger.debug(f"Calling tool '{tool_name}' with args: {arguments}")
            
            response = self.session.post(
                self.server_url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and 'content' in result['result']:
                    # Parse the tool result from MCP response
                    content = result['result']['content'][0]['text']
                    tool_result = json.loads(content)
                    
                    logger.debug(f"Tool '{tool_name}' executed successfully")
                    return {'success': True, 'result': tool_result}
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    logger.error(f"Tool '{tool_name}' failed: {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                logger.error(f"HTTP error {response.status_code}: {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return {'success': False, 'error': str(e)}
    
    def get_entities_by_category(self, category: str, domain_id: str = "engineering-ethics") -> Dict[str, Any]:
        """Get ontology entities by category."""
        return self.call_tool("get_entities_by_category", {
            "category": category,
            "domain_id": domain_id,
            "status": "approved"
        })
    
    def get_all_role_entities(self, domain_id: str = "engineering-ethics") -> List[Dict[str, Any]]:
        """Get all role entities for context during extraction."""
        result = self.get_entities_by_category("Role", domain_id)
        
        if result.get('success') and result.get('result'):
            entities = result['result'].get('entities', [])
            logger.info(f"Retrieved {len(entities)} role entities from external MCP")
            return entities
        else:
            logger.warning(f"Failed to get role entities: {result.get('error', 'Unknown error')}")
            return []
    
    def get_all_principle_entities(self, domain_id: str = "engineering-ethics") -> List[Dict[str, Any]]:
        """Get all principle entities from external MCP server."""
        try:
            result = self.get_entities_by_category("principle", domain_id)
            entities = result.get('entities', [])
            logger.info(f"Retrieved {len(entities)} principle entities from external MCP")
            return entities
        except Exception as e:
            logger.warning(f"Failed to get principle entities: {e}")
            return []
    
    def get_all_obligation_entities(self, domain_id: str = "engineering-ethics") -> List[Dict[str, Any]]:
        """Get all obligation entities from external MCP server."""
        try:
            result = self.get_entities_by_category("obligation", domain_id)
            entities = result.get('entities', [])
            logger.info(f"Retrieved {len(entities)} obligation entities from external MCP")
            return entities
        except Exception as e:
            logger.warning(f"Failed to get obligation entities: {e}")
            return []
    
    def submit_candidate_concept(self, concept: Dict[str, Any], domain_id: str = "engineering-ethics") -> Dict[str, Any]:
        """Submit a candidate concept to the external MCP server."""
        return self.call_tool("submit_candidate_concept", {
            "concept": concept,
            "domain_id": domain_id,
            "submitted_by": "proethica-external-extraction"
        })
    
    def get_domain_info(self, domain_id: str = "engineering-ethics") -> Dict[str, Any]:
        """Get information about a domain."""
        return self.call_tool("get_domain_info", {
            "domain_id": domain_id
        })
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the external MCP server is healthy."""
        try:
            health_url = f"{self.server_url}/health"
            response = self.session.get(health_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info("External MCP server health check passed")
                return {'success': True, 'data': data}
            else:
                logger.warning(f"Health check failed: HTTP {response.status_code}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _next_request_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

# Global client instance
_external_mcp_client = None

def get_external_mcp_client() -> ExternalMCPClient:
    """Get or create global external MCP client instance."""
    global _external_mcp_client
    if _external_mcp_client is None:
        _external_mcp_client = ExternalMCPClient()
    return _external_mcp_client
