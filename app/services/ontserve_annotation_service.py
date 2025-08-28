"""
OntServe Annotation Service - Handles integration with OntServe for concept annotation.
"""
import requests
import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from app.models.world import World
from app.models.document_concept_annotation import DocumentConceptAnnotation

logger = logging.getLogger(__name__)

class OntServeAnnotationService:
    """Service for integrating with OntServe API for document annotation."""
    
    def __init__(self, ontserve_url: str = "http://localhost:5003"):
        self.ontserve_url = ontserve_url
        self.cache = {}
        self.session = requests.Session()
        
        # Set up session defaults
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ProEthica-AnnotationService/1.0'
        })
        
        # Default timeout
        self.timeout = 30
    
    def get_ontology_concepts(self, ontology_names: List[str], 
                            concept_types: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Fetch all relevant concepts from specified ontologies.
        
        Args:
            ontology_names: List of ontology names to query
            concept_types: Optional filter for specific concept types
            
        Returns:
            Dictionary mapping ontology names to lists of concept dictionaries
        """
        concepts = {}
        
        for ontology in ontology_names:
            try:
                # Check cache first
                cache_key = f"{ontology}_{concept_types}"
                if cache_key in self.cache:
                    logger.debug(f"Using cached concepts for {ontology}")
                    concepts[ontology] = self.cache[cache_key]
                    continue
                
                # Fetch from OntServe API
                logger.info(f"Fetching concepts from ontology: {ontology}")
                url = urljoin(self.ontserve_url, f"/editor/api/ontologies/{ontology}/entities")
                
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                response_data = response.json()
                entities_data = response_data.get('entities', {})
                
                # Flatten the nested structure (classes and properties)
                all_entities = []
                for entity_type, entity_list in entities_data.items():
                    if isinstance(entity_list, list):
                        all_entities.extend(entity_list)
                
                # Filter by concept types if specified
                if concept_types:
                    all_entities = [e for e in all_entities if e.get('category') in concept_types or e.get('type') in concept_types]
                
                # Transform entities to standard format
                formatted_entities = []
                for entity in all_entities:
                    formatted_entity = {
                        'uri': entity.get('id', entity.get('uri', '')),
                        'label': entity.get('label', entity.get('name', '')),
                        'definition': entity.get('description', entity.get('definition', '')),
                        'type': entity.get('category', entity.get('type', 'Unknown')),
                        'ontology': ontology,
                        'properties': entity.get('properties', {})
                    }
                    formatted_entities.append(formatted_entity)
                
                concepts[ontology] = formatted_entities
                
                # Cache the results
                self.cache[cache_key] = formatted_entities
                
                logger.info(f"Fetched {len(formatted_entities)} concepts from {ontology}")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to fetch concepts from {ontology}: {e}")
                concepts[ontology] = []
            except Exception as e:
                logger.error(f"Error processing concepts from {ontology}: {e}")
                concepts[ontology] = []
        
        return concepts
    
    def get_world_ontology_mapping(self, world_id: int) -> Dict[str, str]:
        """
        Get the OntServe ontology mapping for a world.
        
        Args:
            world_id: ID of the world
            
        Returns:
            Dictionary mapping ontology types to OntServe ontology names
        """
        try:
            world = World.query.get(world_id)
            if not world:
                logger.error(f"World {world_id} not found")
                return self._get_default_mapping()
            
            # Get mapping from world metadata
            if hasattr(world, 'ontserve_mapping') and world.ontserve_mapping:
                mapping = world.ontserve_mapping
                logger.debug(f"Using custom mapping for world {world_id}: {mapping}")
            else:
                # Check world_metadata for legacy support
                mapping = world.world_metadata.get('ontserve_mapping', {})
                if not mapping:
                    mapping = self._get_default_mapping()
                    logger.info(f"Using default mapping for world {world_id}")
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error getting ontology mapping for world {world_id}: {e}")
            return self._get_default_mapping()
    
    def _get_default_mapping(self) -> Dict[str, str]:
        """Get the default ontology mapping."""
        return {
            'core': 'proethica-core',
            'intermediate': 'proethica-intermediate',
            'domain': 'engineering-ethics'
        }
    
    def update_world_ontology_mapping(self, world_id: int, mapping: Dict[str, str]) -> bool:
        """
        Update the ontology mapping for a world.
        
        Args:
            world_id: ID of the world
            mapping: New ontology mapping
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from app.models import db
            
            world = World.query.get(world_id)
            if not world:
                logger.error(f"World {world_id} not found")
                return False
            
            # Validate mapping
            if not self._validate_mapping(mapping):
                logger.error(f"Invalid ontology mapping: {mapping}")
                return False
            
            # Update the mapping
            world.ontserve_mapping = mapping
            db.session.commit()
            
            # Clear cache for this world
            self._clear_world_cache(world_id)
            
            logger.info(f"Updated ontology mapping for world {world_id}: {mapping}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating ontology mapping for world {world_id}: {e}")
            return False
    
    def _validate_mapping(self, mapping: Dict[str, str]) -> bool:
        """
        Validate that the ontology mapping is correct.
        
        Args:
            mapping: Mapping to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_keys = {'core', 'intermediate'}
        
        # Check required keys exist
        if not all(key in mapping for key in required_keys):
            return False
        
        # Verify ontologies exist in OntServe
        for ontology_type, ontology_name in mapping.items():
            if not self._ontology_exists(ontology_name):
                logger.warning(f"Ontology '{ontology_name}' not found in OntServe")
                return False
        
        return True
    
    def _ontology_exists(self, ontology_name: str) -> bool:
        """Check if an ontology exists in OntServe."""
        try:
            url = urljoin(self.ontserve_url, f"/api/ontology/{ontology_name}")
            response = self.session.get(url, timeout=self.timeout)
            return response.status_code == 200
        except:
            return False
    
    def _clear_world_cache(self, world_id: int):
        """Clear cache entries related to a world."""
        keys_to_remove = [key for key in self.cache.keys() if str(world_id) in key]
        for key in keys_to_remove:
            del self.cache[key]
    
    def get_ontology_version(self, ontology_name: str) -> Optional[str]:
        """
        Get the current version of an ontology.
        
        Args:
            ontology_name: Name of the ontology
            
        Returns:
            Version string or None if not available
        """
        try:
            url = urljoin(self.ontserve_url, f"/api/ontology/{ontology_name}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            ontology_info = response.json()
            return ontology_info.get('version', None)
            
        except Exception as e:
            logger.error(f"Error getting version for {ontology_name}: {e}")
            return None
    
    def check_for_ontology_updates(self, annotations: List[DocumentConceptAnnotation]) -> Dict[str, bool]:
        """
        Check if there are newer versions of ontologies used in annotations.
        
        Args:
            annotations: List of annotations to check
            
        Returns:
            Dictionary mapping ontology names to whether updates are available
        """
        updates_available = {}
        
        # Get unique ontology names and their versions from annotations
        ontology_versions = {}
        for annotation in annotations:
            if annotation.ontology_name not in ontology_versions:
                ontology_versions[annotation.ontology_name] = annotation.ontology_version
        
        # Check each ontology for updates
        for ontology_name, current_version in ontology_versions.items():
            try:
                latest_version = self.get_ontology_version(ontology_name)
                
                if latest_version and latest_version != current_version:
                    updates_available[ontology_name] = True
                    logger.info(f"Update available for {ontology_name}: {current_version} -> {latest_version}")
                else:
                    updates_available[ontology_name] = False
                    
            except Exception as e:
                logger.error(f"Error checking updates for {ontology_name}: {e}")
                updates_available[ontology_name] = False
        
        return updates_available
    
    def get_concept_details(self, ontology_name: str, concept_uri: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific concept.
        
        Args:
            ontology_name: Name of the ontology
            concept_uri: URI of the concept
            
        Returns:
            Concept details dictionary or None if not found
        """
        try:
            # Extract concept identifier from URI
            concept_id = concept_uri.split('#')[-1] if '#' in concept_uri else concept_uri.split('/')[-1]
            
            url = urljoin(self.ontserve_url, f"/api/ontology/{ontology_name}/entity/{concept_id}")
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Concept {concept_uri} not found in {ontology_name}")
                return None
            else:
                response.raise_for_status()
                
        except Exception as e:
            logger.error(f"Error getting details for concept {concept_uri}: {e}")
            return None
    
    def get_related_concepts(self, ontology_name: str, concept_uri: str, 
                           relation_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get concepts related to the given concept.
        
        Args:
            ontology_name: Name of the ontology
            concept_uri: URI of the concept
            relation_types: Optional list of relation types to filter by
            
        Returns:
            List of related concept dictionaries
        """
        try:
            concept_details = self.get_concept_details(ontology_name, concept_uri)
            if not concept_details:
                return []
            
            relationships = concept_details.get('relationships', [])
            
            if relation_types:
                relationships = [r for r in relationships if r.get('type') in relation_types]
            
            related_concepts = []
            for rel in relationships:
                if 'target' in rel:
                    target_details = self.get_concept_details(ontology_name, rel['target'])
                    if target_details:
                        related_concepts.append({
                            'concept': target_details,
                            'relationship': rel.get('type', 'related'),
                            'direction': rel.get('direction', 'outgoing')
                        })
            
            return related_concepts
            
        except Exception as e:
            logger.error(f"Error getting related concepts for {concept_uri}: {e}")
            return []
    
    def validate_annotation_candidate(self, text_segment: str, concept_uri: str, 
                                    ontology_name: str, context: str = "") -> Dict[str, Any]:
        """
        Validate that a text segment appropriately matches a concept.
        
        Args:
            text_segment: The text being annotated
            concept_uri: URI of the proposed concept
            ontology_name: Name of the ontology
            context: Additional context for validation
            
        Returns:
            Validation result with confidence and reasoning
        """
        try:
            concept_details = self.get_concept_details(ontology_name, concept_uri)
            if not concept_details:
                return {
                    'valid': False,
                    'confidence': 0.0,
                    'reasoning': f"Concept {concept_uri} not found in {ontology_name}"
                }
            
            # Basic validation based on concept definition and label
            concept_label = concept_details.get('label', '')
            concept_definition = concept_details.get('definition', '')
            
            # Simple keyword matching for now (could be enhanced with semantic similarity)
            text_lower = text_segment.lower()
            label_words = concept_label.lower().split() if concept_label else []
            definition_words = concept_definition.lower().split() if concept_definition else []
            
            # Calculate basic similarity score
            label_matches = sum(1 for word in label_words if word in text_lower)
            definition_matches = sum(1 for word in definition_words[:10] if word in text_lower)  # First 10 words
            
            total_score = (label_matches * 2 + definition_matches) / max(len(label_words) + 10, 1)
            confidence = min(total_score, 1.0)
            
            return {
                'valid': confidence > 0.3,  # Threshold for validity
                'confidence': confidence,
                'reasoning': f"Match score: {confidence:.2f} based on label and definition similarity",
                'concept_label': concept_label,
                'concept_definition': concept_definition
            }
            
        except Exception as e:
            logger.error(f"Error validating annotation: {e}")
            return {
                'valid': False,
                'confidence': 0.0,
                'reasoning': f"Validation error: {str(e)}"
            }
    
    def clear_cache(self):
        """Clear the entire cache."""
        self.cache.clear()
        logger.info("OntServe annotation service cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_entries': len(self.cache),
            'cache_keys': list(self.cache.keys())
        }
