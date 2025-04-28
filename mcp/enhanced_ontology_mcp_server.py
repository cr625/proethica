#!/usr/bin/env python3
"""
Enhanced Ontology MCP Server

This module provides an enhanced MCP server that extends the basic HTTP ontology MCP server
with more sophisticated ontology interaction capabilities.
"""

import json
import os
import sys
import asyncio
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal
from rdflib.namespace import OWL
from aiohttp import web
import traceback

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mcp.http_ontology_mcp_server import OntologyMCPServer
from app.services.entity_triple_service import EntityTripleService

class EnhancedOntologyMCPServer(OntologyMCPServer):
    """
    Enhanced MCP server with advanced ontology capabilities.
    
    This server extends the basic HTTP ontology MCP server with more sophisticated
    ontology interaction tools, including:
    - Advanced query capabilities
    - Relationship navigation
    - Entity hierarchy traversal
    - Constraint checking
    - Semantic search capabilities
    """
    
    def __init__(self):
        """Initialize the enhanced MCP server."""
        super().__init__()
        self.entity_triple_service = EntityTripleService()
        self.mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:5001")
        print("Enhanced Ontology MCP Server initialized")
        
        # Initialize Flask app context for database access
        try:
            from app import create_app
            self.app = create_app()
            print("Successfully initialized Flask app")
        except Exception as e:
            print(f"Warning: Failed to initialize Flask app: {str(e)}")
            self.app = None
            
    def _load_graph_from_file(self, ontology_source):
        """
        Override the base class method to ensure proper Flask application context
        when loading ontologies from the database.
        
        Args:
            ontology_source: Source identifier for ontology (domain_id or filename)
            
        Returns:
            RDFLib Graph object with loaded ontology
        """
        # If we have a Flask app, use its context for database access
        if self.app:
            with self.app.app_context():
                return super()._load_graph_from_file(ontology_source)
        else:
            # Fallback to the parent implementation without app context
            return super()._load_graph_from_file(ontology_source)
    
    async def _handle_list_tools(self, params):
        """
        Override to include more advanced ontology tools.
        
        Returns:
            Dictionary listing all available tools
        """
        return {
            "tools": [
                "get_world_entities",
                "query_ontology",
                "get_entity_relationships",
                "navigate_entity_hierarchy",
                "check_constraint",
                "search_entities",
                "get_entity_details",
                "get_ontology_guidelines"
            ]
        }
    
    async def _handle_call_tool(self, params):
        """
        Override to handle more advanced tools.
        
        Args:
            params: Parameters for the tool call
            
        Returns:
            Result of the tool execution
        """
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if name == "get_world_entities":
                return await self._handle_get_world_entities(arguments)
            elif name == "query_ontology":
                return await self._handle_query_ontology(arguments)
            elif name == "get_entity_relationships":
                return await self._handle_get_entity_relationships(arguments)
            elif name == "navigate_entity_hierarchy":
                return await self._handle_navigate_entity_hierarchy(arguments)
            elif name == "check_constraint":
                return await self._handle_check_constraint(arguments)
            elif name == "search_entities":
                return await self._handle_search_entities(arguments)
            elif name == "get_entity_details":
                return await self._handle_get_entity_details(arguments)
            elif name == "get_ontology_guidelines":
                return await self._handle_get_ontology_guidelines(arguments)
            
            return {"content": [{"text": json.dumps({"error": "Unknown tool"})}]}
        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error executing tool {name}: {str(e)}"
            print(error_msg)
            return {"content": [{"text": json.dumps({"error": error_msg})}]}
    
    async def _handle_get_world_entities(self, arguments):
        """
        Handle the get_world_entities tool.
        
        Arguments:
            ontology_source: Source identifier for ontology
            entity_type: Type of entity to retrieve (roles, conditions, etc.)
        """
        ontology_source = arguments.get("ontology_source")
        entity_type = arguments.get("entity_type", "all")
        g = self._load_graph_from_file(ontology_source)
        entities = self._extract_entities(g, entity_type)
        return {"content": [{"text": json.dumps({"entities": entities})}]}
    
    async def _handle_query_ontology(self, arguments):
        """
        Handle the query_ontology tool for running SPARQL queries against ontologies.
        
        Arguments:
            ontology_source: Source identifier for ontology
            query: SPARQL query string
            
        Returns:
            Query results
        """
        try:
            ontology_source = arguments.get("ontology_source")
            query = arguments.get("query")
            
            if not ontology_source or not query:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source and query"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Execute the SPARQL query
            results = []
            for row in g.query(query):
                result = {}
                for i, var in enumerate(row.vars):
                    value = row[i]
                    if isinstance(value, rdflib.term.URIRef):
                        # For URI references, include label if available
                        label = g.value(value, RDFS.label)
                        result[str(var)] = {
                            "uri": str(value), 
                            "label": str(label) if label else str(value).split("/")[-1].replace("_", " ")
                        }
                    else:
                        result[str(var)] = str(value)
                results.append(result)
            
            return {"content": [{"text": json.dumps({
                "results": results,
                "query": query
            })}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error executing query: {str(e)}"
            })}]}
    
    async def _handle_get_entity_relationships(self, arguments):
        """
        Handle the get_entity_relationships tool for exploring entity connections.
        
        Arguments:
            ontology_source: Source identifier for ontology
            entity_uri: URI of the entity to find relationships for
            relationship_type: Optional type of relationship to filter by
            
        Returns:
            Incoming and outgoing relationships for the entity
        """
        try:
            ontology_source = arguments.get("ontology_source")
            entity_uri = arguments.get("entity_uri")
            relationship_type = arguments.get("relationship_type")
            
            if not ontology_source or not entity_uri:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source and entity_uri"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Create URIRef from string
            entity = URIRef(entity_uri)
            
            # Get incoming relationships (where entity is the object)
            incoming = []
            for s, p in g.subject_predicates(entity):
                # Skip if filtering by relationship type and it doesn't match
                if relationship_type and str(p) != relationship_type:
                    continue
                    
                # Get labels
                s_label = g.value(s, RDFS.label)
                p_label = g.value(p, RDFS.label)
                
                incoming.append({
                    "subject": {
                        "uri": str(s),
                        "label": str(s_label) if s_label else str(s).split("/")[-1].replace("_", " ")
                    },
                    "predicate": {
                        "uri": str(p),
                        "label": str(p_label) if p_label else str(p).split("/")[-1].replace("_", " ")
                    }
                })
            
            # Get outgoing relationships (where entity is the subject)
            outgoing = []
            for p, o in g.predicate_objects(entity):
                # Skip if filtering by relationship type and it doesn't match
                if relationship_type and str(p) != relationship_type:
                    continue
                    
                # Get labels
                p_label = g.value(p, RDFS.label)
                
                if isinstance(o, URIRef):
                    o_label = g.value(o, RDFS.label)
                    outgoing.append({
                        "predicate": {
                            "uri": str(p),
                            "label": str(p_label) if p_label else str(p).split("/")[-1].replace("_", " ")
                        },
                        "object": {
                            "uri": str(o),
                            "label": str(o_label) if o_label else str(o).split("/")[-1].replace("_", " "),
                            "is_literal": False
                        }
                    })
                else:
                    outgoing.append({
                        "predicate": {
                            "uri": str(p),
                            "label": str(p_label) if p_label else str(p).split("/")[-1].replace("_", " ")
                        },
                        "object": {
                            "value": str(o),
                            "datatype": str(o.datatype) if hasattr(o, 'datatype') else None,
                            "is_literal": True
                        }
                    })
            
            # Get entity label
            entity_label = g.value(entity, RDFS.label)
            entity_label = str(entity_label) if entity_label else entity_uri.split("/")[-1].replace("_", " ")
            
            return {"content": [{"text": json.dumps({
                "entity": {
                    "uri": entity_uri,
                    "label": entity_label
                },
                "incoming_relationships": incoming,
                "outgoing_relationships": outgoing
            })}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error getting entity relationships: {str(e)}"
            })}]}
    
    async def _handle_navigate_entity_hierarchy(self, arguments):
        """
        Handle the navigate_entity_hierarchy tool for exploring class/subclass relationships.
        
        Arguments:
            ontology_source: Source identifier for ontology
            entity_uri: URI of the entity to navigate from
            direction: 'up' for parents, 'down' for children, 'both' for both
            
        Returns:
            Parent and/or child entities in the hierarchy
        """
        try:
            ontology_source = arguments.get("ontology_source")
            entity_uri = arguments.get("entity_uri")
            direction = arguments.get("direction", "both")
            
            if not ontology_source or not entity_uri:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source and entity_uri"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Create URIRef from string
            entity = URIRef(entity_uri)
            
            # Get entity label
            entity_label = g.value(entity, RDFS.label)
            entity_label = str(entity_label) if entity_label else entity_uri.split("/")[-1].replace("_", " ")
            
            result = {
                "entity": {
                    "uri": entity_uri,
                    "label": entity_label
                }
            }
            
            # Get parent classes if direction is 'up' or 'both'
            if direction in ['up', 'both']:
                parents = []
                for o in g.objects(entity, RDFS.subClassOf):
                    if isinstance(o, URIRef):
                        o_label = g.value(o, RDFS.label)
                        parents.append({
                            "uri": str(o),
                            "label": str(o_label) if o_label else str(o).split("/")[-1].replace("_", " ")
                        })
                result["parents"] = parents
            
            # Get child classes if direction is 'down' or 'both'
            if direction in ['down', 'both']:
                children = []
                for s in g.subjects(RDFS.subClassOf, entity):
                    if isinstance(s, URIRef):
                        s_label = g.value(s, RDFS.label)
                        children.append({
                            "uri": str(s),
                            "label": str(s_label) if s_label else str(s).split("/")[-1].replace("_", " ")
                        })
                result["children"] = children
            
            return {"content": [{"text": json.dumps(result)}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error navigating entity hierarchy: {str(e)}"
            })}]}
    
    async def _handle_check_constraint(self, arguments):
        """
        Handle the check_constraint tool for validating against ontology constraints.
        
        Arguments:
            ontology_source: Source identifier for ontology
            constraint_type: Type of constraint to check
            entity_uri: URI of the entity to check constraints for
            constraint_data: Additional data needed for checking the constraint
            
        Returns:
            Constraint check result
        """
        try:
            ontology_source = arguments.get("ontology_source")
            constraint_type = arguments.get("constraint_type")
            entity_uri = arguments.get("entity_uri")
            constraint_data = arguments.get("constraint_data", {})
            
            if not all([ontology_source, constraint_type, entity_uri]):
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source, constraint_type, entity_uri"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Create URIRef from string
            entity = URIRef(entity_uri)
            
            # Different types of constraints
            if constraint_type == "domain_range":
                # Check if a property can be used with the given domain/range
                property_uri = constraint_data.get("property_uri")
                target_uri = constraint_data.get("target_uri")
                
                if not property_uri or not target_uri:
                    return {"content": [{"text": json.dumps({
                        "error": "Missing required constraint_data: property_uri, target_uri"
                    })}]}
                
                property_entity = URIRef(property_uri)
                target_entity = URIRef(target_uri)
                
                # Check domain constraints
                domains = list(g.objects(property_entity, RDFS.domain))
                is_valid_domain = not domains or any(
                    g.transitive_objects(entity, RDFS.subClassOf).__contains__(domain)
                    for domain in domains
                )
                
                # Check range constraints
                ranges = list(g.objects(property_entity, RDFS.range))
                is_valid_range = not ranges or any(
                    g.transitive_objects(target_entity, RDFS.subClassOf).__contains__(range_obj)
                    for range_obj in ranges
                )
                
                return {"content": [{"text": json.dumps({
                    "is_valid": is_valid_domain and is_valid_range,
                    "domain_valid": is_valid_domain,
                    "range_valid": is_valid_range,
                    "domains": [str(d) for d in domains],
                    "ranges": [str(r) for r in ranges]
                })}]}
            
            elif constraint_type == "cardinality":
                # Check cardinality constraints for a property
                property_uri = constraint_data.get("property_uri")
                
                if not property_uri:
                    return {"content": [{"text": json.dumps({
                        "error": "Missing required constraint_data: property_uri"
                    })}]}
                
                property_entity = URIRef(property_uri)
                
                # Count existing values for this property
                values = list(g.objects(entity, property_entity))
                count = len(values)
                
                # Check if there are any cardinality restrictions
                min_cardinality = None
                max_cardinality = None
                
                # Check for owl:Restriction on the class or its parents
                for parent in g.transitive_objects(entity, RDFS.subClassOf):
                    if (parent, RDF.type, OWL.Restriction) in g:
                        # Check if the restriction is on our property
                        if (parent, OWL.onProperty, property_entity) in g:
                            # Check min cardinality
                            for min_card in g.objects(parent, OWL.minCardinality):
                                try:
                                    min_cardinality = int(min_card)
                                except (ValueError, TypeError):
                                    pass
                            
                            # Check max cardinality
                            for max_card in g.objects(parent, OWL.maxCardinality):
                                try:
                                    max_cardinality = int(max_card)
                                except (ValueError, TypeError):
                                    pass
                
                # Determine if constraints are satisfied
                min_satisfied = min_cardinality is None or count >= min_cardinality
                max_satisfied = max_cardinality is None or count <= max_cardinality
                
                return {"content": [{"text": json.dumps({
                    "is_valid": min_satisfied and max_satisfied,
                    "current_count": count,
                    "min_cardinality": min_cardinality,
                    "max_cardinality": max_cardinality,
                    "min_satisfied": min_satisfied,
                    "max_satisfied": max_satisfied
                })}]}
            
            elif constraint_type == "custom":
                # Custom constraints - pass validation to specialized functions
                validation_type = constraint_data.get("validation_type")
                
                if validation_type == "role_capability":
                    # Check if a role has the required capabilities
                    required_capabilities = constraint_data.get("required_capabilities", [])
                    
                    if not required_capabilities:
                        return {"content": [{"text": json.dumps({
                            "error": "No required capabilities specified"
                        })}]}
                    
                    # Find capabilities of the role
                    proeth = self.namespaces.get("proethica-intermediate", 
                                                Namespace("http://proethica.org/ontology/intermediate#"))
                    
                    role_capabilities = list(g.objects(entity, proeth.hasCapability))
                    role_capability_uris = [str(c) for c in role_capabilities]
                    
                    # Check if all required capabilities are present
                    missing_capabilities = []
                    for cap in required_capabilities:
                        if cap not in role_capability_uris:
                            missing_capabilities.append(cap)
                    
                    return {"content": [{"text": json.dumps({
                        "is_valid": len(missing_capabilities) == 0,
                        "role_capabilities": role_capability_uris,
                        "missing_capabilities": missing_capabilities
                    })}]}
                
                else:
                    return {"content": [{"text": json.dumps({
                        "error": f"Unsupported validation_type: {validation_type}"
                    })}]}
            
            else:
                return {"content": [{"text": json.dumps({
                    "error": f"Unsupported constraint_type: {constraint_type}"
                })}]}
        
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error checking constraint: {str(e)}"
            })}]}
    
    async def _handle_search_entities(self, arguments):
        """
        Handle the search_entities tool for finding entities by keywords or patterns.
        
        Arguments:
            ontology_source: Source identifier for ontology
            query: Text to search for
            entity_type: Optional type of entity to filter by
            match_mode: How to match (contains, exact, regex)
            
        Returns:
            List of matching entities
        """
        try:
            ontology_source = arguments.get("ontology_source")
            query = arguments.get("query")
            entity_type = arguments.get("entity_type")
            match_mode = arguments.get("match_mode", "contains")
            
            if not ontology_source or not query:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source and query"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Find all entities of the specified type (or all types)
            entities = []
            
            # Get all subjects with labels
            for s, p, o in g.triples((None, RDFS.label, None)):
                # Skip if not a resource
                if not isinstance(s, URIRef):
                    continue
                    
                # Get label as string
                label = str(o)
                
                # Check if entity matches search criteria
                matches = False
                if match_mode == "contains":
                    matches = query.lower() in label.lower()
                elif match_mode == "exact":
                    matches = query.lower() == label.lower()
                elif match_mode == "regex":
                    import re
                    try:
                        matches = re.search(query, label, re.IGNORECASE) is not None
                    except:
                        matches = False
                
                # If no match, skip this entity
                if not matches:
                    continue
                
                # If filtering by entity type
                if entity_type:
                    # Get types of the entity
                    types = [str(t) for t in g.objects(s, RDF.type)]
                    
                    # Check if any type matches the filter
                    type_match = False
                    for entity_type_uri in types:
                        if entity_type.lower() in entity_type_uri.lower():
                            type_match = True
                            break
                    
                    # Skip if no matching type
                    if not type_match:
                        continue
                
                # Add to results
                entities.append({
                    "uri": str(s),
                    "label": label,
                    "types": [str(t) for t in g.objects(s, RDF.type)]
                })
            
            return {"content": [{"text": json.dumps({
                "entities": entities,
                "count": len(entities),
                "query": query
            })}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error searching entities: {str(e)}"
            })}]}
    
    async def _handle_get_entity_details(self, arguments):
        """
        Handle the get_entity_details tool for getting comprehensive information about an entity.
        
        Arguments:
            ontology_source: Source identifier for ontology
            entity_uri: URI of the entity to get details for
            
        Returns:
            Comprehensive entity information
        """
        try:
            ontology_source = arguments.get("ontology_source")
            entity_uri = arguments.get("entity_uri")
            
            if not ontology_source or not entity_uri:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameters: ontology_source and entity_uri"
                })}]}
            
            g = self._load_graph_from_file(ontology_source)
            
            # Create URIRef from string
            entity = URIRef(entity_uri)
            
            # Basic entity information
            label = g.value(entity, RDFS.label)
            comment = g.value(entity, RDFS.comment)
            
            # Get types
            types = []
            for t in g.objects(entity, RDF.type):
                if isinstance(t, URIRef):
                    t_label = g.value(t, RDFS.label)
                    types.append({
                        "uri": str(t),
                        "label": str(t_label) if t_label else str(t).split("/")[-1].replace("_", " ")
                    })
            
            # Get all properties and values
            properties = []
            for p, o in g.predicate_objects(entity):
                # Skip standard RDF/RDFS properties
                if p in [RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf]:
                    continue
                    
                # Get predicate label
                p_label = g.value(p, RDFS.label)
                p_label = str(p_label) if p_label else str(p).split("/")[-1].replace("_", " ")
                
                # Format object based on type
                if isinstance(o, URIRef):
                    o_label = g.value(o, RDFS.label)
                    o_formatted = {
                        "uri": str(o),
                        "label": str(o_label) if o_label else str(o).split("/")[-1].replace("_", " "),
                        "is_literal": False
                    }
                else:
                    o_formatted = {
                        "value": str(o),
                        "datatype": str(o.datatype) if hasattr(o, 'datatype') else None,
                        "is_literal": True
                    }
                
                properties.append({
                    "predicate": {
                        "uri": str(p),
                        "label": p_label
                    },
                    "object": o_formatted
                })
            
            # Get parent classes
            parents = []
            for o in g.objects(entity, RDFS.subClassOf):
                if isinstance(o, URIRef):
                    o_label = g.value(o, RDFS.label)
                    parents.append({
                        "uri": str(o),
                        "label": str(o_label) if o_label else str(o).split("/")[-1].replace("_", " ")
                    })
            
            # Get child classes
            children = []
            for s in g.subjects(RDFS.subClassOf, entity):
                if isinstance(s, URIRef):
                    s_label = g.value(s, RDFS.label)
                    children.append({
                        "uri": str(s),
                        "label": str(s_label) if s_label else str(s).split("/")[-1].replace("_", " ")
                    })
            
            # Compile all information
            entity_details = {
                "uri": entity_uri,
                "label": str(label) if label else entity_uri.split("/")[-1].replace("_", " "),
                "description": str(comment) if comment else None,
                "types": types,
                "properties": properties,
                "parents": parents,
                "children": children
            }
            
            # Check if this is a specific entity type
            proeth = self.namespaces.get("proethica-intermediate", 
                                         Namespace("http://proethica.org/ontology/intermediate#"))
            
            # If it's a role, add capabilities
            if (entity, RDF.type, proeth.Role) in g or any(t['uri'] == str(proeth.Role) for t in types):
                capabilities = []
                for cap in g.objects(entity, proeth.hasCapability):
                    if isinstance(cap, URIRef):
                        cap_label = g.value(cap, RDFS.label)
                        cap_desc = g.value(cap, RDFS.comment)
                        capabilities.append({
                            "uri": str(cap),
                            "label": str(cap_label) if cap_label else str(cap).split("/")[-1].replace("_", " "),
                            "description": str(cap_desc) if cap_desc else None
                        })
                entity_details["capabilities"] = capabilities
            
            return {"content": [{"text": json.dumps(entity_details)}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error getting entity details: {str(e)}"
            })}]}
    
    async def _handle_get_ontology_guidelines(self, arguments):
        """
        Handle the get_ontology_guidelines tool for extracting guidelines from ontology.
        
        Arguments:
            ontology_source: Source identifier for ontology or world name
            
        Returns:
            Guidelines extracted from the ontology
        """
        try:
            ontology_source = arguments.get("ontology_source")
            
            if not ontology_source:
                return {"content": [{"text": json.dumps({
                    "error": "Missing required parameter: ontology_source"
                })}]}
            
            # First try to get guidelines from the API endpoint
            try:
                response = await self._get_guidelines_from_endpoint(ontology_source)
                if response:
                    return {"content": [{"text": json.dumps(response)}]}
            except Exception as e:
                print(f"Error getting guidelines from endpoint: {str(e)}")
                
            # If that fails, extract from the ontology
            g = self._load_graph_from_file(ontology_source)
            
            # Look for Guideline or Principle classes
            guidelines = []
            
            # Define common guideline/principle predicates
            guideline_types = [
                URIRef("http://proethica.org/ontology/Guideline"),
                URIRef("http://proethica.org/ontology/Principle"),
                URIRef("http://proethica.org/ontology/ethical-principle"),
                URIRef("http://proethica.org/ontology/intermediate#Guideline"),
                URIRef("http://proethica.org/ontology/intermediate#Principle"),
            ]
            
            # Add domain-specific types
            namespaces = [ns for ns in self.namespaces.values()]
            for ns in namespaces:
                guideline_types.extend([
                    ns.Guideline if hasattr(ns, 'Guideline') else None,
                    ns.Principle if hasattr(ns, 'Principle') else None,
                    ns.EthicalPrinciple if hasattr(ns, 'EthicalPrinciple') else None,
                ])
            
            # Filter out None values
            guideline_types = [t for t in guideline_types if t]
            
            # Find all instances of these types
            for guideline_type in guideline_types:
                for s in g.subjects(RDF.type, guideline_type):
                    label = g.value(s, RDFS.label)
                    comment = g.value(s, RDFS.comment)
                    
                    if label:
                        guidelines.append({
                            "uri": str(s),
                            "label": str(label),
                            "description": str(comment) if comment else None,
                            "type": str(guideline_type)
                        })
            
            # Look for principles defined as annotations
            principle_predicates = [
                URIRef("http://proethica.org/ontology/hasPrinciple"),
                URIRef("http://proethica.org/ontology/hasGuideline"),
                URIRef("http://proethica.org/ontology/intermediate#hasPrinciple"),
                URIRef("http://proethica.org/ontology/intermediate#hasGuideline"),
            ]
            
            # Look for annotations using these predicates
            for pred in principle_predicates:
                for s, o in g.subject_objects(pred):
                    if isinstance(o, Literal):
                        # This is a literal guideline annotation
                        guidelines.append({
                            "uri": str(s) + "#principle-" + str(len(guidelines)),
                            "label": str(o),
                            "description": None,
                            "type": str(pred),
                            "is_annotation": True
                        })
            
            return {"content": [{"text": json.dumps({
                "guidelines": guidelines,
                "count": len(guidelines),
                "ontology_source": ontology_source
            })}]}
        except Exception as e:
            traceback.print_exc()
            return {"content": [{"text": json.dumps({
                "error": f"Error getting ontology guidelines: {str(e)}"
            })}]}
    
    async def _get_guidelines_from_endpoint(self, world_name):
        """
        Get guidelines from the guidelines API endpoint.
        
        Args:
            world_name: Name of the world or ontology source
            
        Returns:
            Guidelines data or None if not found
        """
        try:
            # Make request to the guidelines endpoint
            url = f"{self.mcp_url}/api/guidelines/{world_name}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        print(f"Error getting guidelines: {response.status} - {await response.text()}")
                        return None
        except Exception as e:
            print(f"Error accessing guidelines endpoint: {str(e)}")
            return None
