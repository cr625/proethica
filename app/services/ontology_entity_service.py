"""
Service for directly extracting entities from ontologies stored in the database.
This service bypasses the MCP server for entity retrieval, making entity extraction
more reliable and simpler.
"""
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS
from app import db
from app.models.ontology import Ontology
import logging

logger = logging.getLogger(__name__)

class OntologyEntityService:
    """Service for extracting entities from ontologies."""
    
    # Singleton pattern
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize the service."""
        # Cache to avoid repeated parsing of the same ontology
        self.ontology_cache = {}
        
        # Define the namespaces we'll use
        self.namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "nspe": Namespace("http://proethica.org/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/")
        }
    
    def get_entities_for_world(self, world):
        """
        Get entities for a world directly from the database.
        
        Args:
            world: World model instance
            
        Returns:
            Dict containing entities organized by type
        """
        if not world.ontology_id:
            logger.warning(f"World {world.id} has no ontology_id")
            return {"entities": {}, "is_mock": False}
        
        # Check if we have cached results
        cache_key = f"ontology_{world.ontology_id}"
        if cache_key in self.ontology_cache:
            logger.info(f"Using cached entities for ontology {world.ontology_id}")
            return self.ontology_cache[cache_key]
        
        # Get the ontology from the database
        ontology = Ontology.query.get(world.ontology_id)
        if not ontology:
            logger.warning(f"Ontology {world.ontology_id} not found")
            return {"entities": {}, "is_mock": False}
        
        # Extract entities from the ontology
        try:
            entities = self._extract_entities_from_ontology(ontology)
            
            # Cache the results
            self.ontology_cache[cache_key] = entities
            
            return entities
        except Exception as e:
            logger.error(f"Error extracting entities from ontology {world.ontology_id}: {e}")
            return {"entities": {}, "is_mock": False, "error": str(e)}
    
    def _extract_entities_from_ontology(self, ontology):
        """
        Extract entities from an ontology using RDFLib.
        
        Args:
            ontology: Ontology model instance
            
        Returns:
            Dict containing entities organized by type
        """
        # Parse the ontology content into a graph
        g = Graph()
        try:
            g.parse(data=ontology.content, format="turtle")
            logger.info(f"Successfully parsed ontology {ontology.id} with {len(g)} triples")
        except Exception as e:
            logger.error(f"Error parsing ontology {ontology.id}: {e}")
            return {"entities": {}, "is_mock": False, "error": f"Parse error: {str(e)}"}
        
        # Extract all entity types
        entities = {
            "roles": self._extract_roles(g),
            "conditions": self._extract_condition_types(g),
            "resources": self._extract_resource_types(g),
            "events": self._extract_event_types(g),
            "actions": self._extract_action_types(g),
            "capabilities": self._extract_capabilities(g)
        }
        
        result = {
            "entities": entities,
            "is_mock": False
        }
        
        # Log a summary of what we found
        for entity_type, entity_list in entities.items():
            logger.info(f"Found {len(entity_list)} {entity_type} in ontology {ontology.id}")
        
        return result
    
    def _detect_namespace(self, graph):
        """
        Detect the primary namespace used in the ontology.
        
        Args:
            graph: RDFLib Graph
            
        Returns:
            Namespace object for the primary namespace
        """
        # Default to engineering-ethics
        default_ns = self.namespaces["engineering-ethics"]
        
        # Try to detect based on owl:Ontology declaration
        for s, p, o in graph.triples((None, rdflib.OWL.Ontology, None)):
            ontology_uri = str(s)
            if "engineering-ethics" in ontology_uri:
                return self.namespaces["engineering-ethics"]
            elif "intermediate" in ontology_uri:
                return self.namespaces["intermediate"]
            elif "nspe" in ontology_uri:
                return self.namespaces["nspe"]
        
        return default_ns
    
    def _extract_roles(self, graph):
        """Extract Role entities from the graph."""
        roles = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        def safe_get_property(s, prop, default=""):
            try:
                return str(next(graph.objects(s, prop), default))
            except:
                return default
        
        # Find Role instances
        role_subjects = set()
        role_subjects.update(graph.subjects(RDF.type, namespace.Role))
        role_subjects.update(graph.subjects(RDF.type, proeth_namespace.Role))
        
        # Also find instances that have both EntityType and Role types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.Role) in graph:
                role_subjects.add(s)
        
        # Create role objects
        for s in role_subjects:
            roles.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "tier": safe_get_property(s, namespace.hasTier),
                "capabilities": [
                    {
                        "id": str(o),
                        "label": label_or_id(o),
                        "description": get_description(o)
                    }
                    for o in graph.objects(s, proeth_namespace.hasCapability)
                ]
            })
        
        return roles
    
    def _extract_condition_types(self, graph):
        """Extract ConditionType entities from the graph."""
        conditions = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find ConditionType instances
        condition_subjects = set()
        condition_subjects.update(graph.subjects(RDF.type, namespace.ConditionType))
        condition_subjects.update(graph.subjects(RDF.type, proeth_namespace.ConditionType))
        
        # Also find instances that have both EntityType and ConditionType types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.ConditionType) in graph:
                condition_subjects.add(s)
        
        # Create condition objects
        for s in condition_subjects:
            conditions.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            })
        
        return conditions
    
    def _extract_resource_types(self, graph):
        """Extract ResourceType entities from the graph."""
        resources = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find ResourceType instances
        resource_subjects = set()
        resource_subjects.update(graph.subjects(RDF.type, namespace.ResourceType))
        resource_subjects.update(graph.subjects(RDF.type, proeth_namespace.ResourceType))
        
        # Also find instances that have both EntityType and ResourceType types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.ResourceType) in graph:
                resource_subjects.add(s)
        
        # Create resource objects
        for s in resource_subjects:
            resources.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            })
        
        return resources
    
    def _extract_event_types(self, graph):
        """Extract EventType entities from the graph."""
        events = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find EventType instances
        event_subjects = set()
        event_subjects.update(graph.subjects(RDF.type, namespace.EventType))
        event_subjects.update(graph.subjects(RDF.type, proeth_namespace.EventType))
        
        # Also find instances that have both EntityType and EventType types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.EventType) in graph:
                event_subjects.add(s)
        
        # Create event objects
        for s in event_subjects:
            events.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            })
        
        return events
    
    def _extract_action_types(self, graph):
        """Extract ActionType entities from the graph."""
        actions = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find ActionType instances
        action_subjects = set()
        action_subjects.update(graph.subjects(RDF.type, namespace.ActionType))
        action_subjects.update(graph.subjects(RDF.type, proeth_namespace.ActionType))
        
        # Also find instances that have both EntityType and ActionType types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.ActionType) in graph:
                action_subjects.add(s)
        
        # Create action objects
        for s in action_subjects:
            actions.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            })
        
        return actions
    
    def _extract_capabilities(self, graph):
        """Extract Capability entities from the graph."""
        capabilities = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find Capability instances
        capability_subjects = set()
        capability_subjects.update(graph.subjects(RDF.type, namespace.Capability))
        capability_subjects.update(graph.subjects(RDF.type, proeth_namespace.Capability))
        
        # Also find instances that have both EntityType and Capability types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.Capability) in graph:
                capability_subjects.add(s)
        
        # Additionally get capabilities associated with roles
        for role in graph.subjects(RDF.type, namespace.Role):
            capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
        for role in graph.subjects(RDF.type, proeth_namespace.Role):
            capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
        
        # Create capability objects
        for s in capability_subjects:
            capabilities.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            })
        
        return capabilities
        
    def invalidate_cache(self, ontology_id=None):
        """
        Invalidate the entity cache for a specific ontology or all ontologies.
        
        Args:
            ontology_id: ID of the ontology to invalidate, or None to invalidate all
        """
        if ontology_id:
            cache_key = f"ontology_{ontology_id}"
            if cache_key in self.ontology_cache:
                del self.ontology_cache[cache_key]
                logger.info(f"Invalidated cache for ontology {ontology_id}")
        else:
            self.ontology_cache.clear()
            logger.info("Invalidated all ontology caches")
