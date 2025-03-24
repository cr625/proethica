import requests
import json
from typing import Dict, List, Any, Optional
import os
from app.services.zotero_client import ZoteroClient

class MCPClient:
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
        
        # Initialize session
        self.session = requests.Session()
    
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
    
    def get_world_entities(self, ontology_source: str) -> Dict[str, Any]:
        """
        Get entities for a specific world from ontology.
        
        Args:
            ontology_source: Source of the ontology
            
        Returns:
            Dictionary containing entities
        """
        try:
            # Make request to MCP server
            response = self.session.get(f"{self.mcp_url}/api/ontology/{ontology_source}/entities")
            
            # Check if request was successful
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting entities: {response.status_code} - {response.text}")
                # Fall back to mock data
                return self.get_mock_entities(ontology_source)
        except Exception as e:
            print(f"Error getting entities: {str(e)}")
            # Fall back to mock data
            return self.get_mock_entities(ontology_source)
    
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
            
            # Search for references using the search_zotero_items method
            return self.search_zotero_items(query)
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
            print(f"Error retrieving references: {str(e)}")
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
            # Get ZoteroClient instance using the singleton pattern
            zotero_client = ZoteroClient.get_instance()
            
            # Search for items
            return zotero_client.search_items(query, collection_key, limit)
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
            # Get ZoteroClient instance using the singleton pattern
            zotero_client = ZoteroClient.get_instance()
            
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
            # Get ZoteroClient instance
            zotero_client = ZoteroClient.get_instance()
            
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
            # Get ZoteroClient instance
            zotero_client = ZoteroClient.get_instance()
            
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
            # Get ZoteroClient instance
            zotero_client = ZoteroClient.get_instance()
            
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
            # Get ZoteroClient instance
            zotero_client = ZoteroClient.get_instance()
            
            # Add item
            return zotero_client.add_item(item_type, title, creators, collection_key, additional_fields)
        except Exception as e:
            print(f"Error adding item: {str(e)}")
            return {"error": str(e)}
    
    def get_mock_guidelines(self, world_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get mock guidelines for development and testing.
        
        Args:
            world_name: Name of the world
            
        Returns:
            Dictionary containing mock guidelines
        """
        # Mock guidelines for different worlds
        mock_guidelines = {
            "engineering-ethics": [
                {
                    "name": "Engineering Code of Ethics",
                    "description": "Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.",
                    "principles": [
                        "Engineers shall recognize that the lives, safety, health and welfare of the general public are dependent upon engineering judgments, decisions and practices incorporated into structures, machines, products, processes and devices.",
                        "Engineers shall approve or seal only those design documents, reviewed or prepared by them, which are determined to be safe for public health and welfare in conformity with accepted engineering standards.",
                        "Engineers shall not reveal facts, data or information obtained in a professional capacity without the prior consent of the client or employer except as authorized or required by law.",
                        "Engineers shall act in professional matters for each employer or client as faithful agents or trustees.",
                        "Engineers shall disclose all known or potential conflicts of interest to their employers or clients by promptly informing them of any business association, interest, or other circumstances which could influence or appear to influence their judgment or the quality of their services."
                    ],
                    "factors": [
                        "Public safety and welfare",
                        "Professional competence",
                        "Truthfulness and objectivity",
                        "Confidentiality",
                        "Conflicts of interest",
                        "Professional development"
                    ]
                }
            ],
            "military-medical-ethics": [
                {
                    "name": "Military Medical Triage Guidelines",
                    "description": "Triage is the process of sorting casualties based on the severity of injury and likelihood of survival to determine treatment priority.",
                    "principles": [
                        "Maximize the number of lives saved",
                        "Allocate scarce resources efficiently",
                        "Treat patients according to medical need and urgency",
                        "Reassess patients regularly",
                        "Document decisions and rationales"
                    ],
                    "categories": [
                        {
                            "name": "Immediate (T1/Red)",
                            "description": "Casualties who require immediate life-saving intervention. Without immediate treatment, they will likely die within 1-2 hours."
                        },
                        {
                            "name": "Delayed (T2/Yellow)",
                            "description": "Casualties whose treatment can be delayed without significant risk to life or limb. They require medical care but can wait hours without serious consequences."
                        },
                        {
                            "name": "Minimal (T3/Green)",
                            "description": "Casualties with minor injuries who can effectively care for themselves or be helped by untrained personnel."
                        },
                        {
                            "name": "Expectant (T4/Black)",
                            "description": "Casualties who are so severely injured that they are unlikely to survive given the available resources. In mass casualty situations, these patients receive palliative care rather than resource-intensive interventions."
                        }
                    ],
                    "considerations": [
                        "Available medical resources (personnel, equipment, supplies)",
                        "Number and types of casualties",
                        "Environmental conditions",
                        "Evacuation capabilities",
                        "Ongoing threats or hazards"
                    ]
                }
            ],
            "legal-ethics": [
                {
                    "name": "Legal Ethics Guidelines",
                    "description": "Lawyers must maintain the highest standards of ethical conduct. These guidelines outline the ethical responsibilities of legal professionals.",
                    "principles": [
                        "Competence: Lawyers shall provide competent representation to clients.",
                        "Confidentiality: Lawyers shall not reveal information relating to the representation of a client unless the client gives informed consent.",
                        "Conflicts of Interest: Lawyers shall not represent a client if the representation involves a concurrent conflict of interest.",
                        "Candor: Lawyers shall not knowingly make a false statement of fact or law to a tribunal.",
                        "Fairness: Lawyers shall deal fairly with all parties in legal proceedings."
                    ],
                    "steps": [
                        "Identify the ethical issue",
                        "Consult relevant rules and precedents",
                        "Consider all stakeholders affected",
                        "Evaluate alternative courses of action",
                        "Make a decision and implement it",
                        "Reflect on the outcome and learn from it"
                    ]
                }
            ]
        }
        
        # Return mock guidelines for the specified world or empty dictionary if not found
        return {"guidelines": mock_guidelines.get(world_name, [])}
    
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
            },
            "military_medical_ethics.ttl": {
                "roles": [
                    {
                        "label": "Medical Officer",
                        "description": "Military physician responsible for providing medical care to personnel."
                    },
                    {
                        "label": "Combat Medic",
                        "description": "Soldier with medical training who provides first aid in combat situations."
                    },
                    {
                        "label": "Triage Officer",
                        "description": "Medical professional responsible for sorting casualties based on severity and priority."
                    }
                ],
                "conditions": [
                    {
                        "label": "Mass Casualty Event",
                        "description": "Situation where the number of casualties exceeds available medical resources."
                    },
                    {
                        "label": "Active Combat",
                        "description": "Ongoing military engagement with hostile forces."
                    },
                    {
                        "label": "Resource Limitation",
                        "description": "Shortage of medical supplies, equipment, or personnel."
                    }
                ],
                "resources": [
                    {
                        "label": "Medical Supplies",
                        "description": "Materials used for treating injuries and illnesses."
                    },
                    {
                        "label": "Evacuation Assets",
                        "description": "Vehicles and aircraft used to transport casualties."
                    }
                ],
                "actions": [
                    {
                        "label": "Perform Triage",
                        "description": "Sort casualties based on severity and treatment priority."
                    },
                    {
                        "label": "Administer Treatment",
                        "description": "Provide medical care to injured personnel."
                    },
                    {
                        "label": "Order Evacuation",
                        "description": "Arrange for transport of casualties to higher levels of care."
                    }
                ]
            },
            "legal_ethics.ttl": {
                "roles": [
                    {
                        "label": "Attorney",
                        "description": "Legal professional qualified to represent clients in court."
                    },
                    {
                        "label": "Client",
                        "description": "Person or entity receiving legal representation."
                    },
                    {
                        "label": "Judge",
                        "description": "Official who presides over court proceedings."
                    }
                ],
                "conditions": [
                    {
                        "label": "Conflict of Interest",
                        "description": "Situation where professional judgment may be compromised by personal interests."
                    },
                    {
                        "label": "Confidential Information",
                        "description": "Private details protected by attorney-client privilege."
                    }
                ],
                "resources": [
                    {
                        "label": "Rules of Professional Conduct",
                        "description": "Ethical standards governing the legal profession."
                    },
                    {
                        "label": "Case Law",
                        "description": "Previous court decisions that establish precedent."
                    }
                ],
                "actions": [
                    {
                        "label": "Disclose Conflict",
                        "description": "Inform affected parties about potential conflicts of interest."
                    },
                    {
                        "label": "Maintain Confidentiality",
                        "description": "Protect private information shared by clients."
                    },
                    {
                        "label": "Withdraw Representation",
                        "description": "End attorney-client relationship when ethically required."
                    }
                ]
            },
            "nj_legal_ethics.ttl": {
                "roles": [
                    {
                        "label": "Attorney",
                        "description": "Legal professional qualified to represent clients in New Jersey courts."
                    },
                    {
                        "label": "Client",
                        "description": "Person or entity receiving legal representation in New Jersey."
                    },
                    {
                        "label": "Judge",
                        "description": "Official who presides over New Jersey court proceedings."
                    },
                    {
                        "label": "Paralegal",
                        "description": "Legal assistant who supports attorneys in case preparation and research."
                    }
                ],
                "conditions": [
                    {
                        "label": "Conflict of Interest",
                        "description": "Situation where professional judgment may be compromised by personal interests (RPC 1.7)."
                    },
                    {
                        "label": "Confidentiality Issue",
                        "description": "Concerns about protecting private client information (RPC 1.6)."
                    },
                    {
                        "label": "Client Perjury",
                        "description": "Ethical dilemma when a client intends to commit perjury (RPC 3.3)."
                    },
                    {
                        "label": "Evidence Handling",
                        "description": "Proper treatment of documentary and physical evidence (RPC 3.4)."
                    }
                ],
                "resources": [
                    {
                        "label": "NJ Rules of Professional Conduct",
                        "description": "Ethical standards governing the legal profession in New Jersey."
                    },
                    {
                        "label": "NJ Case Law",
                        "description": "Previous New Jersey court decisions that establish precedent."
                    },
                    {
                        "label": "Legal Research Database",
                        "description": "Electronic resources for researching legal issues and precedents."
                    }
                ],
                "actions": [
                    {
                        "label": "Disclose Conflict",
                        "description": "Inform affected parties about potential conflicts of interest."
                    },
                    {
                        "label": "Maintain Confidentiality",
                        "description": "Protect private information shared by clients."
                    },
                    {
                        "label": "Withdraw Representation",
                        "description": "End attorney-client relationship when ethically required."
                    },
                    {
                        "label": "File Motion",
                        "description": "Submit formal request to the court for a specific action or decision."
                    },
                    {
                        "label": "Report Misconduct",
                        "description": "Notify appropriate authorities about unethical behavior by legal professionals."
                    }
                ]
            }
        }
        
        # Return mock entities for the specified ontology or empty dictionary if not found
        return {"entities": mock_entities.get(ontology_source, {})}
