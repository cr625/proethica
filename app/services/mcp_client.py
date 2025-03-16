import os
import json
import subprocess
from typing import Dict, List, Any, Optional

class MCPClient:
    """Client for interacting with the MCP server."""
    
    def __init__(self, server_path: Optional[str] = None):
        """
        Initialize the MCP client.
        
        Args:
            server_path: Path to the MCP server script (optional)
        """
        self.server_path = server_path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'mcp', 'server.py')
        self.server_process = None
    
    def start_server(self):
        """Start the MCP server process."""
        if self.server_process is None or self.server_process.poll() is not None:
            # Server not running, start it
            self.server_process = subprocess.Popen(
                ['python', self.server_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
    
    def stop_server(self):
        """Stop the MCP server process."""
        if self.server_process is not None and self.server_process.poll() is None:
            # Server running, stop it
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
            self.server_process = None
    
    def _send_request(self, request_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a request to the MCP server.
        
        Args:
            request_type: Type of request
            params: Request parameters
            
        Returns:
            Response from the server
        """
        # Ensure server is running
        self.start_server()
        
        # Prepare request
        request = {
            "jsonrpc": "2.0",
            "method": request_type,
            "params": params,
            "id": 1
        }
        
        # Send request
        self.server_process.stdin.write(json.dumps(request) + '\n')
        self.server_process.stdin.flush()
        
        # Read response
        response_line = self.server_process.stdout.readline()
        response = json.loads(response_line)
        
        # Check for errors
        if "error" in response:
            raise Exception(f"MCP server error: {response['error']['message']}")
        
        return response["result"]
    
    def get_guidelines(self, domain: str = "military-medical-triage") -> Dict[str, Any]:
        """
        Get guidelines for a specific domain.
        
        Args:
            domain: Domain to get guidelines for (military-medical-triage, engineering-ethics, us-law-practice)
            
        Returns:
            Dictionary containing guidelines
        """
        response = self._send_request(
            "read_resource",
            {"uri": f"ethical-dm://guidelines/{domain}"}
        )
        
        # Parse JSON content
        content = response["contents"][0]["text"]
        return json.loads(content)
    
    def get_cases(self, domain: str = "military-medical-triage") -> Dict[str, Any]:
        """
        Get cases for a specific domain.
        
        Args:
            domain: Domain to get cases for (military-medical-triage, engineering-ethics, us-law-practice)
            
        Returns:
            Dictionary containing cases
        """
        response = self._send_request(
            "read_resource",
            {"uri": f"ethical-dm://cases/{domain}"}
        )
        
        # Parse JSON content
        content = response["contents"][0]["text"]
        return json.loads(content)
    
    def search_cases(self, query: str, domain: str = "military-medical-triage", limit: int = 5) -> Dict[str, Any]:
        """
        Search for cases matching a query in a specific domain.
        
        Args:
            query: Search query
            domain: Domain to search in (military-medical-triage, engineering-ethics, us-law-practice)
            limit: Maximum number of results to return
            
        Returns:
            Dictionary containing search results
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "search_cases",
                "arguments": {
                    "query": query,
                    "domain": domain,
                    "limit": limit
                }
            }
        )
        
        # Parse JSON content
        content = response["content"][0]["text"]
        return json.loads(content)
    
    def add_case(self, title: str, description: str, decision: str, domain: str = "military-medical-triage",
                 outcome: Optional[str] = None, ethical_analysis: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a new case to the repository.
        
        Args:
            title: Case title
            description: Case description
            decision: Decision made in the case
            domain: Domain for the case (military-medical-triage, engineering-ethics, us-law-practice)
            outcome: Outcome of the decision (optional)
            ethical_analysis: Ethical analysis of the case (optional)
            
        Returns:
            Dictionary containing result of the operation
        """
        # Prepare arguments
        arguments = {
            "title": title,
            "description": description,
            "decision": decision,
            "domain": domain
        }
        
        if outcome is not None:
            arguments["outcome"] = outcome
        
        if ethical_analysis is not None:
            arguments["ethical_analysis"] = ethical_analysis
        
        response = self._send_request(
            "call_tool",
            {
                "name": "add_case",
                "arguments": arguments
            }
        )
        
        # Parse JSON content
        content = response["content"][0]["text"]
        return json.loads(content)
    
    def get_similar_cases(self, scenario: Dict[str, Any]) -> str:
        """
        Get similar cases for a scenario.
        
        Args:
            scenario: Dictionary containing scenario data
            
        Returns:
            String containing similar cases for reference
        """
        # Create a query from the scenario
        query = f"{scenario.get('name', '')} {scenario.get('description', '')}"
        
        # Add character information
        for char in scenario.get('characters', []):
            query += f" {char.get('name', '')} {char.get('role', '')}"
            for cond in char.get('conditions', []):
                query += f" {cond.get('name', '')}"
        
        # Get domain from scenario or default to military-medical-triage
        domain = "military-medical-triage"
        if hasattr(scenario, 'domain') and scenario.domain:
            domain = scenario.domain.name.lower().replace(' ', '-')
        elif hasattr(scenario, 'domain_id') and scenario.domain_id:
            # Get domain name from database
            from app.models import Domain
            domain_obj = Domain.query.get(scenario.domain_id)
            if domain_obj:
                domain = domain_obj.name.lower().replace(' ', '-')
        
        # Search for similar cases
        results = self.search_cases(query, domain=domain)
        
        # Format results as text
        text = ""
        for case in results.get('results', []):
            text += f"Case {case.get('id', '')}: {case.get('title', '')}\n"
            text += f"Description: {case.get('description', '')}\n"
            text += f"Decision: {case.get('decision', '')}\n"
            text += f"Outcome: {case.get('outcome', '')}\n"
            text += f"Ethical Analysis: {case.get('ethical_analysis', '')}\n\n"
        
        return text
