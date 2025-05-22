#!/usr/bin/env python3
"""
OntologyTripleLoader - Loads and processes ontology triples directly from .ttl files.

This module provides functionality to load ontology triple data from TTL files into
an RDFLib graph and extract concepts with semantic properties. It focuses on role-related
concepts as a priority for section matching.
"""

import os
import logging
from typing import Dict, List, Set, Optional, Any, Tuple
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OntologyTripleLoader:
    """
    Loads and processes ontology triples directly from .ttl files.
    
    This class handles loading ontology files into an RDFLib graph, extracting
    concepts and their properties, identifying role-related concepts, and
    preparing concept text for embedding generation.
    """

    def __init__(self, ontology_files: Optional[List[str]] = None) -> None:
        """
        Initialize with optional ontology file paths, otherwise use defaults.
        
        Args:
            ontology_files: List of paths to .ttl files to load
        """
        if ontology_files is None:
            # Default to the standard ontology files
            self.ontology_files = [
                "ontologies/proethica-intermediate.ttl",
                "ontologies/engineering-ethics.ttl"
            ]
        else:
            self.ontology_files = ontology_files
            
        self.graph = None
        self.concepts = {}
        self.role_concepts = {}
        self.role_related_concepts = {}
        self.principle_concepts = {}
        
        # Define common namespaces for easier reference
        self.proeth = "http://proethica.org/ontology/intermediate#"
        self.eng_ethics = "http://proethica.org/ontology/engineering-ethics#"
        
    def load(self) -> None:
        """
        Load ontologies from .ttl files into an RDFLib graph.
        
        Checks that the files exist and processes them into the graph.
        Then extracts concepts and their properties.
        
        Raises:
            FileNotFoundError: If any of the ontology files cannot be found
        """
        self.graph = Graph()
        
        # Load each ontology file
        for file_path in self.ontology_files:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Ontology file not found: {file_path}")
                
            logger.info(f"Loading ontology file: {file_path}")
            self.graph.parse(file_path, format="turtle")
            
        logger.info(f"Loaded {len(self.graph)} triples from ontology files")
        
        # Extract concepts after loading
        self._extract_concepts()
        
    def _extract_concepts(self) -> None:
        """
        Extract concepts from the loaded graph with their properties.
        
        This method:
        1. Extracts all classes with their basic properties
        2. Identifies role-related concepts specifically (priority)
        3. Identifies principle concepts
        """
        if self.graph is None:
            logger.warning("No graph loaded. Call load() before extracting concepts.")
            return
            
        logger.info("Extracting concepts from ontology graph...")
        
        # First extract all classes
        self._extract_all_classes()
        
        # Then identify specific concept types
        self._extract_role_concepts()
        self._extract_principle_concepts()
        
        logger.info(f"Extracted {len(self.concepts)} total concepts")
        logger.info(f"Found {len(self.role_concepts)} role concepts")
        logger.info(f"Found {len(self.role_related_concepts)} role-related concepts")
        logger.info(f"Found {len(self.principle_concepts)} principle concepts")
    
    def _extract_all_classes(self) -> None:
        """
        Extract all classes with their semantic properties.
        
        This extracts all owl:Class entities and their properties like
        label, comment, matching terms, categories, etc.
        """
        # Get semantic property URIs
        has_category = URIRef(self.proeth + "hasCategory")
        has_matching_term = URIRef(self.proeth + "hasMatchingTerm")
        has_text_reference = URIRef(self.proeth + "hasTextReference")
        has_relevance_score = URIRef(self.proeth + "hasRelevanceScore")
        
        # Query for all classes
        class_count = 0
        for class_uri in self.graph.subjects(RDF.type, OWL.Class):
            try:
                # Skip blank nodes
                if isinstance(class_uri, BNode):
                    continue
                
                # Get basic properties
                labels = list(self.graph.objects(class_uri, RDFS.label))
                comments = list(self.graph.objects(class_uri, RDFS.comment))
                
                # Get semantic matching properties
                matching_terms = list(self.graph.objects(class_uri, has_matching_term))
                categories = list(self.graph.objects(class_uri, has_category))
                text_refs = list(self.graph.objects(class_uri, has_text_reference))
                relevance_scores = list(self.graph.objects(class_uri, has_relevance_score))
                
                # Create structured concept representation
                self.concepts[str(class_uri)] = {
                    "uri": str(class_uri),
                    "label": str(labels[0]) if labels else "",
                    "description": str(comments[0]) if comments else "",
                    "matching_terms": [str(term) for term in matching_terms],
                    "categories": [str(cat) for cat in categories],
                    "text_references": [str(ref) for ref in text_refs],
                    "relevance_score": float(relevance_scores[0]) if relevance_scores else 0.5
                }
                
                class_count += 1
                
            except Exception as e:
                logger.warning(f"Error processing class {class_uri}: {str(e)}")
        
        logger.info(f"Extracted {class_count} classes from ontology")
    
    def _extract_role_concepts(self) -> None:
        """
        Extract concepts related to roles (high priority).
        
        This identifies:
        1. Direct Role concepts (classes that are Role or subclasses of Role)
        2. Role-related concepts (classes that reference roles)
        """
        if not self.graph or not self.concepts:
            logger.warning("Graph or concepts not loaded")
            return
            
        # Find Role class
        role_class_uri = URIRef(self.proeth + "Role")
        
        # Function to check if a class is a Role or subclass of Role
        # Using a set to track visited nodes to avoid infinite recursion
        visited_nodes = set()
        
        def is_role_or_subclass(class_uri):
            if class_uri == role_class_uri:
                return True
                
            # Avoid infinite recursion by tracking visited nodes
            if class_uri in visited_nodes:
                return False
            
            visited_nodes.add(class_uri)
                
            # Check if it's a direct subclass
            is_subclass = (class_uri, RDFS.subClassOf, role_class_uri) in self.graph
            
            # Check for indirect subclass relationship
            if not is_subclass:
                for parent in self.graph.objects(class_uri, RDFS.subClassOf):
                    if is_role_or_subclass(parent):
                        return True
            
            return is_subclass
        
        # Find all Role classes and subclasses
        for uri in self.concepts:
            class_uri = URIRef(uri)
            if is_role_or_subclass(class_uri):
                self.role_concepts[uri] = self.concepts[uri]
        
        # Find concepts that reference roles
        for subj, pred, obj in self.graph:
            # Check if the object is a role concept
            if str(obj) in self.role_concepts and str(subj) in self.concepts:
                self.role_related_concepts[str(subj)] = self.concepts[str(subj)]
            
            # Also check references by URI string
            # Some ontologies might reference roles without explicit links
            if isinstance(obj, Literal) and "role" in str(obj).lower() and str(subj) in self.concepts:
                if str(subj) not in self.role_related_concepts:
                    self.role_related_concepts[str(subj)] = self.concepts[str(subj)]
    
    def _extract_principle_concepts(self) -> None:
        """
        Extract principle-related concepts.
        
        This identifies classes that are principles or related to ethical principles.
        """
        if not self.graph or not self.concepts:
            logger.warning("Graph or concepts not loaded")
            return
            
        # Find Principle class
        principle_class_uris = [
            URIRef(self.proeth + "EthicalPrinciple"),
            URIRef(self.proeth + "Principle"),
            URIRef(self.eng_ethics + "Principle")
        ]
        
        # Function to check if a class is a Principle or subclass of Principle
        # Using a set to track visited nodes to avoid infinite recursion
        visited_nodes = set()
        
        def is_principle_or_subclass(class_uri):
            for principle_uri in principle_class_uris:
                if class_uri == principle_uri:
                    return True
                    
                # Check if it's a direct subclass
                if (class_uri, RDFS.subClassOf, principle_uri) in self.graph:
                    return True
            
            # Avoid infinite recursion by tracking visited nodes
            if class_uri in visited_nodes:
                return False
            
            visited_nodes.add(class_uri)
            
            # Check for indirect subclass relationship
            for parent in self.graph.objects(class_uri, RDFS.subClassOf):
                if is_principle_or_subclass(parent):
                    return True
            
            return False
        
        # Find all Principle classes and subclasses
        for uri in self.concepts:
            class_uri = URIRef(uri)
            if is_principle_or_subclass(class_uri):
                self.principle_concepts[uri] = self.concepts[uri]
            
            # Also check for principle in the name or description
            concept = self.concepts[uri]
            if "principle" in concept["label"].lower() or "principle" in concept["description"].lower():
                self.principle_concepts[uri] = concept
    
    def get_concept_text_for_embedding(self, concept_uri: str) -> str:
        """
        Get a text representation of a concept suitable for embedding.
        
        Args:
            concept_uri: URI of the concept
            
        Returns:
            Text string concatenating label, description, and matching terms
        """
        if concept_uri not in self.concepts:
            return ""
            
        concept = self.concepts[concept_uri]
        
        # Combine relevant text, ignoring formatting tokens
        parts = []
        
        # Add label with stronger weight (duplicate to increase importance)
        if concept["label"]:
            parts.append(concept["label"])
            parts.append(concept["label"])  # Duplicate for emphasis
            
        # Add description
        if concept["description"]:
            # Clean description
            desc = concept["description"]
            # Remove formulaic prefixes if present
            prefixes = [
                "The principle that ", 
                "The obligation for ",
                "The duty to ",
                "The responsibility to "
            ]
            for prefix in prefixes:
                if desc.startswith(prefix):
                    desc = desc[len(prefix):]
            parts.append(desc)
            
        # Add matching terms
        if concept["matching_terms"]:
            parts.append("Keywords: " + ", ".join(concept["matching_terms"]))
            
        # Add categories
        if concept["categories"]:
            parts.append("Categories: " + ", ".join(concept["categories"]))
            
        return " ".join(parts)
    
    def generate_concept_embeddings(self, embedding_service) -> Dict[str, Any]:
        """
        Generate embeddings for all concepts.
        
        Args:
            embedding_service: Service to generate embeddings
            
        Returns:
            Dictionary mapping concept URIs to embeddings
        """
        embeddings = {}
        
        # First process role concepts (high priority)
        for uri in self.role_concepts:
            text = self.get_concept_text_for_embedding(uri)
            if text:
                embedding = embedding_service.generate_embedding(text)
                if embedding is not None:
                    embeddings[uri] = embedding
        
        # Then process role-related concepts (high priority)
        for uri in self.role_related_concepts:
            if uri not in embeddings:  # Skip if already processed
                text = self.get_concept_text_for_embedding(uri)
                if text:
                    embedding = embedding_service.generate_embedding(text)
                    if embedding is not None:
                        embeddings[uri] = embedding
        
        # Then process principle concepts (medium priority)
        for uri in self.principle_concepts:
            if uri not in embeddings:  # Skip if already processed
                text = self.get_concept_text_for_embedding(uri)
                if text:
                    embedding = embedding_service.generate_embedding(text)
                    if embedding is not None:
                        embeddings[uri] = embedding
        
        # Finally process remaining concepts
        for uri in self.concepts:
            if uri not in embeddings:  # Skip if already processed
                text = self.get_concept_text_for_embedding(uri)
                if text:
                    embedding = embedding_service.generate_embedding(text)
                    if embedding is not None:
                        embeddings[uri] = embedding
        
        return embeddings
    
    def get_all_concepts(self) -> Dict[str, Dict[str, Any]]:
        """Get all extracted concepts."""
        return self.concepts
    
    def get_role_concepts(self) -> Dict[str, Dict[str, Any]]:
        """Get role-specific concepts (high priority)."""
        return self.role_concepts
    
    def get_role_related_concepts(self) -> Dict[str, Dict[str, Any]]:
        """Get concepts that reference roles (high priority)."""
        return self.role_related_concepts
        
    def get_principle_concepts(self) -> Dict[str, Dict[str, Any]]:
        """Get principle-related concepts."""
        return self.principle_concepts
