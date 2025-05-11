#!/usr/bin/env python3
"""
Query Module for Unified Ontology Server

This module provides query functionality for the unified ontology server,
including entity retrieval, SPARQL execution, and guideline access.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
import traceback

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL
from rdflib.plugins.sparql import prepareQuery

from mcp.modules.base_module import BaseModule

# Set up logging
logger = logging.getLogger("QueryModule")


class QueryModule(BaseModule):
    """
    Query module for accessing ontology data.
    
    Provides tools for querying ontology entities, executing SPARQL queries,
    and accessing ontology guidelines.
    """
    
    @property
    def name(self) -> str:
        """Get the name of this module."""
        return "query"
    
    @property
    def description(self) -> str:
        """Get the description of this module."""
        return "Query functionality for ontology access"
    
    def _register_tools(self) -> None:
        """Register the tools provided by this module."""
        self.tools = {
            "get_entities": self.get_entities,
            "execute_sparql": self.execute_sparql,
            "get_guidelines": self.get_guidelines,
            "get_entity_details": self.get_entity_details
        }
    
    def get_entities(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get entities of a specific type from an ontology.
        
        Args:
            arguments: Dict with keys:
                - ontology_source: Source identifier for ontology
                - entity_type: Type of entities to retrieve (optional, default: 'all')
                
        Returns:
            Dict with entities
        """
        ontology_source = arguments.get("ontology_source")
        entity_type = arguments.get("entity_type", "all")
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Load the graph
            g = self.server._load_graph_from_file(ontology_source)
            
            entities = []
            
            # For 'all' entity type, get all classes
            if entity_type == "all":
                # Get all classes (excluding some builtin ones)
                for s in g.subjects(RDF.type, OWL.Class):
                    if isinstance(s, URIRef) and not str(s).startswith(str(OWL)):
                        # Get label and description
                        labels = list(g.objects(s, RDFS.label))
                        comments = list(g.objects(s, RDFS.comment))
                        
                        entity = {
                            "id": str(s),
                            "label": str(labels[0]) if labels else str(s).split("/")[-1].split("#")[-1],
                            "description": str(comments[0]) if comments else "",
                            "type": "class"
                        }
                        
                        entities.append(entity)
            elif entity_type == "properties":
                # Get all properties
                for s in g.subjects(RDF.type, OWL.ObjectProperty):
                    if isinstance(s, URIRef):
                        # Get label and description
                        labels = list(g.objects(s, RDFS.label))
                        comments = list(g.objects(s, RDFS.comment))
                        
                        entity = {
                            "id": str(s),
                            "label": str(labels[0]) if labels else str(s).split("/")[-1].split("#")[-1],
                            "description": str(comments[0]) if comments else "",
                            "type": "property"
                        }
                        
                        entities.append(entity)
            elif entity_type == "individuals":
                # Get all individuals (instances)
                seen_individuals = set()
                
                # Look for things that are instances of classes
                for s, o in g.subject_objects(RDF.type):
                    if isinstance(s, URIRef) and isinstance(o, URIRef) and o != OWL.Class and o != OWL.ObjectProperty:
                        if str(s) in seen_individuals:
                            continue
                            
                        seen_individuals.add(str(s))
                        
                        # Get label and description
                        labels = list(g.objects(s, RDFS.label))
                        comments = list(g.objects(s, RDFS.comment))
                        
                        entity = {
                            "id": str(s),
                            "label": str(labels[0]) if labels else str(s).split("/")[-1].split("#")[-1],
                            "description": str(comments[0]) if comments else "",
                            "type": "individual",
                            "class": str(o)
                        }
                        
                        entities.append(entity)
            else:
                # Try to get entities of a specific type
                try:
                    type_uri = URIRef(entity_type)
                except:
                    # If not a URI, try to find by name/fragment
                    found = False
                    for cls in g.subjects(RDF.type, OWL.Class):
                        if isinstance(cls, URIRef):
                            name = str(cls).split("/")[-1].split("#")[-1]
                            if name.lower() == entity_type.lower():
                                type_uri = cls
                                found = True
                                break
                    
                    if not found:
                        return {"error": f"Entity type not found: {entity_type}"}
                
                # Get instances of this class
                for s in g.subjects(RDF.type, type_uri):
                    if isinstance(s, URIRef):
                        # Get label and description
                        labels = list(g.objects(s, RDFS.label))
                        comments = list(g.objects(s, RDFS.comment))
                        
                        entity = {
                            "id": str(s),
                            "label": str(labels[0]) if labels else str(s).split("/")[-1].split("#")[-1],
                            "description": str(comments[0]) if comments else "",
                            "type": "individual",
                            "class": str(type_uri)
                        }
                        
                        entities.append(entity)
            
            return {
                "entities": entities,
                "count": len(entities),
                "ontology_source": ontology_source,
                "entity_type": entity_type
            }
        except Exception as e:
            logger.error(f"Error getting entities: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error getting entities: {str(e)}"}
    
    def execute_sparql(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a SPARQL query on an ontology.
        
        Args:
            arguments: Dict with keys:
                - ontology_source: Source identifier for ontology
                - query: SPARQL query to execute
                - include_prefixes: Whether to include common prefixes (optional, default: true)
                
        Returns:
            Dict with query results
        """
        ontology_source = arguments.get("ontology_source")
        query = arguments.get("query")
        include_prefixes = arguments.get("include_prefixes", True)
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        if not query:
            return {"error": "Missing query parameter"}
        
        try:
            # Load the graph
            g = self.server._load_graph_from_file(ontology_source)
            
            # Add common prefixes if requested
            if include_prefixes:
                prefixes = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_>
                PREFIX proethica: <http://proethica.org/ontology/>
                PREFIX proethica-i: <http://proethica.org/ontology/intermediate#>
                PREFIX mseo: <http://matportal.org/ontology/MSEO#>
                """
                # Only add prefixes if they're not already in the query
                if not any(line.strip().lower().startswith("prefix") for line in query.split("\n")):
                    query = prefixes + query
            
            # Prepare and execute query
            try:
                results = g.query(query)
                
                # Process results based on query type
                if results.type == "SELECT":
                    # Convert to list of dicts
                    bindings = []
                    for row in results.bindings:
                        binding = {}
                        for var in results.vars:
                            if var in row:
                                value = row[var]
                                if isinstance(value, URIRef):
                                    binding[var] = {"type": "uri", "value": str(value)}
                                elif isinstance(value, Literal):
                                    binding[var] = {"type": "literal", "value": str(value)}
                                elif isinstance(value, BNode):
                                    binding[var] = {"type": "bnode", "value": str(value)}
                                else:
                                    binding[var] = {"type": "unknown", "value": str(value)}
                        bindings.append(binding)
                    
                    return {
                        "head": {"vars": [str(v) for v in results.vars]},
                        "results": {"bindings": bindings},
                        "count": len(bindings)
                    }
                elif results.type == "ASK":
                    return {"boolean": results.askAnswer}
                elif results.type == "CONSTRUCT" or results.type == "DESCRIBE":
                    # Convert result graph to triples
                    triples = []
                    for s, p, o in results.graph:
                        triple = {
                            "subject": {"type": "uri" if isinstance(s, URIRef) else "bnode", "value": str(s)},
                            "predicate": {"type": "uri", "value": str(p)},
                            "object": {}
                        }
                        
                        if isinstance(o, URIRef):
                            triple["object"] = {"type": "uri", "value": str(o)}
                        elif isinstance(o, Literal):
                            triple["object"] = {"type": "literal", "value": str(o)}
                        else:
                            triple["object"] = {"type": "bnode", "value": str(o)}
                        
                        triples.append(triple)
                    
                    return {
                        "triples": triples,
                        "count": len(triples)
                    }
            except Exception as e:
                return {"error": f"SPARQL error: {str(e)}"}
            
            return {"error": "Unknown result type"}
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error executing SPARQL query: {str(e)}"}
    
    def get_guidelines(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get guidelines for a specific world or ontology.
        
        Args:
            arguments: Dict with keys:
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with guidelines text
        """
        ontology_source = arguments.get("ontology_source")
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Try to look up world in database
            if self.server.app:
                with self.server.app.app_context():
                    try:
                        # Look up World by name or ID
                        from app.models.world import World
                        
                        world = None
                        try:
                            # Try as integer ID
                            world_id = int(ontology_source)
                            world = World.query.get(world_id)
                        except (ValueError, TypeError):
                            # Try by name
                            world = World.query.filter_by(name=ontology_source).first()
                        
                        if world:
                            guidelines = world.guidelines if hasattr(world, 'guidelines') and world.guidelines else world.description
                            
                            return {
                                "guidelines": guidelines,
                                "world_id": world.id,
                                "world_name": world.name
                            }
                    except ImportError:
                        logger.warning("World model not available")
                    except Exception as e:
                        logger.error(f"Error retrieving world: {str(e)}")
            
            # If no world found, try to extract guidelines from ontology
            try:
                g = self.server._load_graph_from_file(ontology_source)
                
                # Look for ontology metadata
                for s in g.subjects(RDF.type, OWL.Ontology):
                    comments = list(g.objects(s, RDFS.comment))
                    if comments:
                        return {
                            "guidelines": str(comments[0]),
                            "source": str(s)
                        }
                
                # If no ontology metadata found, return empty guidelines
                return {
                    "guidelines": f"No guidelines found for {ontology_source}",
                    "source": ontology_source
                }
            except Exception as e:
                logger.error(f"Error extracting guidelines from ontology: {str(e)}")
                return {
                    "guidelines": f"Error extracting guidelines: {str(e)}",
                    "source": ontology_source
                }
        except Exception as e:
            logger.error(f"Error getting guidelines: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error getting guidelines: {str(e)}"}
    
    def get_entity_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed information about a specific entity.
        
        Args:
            arguments: Dict with keys:
                - ontology_source: Source identifier for ontology
                - entity_id: URI or ID of the entity
                
        Returns:
            Dict with entity details
        """
        ontology_source = arguments.get("ontology_source")
        entity_id = arguments.get("entity_id")
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        if not entity_id:
            return {"error": "Missing entity_id parameter"}
        
        try:
            # Load the graph
            g = self.server._load_graph_from_file(ontology_source)
            
            # Try to convert entity_id to URI
            try:
                entity_uri = URIRef(entity_id)
            except:
                # If not a valid URI, try to find by name/fragment
                found = False
                for s in g.subjects():
                    if isinstance(s, URIRef):
                        name = str(s).split("/")[-1].split("#")[-1]
                        if name.lower() == entity_id.lower():
                            entity_uri = s
                            found = True
                            break
                
                if not found:
                    return {"error": f"Entity not found: {entity_id}"}
            
            # Check if entity exists in the graph
            if not (entity_uri, None, None) in g and not (None, None, entity_uri) in g:
                return {"error": f"Entity not found: {entity_id}"}
            
            # Get basic information
            labels = list(g.objects(entity_uri, RDFS.label))
            comments = list(g.objects(entity_uri, RDFS.comment))
            types = list(g.objects(entity_uri, RDF.type))
            
            # Determine entity type
            entity_type = "unknown"
            if (entity_uri, RDF.type, OWL.Class) in g:
                entity_type = "class"
            elif (entity_uri, RDF.type, OWL.ObjectProperty) in g:
                entity_type = "property"
            elif (entity_uri, RDF.type, OWL.DatatypeProperty) in g:
                entity_type = "datatype_property"
            elif types:
                entity_type = "individual"
            
            # Get all properties and values
            properties = []
            for p, o in g.predicate_objects(entity_uri):
                prop = {
                    "predicate": str(p),
                    "object": str(o)
                }
                
                # Get predicate label if available
                pred_labels = list(g.objects(p, RDFS.label))
                if pred_labels:
                    prop["predicate_label"] = str(pred_labels[0])
                else:
                    prop["predicate_label"] = str(p).split("/")[-1].split("#")[-1]
                
                # Get object details if it's a URI
                if isinstance(o, URIRef):
                    obj_labels = list(g.objects(o, RDFS.label))
                    if obj_labels:
                        prop["object_label"] = str(obj_labels[0])
                    else:
                        prop["object_label"] = str(o).split("/")[-1].split("#")[-1]
                    
                    prop["object_type"] = "uri"
                elif isinstance(o, Literal):
                    prop["object_type"] = "literal"
                    if o.datatype:
                        prop["datatype"] = str(o.datatype)
                else:
                    prop["object_type"] = "bnode"
                
                properties.append(prop)
            
            # Get incoming relationships
            incoming = []
            for s, p in g.subject_predicates(entity_uri):
                rel = {
                    "subject": str(s),
                    "predicate": str(p)
                }
                
                # Get subject label if it's a URI
                if isinstance(s, URIRef):
                    subj_labels = list(g.objects(s, RDFS.label))
                    if subj_labels:
                        rel["subject_label"] = str(subj_labels[0])
                    else:
                        rel["subject_label"] = str(s).split("/")[-1].split("#")[-1]
                    
                    rel["subject_type"] = "uri"
                elif isinstance(s, BNode):
                    rel["subject_type"] = "bnode"
                
                # Get predicate label
                pred_labels = list(g.objects(p, RDFS.label))
                if pred_labels:
                    rel["predicate_label"] = str(pred_labels[0])
                else:
                    rel["predicate_label"] = str(p).split("/")[-1].split("#")[-1]
                
                incoming.append(rel)
            
            # Assemble entity details
            details = {
                "id": str(entity_uri),
                "label": str(labels[0]) if labels else str(entity_uri).split("/")[-1].split("#")[-1],
                "description": str(comments[0]) if comments else "",
                "type": entity_type,
                "types": [str(t) for t in types],
                "properties": properties,
                "incoming_relationships": incoming
            }
            
            # Add class-specific information
            if entity_type == "class":
                # Get subclasses and superclasses
                subclasses = [str(s) for s in g.subjects(RDFS.subClassOf, entity_uri) if isinstance(s, URIRef)]
                superclasses = [str(o) for o in g.objects(entity_uri, RDFS.subClassOf) if isinstance(o, URIRef)]
                
                details["subclasses"] = subclasses
                details["superclasses"] = superclasses
                
                # Get class instances
                instances = [str(s) for s in g.subjects(RDF.type, entity_uri) if isinstance(s, URIRef)]
                details["instances"] = instances
                details["instance_count"] = len(instances)
            
            # Add property-specific information
            if entity_type in ["property", "datatype_property"]:
                # Get domain and range
                domains = [str(o) for o in g.objects(entity_uri, RDFS.domain) if isinstance(o, URIRef)]
                ranges = [str(o) for o in g.objects(entity_uri, RDFS.range) if isinstance(o, URIRef)]
                
                details["domains"] = domains
                details["ranges"] = ranges
            
            return details
        except Exception as e:
            logger.error(f"Error getting entity details: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error getting entity details: {str(e)}"}
