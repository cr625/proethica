import os
import sys
import json
import subprocess
import signal
import atexit
from typing import Dict, List, Any, Optional, Literal, ClassVar

ServerType = Literal["ethical-dm", "zotero"]

class MCPClient:
    """Client for interacting with the MCP servers."""
    
    # Class variable to implement singleton pattern
    _instance: ClassVar[Optional['MCPClient']] = None
    
    # Lock file paths
    ETHICAL_DM_LOCKFILE = "/tmp/ontology_mcp_server.lock"
    ZOTERO_LOCKFILE = "/tmp/zotero_mcp_server.lock"
    
    # Initialize server process attributes as class variables
    ethical_dm_server_process = None
    zotero_server_process = None
    
    @classmethod
    def get_instance(cls, ethical_dm_server_path: Optional[str] = None, zotero_server_path: Optional[str] = None) -> 'MCPClient':
        """
        Get the singleton instance of MCPClient.
        
        Args:
            ethical_dm_server_path: Path to the ethical-dm MCP server script (optional)
            zotero_server_path: Path to the Zotero MCP server script (optional)
            
        Returns:
            The singleton MCPClient instance
        """
        if cls._instance is None:
            cls._instance = cls(ethical_dm_server_path, zotero_server_path)
        return cls._instance
    
    def __init__(self, ethical_dm_server_path: Optional[str] = None, zotero_server_path: Optional[str] = None):
        """
        Initialize the MCP client.
        
        Args:
            ethical_dm_server_path: Path to the ethical-dm MCP server script (optional)
            zotero_server_path: Path to the Zotero MCP server script (optional)
        """
        # If an instance already exists, return it instead of creating a new one
        if MCPClient._instance is not None and MCPClient._instance is not self:
            return
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.ethical_dm_server_path = ethical_dm_server_path or os.path.join(base_dir, 'mcp', 'ontology_mcp_server.py')
        self.zotero_server_path = zotero_server_path or os.path.join(base_dir, '..', 'zotero-mcp-server', 'src', 'server.py')
        
        # Initialize server process attributes if they don't exist yet
        if MCPClient.ethical_dm_server_process is None:
            MCPClient.ethical_dm_server_process = subprocess.Popen(
                ['echo', 'Dummy process for initialization'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        
        if MCPClient.zotero_server_process is None:
            MCPClient.zotero_server_process = subprocess.Popen(
                ['echo', 'Dummy process for initialization'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        
        # Register cleanup handler
        atexit.register(self._cleanup)
        
        # Set the instance
        MCPClient._instance = self
    
    def __new__(cls, *args, **kwargs):
        """Override __new__ to implement the singleton pattern."""
        if cls._instance is None:
            cls._instance = super(MCPClient, cls).__new__(cls)
        return cls._instance
    
    def _cleanup(self):
        """Clean up resources when the client is destroyed."""
        self.stop_server("ethical-dm")
        self.stop_server("zotero")
    
    def _get_lockfile_path(self, server_type: ServerType) -> str:
        """
        Get the path to the lock file for the specified server type.
        
        Args:
            server_type: Type of server (ethical-dm or zotero)
            
        Returns:
            Path to the lock file
        """
        if server_type == "ethical-dm":
            return self.ETHICAL_DM_LOCKFILE
        elif server_type == "zotero":
            return self.ZOTERO_LOCKFILE
        else:
            raise ValueError(f"Invalid server type: {server_type}")
    
    def _check_existing_server(self, server_type: ServerType) -> Optional[int]:
        """
        Check if a server of the specified type is already running.
        
        Args:
            server_type: Type of server to check (ethical-dm or zotero)
            
        Returns:
            PID of the running server if found, None otherwise
        """
        lockfile = self._get_lockfile_path(server_type)
        
        if os.path.exists(lockfile):
            try:
                with open(lockfile, "r") as lock:
                    pid = int(lock.read().strip())
                    try:
                        # Check if the process is still running
                        os.kill(pid, 0)
                        print(f"Found running {server_type} server (PID: {pid}).", file=sys.stderr)
                        return pid
                    except ProcessLookupError:
                        # Process not running, remove stale lock file
                        print(f"Stale lock file found for {server_type} server. Removing it.", file=sys.stderr)
                        os.remove(lockfile)
            except (IOError, ValueError) as e:
                print(f"Error reading lock file for {server_type} server: {str(e)}", file=sys.stderr)
                if os.path.exists(lockfile):
                    os.remove(lockfile)
        
        return None
    
    def _create_lockfile(self, server_type: ServerType, pid: int):
        """
        Create a lock file for the specified server type.
        
        Args:
            server_type: Type of server (ethical-dm or zotero)
            pid: PID of the server process
        """
        lockfile = self._get_lockfile_path(server_type)
        
        try:
            with open(lockfile, "w") as lock:
                lock.write(str(pid))
            print(f"Created lock file for {server_type} server (PID: {pid}).", file=sys.stderr)
        except IOError as e:
            print(f"Error creating lock file for {server_type} server: {str(e)}", file=sys.stderr)
    
    def _remove_lockfile(self, server_type: ServerType):
        """
        Remove the lock file for the specified server type.
        
        Args:
            server_type: Type of server (ethical-dm or zotero)
        """
        lockfile = self._get_lockfile_path(server_type)
        
        if os.path.exists(lockfile):
            try:
                os.remove(lockfile)
                print(f"Removed lock file for {server_type} server.", file=sys.stderr)
            except IOError as e:
                print(f"Error removing lock file for {server_type} server: {str(e)}", file=sys.stderr)
    
    def start_server(self, server_type: ServerType = "ethical-dm"):
        """
        Start the MCP server process.
        
        Args:
            server_type: Type of server to start (ethical-dm or zotero)
        """
        # Check if a server is already running
        existing_pid = self._check_existing_server(server_type)
        
        if server_type == "ethical-dm":
            if existing_pid is not None:
                # Server already running, use it
                if MCPClient.ethical_dm_server_process is None or MCPClient.ethical_dm_server_process.poll() is None:
                    print(f"Connecting to existing ethical-dm server (PID: {existing_pid}).", file=sys.stderr)
                    # We don't have a handle to the existing process, but we know it's running
                    # We'll create a new process object but won't actually start a new process
                    MCPClient.ethical_dm_server_process = subprocess.Popen(
                        ['echo', 'Dummy process for existing server'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
            elif MCPClient.ethical_dm_server_process is None or MCPClient.ethical_dm_server_process.poll() is not None:
                # No server running, start a new one
                print(f"Starting new ethical-dm server.", file=sys.stderr)
                MCPClient.ethical_dm_server_process = subprocess.Popen(
                    ['python', self.ethical_dm_server_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1  # Line buffered
                )
                # Create lock file with the PID of the new process
                self._create_lockfile(server_type, MCPClient.ethical_dm_server_process.pid)
        elif server_type == "zotero":
            if existing_pid is not None:
                # Server already running, use it
                if MCPClient.zotero_server_process is None or MCPClient.zotero_server_process.poll() is None:
                    print(f"Connecting to existing zotero server (PID: {existing_pid}).", file=sys.stderr)
                    # We don't have a handle to the existing process, but we know it's running
                    # We'll create a new process object but won't actually start a new process
                    MCPClient.zotero_server_process = subprocess.Popen(
                        ['echo', 'Dummy process for existing server'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
            elif MCPClient.zotero_server_process is None or MCPClient.zotero_server_process.poll() is not None:
                # No server running, start a new one
                print(f"Starting new zotero server.", file=sys.stderr)
                MCPClient.zotero_server_process = subprocess.Popen(
                    ['python', self.zotero_server_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1  # Line buffered
                )
                # Create lock file with the PID of the new process
                self._create_lockfile(server_type, MCPClient.zotero_server_process.pid)
    
    def stop_server(self, server_type: ServerType = "ethical-dm"):
        """
        Stop the MCP server process.
        
        Args:
            server_type: Type of server to stop (ethical-dm or zotero)
        """
        if server_type == "ethical-dm":
            if MCPClient.ethical_dm_server_process is not None and MCPClient.ethical_dm_server_process.poll() is None:
                # Server running, stop it
                try:
                    MCPClient.ethical_dm_server_process.terminate()
                    MCPClient.ethical_dm_server_process.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError) as e:
                    print(f"Error terminating ethical-dm server: {str(e)}", file=sys.stderr)
                    try:
                        MCPClient.ethical_dm_server_process.kill()
                    except OSError:
                        pass
                MCPClient.ethical_dm_server_process = None
                
                # Remove lock file
                self._remove_lockfile(server_type)
        elif server_type == "zotero":
            if MCPClient.zotero_server_process is not None and MCPClient.zotero_server_process.poll() is None:
                # Server running, stop it
                try:
                    MCPClient.zotero_server_process.terminate()
                    MCPClient.zotero_server_process.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError) as e:
                    print(f"Error terminating zotero server: {str(e)}", file=sys.stderr)
                    try:
                        MCPClient.zotero_server_process.kill()
                    except OSError:
                        pass
                MCPClient.zotero_server_process = None
                
                # Remove lock file
                self._remove_lockfile(server_type)
    
    def _send_request(self, request_type: str, params: Dict[str, Any], server_type: ServerType = "ethical-dm") -> Dict[str, Any]:
        """
        Send a request to the MCP server.
        
        Args:
            request_type: Type of request
            params: Request parameters
            server_type: Type of server to send request to (ethical-dm or zotero)
            
        Returns:
            Response from the server
        """
        # Prepare request
        request = {
            "jsonrpc": "2.0",
            "method": request_type,
            "params": params,
            "id": 1
        }
        
        # Try to send the request, with retry logic for broken pipes
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Ensure server is running (force restart on retry)
                if attempt > 0:
                    print(f"Restarting {server_type} server after failed attempt...", file=sys.stderr)
                    self.stop_server(server_type)
                    # Remove lock file if it exists
                    lockfile = self._get_lockfile_path(server_type)
                    if os.path.exists(lockfile):
                        os.remove(lockfile)
                
                self.start_server(server_type)
                
                # Get the appropriate server process
                if server_type == "ethical-dm":
                    server_process = MCPClient.ethical_dm_server_process
                elif server_type == "zotero":
                    server_process = MCPClient.zotero_server_process
                else:
                    raise ValueError(f"Invalid server type: {server_type}")
                
                # Send request
                server_process.stdin.write(json.dumps(request) + '\n')
                server_process.stdin.flush()
                
                # Read response
                response_line = server_process.stdout.readline()
                if not response_line:
                    raise BrokenPipeError("Empty response from server")
                
                response = json.loads(response_line)
                
                # Check for errors
                if "error" in response:
                    raise Exception(f"MCP server error: {response['error']['message']}")
                
                return response["result"]
                
            except (BrokenPipeError, IOError) as e:
                if attempt < max_retries:
                    print(f"Pipe error with {server_type} server: {str(e)}. Retrying...", file=sys.stderr)
                    continue
                else:
                    raise Exception(f"Failed to communicate with {server_type} server after {max_retries + 1} attempts: {str(e)}")
            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    print(f"JSON decode error with {server_type} server: {str(e)}. Retrying...", file=sys.stderr)
                    continue
                else:
                    raise Exception(f"Failed to parse response from {server_type} server after {max_retries + 1} attempts: {str(e)}")
    
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
    
    def get_world_entities(self, ontology_source: str, entity_type: str = "all") -> Dict[str, Any]:
        """
        Get entities from a specific world's ontology.
        
        Args:
            ontology_source: Path to the ontology file (e.g., "tccc.ttl")
            entity_type: Type of entity to retrieve (characters, conditions, resources, all)
            
        Returns:
            Dictionary containing world entities
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "get_world_entities",
                "arguments": {
                    "ontology_source": ontology_source,
                    "entity_type": entity_type
                }
            }
        )
        
        # Parse JSON content
        content = response["content"][0]["text"]
        return json.loads(content)
    
    def get_world_ontology(self, world_name: str) -> str:
        """
        Get the ontology for a specific world.
        
        Args:
            world_name: Name of the world (e.g., military-medical-triage)
            
        Returns:
            String containing the world ontology
        """
        response = self._send_request(
            "read_resource",
            {"uri": f"ethical-dm://worlds/{world_name}"}
        )
        
        # Return the ontology content
        return response["contents"][0]["text"]
    
    # Zotero MCP server methods
    
    def get_zotero_collections(self) -> Dict[str, Any]:
        """
        Get collections from the Zotero library.
        
        Returns:
            Dictionary containing collections
        """
        response = self._send_request(
            "read_resource",
            {"uri": "zotero://collections"},
            server_type="zotero"
        )
        
        # Parse JSON content
        content = response["contents"][0]["text"]
        return json.loads(content)
    
    def get_zotero_recent_items(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get recent items from the Zotero library.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            Dictionary containing recent items
        """
        response = self._send_request(
            "read_resource",
            {"uri": "zotero://items/recent"},
            server_type="zotero"
        )
        
        # Parse JSON content
        content = response["contents"][0]["text"]
        return json.loads(content)
    
    def search_zotero_items(self, query: str, collection_key: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Search for items in the Zotero library.
        
        Args:
            query: Search query
            collection_key: Collection key to search in (optional)
            limit: Maximum number of results to return
            
        Returns:
            Dictionary containing search results
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "search_items",
                "arguments": {
                    "query": query,
                    "collection_key": collection_key,
                    "limit": limit
                }
            },
            server_type="zotero"
        )
        
        # Parse JSON content
        content = response["content"][0]["text"]
        return json.loads(content)
    
    def get_zotero_citation(self, item_key: str, style: str = "apa") -> str:
        """
        Get citation for a specific Zotero item.
        
        Args:
            item_key: Item key
            style: Citation style (e.g., apa, mla, chicago)
            
        Returns:
            Citation text
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "get_citation",
                "arguments": {
                    "item_key": item_key,
                    "style": style
                }
            },
            server_type="zotero"
        )
        
        # Return citation text
        return response["content"][0]["text"]
    
    def add_zotero_item(self, item_type: str, title: str, creators: Optional[List[Dict[str, str]]] = None,
                        collection_key: Optional[str] = None, additional_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add a new item to the Zotero library.
        
        Args:
            item_type: Item type (e.g., journalArticle, book, webpage)
            title: Item title
            creators: Item creators (authors, editors, etc.)
            collection_key: Collection key to add the item to (optional)
            additional_fields: Additional fields for the item (e.g., date, url, publisher)
            
        Returns:
            Dictionary containing response from the server
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "add_item",
                "arguments": {
                    "item_type": item_type,
                    "title": title,
                    "creators": creators or [],
                    "collection_key": collection_key,
                    "additional_fields": additional_fields or {}
                }
            },
            server_type="zotero"
        )
        
        # Parse JSON content
        content = response["content"][0]["text"]
        return json.loads(content)
    
    def get_zotero_bibliography(self, item_keys: List[str], style: str = "apa") -> str:
        """
        Get bibliography for multiple Zotero items.
        
        Args:
            item_keys: Array of item keys
            style: Citation style (e.g., apa, mla, chicago)
            
        Returns:
            Bibliography text
        """
        response = self._send_request(
            "call_tool",
            {
                "name": "get_bibliography",
                "arguments": {
                    "item_keys": item_keys,
                    "style": style
                }
            },
            server_type="zotero"
        )
        
        # Return bibliography text
        return response["content"][0]["text"]
    
    def get_references_for_scenario(self, scenario) -> Dict[str, Any]:
        """
        Get references for a specific scenario.
        
        Args:
            scenario: Scenario object
            
        Returns:
            Dictionary containing references
        """
        # Create query from scenario
        query = f"{scenario.name} {scenario.description}"
        
        # Add character information
        for char in scenario.characters:
            query += f" {char.name} {char.role}"
            for cond in char.conditions:
                query += f" {cond.name}"
        
        # Search for references
        return self.search_zotero_items(query, limit=10)
    
    def get_references_for_world(self, world) -> Dict[str, Any]:
        """
        Get references for a specific world.
        
        Args:
            world: World object
            
        Returns:
            Dictionary containing references
        """
        # Create query from world
        query = f"{world.name} {world.description}"
        
        # Add ontology source if available
        if world.ontology_source:
            query += f" {world.ontology_source}"
        
        # Add metadata if available
        if world.world_metadata:
            for key, value in world.world_metadata.items():
                if isinstance(value, str):
                    query += f" {value}"
                elif isinstance(value, (dict, list)):
                    # Try to extract text from complex structures
                    try:
                        query += f" {json.dumps(value)}"
                    except:
                        pass
        
        # Search for references
        return self.search_zotero_items(query, limit=10)
