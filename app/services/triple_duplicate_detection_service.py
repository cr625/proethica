"""
Triple Duplicate Detection Service

Detects duplicate triples before they are created, checking against:
1. Core ontology files (engineering-ethics.ttl, etc.)
2. Existing database triples
3. Similar/equivalent triples using semantic matching
"""

import os
import logging
from typing import Dict, List, Tuple, Optional, Set
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology

logger = logging.getLogger(__name__)

# Define namespaces
PROETHICA = Namespace("http://proethica.org/ontology/")
ENG_ETHICS = Namespace("http://proethica.org/ontology/engineering-ethics#")
PROETH_INT = Namespace("http://proethica.org/ontology/intermediate#")


class TripleDuplicateDetectionService:
    """Service for detecting duplicate triples across ontologies and database."""
    
    def __init__(self):
        self.ontology_graph = Graph()
        self.loaded_ontologies = set()
        self._load_core_ontologies()
    
    def _load_core_ontologies(self):
        """Load core ontology files into memory for duplicate checking."""
        # Try to load from database first
        try:
            ontologies = Ontology.query.filter_by(is_active=True).all()
            for ont in ontologies:
                if ont.content:
                    try:
                        self.ontology_graph.parse(data=ont.content, format='turtle')
                        self.loaded_ontologies.add(ont.name)
                        logger.info(f"Loaded ontology from DB: {ont.name}")
                    except Exception as e:
                        logger.error(f"Error parsing ontology {ont.name}: {e}")
        except Exception as e:
            logger.warning(f"Could not load ontologies from database: {e}")
        
        # Fallback to file loading
        ontology_files = [
            ('ontologies/engineering-ethics.ttl', 'engineering-ethics'),
            ('ontologies/proethica-intermediate.ttl', 'proethica-intermediate'),
            ('ontologies/bfo.ttl', 'bfo')
        ]
        
        for file_path, name in ontology_files:
            if name not in self.loaded_ontologies and os.path.exists(file_path):
                try:
                    self.ontology_graph.parse(file_path, format='turtle')
                    self.loaded_ontologies.add(name)
                    logger.info(f"Loaded ontology from file: {file_path}")
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
    
    def check_triple_exists_in_ontology(self, subject: str, predicate: str, 
                                      object_value: str, is_literal: bool = False) -> bool:
        """
        Check if a triple exists in the loaded ontology graphs.
        
        Args:
            subject: Subject URI
            predicate: Predicate URI  
            object_value: Object value (URI or literal)
            is_literal: Whether object is a literal value
            
        Returns:
            True if triple exists in ontology
        """
        subject_ref = URIRef(subject)
        predicate_ref = URIRef(predicate)
        
        if is_literal:
            object_ref = Literal(object_value)
        else:
            object_ref = URIRef(object_value)
        
        return (subject_ref, predicate_ref, object_ref) in self.ontology_graph
    
    def check_triple_exists_in_database(self, subject: str, predicate: str,
                                      object_value: str, is_literal: bool = False,
                                      exclude_guideline_id: Optional[int] = None) -> Optional[EntityTriple]:
        """
        Check if a triple exists in the database.
        
        Args:
            subject: Subject URI
            predicate: Predicate URI
            object_value: Object value (URI or literal)
            is_literal: Whether object is a literal value
            exclude_guideline_id: Guideline ID to exclude from check
            
        Returns:
            EntityTriple if found, None otherwise
        """
        query = EntityTriple.query.filter_by(
            subject=subject,
            predicate=predicate,
            is_literal=is_literal
        )
        
        if is_literal:
            query = query.filter_by(object_literal=object_value)
        else:
            query = query.filter_by(object_uri=object_value)
        
        if exclude_guideline_id:
            query = query.filter(EntityTriple.guideline_id != exclude_guideline_id)
        
        return query.first()
    
    def find_equivalent_concepts(self, concept_uri: str) -> Set[str]:
        """
        Find URIs that represent equivalent concepts.
        
        This handles cases where the same concept might have different URIs:
        - Different namespace versions
        - Aliases or alternative names
        - rdfs:seeAlso or owl:sameAs relationships
        
        Args:
            concept_uri: The concept URI to check
            
        Returns:
            Set of equivalent URIs (including the original)
        """
        equivalent = {concept_uri}
        
        # Check for owl:sameAs and rdfs:seeAlso relationships
        concept_ref = URIRef(concept_uri)
        
        # Find sameAs relationships
        for same in self.ontology_graph.objects(concept_ref, URIRef('http://www.w3.org/2002/07/owl#sameAs')):
            equivalent.add(str(same))
        
        # Find seeAlso relationships  
        for see_also in self.ontology_graph.objects(concept_ref, RDFS.seeAlso):
            equivalent.add(str(see_also))
        
        # Check common namespace variations
        variations = self._generate_namespace_variations(concept_uri)
        equivalent.update(variations)
        
        return equivalent
    
    def _generate_namespace_variations(self, uri: str) -> Set[str]:
        """Generate common namespace variations of a URI."""
        variations = set()
        
        # Common namespace mappings
        namespace_maps = [
            ('http://proethica.org/ontology/', 'http://proethica.org/ontology/engineering-ethics#'),
            ('http://proethica.org/ontology/intermediate#', 'http://proethica.org/ontology/'),
        ]
        
        for old_ns, new_ns in namespace_maps:
            if uri.startswith(old_ns):
                local_name = uri[len(old_ns):]
                variations.add(new_ns + local_name)
        
        return variations
    
    def check_duplicate_with_details(self, subject: str, predicate: str,
                                   object_value: str, is_literal: bool = False,
                                   exclude_guideline_id: Optional[int] = None) -> Dict:
        """
        Comprehensive duplicate check with detailed results.
        
        Returns:
            Dict with keys:
                - is_duplicate: bool
                - in_ontology: bool
                - in_database: bool
                - equivalent_found: bool
                - details: str describing what was found
                - existing_triple: Optional[EntityTriple]
        """
        result = {
            'is_duplicate': False,
            'in_ontology': False,
            'in_database': False,
            'equivalent_found': False,
            'details': '',
            'existing_triple': None
        }
        
        # Check exact match in ontology
        if self.check_triple_exists_in_ontology(subject, predicate, object_value, is_literal):
            result['is_duplicate'] = True
            result['in_ontology'] = True
            result['details'] = 'Exact triple exists in core ontology'
            return result
        
        # Check exact match in database
        existing = self.check_triple_exists_in_database(
            subject, predicate, object_value, is_literal, exclude_guideline_id
        )
        if existing:
            result['is_duplicate'] = True
            result['in_database'] = True
            result['existing_triple'] = existing
            result['details'] = f'Exact triple exists in database (from {existing.entity_type})'
            return result
        
        # Check for equivalent concepts
        equivalent_subjects = self.find_equivalent_concepts(subject)
        if not is_literal:
            equivalent_objects = self.find_equivalent_concepts(object_value)
        else:
            equivalent_objects = {object_value}
        
        # Check all combinations of equivalent URIs
        for eq_subject in equivalent_subjects:
            for eq_object in equivalent_objects:
                if eq_subject != subject or eq_object != object_value:
                    # Check ontology
                    if self.check_triple_exists_in_ontology(eq_subject, predicate, eq_object, is_literal):
                        result['is_duplicate'] = True
                        result['in_ontology'] = True
                        result['equivalent_found'] = True
                        result['details'] = f'Equivalent triple found in ontology: {eq_subject} -> {eq_object}'
                        return result
                    
                    # Check database
                    existing = self.check_triple_exists_in_database(
                        eq_subject, predicate, eq_object, is_literal, exclude_guideline_id
                    )
                    if existing:
                        result['is_duplicate'] = True
                        result['in_database'] = True
                        result['equivalent_found'] = True
                        result['existing_triple'] = existing
                        result['details'] = f'Equivalent triple found in database: {eq_subject} -> {eq_object}'
                        return result
        
        result['details'] = 'No duplicate found'
        return result
    
    def filter_duplicate_triples(self, triples: List[Dict],
                               exclude_guideline_id: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter a list of triples to remove duplicates.
        
        Args:
            triples: List of triple dictionaries with keys: subject, predicate, object, is_literal
            exclude_guideline_id: Guideline ID to exclude from duplicate checks
            
        Returns:
            Tuple of (unique_triples, duplicate_triples) where duplicate_triples includes details
        """
        unique_triples = []
        duplicate_triples = []
        
        for triple in triples:
            # Handle different object field names
            object_value = triple.get('object_uri', triple.get('object_literal', triple.get('object', '')))
            is_literal = triple.get('is_literal', False) or 'object_literal' in triple
            
            check_result = self.check_duplicate_with_details(
                triple['subject'],
                triple['predicate'], 
                object_value,
                is_literal,
                exclude_guideline_id
            )
            
            if check_result['is_duplicate']:
                triple['duplicate_info'] = check_result
                duplicate_triples.append(triple)
            else:
                unique_triples.append(triple)
        
        logger.info(f"Filtered {len(triples)} triples: {len(unique_triples)} unique, {len(duplicate_triples)} duplicates")
        
        return unique_triples, duplicate_triples
    
    def classify_triple_value(self, predicate: str, predicate_label: Optional[str] = None) -> str:
        """
        Classify a triple's value based on its predicate.
        
        Args:
            predicate: Predicate URI
            predicate_label: Human-readable predicate label
            
        Returns:
            'high', 'medium', or 'low'
        """
        # Use label if available, otherwise use URI
        check_value = (predicate_label or predicate).lower()
        
        # High value predicates
        high_value_keywords = [
            'defines', 'requires', 'emphasizes', 'implements',
            'alignswith', 'relatesto', 'isprimaryobligationof',
            'isethicalrequirementfor', 'primaryobligation'
        ]
        
        # Low value predicates  
        low_value_keywords = [
            'mentionsterm', 'mentions term', 'hastext', 'hastextcontent',
            'type', 'label'  # Basic RDF properties
        ]
        
        # Check classification
        for keyword in high_value_keywords:
            if keyword in check_value.replace(' ', '').replace('_', ''):
                return 'high'
        
        for keyword in low_value_keywords:
            if keyword in check_value.replace(' ', '').replace('_', ''):
                return 'low'
        
        return 'medium'


# Singleton instance
_duplicate_detection_service = None


def get_duplicate_detection_service() -> TripleDuplicateDetectionService:
    """Get or create the singleton duplicate detection service."""
    global _duplicate_detection_service
    if _duplicate_detection_service is None:
        _duplicate_detection_service = TripleDuplicateDetectionService()
    return _duplicate_detection_service