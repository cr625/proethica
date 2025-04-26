"""
Entity Service for Ontology Editor

This service provides functionality to manage entities in ontologies:
- Create new entities
- Update existing entities
- Delete entities
- Check entity editability (protected vs. modifiable)
"""

import os
import re
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from app import db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion

class EntityService:
    @classmethod
    def is_parent_of(cls, parent, entity):
        """
        Check if parent is the parent of an entity.
        Used for selecting the correct parent in the dropdown.
        
        Args:
            parent (dict): Parent entity data
            entity (dict): Entity data
            
        Returns:
            bool: True if parent is the parent of entity
        """
        if not parent or not entity:
            return False
            
        # Debug output
        print(f"Comparing parent ID: {parent.get('id')}")
        print(f"With entity parent_class: {entity.get('parent_class')}")
        
        # Ensure consistent string comparison
        parent_id = str(parent.get('id')).strip() if parent.get('id') else None
        entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
        
        print(f"Cleaned comparison: '{parent_id}' == '{entity_parent}'")
        print(f"Result: {parent_id == entity_parent}")
        
        return parent_id == entity_parent

    """Service for ontology entity management"""
    
    # Entity types mapping to their classes in the ontology
    ENTITY_TYPES = {
        'role': 'Role',
        'condition': 'ConditionType',
        'resource': 'ResourceType',
        'action': 'ActionType',
        'event': 'EventType',
        'capability': 'Capability'
    }
    
    # Base ontology namespace prefixes (protected from editing)
    PROTECTED_NAMESPACES = [
        'http://purl.obolibrary.org/obo/BFO_',  # BFO
        'http://proethica.org/ontology/intermediate#'  # Intermediate ontology
    ]
    
    @classmethod
    def is_editable(cls, entity):
        """
        Check if an entity is editable (not part of protected base ontologies)
        
        Args:
            entity (dict): Entity data with id
            
        Returns:
            bool: True if entity can be edited, False if protected
        """
        if not entity or not entity.get('id'):
            return False
            
        # Check if entity ID is in any protected namespace
        entity_id = entity['id']
        return not any(entity_id.startswith(ns) for ns in cls.PROTECTED_NAMESPACES)
    
    @classmethod
    def get_entity_origin(cls, entity):
        """
        Get the origin namespace of an entity
        
        Args:
            entity (dict): Entity data with id
            
        Returns:
            str: Origin description ("Base BFO", "Intermediate", "Domain")
        """
        if not entity or not entity.get('id'):
            return "Unknown"
            
        entity_id = entity['id']
        
        if entity_id.startswith('http://purl.obolibrary.org/obo/BFO_'):
            return "Base BFO"
        elif entity_id.startswith('http://proethica.org/ontology/intermediate#'):
            return "Intermediate Ontology"
        else:
            return "Domain Ontology"
    
    @classmethod
    def get_valid_parents(cls, ontology_id, entity_type):
        """
        Get valid parent classes for a given entity type
        
        Args:
            ontology_id (int): Ontology ID
            entity_type (str): Entity type ('role', 'condition', etc.)
            
        Returns:
            list: List of valid parent classes
        """
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            return []
            
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Determine namespace patterns from data
        namespaces = {}
        for prefix, ns in g.namespaces():
            namespaces[prefix] = ns
        
        # Try to find the class type URI from common patterns
        class_type = cls.ENTITY_TYPES.get(entity_type)
        if not class_type:
            return []
        
        # Get all instances of the class type
        class_instances = []
        
        # Common base URIs to check
        base_uris = [
            'http://purl.obolibrary.org/obo/BFO_',
            'http://proethica.org/ontology/intermediate#',
            'http://proethica.org/ontology/engineering#'
        ]
        
        # Try with common URIs first
        for base_uri in base_uris:
            try:
                class_uri = URIRef(f"{base_uri}{class_type}")
                class_instances.extend(g.subjects(RDF.type, class_uri))
            except Exception as e:
                print(f"Error with {base_uri}: {e}")
        
        # Check for domain-specific namespaces
        for prefix, ns in g.namespaces():
            try:
                # ns is already a Namespace object with __getitem__ defined
                class_uri = ns[class_type]
                class_instances.extend(g.subjects(RDF.type, class_uri))
            except Exception as e:
                pass
        
        # Get information about each instance
        results = []
        for instance in class_instances:
            label = next(g.objects(instance, RDFS.label), None)
            label = str(label) if label else str(instance).split('#')[-1]
            
            results.append({
                'id': str(instance),
                'label': label
            })
        
        # Add special base classes if they're missing
        if entity_type == 'role':
            # Check if EngineeringRole is already in results
            eng_role_id = "http://proethica.org/ontology/engineering-ethics#EngineeringRole"
            eng_role_in_results = any(r['id'] == eng_role_id for r in results)
            
            if not eng_role_in_results:
                # Add EngineeringRole explicitly
                print("Adding EngineeringRole explicitly to parent options")
                results.append({
                    'id': eng_role_id,
                    'label': "Engineering Role"
                })
                
            # Also add intermediate Role if needed
            int_role_id = "http://proethica.org/ontology/intermediate#Role"
            int_role_in_results = any(r['id'] == int_role_id for r in results)
            
            if not int_role_in_results:
                # Add intermediate Role explicitly
                print("Adding intermediate Role explicitly to parent options")
                results.append({
                    'id': int_role_id,
                    'label': "Role (Base)"
                })
        
        elif entity_type == 'condition':
            # Add special condition base classes if missing
            condition_base_classes = [
                {
                    'id': "http://proethica.org/ontology/intermediate#ConditionType",
                    'label': "Condition Type"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EthicalDilemma",
                    'label': "Ethical Dilemma"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#Principle",
                    'label': "Principle"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#SafetyPrinciple",
                    'label': "Safety Principle"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#ConflictOfInterestCondition",
                    'label': "Conflict of Interest Condition"
                }
            ]
            
            # Add any missing base classes
            for base_class in condition_base_classes:
                if not any(r['id'] == base_class['id'] for r in results):
                    print(f"Adding {base_class['label']} explicitly to condition parent options")
                    results.append(base_class)
        
        elif entity_type == 'resource':
            # Add special resource base classes if missing
            resource_base_classes = [
                {
                    'id': "http://proethica.org/ontology/intermediate#ResourceType",
                    'label': "Resource Type"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringDocument",
                    'label': "Engineering Document"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringDrawing",
                    'label': "Engineering Drawing"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringSpecification",
                    'label': "Engineering Specification"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringReport",
                    'label': "Engineering Report"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#BuildingCode",
                    'label': "Building Code"
                }
            ]
            
            # Add any missing base classes
            for base_class in resource_base_classes:
                if not any(r['id'] == base_class['id'] for r in results):
                    print(f"Adding {base_class['label']} explicitly to resource parent options")
                    results.append(base_class)
        
        # Sort results by label for consistent order
        results.sort(key=lambda x: x['label'])
        
        return results
    
    @classmethod
    def create_entity(cls, ontology_id, entity_type, data):
        """
        Create a new entity in the ontology
        
        Args:
            ontology_id (int): Ontology ID
            entity_type (str): Entity type ('role', 'condition', etc.)
            data (dict): Entity data with label, description, parent_class
            
        Returns:
            tuple: (success, result)
                success (bool): Whether the operation succeeded
                result (dict): Result data or error message
        """
        # Validate inputs
        if not entity_type in cls.ENTITY_TYPES:
            return False, {"error": f"Invalid entity type: {entity_type}"}
            
        if not data.get('label'):
            return False, {"error": "Label is required"}
            
        if not data.get('parent_class'):
            return False, {"error": "Parent class is required"}
            
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            return False, {"error": f"Ontology not found: {ontology_id}"}
            
        # Check if ontology is editable
        if not ontology.is_editable:
            return False, {"error": "This ontology is protected and cannot be modified"}
            
        try:
            # Parse the ontology content
            g = Graph()
            g.parse(data=ontology.content, format="turtle")
            
            # Determine base URI for new entity
            base_uri = cls._get_ontology_base_uri(g)
            if not base_uri:
                # Fallback to generating one based on ontology domain
                base_uri = f"http://proethica.org/ontology/{ontology.domain_id.lower()}#"
            
            # Create sanitized ID from label
            entity_id = cls._sanitize_for_uri(data['label'])
            entity_uri = URIRef(f"{base_uri}{entity_id}")
            
            # Check if entity already exists
            if (entity_uri, None, None) in g:
                return False, {"error": f"Entity already exists with ID: {entity_id}"}
            
            # Get class type
            class_type = cls.ENTITY_TYPES.get(entity_type)
            class_uri = URIRef(f"{base_uri}{class_type}")
            
            # Ensure the class URI exists
            proethica_uri = "http://proethica.org/ontology/intermediate#"
            proethica_class_uri = URIRef(f"{proethica_uri}{class_type}")
            
            if (class_uri, None, None) not in g and (proethica_class_uri, None, None) not in g:
                class_uri = proethica_class_uri  # Fall back to intermediate ontology
            
            # Add entity triples
            g.add((entity_uri, RDF.type, class_uri))
            g.add((entity_uri, RDFS.label, Literal(data['label'])))
            
            if data.get('description'):
                g.add((entity_uri, RDFS.comment, Literal(data['description'])))
            
            # Add parent class relationship
            parent_uri = URIRef(data['parent_class'])
            g.add((entity_uri, RDFS.subClassOf, parent_uri))
            
            # Add capabilities for roles
            if entity_type == 'role' and 'capabilities' in data and data['capabilities']:
                proethica_ns = Namespace("http://proethica.org/ontology/intermediate#")
                for capability_id in data['capabilities']:
                    g.add((entity_uri, proethica_ns.hasCapability, URIRef(capability_id)))
            
            # Create new ontology version
            new_content = g.serialize(format="turtle")
            
            # Create a new version
            next_version = cls._get_next_version_number(ontology_id)
            version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=next_version,
                content=new_content,
                commit_message=f"Added {entity_type}: {data['label']}"
            )
            db.session.add(version)
            
            # Update the ontology content
            ontology.content = new_content
            db.session.commit()
            
            return True, {
                "success": True,
                "message": f"{entity_type.capitalize()} created successfully",
                "entity_id": str(entity_uri)
            }
            
        except Exception as e:
            db.session.rollback()
            return False, {"error": f"Error creating entity: {str(e)}"}
    
    @classmethod
    def update_entity(cls, ontology_id, entity_type, entity_id, data):
        """
        Update an existing entity in the ontology
        
        Args:
            ontology_id (int): Ontology ID
            entity_type (str): Entity type ('role', 'condition', etc.)
            entity_id (str): Entity ID
            data (dict): Entity data with label, description, parent_class
            
        Returns:
            tuple: (success, result)
                success (bool): Whether the operation succeeded
                result (dict): Result data or error message
        """
        # Validate inputs
        if not entity_type in cls.ENTITY_TYPES:
            return False, {"error": f"Invalid entity type: {entity_type}"}
            
        if not data.get('label'):
            return False, {"error": "Label is required"}
            
        if not data.get('parent_class'):
            return False, {"error": "Parent class is required"}
            
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            return False, {"error": f"Ontology not found: {ontology_id}"}
            
        # Check if ontology is editable
        if not ontology.is_editable:
            return False, {"error": "This ontology is protected and cannot be modified"}
            
        try:
            # Parse the ontology content
            g = Graph()
            g.parse(data=ontology.content, format="turtle")
            
            # Get entity URI
            entity_uri = URIRef(entity_id)
            
            # Check if entity exists
            if (entity_uri, None, None) not in g:
                return False, {"error": f"Entity not found: {entity_id}"}
            
            # Check if entity is protected
            if any(entity_id.startswith(ns) for ns in cls.PROTECTED_NAMESPACES):
                return False, {"error": "This entity is protected and cannot be modified"}
            
            # Update entity triples
            
            # Update label
            for old_label in list(g.objects(entity_uri, RDFS.label)):
                g.remove((entity_uri, RDFS.label, old_label))
            g.add((entity_uri, RDFS.label, Literal(data['label'])))
            
            # Update description
            for old_desc in list(g.objects(entity_uri, RDFS.comment)):
                g.remove((entity_uri, RDFS.comment, old_desc))
            if data.get('description'):
                g.add((entity_uri, RDFS.comment, Literal(data['description'])))
            
            # Update parent class
            for old_parent in list(g.objects(entity_uri, RDFS.subClassOf)):
                g.remove((entity_uri, RDFS.subClassOf, old_parent))
            parent_uri = URIRef(data['parent_class'])
            g.add((entity_uri, RDFS.subClassOf, parent_uri))
            
            # Update capabilities for roles
            if entity_type == 'role':
                proethica_ns = Namespace("http://proethica.org/ontology/intermediate#")
                
                # Remove existing capabilities
                for old_cap in list(g.objects(entity_uri, proethica_ns.hasCapability)):
                    g.remove((entity_uri, proethica_ns.hasCapability, old_cap))
                
                # Add new capabilities
                if 'capabilities' in data and data['capabilities']:
                    for capability_id in data['capabilities']:
                        g.add((entity_uri, proethica_ns.hasCapability, URIRef(capability_id)))
            
            # Create new ontology version
            new_content = g.serialize(format="turtle")
            
            # Create a new version
            next_version = cls._get_next_version_number(ontology_id)
            version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=next_version,
                content=new_content,
                commit_message=f"Updated {entity_type}: {data['label']}"
            )
            db.session.add(version)
            
            # Update the ontology content
            ontology.content = new_content
            db.session.commit()
            
            return True, {
                "success": True,
                "message": f"{entity_type.capitalize()} updated successfully"
            }
            
        except Exception as e:
            db.session.rollback()
            return False, {"error": f"Error updating entity: {str(e)}"}
    
    @classmethod
    def delete_entity(cls, ontology_id, entity_type, entity_id):
        """
        Delete an entity from the ontology
        
        Args:
            ontology_id (int): Ontology ID
            entity_type (str): Entity type ('role', 'condition', etc.)
            entity_id (str): Entity ID
            
        Returns:
            tuple: (success, result)
                success (bool): Whether the operation succeeded
                result (dict): Result data or error message
        """
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            return False, {"error": f"Ontology not found: {ontology_id}"}
            
        # Check if ontology is editable
        if not ontology.is_editable:
            return False, {"error": "This ontology is protected and cannot be modified"}
            
        try:
            # Parse the ontology content
            g = Graph()
            g.parse(data=ontology.content, format="turtle")
            
            # Get entity URI
            entity_uri = URIRef(entity_id)
            
            # Check if entity exists
            if (entity_uri, None, None) not in g:
                return False, {"error": f"Entity not found: {entity_id}"}
            
            # Check if entity is protected
            if any(entity_id.startswith(ns) for ns in cls.PROTECTED_NAMESPACES):
                return False, {"error": "This entity is protected and cannot be deleted"}
            
            # Get label for commit message
            entity_label = next(g.objects(entity_uri, RDFS.label), entity_id.split('#')[-1])
            
            # Remove all triples with entity as subject
            for p, o in g.predicate_objects(entity_uri):
                g.remove((entity_uri, p, o))
            
            # Remove all triples with entity as object
            for s, p in g.subject_predicates(entity_uri):
                g.remove((s, p, entity_uri))
            
            # Create new ontology version
            new_content = g.serialize(format="turtle")
            
            # Create a new version
            next_version = cls._get_next_version_number(ontology_id)
            version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=next_version,
                content=new_content,
                commit_message=f"Deleted {entity_type}: {entity_label}"
            )
            db.session.add(version)
            
            # Update the ontology content
            ontology.content = new_content
            db.session.commit()
            
            return True, {
                "success": True,
                "message": f"{entity_type.capitalize()} deleted successfully"
            }
            
        except Exception as e:
            db.session.rollback()
            return False, {"error": f"Error deleting entity: {str(e)}"}

    @classmethod
    def _get_ontology_base_uri(cls, graph):
        """Get the base URI of the ontology"""
        # Try to get from ontology declaration
        for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
            base_uri = str(s)
            if '#' in base_uri:
                return base_uri.split('#')[0] + '#'
            elif base_uri.endswith('/'):
                return base_uri
            else:
                return base_uri + '#'
        
        # Try to infer from the most common namespace
        namespaces = {}
        for s, p, o in graph:
            for node in [s, p, o]:
                if isinstance(node, URIRef):
                    uri = str(node)
                    if '#' in uri:
                        ns = uri.split('#')[0] + '#'
                        namespaces[ns] = namespaces.get(ns, 0) + 1
        
        if namespaces:
            return max(namespaces.items(), key=lambda x: x[1])[0]
        
        return None
        
    @classmethod
    def _sanitize_for_uri(cls, text):
        """Sanitize text for use in URIs"""
        # Replace spaces and invalid characters with underscores
        text = re.sub(r'[^a-zA-Z0-9]+', '_', text)
        # Remove leading/trailing underscores
        text = text.strip('_')
        # Ensure first character is a letter
        if not text[0].isalpha():
            text = 'X' + text
        return text
        
    @classmethod
    def _get_next_version_number(cls, ontology_id):
        """Get the next version number for an ontology"""
        # Get the latest version
        latest_version = OntologyVersion.query.filter_by(
            ontology_id=ontology_id
        ).order_by(
            OntologyVersion.version_number.desc()
        ).first()
        
        if latest_version:
            return latest_version.version_number + 1
        else:
            return 1
