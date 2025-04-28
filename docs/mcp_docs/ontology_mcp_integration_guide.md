# Ontology Integration with MCP Servers

This guide explains how to effectively integrate ontologies with Model Context Protocol (MCP) servers, with a special focus on creating MCP servers that expose ontology data to LLMs.

## Table of Contents

- [Ontology Integration with MCP Servers](#ontology-integration-with-mcp-servers)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Understanding Ontologies in AI Systems](#understanding-ontologies-in-ai-systems)
    - [What is an Ontology?](#what-is-an-ontology)
    - [Ontologies in Ethical Decision Making](#ontologies-in-ethical-decision-making)
  - [MCP Server Design for Ontology Access](#mcp-server-design-for-ontology-access)
    - [1. Graph-Based Access Layer](#1-graph-based-access-layer)
    - [2. MCP Server Integration](#2-mcp-server-integration)
  - [Entity Type Handling](#entity-type-handling)
    - [1. Flexible Type Detection](#1-flexible-type-detection)
    - [2. Common Entity Types](#2-common-entity-types)
    - [3. Rich Entity Information](#3-rich-entity-information)
  - [Database vs File-Based Storage](#database-vs-file-based-storage)
    - [Database-First Approach with File Fallback](#database-first-approach-with-file-fallback)
  - [Namespace Management](#namespace-management)
    - [Detecting and Handling Namespaces](#detecting-and-handling-namespaces)
  - [Relationship Extraction](#relationship-extraction)
    - [Entity Hierarchies](#entity-hierarchies)
    - [Semantic Relationships](#semantic-relationships)

## Introduction

Ontologies provide a structured way to represent domain knowledge, including concepts, relationships, and rules. When integrated with MCP servers, ontologies allow LLMs to access and reason with domain-specific knowledge, improving their ability to provide accurate, contextually relevant responses.

This guide focuses specifically on:
- Creating MCP servers that expose ontology data
- Extracting entities and relationships from RDF ontologies
- Managing data access efficiently 
- Providing semantic understanding to LLMs

## Understanding Ontologies in AI Systems

### What is an Ontology?

An ontology is a formal representation of knowledge as a set of concepts within a domain, and the relationships between those concepts. Key components include:

- **Classes/Concepts**: Categories or types of entities (e.g., Engineer, Project, Ethical Principle)
- **Instances**: Individual members of classes (e.g., "Bridge Construction Project")
- **Properties/Relations**: Connections between instances (e.g., "manages", "requires", "violates")
- **Attributes**: Data associated with instances (e.g., priority level, start date)
- **Rules/Axioms**: Constraints and logical implications

### Ontologies in Ethical Decision Making

For ethical AI systems, ontologies provide:
- Structured representation of ethical principles
- Domain-specific guidelines and norms
- Entity relationships for ethical reasoning
- Context for ethical decision-making

## MCP Server Design for Ontology Access

When designing an MCP server for ontology access, consider these architectural patterns:

### 1. Graph-Based Access Layer

Create a service layer that loads and queries RDF graphs:

```python
class OntologyAccessLayer:
    def __init__(self):
        self.graphs = {}  # Domain ID -> RDFLib Graph
        self.namespaces = {}  # Domain ID -> Primary Namespace
        
    def load_ontology(self, domain_id, source):
        """Load ontology from file or database."""
        graph = Graph()
        # Load from source (file or DB)
        self.graphs[domain_id] = graph
        self.namespaces[domain_id] = self._detect_primary_namespace(graph)
        
    def get_entities(self, domain_id, entity_type):
        """Extract entities of specified type from ontology."""
        if domain_id not in self.graphs:
            return {"error": "Domain not found"}
            
        graph = self.graphs[domain_id]
        namespace = self.namespaces[domain_id]
        
        # Extract entities based on type
        # ...
```

### 2. MCP Server Integration

Expose ontology data through MCP tools and resources:

```python
from mcp.server import FastMCP

def create_ontology_mcp_server():
    mcp = FastMCP("Ontology Server")
    access_layer = OntologyAccessLayer()
    
    # Load ontologies
    access_layer.load_ontology("engineering", "ontologies/engineering-ethics.ttl")
    access_layer.load_ontology("medical", "ontologies/medical-ethics.ttl")
    
    @mcp.tool("get_world_entities")
    def get_world_entities(ontology_source: str, entity_type: str = "all") -> dict:
        """
        Get entities from specified ontology.
        
        Args:
            ontology_source: Domain ID of the ontology
            entity_type: Type of entity to retrieve (roles, conditions, etc.)
        """
        return access_layer.get_entities(ontology_source, entity_type)
    
    @mcp.resource("guidelines/{domain}")
    def get_guidelines(domain: str) -> dict:
        """Get ethical guidelines for specified domain."""
        return access_layer.get_guidelines(domain)
    
    return mcp
```

## Entity Type Handling

Effective entity type handling is crucial for ontology-based MCP servers. Consider these strategies:

### 1. Flexible Type Detection

Look for entities across multiple potential class definitions:

```python
def get_entities_of_type(graph, type_uri, namespace, intermediate_namespace):
    """Find entities of a specific type across multiple namespaces."""
    entities = set()
    
    # Direct matching in domain namespace
    entities.update(graph.subjects(RDF.type, namespace[type_uri]))
    
    # Matching in intermediate namespace
    entities.update(graph.subjects(RDF.type, intermediate_namespace[type_uri]))
    
    # Look for entities with both EntityType and specific type
    entity_type_subjects = set(graph.subjects(RDF.type, intermediate_namespace.EntityType))
    for subject in entity_type_subjects:
        if (subject, RDF.type, intermediate_namespace[type_uri]) in graph:
            entities.add(subject)
    
    return entities
```

### 2. Common Entity Types

Standard entity types to extract from ethical ontologies:

- **Roles**: Characters or positions (e.g., Engineer, Manager, Doctor)
- **Conditions**: States or contexts (e.g., ConflictOfInterest, EmergencySituation)
- **Resources**: Objects or assets (e.g., Document, MedicalEquipment)
- **Actions**: Activities that can be performed (e.g., Approve, Review, Treat)
- **Events**: Occurrences in time (e.g., Meeting, Accident, Procedure)
- **Capabilities**: Skills or abilities (e.g., StructuralAnalysis, PatientCare)

### 3. Rich Entity Information

Extract comprehensive information about each entity:

```python
def extract_role_info(graph, role_uri, namespace):
    """Extract rich information about a role entity."""
    info = {
        "id": str(role_uri),
        "label": str(next(graph.objects(role_uri, RDFS.label), "")),
        "description": str(next(graph.objects(role_uri, RDFS.comment), "")),
        "capabilities": [],
        "responsibilities": [],
        "relationships": []
    }
    
    # Get capabilities
    for capability in graph.objects(role_uri, namespace.hasCapability):
        info["capabilities"].append({
            "id": str(capability),
            "label": str(next(graph.objects(capability, RDFS.label), ""))
        })
    
    # Get responsibilities
    for responsibility in graph.objects(role_uri, namespace.hasResponsibility):
        info["responsibilities"].append({
            "id": str(responsibility),
            "label": str(next(graph.objects(responsibility, RDFS.label), ""))
        })
    
    # Get relationships to other entities
    for predicate, obj in graph.predicate_objects(role_uri):
        if predicate not in [RDF.type, RDFS.label, RDFS.comment, namespace.hasCapability, namespace.hasResponsibility]:
            info["relationships"].append({
                "predicate": str(predicate),
                "object_id": str(obj),
                "predicate_label": str(next(graph.objects(predicate, RDFS.label), "")),
                "object_label": str(next(graph.objects(obj, RDFS.label), ""))
            })
    
    return info
```

## Database vs File-Based Storage

### Database-First Approach with File Fallback

For robustness, implement a database-first strategy with file-based fallback:

```python
def load_ontology_from_source(ontology_source):
    """Load ontology primarily from database with file fallback."""
    graph = Graph()
    
    try:
        # First try to load from database
        from app import create_app, db
        from app.models.ontology import Ontology
        
        app = create_app()
        with app.app_context():
            # Try to fetch from database
            ontology = Ontology.query.filter_by(domain_id=ontology_source).first()
            
            if ontology:
                graph.parse(data=ontology.content, format="turtle")
                return graph
    except Exception as e:
        print(f"Database loading error: {str(e)}")
    
    # Fall back to file-based loading
    try:
        file_path = f"ontologies/{ontology_source}.ttl"
        if os.path.exists(file_path):
            graph.parse(file_path, format="turtle")
            return graph
    except Exception as e:
        print(f"File loading error: {str(e)}")
    
    return graph  # May be empty if loading failed
```

## Namespace Management

### Detecting and Handling Namespaces

Properly detect and manage namespaces to avoid URI conflicts:

```python
def detect_primary_namespace(graph):
    """Detect the primary namespace used in the ontology."""
    # Track potential matches
    matches = {}
    
    # Try to find the ontology declaration
    for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
        ontology_uri = str(s)
        if "engineering-ethics" in ontology_uri:
            matches["engineering"] = 10  # Higher priority
        elif "medical-ethics" in ontology_uri:
            matches["medical"] = 10
    
    # Check for namespace prefixes in the graph
    for prefix, namespace in graph.namespaces():
        namespace_str = str(namespace)
        if prefix == "eng" or "engineering" in namespace_str:
            matches["engineering"] = matches.get("engineering", 0) + 5
        elif prefix == "med" or "medical" in namespace_str:
            matches["medical"] = matches.get("medical", 0) + 5
    
    # Find the namespace with the highest score
    if matches:
        best_match = max(matches.items(), key=lambda x: x[1])[0]
        if best_match == "engineering":
            return Namespace("http://proethica.org/ontology/engineering-ethics#")
        elif best_match == "medical":
            return Namespace("http://proethica.org/ontology/medical-ethics#")
    
    # Default to intermediate namespace if no clear match
    return Namespace("http://proethica.org/ontology/intermediate#")
```

## Relationship Extraction

### Entity Hierarchies

Extract parent-child relationships for better concept organization:

```python
def extract_entity_hierarchy(graph, entity_type, namespace):
    """Extract hierarchy of entities of a specific type."""
    entities = {}
    
    # Find all entities of the specified type
    for subject in graph.subjects(RDF.type, namespace[entity_type]):
        entity_id = str(subject)
        label = str(next(graph.objects(subject, RDFS.label), ""))
        parent = next(graph.objects(subject, RDFS.subClassOf), None)
        
        entities[entity_id] = {
            "id": entity_id,
            "label": label,
            "parent": str(parent) if parent else None,
            "children": []
        }
    
    # Build hierarchy by assigning children
    for entity_id, entity in entities.items():
        parent_id = entity["parent"]
        if parent_id and parent_id in entities:
            entities[parent_id]["children"].append(entity_id)
    
    return entities
```

### Semantic Relationships

Extract meaningful semantic relationships between entities:

```python
def extract_semantic_relationships(graph):
    """Extract all meaningful semantic relationships between entities."""
    relationships = []
    
    # Skip standard RDF/RDFS/OWL predicates
    skip_predicates = {
        RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf, 
        OWL.equivalentClass, OWL.disjointWith
    }
    
    # Find all relationship triples
    for s, p, o in graph.triples((None, None, None)):
        if p in skip_predicates:
            continue
            
        # Only include relationships between named entities (not literals)
        if isinstance(o, URIRef):
            s_label = str(next(graph.objects(s, RDFS.label), ""))
            p_label = str(next(graph.objects(p, RDFS.label), ""))
            o_label = str(next(graph.objects(o, RDFS.label), ""))
            
            relationships.append({
                "subject_id": str(s),
                "subject_label": s_label if s_label else str(s).split("#")[-1],
                "predicate_id": str(
