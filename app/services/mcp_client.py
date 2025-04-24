import requests
import json
from typing import Dict, List, Any, Optional
import os
from app.services.zotero_client import ZoteroClient

class MCPClient:
    """
    Model Context Protocol client for interacting with the MCP server.
    
    This client handles communication with the MCP server for various operations
    related to world entities, ontologies, guidelines, and other resources.
    """
    """Client for interacting with the MCP server."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'MCPClient':
        """Get singleton instance of MCPClient."""
        if cls._instance is None:
            cls._instance = MCPClient()
        return cls._instance
    
    def __init__(self):
        """Initialize the MCP client."""
        # Get MCP server URL from environment variable or use default
        self.mcp_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:5000')
        self.use_mock_fallback = os.environ.get('USE_MOCK_FALLBACK', 'true').lower() == 'true'
        
        print(f"MCPClient initialized with MCP_SERVER_URL: {self.mcp_url}")
        print(f"Mock data fallback is {'ENABLED' if self.use_mock_fallback else 'DISABLED'}")
        
        # Initialize session with longer timeout
        self.session = requests.Session()
        self.session.timeout = (5, 30)  # (connect timeout, read timeout)
        
        # Initialize ZoteroClient reference (used for testing)
        self._zotero_client = None
        
        # Test connection to MCP server during initialization
        self.is_connected = self.check_connection()
    
    def check_connection(self) -> bool:
        """
        Check if the MCP server is running and accessible.
        
        Returns:
            True if connected, False otherwise
        """
        print(f"Testing connection to MCP server at {self.mcp_url}...")
        
        # Try different endpoints that might be available
        test_endpoints = [
            # First try the dedicated ping endpoint
            "/api/ping",
            # If that fails, try a known API endpoint that should exist
            "/api/guidelines/engineering-ethics",
            # Also check the ontology endpoint
            "/api/ontology/engineering_ethics.ttl/entities"
        ]
        
        for endpoint in test_endpoints:
            try:
                full_url = f"{self.mcp_url}{endpoint}"
                print(f"  Checking endpoint: {full_url}")
                response = self.session.get(full_url, timeout=5)
                
                if response.status_code == 200:
                    print(f"Successfully connected to MCP server at {full_url}")
                    return True
                else:
                    print(f"  Endpoint returned status code {response.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"  Could not connect to {full_url}")
            except Exception as e:
                print(f"  Error checking endpoint {full_url}: {str(e)}")
        
        print(f"All connection attempts to MCP server failed")
        return False
    
    def get_guidelines(self, world_name: str) -> Dict[str, Any]:
        """
        Get guidelines for a specific world.
        
        Args:
            world_name: Name of the world
            
        Returns:
            Dictionary containing guidelines
        """
        try:
            # Make request to MCP server
            response = self.session.get(f"{self.mcp_url}/api/guidelines/{world_name}")
            
            # Check if request was successful
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting guidelines: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            print(f"Error getting guidelines: {str(e)}")
            return {}
    
    def get_world_entities(self, ontology_source: str, entity_type: str = "all") -> Dict[str, Any]:
        """
        Get entities for a specific world from ontology.
        
        Args:
            ontology_source: Source of the ontology
            entity_type: Type of entity to retrieve (roles, conditions, resources, actions, events, or all)
            
        Returns:
            Dictionary containing entities
        """
        # If MCP server is not connected and fallback is disabled, return clear warning
        if not self.is_connected and not self.use_mock_fallback:
            warning = {
                "warning": f"MCP server at {self.mcp_url} is not connected and mock fallback is disabled.",
                "entities": {}
            }
            print(f"WARNING: MCP server is not connected and mock fallback is disabled.")
            return warning
            
        try:
            import traceback
            print(f"MCPClient: Getting entities for ontology source: {ontology_source}")
            
            # If server is not connected but fallback is enabled, skip API call
            if not self.is_connected and self.use_mock_fallback:
                print(f"MCPClient: MCP server not connected, using mock data (fallback enabled)")
                mock_data = self.get_mock_entities(ontology_source)
                mock_data["is_mock"] = True
                return mock_data
            
            # Make request to MCP server
            api_url = f"{self.mcp_url}/api/ontology/{ontology_source}/entities"
            print(f"MCPClient: Making request to: {api_url}")
            
            # Add entity_type as a query parameter if specified
            params = {}
            if entity_type and entity_type != "all":
                params["type"] = entity_type
                
            response = self.session.get(api_url, params=params, timeout=10)
            
            # Check if request was successful
            if response.status_code == 200:
                result = response.json()
                print(f"MCPClient: Got successful response with keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
                
                # Add notice that this is real data, not mock
                result["is_mock"] = False
                return result
            else:
                error_message = f"Error getting entities: {response.status_code} - {response.text}"
                print(error_message)
                
                # Fall back to mock data only if enabled
                if self.use_mock_fallback:
                    print("MCPClient: Falling back to mock data")
                    mock_data = self.get_mock_entities(ontology_source)
                    mock_data["is_mock"] = True
                    return mock_data
                else:
                    return {
                        "error": error_message,
                        "entities": {}
                    }
        except Exception as e:
            stack_trace = traceback.format_exc()
            error_message = f"Error getting entities: {str(e)}"
            print(error_message)
            print(stack_trace)
            
            # Fall back to mock data only if enabled
            if self.use_mock_fallback:
                print("MCPClient: Falling back to mock data due to exception")
                mock_data = self.get_mock_entities(ontology_source)
                mock_data["is_mock"] = True
                return mock_data
            else:
                return {
                    "error": error_message,
                    "entities": {}
                }
    
    # Methods for ontology editor integration
    
    def get_ontology_status(self, ontology_source: str) -> Dict[str, Any]:
        """
        Check if an ontology is current or deprecated.
        
        Args:
            ontology_source: Source of the ontology (e.g., filename.ttl)
            
        Returns:
            Dictionary with status info including 'status' key with value 'current', 'deprecated', or 'unknown'
        """
        try:
            # Make request to check ontology status
            response = self.session.get(f"{self.mcp_url}/api/ontology/{ontology_source}/status")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error checking ontology status: {response.status_code} - {response.text}")
                return {'status': 'unknown', 'message': f'Error: {response.status_code}'}
        except Exception as e:
            print(f"Error checking ontology status: {str(e)}")
            return {'status': 'unknown', 'message': f'Error: {str(e)}'}
    
    def get_ontology_content(self, ontology_source: str) -> Dict[str, Any]:
        """
        Get the content of an ontology file.
        
        Args:
            ontology_source: Source of the ontology (e.g., filename.ttl)
            
        Returns:
            Content of the ontology file as string
        """
        try:
            # Make request to get ontology content
            response = self.session.get(f"{self.mcp_url}/api/ontology/{ontology_source}/content")
            
            if response.status_code == 200:
                # Return content in a dictionary
                return {'content': response.text, 'success': True}
            else:
                print(f"Error getting ontology content: {response.status_code} - {response.text}")
                return {'content': '', 'success': False, 'error': f"{response.status_code} - {response.text}"}
        except Exception as e:
            print(f"Error getting ontology content: {str(e)}")
            return {'content': '', 'success': False, 'error': str(e)}
    
    def update_ontology_content(self, ontology_source: str, content: str) -> Dict[str, Any]:
        """
        Update the content of an ontology file.
        
        Args:
            ontology_source: Source of the ontology (e.g., filename.ttl)
            content: New content for the ontology file
            
        Returns:
            Dictionary containing success status and message
        """
        try:
            # Make request to update ontology content
            response = self.session.put(
                f"{self.mcp_url}/api/ontology/{ontology_source}/content",
                data=content,
                headers={'Content-Type': 'text/turtle'}
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Ontology updated successfully'}
            else:
                print(f"Error updating ontology content: {response.status_code} - {response.text}")
                return {'success': False, 'message': f"Error: {response.status_code} - {response.text}"}
        except Exception as e:
            print(f"Error updating ontology content: {str(e)}")
            return {'success': False, 'message': f"Error: {str(e)}"}
    
    def refresh_world_entities_by_ontology(self, ontology_source: str) -> Dict[str, Any]:
        """
        Refresh all worlds using a specific ontology.
        
        Args:
            ontology_source: Source of the ontology
            
        Returns:
            Dictionary with results of the refresh operation
        """
        try:
            # Find all worlds using this ontology source
            from app.models.world import World
            from app import db
            
            worlds = World.query.filter_by(ontology_source=ontology_source).all()
            
            if not worlds:
                return {'success': True, 'message': f'No worlds found using ontology {ontology_source}'}
            
            results = []
            for world in worlds:
                result = self.refresh_world_entities(world.id)
                results.append({
                    'world_id': world.id,
                    'world_name': world.name,
                    'success': result
                })
            
            # Check if any refreshes failed
            all_successful = all(r['success'] for r in results)
            
            return {
                'success': all_successful,
                'message': f"Refreshed {len(results)} world(s) using ontology {ontology_source}",
                'details': results
            }
        except Exception as e:
            print(f"Error refreshing worlds for ontology {ontology_source}: {str(e)}")
            return {'success': False, 'message': f"Error: {str(e)}"}
    
    def refresh_world_entities(self, world_id: int) -> bool:
        """
        Refresh world entities after ontology changes.
        
        Args:
            world_id: ID of the world to refresh
            
        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            from app.models.world import World
            
            # Get the world
            world = World.query.get(world_id)
            if not world or not world.ontology_source:
                print(f"World not found or no ontology source for world {world_id}")
                return False
            
            # Make request to refresh entities
            response = self.session.post(
                f"{self.mcp_url}/api/world/{world_id}/refresh_entities",
                json={'ontology_source': world.ontology_source}
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"Error refreshing world entities: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error refreshing world entities: {str(e)}")
            return False
    
    def get_references_for_world(self, world) -> List[Dict[str, Any]]:
        """
        Get references for a specific world.
        
        Args:
            world: World object
            
        Returns:
            List of references
        """
        try:
            # Create search query based on world properties
            query_parts = []
            if hasattr(world, 'name') and world.name:
                query_parts.append(world.name)
            if hasattr(world, 'description') and world.description:
                query_parts.append(world.description)
            if hasattr(world, 'ontology_source') and world.ontology_source:
                query_parts.append(world.ontology_source)
            
            # Add metadata if available
            if hasattr(world, 'world_metadata') and world.world_metadata:
                for key, value in world.world_metadata.items():
                    if isinstance(value, str):
                        query_parts.append(value)
                    elif isinstance(value, (dict, list)):
                        # Convert to string for search
                        query_parts.append(str(value))
            elif hasattr(world, 'metadata') and world.metadata:
                for key, value in world.metadata.items():
                    if isinstance(value, str):
                        query_parts.append(value)
                    elif isinstance(value, (dict, list)):
                        # Convert to string for search
                        query_parts.append(str(value))
            
            # Create query string
            query = " ".join(query_parts)
            
            # Get ZoteroClient instance or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Search for references using the ZoteroClient's search_items method directly
            return zotero_client.search_items(query)
        except Exception as e:
            print(f"Error retrieving references: {str(e)}")
            return []
    
    def get_references_for_scenario(self, scenario) -> List[Dict[str, Any]]:
        """
        Get references for a specific scenario.
        
        Args:
            scenario: Scenario object
            
        Returns:
            List of references
        """
        try:
            # Create search query based on scenario properties
            query_parts = []
            if hasattr(scenario, 'name') and scenario.name:
                query_parts.append(scenario.name)
            if hasattr(scenario, 'description') and scenario.description:
                query_parts.append(scenario.description)
            
            # Add metadata if available
            if hasattr(scenario, 'metadata') and scenario.metadata:
                for key, value in scenario.metadata.items():
                    if isinstance(value, str):
                        query_parts.append(value)
                    elif isinstance(value, (dict, list)):
                        # Convert to string for search
                        query_parts.append(str(value))
            
            # Create query string
            query = " ".join(query_parts)
            
            # Search for references using the search_zotero_items method
            return self.search_zotero_items(query)
        except Exception as e:
            print(f"Error retrieving references for scenario: {str(e)}")
            return []
    
    def search_zotero_items(self, query: str, collection_key: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for items in the Zotero library.
        
        Args:
            query: Search query
            collection_key: Collection key to search in (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of items
        """
        try:
            # Get ZoteroClient instance using the singleton pattern or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Search for items
            items = zotero_client.search_items(query, collection_key, limit)
            return items
        except Exception as e:
            print(f"Error searching Zotero items: {str(e)}")
            return []
    
    def get_zotero_citation(self, item_key: str, style: str = "apa") -> str:
        """
        Get citation for a specific Zotero item.
        
        Args:
            item_key: Item key
            style: Citation style (e.g., apa, mla, chicago)
            
        Returns:
            Citation text
        """
        try:
            # Get ZoteroClient instance using the singleton pattern or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Get citation
            return zotero_client.get_citation(item_key, style)
        except Exception as e:
            print(f"Error getting citation: {str(e)}")
            return f"Error: {str(e)}"
    
    def get_zotero_bibliography(self, item_keys: List[str], style: str = "apa") -> str:
        """
        Get bibliography for multiple Zotero items.
        
        Args:
            item_keys: Array of item keys
            style: Citation style (e.g., apa, mla, chicago)
            
        Returns:
            Bibliography text
        """
        try:
            # Get ZoteroClient instance or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Get bibliography
            return zotero_client.get_bibliography(item_keys, style)
        except Exception as e:
            print(f"Error getting bibliography: {str(e)}")
            return f"Error: {str(e)}"
    
    def get_zotero_collections(self) -> List[Dict[str, Any]]:
        """
        Get collections from the Zotero library.
        
        Returns:
            List of collections
        """
        try:
            # Get ZoteroClient instance or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Get collections
            return zotero_client.get_collections()
        except Exception as e:
            print(f"Error getting collections: {str(e)}")
            return []
    
    def get_zotero_recent_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent items from the Zotero library.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of items
        """
        try:
            # Get ZoteroClient instance or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Get recent items
            return zotero_client.get_recent_items(limit)
        except Exception as e:
            print(f"Error getting recent items: {str(e)}")
            return []
    
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
            Response from the Zotero API
        """
        try:
            # Get ZoteroClient instance or use the one set for testing
            zotero_client = self._zotero_client if self._zotero_client else ZoteroClient.get_instance()
            
            # Add item
            return zotero_client.add_item(item_type, title, creators, collection_key, additional_fields)
        except Exception as e:
            print(f"Error adding item: {str(e)}")
            return {"error": str(e)}
    
    def get_mock_entities(self, ontology_source: str) -> Dict[str, Any]:
        """
        Get mock entities for development and testing.
        
        Args:
            ontology_source: Source of the ontology
            
        Returns:
            Dictionary containing mock entities
        """
        # Mock entities for different ontologies
        mock_entities = {
            "engineering_ethics.ttl": {
                "roles": [
                    {
                        "label": "Engineer",
                        "description": "Professional responsible for designing, building, and maintaining systems, structures, and products."
                    },
                    {
                        "label": "Manager",
                        "description": "Person responsible for overseeing projects and teams."
                    },
                    {
                        "label": "Client",
                        "description": "Person or organization that commissions engineering work."
                    }
                ],
                "conditions": [
                    {
                        "label": "Safety Risk",
                        "description": "Situation where there is potential for harm to people or property."
                    },
                    {
                        "label": "Budget Constraint",
                        "description": "Limitation on financial resources available for a project."
                    },
                    {
                        "label": "Time Pressure",
                        "description": "Urgency to complete work within a tight deadline."
                    }
                ],
                "resources": [
                    {
                        "label": "Engineering Code of Ethics",
                        "description": "Professional standards that govern the practice of engineering."
                    },
                    {
                        "label": "Technical Specifications",
                        "description": "Detailed requirements for a system or component."
                    }
                ],
                "actions": [
                    {
                        "label": "Report Safety Concern",
                        "description": "Notify appropriate parties about potential safety issues."
                    },
                    {
                        "label": "Approve Design",
                        "description": "Formally accept a design as meeting requirements and standards."
                    },
                    {
                        "label": "Request Additional Testing",
                        "description": "Ask for more verification of a system's performance or safety."
                    }
                ]
            }
        }
        
        # Return mock entities for the specified ontology or empty dictionary if not found
        return {"entities": mock_entities.get(ontology_source, {})}
