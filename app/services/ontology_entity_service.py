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
        
        # First, get the proethica-intermediate ontology to extract GuidelineConceptTypes
        guideline_concept_types = self._extract_guideline_concept_types(g)
        
        # Extract entities for each GuidelineConceptType found
        entities = {}
        for concept_type_name, concept_type_uri in guideline_concept_types.items():
            entity_list = self._extract_entities_by_type(g, concept_type_name, concept_type_uri)
            if entity_list:  # Only include types that have entities
                entities[concept_type_name.lower()] = entity_list
        
        # If no dynamic types found, fall back to legacy hardcoded extraction
        if not entities:
            logger.warning(f"No GuidelineConceptTypes found in ontology {ontology.id}, using legacy extraction")
            entities = {
                "role": self._extract_roles(g),
                "principle": self._extract_principles(g),
                "obligation": self._extract_obligations(g),
                "state": self._extract_condition_types(g),  # conditions -> states
                "resource": self._extract_resource_types(g),
                "event": self._extract_event_types(g),
                "action": self._extract_action_types(g),
                "capability": self._extract_capabilities(g)
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
    
    def _extract_guideline_concept_types(self, graph):
        """
        Extract GuidelineConceptTypes from the proethica-intermediate ontology.
        
        Args:
            graph: RDFLib Graph
            
        Returns:
            Dict mapping concept type names to their URIs
        """
        guideline_concept_types = {}
        proeth_namespace = self.namespaces["intermediate"]
        
        # SPARQL query to find all GuidelineConceptTypes
        # SELECT ?type ?label WHERE {
        #   ?type rdf:type :GuidelineConceptType .
        #   ?type rdfs:label ?label .
        # }
        
        # Find all classes that are GuidelineConceptTypes
        for concept_type in graph.subjects(RDF.type, proeth_namespace.GuidelineConceptType):
            # Get the label for this concept type
            label = next(graph.objects(concept_type, RDFS.label), None)
            if label:
                concept_name = str(label)
                guideline_concept_types[concept_name] = str(concept_type)
                logger.info(f"Found GuidelineConceptType: {concept_name} -> {concept_type}")
        
        # If we don't find any in the current graph, try to load proethica-intermediate
        if not guideline_concept_types:
            logger.info("No GuidelineConceptTypes found in current graph, checking proethica-intermediate ontology")
            
            # Try to get the proethica-intermediate ontology from database
            try:
                proethica_ontology = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
                if proethica_ontology:
                    proethica_graph = Graph()
                    try:
                        proethica_graph.parse(data=proethica_ontology.content, format="turtle")
                        
                        # Extract from proethica-intermediate
                        for concept_type in proethica_graph.subjects(RDF.type, proeth_namespace.GuidelineConceptType):
                            label = next(proethica_graph.objects(concept_type, RDFS.label), None)
                            if label:
                                concept_name = str(label)
                                guideline_concept_types[concept_name] = str(concept_type)
                                logger.info(f"Found GuidelineConceptType from proethica-intermediate: {concept_name} -> {concept_type}")
                                
                    except Exception as e:
                        logger.error(f"Error parsing proethica-intermediate ontology: {e}")
            except Exception as e:
                logger.error(f"Error accessing proethica-intermediate ontology from database: {e}")
                
                # If database access fails, try loading from file system
                try:
                    import os
                    intermediate_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                                   'ontologies', 'proethica-intermediate.ttl')
                    if os.path.exists(intermediate_path):
                        logger.info(f"Loading proethica-intermediate from file: {intermediate_path}")
                        proethica_graph = Graph()
                        proethica_graph.parse(intermediate_path, format="turtle")
                        
                        # Extract from proethica-intermediate
                        for concept_type in proethica_graph.subjects(RDF.type, proeth_namespace.GuidelineConceptType):
                            label = next(proethica_graph.objects(concept_type, RDFS.label), None)
                            if label:
                                concept_name = str(label)
                                guideline_concept_types[concept_name] = str(concept_type)
                                logger.info(f"Found GuidelineConceptType from file: {concept_name} -> {concept_type}")
                except Exception as file_error:
                    logger.error(f"Error loading proethica-intermediate from file: {file_error}")
        
        # If still no GuidelineConceptTypes found, use hardcoded fallback
        if not guideline_concept_types:
            logger.info("Using hardcoded GuidelineConceptTypes fallback")
            guideline_concept_types = {
                "Role": "http://proethica.org/ontology/intermediate#Role",
                "Principle": "http://proethica.org/ontology/intermediate#Principle", 
                "Obligation": "http://proethica.org/ontology/intermediate#Obligation",
                "State": "http://proethica.org/ontology/intermediate#State",
                "Resource": "http://proethica.org/ontology/intermediate#Resource",
                "Action": "http://proethica.org/ontology/intermediate#Action",
                "Event": "http://proethica.org/ontology/intermediate#Event", 
                "Capability": "http://proethica.org/ontology/intermediate#Capability"
            }
            
        logger.info(f"Final GuidelineConceptTypes: {guideline_concept_types}")
        
        return guideline_concept_types
    
    def _extract_entities_by_type(self, graph, concept_type_name, concept_type_uri):
        """
        Extract entities of a specific GuidelineConceptType from the graph.
        
        Args:
            graph: RDFLib Graph
            concept_type_name: Name of the concept type (e.g., "Role", "Principle")
            concept_type_uri: URI of the concept type
            
        Returns:
            List of entity dictionaries
        """
        entities = []
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s.split('/')[-1].split('#')[-1]))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find all instances of this GuidelineConceptType
        concept_type_ref = rdflib.URIRef(concept_type_uri)
        
        # Find subjects that are instances of this concept type
        entity_subjects = set()
        
        # Method 1: Direct instances of the intermediate ontology type
        entity_subjects.update(graph.subjects(RDF.type, concept_type_ref))
        
        # Method 2: Look for namespace-specific types with the same name
        # e.g., engineering-ethics#Role, engineering-ethics#State, etc.
        namespace = self._detect_namespace(graph)
        local_type_ref = getattr(namespace, concept_type_name, None)
        if local_type_ref:
            entity_subjects.update(graph.subjects(RDF.type, local_type_ref))
        
        # Method 3: Check meta-types in both namespaces
        # e.g., things typed as ResourceType, EventType, etc.
        meta_type_mapping = {
            "Role": "Role",
            "State": "State", 
            "Resource": "ResourceType",
            "Event": "EventType",
            "Action": "ActionType",
            "Capability": "CapabilityType",
            "Principle": "PrincipleType",
            "Obligation": "ObligationType"
        }
        
        if concept_type_name in meta_type_mapping:
            meta_type = meta_type_mapping[concept_type_name]
            # Try both intermediate namespace and local namespace
            meta_type_refs = [
                getattr(proeth_namespace, meta_type, None),
                getattr(namespace, meta_type, None)
            ]
            
            for meta_type_ref in meta_type_refs:
                if meta_type_ref:
                    # Find entities that have this meta-type
                    meta_entities = list(graph.subjects(RDF.type, meta_type_ref))
                    entity_subjects.update(meta_entities)
                    logger.debug(f"Found {len(meta_entities)} entities with meta-type {meta_type_ref}")
        
        # Method 4: Entities that are both EntityType and this GuidelineConceptType
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            # Check if it has any of the type references we're looking for
            if ((s, RDF.type, concept_type_ref) in graph or
                (local_type_ref and (s, RDF.type, local_type_ref) in graph)):
                entity_subjects.add(s)
        
        # Method 5: Look for subclasses of the concept type
        for subclass in graph.subjects(RDFS.subClassOf, concept_type_ref):
            entity_subjects.update(graph.subjects(RDF.type, subclass))
        
        # Method 6: For Capabilities, find classes that end with "Capability" or are subclasses of capability classes
        if concept_type_name == "Capability":
            # Find all classes that end with "Capability"
            for s, p, o in graph.triples((None, RDF.type, rdflib.OWL.Class)):
                class_uri = str(s)
                if class_uri.endswith("Capability") or "Capability" in class_uri:
                    entity_subjects.add(s)
                    logger.debug(f"Found capability class by name: {class_uri}")
            
            # Find classes that are subclasses of any capability-related class
            capability_base_classes = set()
            for s in graph.subjects():
                if str(s).endswith("Capability") or "Capability" in str(s):
                    capability_base_classes.add(s)
            
            # Find all subclasses of capability base classes
            for base_class in capability_base_classes:
                for subclass in graph.subjects(RDFS.subClassOf, base_class):
                    entity_subjects.add(subclass)
                    logger.debug(f"Found capability subclass: {subclass} -> {base_class}")
                    # Also include the base class itself if it's a capability
                    if str(base_class).endswith("Capability"):
                        entity_subjects.add(base_class)
        
        # Method 7: For Obligations, find classes that contain obligation-related terms
        elif concept_type_name == "Obligation":
            obligation_terms = ["Duty", "Obligation", "Responsibility", "Requirement", "Must", "Shall"]
            
            # Find all classes that contain obligation-related terms
            for s, p, o in graph.triples((None, RDF.type, rdflib.OWL.Class)):
                class_uri = str(s)
                class_local_name = class_uri.split('#')[-1].split('/')[-1]
                
                # Check if the class name contains obligation-related terms
                for term in obligation_terms:
                    if term in class_local_name:
                        entity_subjects.add(s)
                        logger.debug(f"Found obligation class by name pattern: {class_uri}")
                        break
                
                # Also check rdfs:label and rdfs:comment for obligation-related content
                label = next(graph.objects(s, RDFS.label), None)
                comment = next(graph.objects(s, RDFS.comment), None)
                
                obligation_indicators = []
                if label:
                    obligation_indicators.append(str(label).lower())
                if comment:
                    obligation_indicators.append(str(comment).lower())
                
                for indicator_text in obligation_indicators:
                    # Look for obligation-related keywords in labels/comments
                    obligation_keywords = ["must", "shall", "required", "duty", "obligation", "responsibility", "accountable"]
                    if any(keyword in indicator_text for keyword in obligation_keywords):
                        # Additional check: make sure it's not just a dilemma or decision about obligations
                        if not any(exclusion in indicator_text for exclusion in ["dilemma", "decision", "conflict"]):
                            entity_subjects.add(s)
                            logger.debug(f"Found obligation class by content: {class_uri} - {indicator_text[:50]}...")
                            break
            
            # Find classes that are subclasses of any obligation-related class
            obligation_base_classes = set()
            for s in graph.subjects():
                class_uri = str(s)
                class_local_name = class_uri.split('#')[-1].split('/')[-1]
                if any(term in class_local_name for term in obligation_terms):
                    obligation_base_classes.add(s)
            
            # Find all subclasses of obligation base classes
            for base_class in obligation_base_classes:
                for subclass in graph.subjects(RDFS.subClassOf, base_class):
                    entity_subjects.add(subclass)
                    logger.debug(f"Found obligation subclass: {subclass} -> {base_class}")
                    # Also include the base class itself
                    entity_subjects.add(base_class)
        
        # Create entity objects
        for s in entity_subjects:
            # Skip the concept type definition itself
            if s == concept_type_ref:
                continue
                
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            entity = {
                "id": str(s),
                "uri": str(s), 
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri,
                "type": concept_type_name.lower()
            }
            
            # For roles, also include capabilities
            if concept_type_name.lower() == "role":
                entity["capabilities"] = [
                    {
                        "id": str(o),
                        "label": label_or_id(o),
                        "description": get_description(o)
                    }
                    for o in graph.objects(s, proeth_namespace.hasCapability)
                ]
            
            entities.append(entity)
        
        logger.info(f"Found {len(entities)} entities for concept type {concept_type_name}")
        return entities
    
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
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            roles.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "tier": safe_get_property(s, namespace.hasTier),
                "parent_class": parent_class_uri,
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
    
    def _extract_principles(self, graph):
        """Extract Principle entities from the graph."""
        principles = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find Principle instances
        principle_subjects = set()
        principle_subjects.update(graph.subjects(RDF.type, proeth_namespace.Principle))
        
        # Also find instances that have both EntityType and Principle types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.Principle) in graph:
                principle_subjects.add(s)
        
        # Create principle objects
        for s in principle_subjects:
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            principles.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
            })
        
        return principles
    
    def _extract_obligations(self, graph):
        """Extract Obligation entities from the graph."""
        obligations = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find Obligation instances
        obligation_subjects = set()
        obligation_subjects.update(graph.subjects(RDF.type, proeth_namespace.Obligation))
        
        # Also find instances that have both EntityType and Obligation types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.Obligation) in graph:
                obligation_subjects.add(s)
        
        # Create obligation objects
        for s in obligation_subjects:
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            obligations.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
            })
        
        return obligations
    
    def _extract_condition_types(self, graph):
        """Extract State entities from the graph (legacy method name for compatibility)."""
        states = []
        namespace = self._detect_namespace(graph)
        proeth_namespace = self.namespaces["intermediate"]
        
        # Helper functions for getting properties
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        # Find State instances (updated to use State instead of ConditionType)
        state_subjects = set()
        state_subjects.update(graph.subjects(RDF.type, proeth_namespace.State))
        
        # Also find instances that have both EntityType and State types
        entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
        for s in entity_type_subjects:
            if (s, RDF.type, proeth_namespace.State) in graph:
                state_subjects.add(s)
        
        # Create state objects
        for s in state_subjects:
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            states.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
            })
        
        return states
    
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
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            resources.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
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
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            events.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
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
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            actions.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
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
            # Get parent class (RDFS.subClassOf)
            parent_class = next(graph.objects(s, RDFS.subClassOf), None)
            parent_class_uri = str(parent_class) if parent_class else None
            
            capabilities.append({
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s),
                "parent_class": parent_class_uri
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
