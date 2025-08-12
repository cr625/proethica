"""
Enhanced Guideline Analysis Service v2 - Ontology-aware concept extraction and triple generation.
This extends the base GuidelineAnalysisService with advanced features while maintaining compatibility.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re
from slugify import slugify

from app.models import db
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.services.embedding_service import EmbeddingService
from app.models.guideline import Guideline
from app.models.ontology import Ontology
from sqlalchemy import text

logger = logging.getLogger(__name__)


class GuidelineAnalysisServiceV2(GuidelineAnalysisService):
    """
    Enhanced version of GuidelineAnalysisService with:
    - Ontology-aware concept extraction
    - Term candidate identification
    - Semantic triple generation
    - Embedding-based similarity matching
    """
    
    def __init__(self):
        super().__init__()
        self.embedding_service = EmbeddingService()
        self._ontology_index = None
        self._ontology_embeddings = None
        
    def extract_concepts_v2(self, content: str, guideline_id: Optional[int] = None, 
                           world_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Enhanced concept extraction with ontology awareness.
        
        Args:
            content: Guideline text content
            guideline_id: Optional guideline ID for tracking
            world_id: Optional world ID for context (default: Engineering World)
            
        Returns:
            Dict with extracted concepts, ontology matches, and new term candidates
        """
        try:
            logger.info(f"Starting v2 concept extraction for guideline {guideline_id}")
            
            # Load ontology for the world
            if not world_id:
                world_id = 1  # Default to Engineering World
            
            # Build ontology index if not already loaded
            if not self._ontology_index:
                self._build_ontology_index(world_id)
            
            # Phase 1: Extract concepts with enhanced prompt
            raw_concepts = self._extract_raw_concepts(content)
            logger.info(f"Phase 1: Extracted {len(raw_concepts)} raw concepts")
            
            # Phase 2: Match concepts to existing ontology
            matched_concepts = self._match_concepts_to_ontology(raw_concepts)
            logger.info(f"Phase 2: Matched concepts - {len([c for c in matched_concepts if not c.get('is_new')])} existing, {len([c for c in matched_concepts if c.get('is_new')])} new")
            
            # Phase 3: Identify new term candidates
            term_candidates = self._identify_term_candidates(matched_concepts)
            logger.info(f"Phase 3: Identified {len(term_candidates)} term candidates")
            
            # Phase 4: Generate semantic relationships
            relationships = self._discover_relationships(matched_concepts, content)
            logger.info(f"Phase 4: Discovered {len(relationships)} relationships")
            
            result = {
                'success': True,
                'concepts': matched_concepts,
                'term_candidates': term_candidates,
                'relationships': relationships,
                'stats': {
                    'total_concepts': len(matched_concepts),
                    'matched_concepts': len([c for c in matched_concepts if not c.get('is_new')]),
                    'new_terms': len([c for c in matched_concepts if c.get('is_new')]),
                    'relationships': len(relationships)
                }
            }
            
            # Save term candidates if guideline_id provided
            if guideline_id:
                self._save_term_candidates(guideline_id, term_candidates)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in v2 concept extraction: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_ontology_index(self, world_id: int):
        """Build an index of ontology terms with embeddings for similarity matching."""
        logger.info(f"Building ontology index for world {world_id}")
        
        try:
            # First try to use OntologyEntityService for direct extraction
            from app.services.ontology_entity_service import OntologyEntityService
            from app.models.world import World
            
            world = World.query.get(world_id)
            if world:
                entity_service = OntologyEntityService.get_instance()
                result = entity_service.get_entities_for_world(world)
                
                entities = []
                if result.get('entities'):
                    # Flatten all entity types into a single list
                    for entity_type, entity_list in result['entities'].items():
                        for entity in entity_list:
                            entities.append({
                                'uri': entity.get('uri', entity.get('id', '')),
                                'label': entity.get('label', ''),
                                'description': entity.get('description', ''),
                                'category': entity_type
                            })
                    logger.info(f"Found {len(entities)} ontology entities from OntologyEntityService")
                else:
                    logger.warning("No entities found from OntologyEntityService")
                    
                # Generate embeddings for entities
                self._ontology_index = entities
                self._generate_ontology_embeddings()
                return
                
        except Exception as e:
            logger.warning(f"Error using OntologyEntityService, falling back to database query: {str(e)}")
        
        # Fallback to database query
        try:
            query = text("""
                SELECT DISTINCT e.uri, e.label, e.description, e.entity_type
                FROM ontology_entities e
                JOIN ontologies o ON e.ontology_id = o.id
                WHERE o.name IN ('engineering-ethics', 'proethica-intermediate', 'bfo')
                ORDER BY e.entity_type, e.label
            """)
            
            result = db.session.execute(query)
            entities = []
            
            for row in result:
                entities.append({
                    'uri': row.uri,
                    'label': row.label,
                    'description': row.description or '',
                    'category': self._map_entity_type_to_category(row.entity_type)
                })
            
            logger.info(f"Found {len(entities)} ontology entities from database")
            
        except Exception as e:
            logger.error(f"Error querying database for entities: {str(e)}")
            entities = []
        
        # Generate embeddings for entities
        self._ontology_index = entities
        self._generate_ontology_embeddings()
        
    def _map_entity_type_to_category(self, entity_type: str) -> str:
        """Map ontology entity types to guideline concept categories."""
        mapping = {
            'Class': 'concept',
            'ObjectProperty': 'relationship',
            'DataProperty': 'attribute',
            'Individual': 'instance'
        }
        
        # Also check for specific class types based on URI patterns
        if 'Role' in entity_type or 'Agent' in entity_type:
            return 'role'
        elif 'Principle' in entity_type or 'Value' in entity_type:
            return 'principle'
        elif 'Obligation' in entity_type or 'Duty' in entity_type:
            return 'obligation'
        elif 'Action' in entity_type or 'Process' in entity_type:
            return 'action'
        elif 'Condition' in entity_type or 'State' in entity_type:
            return 'condition'
        elif 'Resource' in entity_type:
            return 'resource'
        elif 'Capability' in entity_type or 'Skill' in entity_type:
            return 'capability'
        elif 'Event' in entity_type:
            return 'event'
        
        return mapping.get(entity_type, 'concept')
    
    def _generate_ontology_embeddings(self):
        """Generate embeddings for ontology terms."""
        if not self._ontology_index:
            logger.warning("No ontology index to generate embeddings from")
            self._ontology_embeddings = {}
            return
        
        logger.info("Generating embeddings for ontology terms")
        
        try:
            # Check if we already have embeddings in database
            existing_embeddings = self._load_existing_embeddings()
            
            embeddings_to_generate = []
            entity_map = {}  # Map URI to entity for quick lookup
            
            for entity in self._ontology_index:
                entity_map[entity['uri']] = entity
                if entity['uri'] not in existing_embeddings:
                    # Combine label and description for richer embedding
                    text = f"{entity['label']}. {entity['description']}"
                    embeddings_to_generate.append((entity['uri'], text))
            
            if embeddings_to_generate:
                logger.info(f"Generating {len(embeddings_to_generate)} new embeddings")
                for uri, text in embeddings_to_generate:
                    try:
                        embedding = self.embedding_service.get_embedding(text)
                        entity = entity_map.get(uri, {})
                        self._save_embedding(uri, entity.get('label', ''), entity.get('category', ''), embedding)
                    except Exception as e:
                        logger.error(f"Error generating embedding for {uri}: {str(e)}")
            
            # Load all embeddings
            self._ontology_embeddings = self._load_all_embeddings()
            logger.info(f"Loaded {len(self._ontology_embeddings)} ontology term embeddings")
            
        except Exception as e:
            logger.error(f"Error in embedding generation: {str(e)}")
            self._ontology_embeddings = {}
    
    def _load_existing_embeddings(self) -> Dict[str, List[float]]:
        """Load existing embeddings from database."""
        query = text("""
            SELECT term_uri, embedding 
            FROM ontology_term_embeddings
        """)
        
        result = db.session.execute(query)
        return {row.term_uri: row.embedding for row in result}
    
    def _save_embedding(self, uri: str, label: str, category: str, embedding: List[float]):
        """Save an embedding to the database."""
        query = text("""
            INSERT INTO ontology_term_embeddings (term_uri, label, category, embedding, embedding_model)
            VALUES (:uri, :label, :category, :embedding, :model)
            ON CONFLICT (term_uri) DO UPDATE
            SET embedding = :embedding, updated_at = CURRENT_TIMESTAMP
        """)
        
        db.session.execute(query, {
            'uri': uri,
            'label': label,
            'category': category,
            'embedding': json.dumps(embedding),
            'model': 'all-MiniLM-L6-v2'
        })
        db.session.commit()
    
    def _load_all_embeddings(self) -> Dict[str, Dict[str, Any]]:
        """Load all embeddings with metadata."""
        query = text("""
            SELECT term_uri, label, category, embedding
            FROM ontology_term_embeddings
        """)
        
        result = db.session.execute(query)
        embeddings = {}
        
        for row in result:
            embeddings[row.term_uri] = {
                'label': row.label,
                'category': row.category,
                'embedding': json.loads(row.embedding) if isinstance(row.embedding, str) else row.embedding
            }
        
        return embeddings
    
    def _extract_raw_concepts(self, content: str) -> List[Dict[str, Any]]:
        """Extract concepts using enhanced prompt focused on ontology categories."""
        prompt = f"""
        Analyze the following professional ethics guideline and extract key concepts.
        Focus on identifying concepts in these ontology categories:
        
        1. **Roles** - Professional positions, stakeholders (e.g., Engineer, Client, Public)
        2. **Principles** - Fundamental ethical values (e.g., Integrity, Honesty, Safety)
        3. **Obligations** - Duties, requirements, responsibilities
        4. **Conditions** - Circumstances, constraints, situations
        5. **Resources** - Tools, documents, information, materials
        6. **Actions** - Activities, processes, behaviors
        7. **Events** - Occurrences, incidents, situations
        8. **Capabilities** - Skills, competencies, abilities
        
        For each concept, provide:
        - label: The concept name
        - description: A clear definition
        - type: One of the above categories (use lowercase: role, principle, obligation, state, resource, action, event, capability)
        - related_concepts: Other concepts it relates to
        - text_references: Quotes from the guideline supporting this concept
        - importance: high/medium/low based on emphasis in the guideline
        
        Guideline content:
        {content}
        
        Return the concepts as a JSON array.
        """

        # Use existing extraction method
        response = super().extract_concepts(content)

        # Check if we got concepts
        if response and isinstance(response, dict):
            if response.get('concepts'):
                # Surface debug info if present (provider, guard stats)
                try:
                    if 'debug_info' in response:
                        logger.info(f"Extraction debug_info: {response['debug_info']}")
                except Exception:
                    pass
                logger.info(f"Raw concept extraction returned {len(response['concepts'])} concepts")
                # Log first concept for debugging
                if response['concepts']:
                    first = response['concepts'][0]
                    logger.info(f"First concept structure: {list(first.keys())}")
                return response['concepts']
            elif response.get('success') is False:
                logger.warning(f"Raw concept extraction failed: {response.get('error', 'Unknown error')}")
                return []

        # If response doesn't have expected structure, it might be returning just concepts
        logger.warning(f"Unexpected response format from parent extract_concepts: {type(response)}")
        return []
    
    def _match_concepts_to_ontology(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match extracted concepts to existing ontology terms using embeddings."""
        matched_concepts = []
        
        # Check if we have embeddings
        if not self._ontology_embeddings:
            logger.warning("No ontology embeddings available, marking all concepts as new")
            for concept in concepts:
                concept['is_new'] = True
                concept['suggested_parent'] = self._suggest_parent_class(concept, [])
                matched_concepts.append(concept)
            return matched_concepts
        
        for concept in concepts:
            try:
                # Generate embedding for concept
                concept_text = f"{concept['label']}. {concept.get('description', '')}"
                concept_embedding = self.embedding_service.get_embedding(concept_text)
                
                # Find similar ontology terms
                similarities = []
                for uri, data in self._ontology_embeddings.items():
                    similarity = self._calculate_similarity(concept_embedding, data['embedding'])
                    similarities.append({
                        'uri': uri,
                        'label': data['label'],
                        'category': data['category'],
                        'similarity': similarity
                    })
                
                # Sort by similarity
                similarities.sort(key=lambda x: x['similarity'], reverse=True)
                
                # Check if we have a good match
                best_match = similarities[0] if similarities else None
                
                if best_match and best_match['similarity'] > 0.75:
                    # Existing concept
                    concept['ontology_match'] = best_match
                    concept['is_new'] = False
                    concept['match_confidence'] = best_match['similarity']
                    logger.info(f"Matched '{concept['label']}' to existing '{best_match['label']}' (similarity: {best_match['similarity']:.2f})")
                else:
                    # New concept
                    concept['is_new'] = True
                    concept['suggested_parent'] = self._suggest_parent_class(concept, similarities)
                    logger.info(f"'{concept['label']}' is a new concept (best match: {best_match['similarity']:.2f if best_match else 0})")
                    
            except Exception as e:
                logger.error(f"Error matching concept '{concept.get('label', 'Unknown')}': {str(e)}")
                # Default to new concept on error
                concept['is_new'] = True
                concept['suggested_parent'] = self._suggest_parent_class(concept, [])
                
            matched_concepts.append(concept)
        
        return matched_concepts
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def _suggest_parent_class(self, concept: Dict[str, Any], 
                             similarities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Suggest a parent class for a new concept based on type and similarities."""
        category = concept.get('type', concept.get('category', 'concept'))
        
        # Map categories to default parent classes
        category_parents = {
            'role': 'http://proethica.ai/ontology#Role',
            'principle': 'http://proethica.ai/ontology#Principle',
            'obligation': 'http://proethica.ai/ontology#Obligation',
            'action': 'http://proethica.ai/ontology#Action',
            'condition': 'http://proethica.ai/ontology#Condition',
            'resource': 'http://proethica.ai/ontology#Resource',
            'capability': 'http://proethica.ai/ontology#Capability',
            'event': 'http://proethica.ai/ontology#Event'
        }
        
        parent_uri = category_parents.get(category, 'http://www.w3.org/2002/07/owl#Thing')
        
        # Find the parent in similarities if available
        for sim in similarities:
            if sim['uri'] == parent_uri:
                return {
                    'uri': parent_uri,
                    'label': sim['label'],
                    'confidence': 0.8  # High confidence for category match
                }
        
        # Default parent
        return {
            'uri': parent_uri,
            'label': category.title(),
            'confidence': 0.6
        }
    
    def _identify_term_candidates(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify concepts that are candidates for new ontology terms."""
        candidates = []
        
        for concept in concepts:
            if concept.get('is_new') and concept.get('importance') in ['high', 'medium']:
                candidate = {
                    'term_label': concept['label'],
                    'term_uri': self._generate_uri(concept['label']),
                    'category': concept['category'],
                    'definition': concept.get('description', ''),
                    'parent_class_uri': concept['suggested_parent']['uri'],
                    'confidence': concept['suggested_parent']['confidence'],
                    'text_references': concept.get('text_references', []),
                    'importance': concept['importance']
                }
                candidates.append(candidate)
        
        return candidates
    
    def _generate_uri(self, label: str) -> str:
        """Generate a URI for a concept."""
        slug = slugify(label, separator='_')
        return f"http://proethica.ai/ontology#{slug}"
    
    def _discover_relationships(self, concepts: List[Dict[str, Any]], 
                               content: str) -> List[Dict[str, Any]]:
        """Discover semantic relationships between concepts."""
        relationships = []
        
        # Relationship patterns
        patterns = {
            'requires': [r'requires?', r'needs?', r'necessary for', r'prerequisite'],
            'enables': [r'enables?', r'allows?', r'permits?', r'facilitates?'],
            'guides': [r'guides?', r'directs?', r'governs?', r'regulates?'],
            'conflictsWith': [r'conflicts? with', r'incompatible', r'opposes?', r'contradicts?'],
            'supports': [r'supports?', r'reinforces?', r'strengthens?', r'upholds?']
        }
        
        # Check each concept pair
        for i, concept1 in enumerate(concepts):
            for j, concept2 in enumerate(concepts[i+1:], i+1):
                # Look for relationships in text references
                rel = self._find_relationship_in_text(
                    concept1, concept2, content, patterns
                )
                
                if rel:
                    relationships.append({
                        'subject_uri': concept1.get('ontology_match', {}).get('uri', 
                                                   self._generate_uri(concept1['label'])),
                        'predicate': rel['type'],
                        'object_uri': concept2.get('ontology_match', {}).get('uri',
                                                  self._generate_uri(concept2['label'])),
                        'confidence': rel['confidence'],
                        'inference_type': rel['inference_type'],
                        'explanation': rel['explanation']
                    })
        
        return relationships
    
    def _find_relationship_in_text(self, concept1: Dict[str, Any], 
                                  concept2: Dict[str, Any], 
                                  content: str,
                                  patterns: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
        """Find relationship between two concepts in text."""
        # Simple pattern matching for now
        # TODO: Enhance with LLM-based inference
        
        label1 = concept1['label'].lower()
        label2 = concept2['label'].lower()
        
        # Check each pattern type
        for rel_type, rel_patterns in patterns.items():
            for pattern in rel_patterns:
                # Create regex to find relationships
                regex = rf"{label1}.*{pattern}.*{label2}"
                if re.search(regex, content.lower()):
                    return {
                        'type': rel_type,
                        'confidence': 0.7,
                        'inference_type': 'pattern',
                        'explanation': f"Pattern '{pattern}' found between concepts"
                    }
        
        return None
    
    def _save_term_candidates(self, guideline_id: int, candidates: List[Dict[str, Any]]):
        """Save term candidates to database."""
        for candidate in candidates:
            query = text("""
                INSERT INTO guideline_term_candidates 
                (guideline_id, term_label, term_uri, category, parent_class_uri, 
                 definition, confidence, is_existing, status)
                VALUES 
                (:guideline_id, :label, :uri, :category, :parent_uri,
                 :definition, :confidence, false, 'pending')
            """)
            
            db.session.execute(query, {
                'guideline_id': guideline_id,
                'label': candidate['term_label'],
                'uri': candidate['term_uri'],
                'category': candidate['category'],
                'parent_uri': candidate['parent_class_uri'],
                'definition': candidate['definition'],
                'confidence': candidate['confidence']
            })
        
        db.session.commit()
        logger.info(f"Saved {len(candidates)} term candidates for guideline {guideline_id}")
    
    def generate_semantic_triples(self, concepts: List[Dict[str, Any]], 
                                 relationships: List[Dict[str, Any]],
                                 guideline_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate rich semantic triples from concepts and relationships.
        
        Returns:
            Dict with triples in various formats
        """
        triples = []
        
        # Generate concept triples
        for concept in concepts:
            uri = concept.get('ontology_match', {}).get('uri', self._generate_uri(concept['label']))
            
            # Basic classification triple
            triples.append({
                'subject': uri,
                'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                'object': concept['suggested_parent']['uri'] if concept.get('is_new') 
                         else concept['ontology_match']['uri']
            })
            
            # Label
            triples.append({
                'subject': uri,
                'predicate': 'http://www.w3.org/2000/01/rdf-schema#label',
                'object': f'"{concept["label"]}"@en'
            })
            
            # Description
            if concept.get('description'):
                triples.append({
                    'subject': uri,
                    'predicate': 'http://purl.org/dc/terms/description',
                    'object': f'"{concept["description"]}"@en'
                })
        
        # Add relationship triples
        triples.extend(relationships)
        
        # Save to database if guideline_id provided
        if guideline_id:
            self._save_semantic_triples(guideline_id, triples)
        
        return {
            'success': True,
            'triples': triples,
            'stats': {
                'total_triples': len(triples),
                'concept_triples': len(concepts) * 3,  # type, label, description
                'relationship_triples': len(relationships)
            }
        }
    
    def _save_semantic_triples(self, guideline_id: int, triples: List[Dict[str, Any]]):
        """Save semantic triples to database."""
        for triple in triples:
            if triple.get('predicate') != 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type':
                # Skip basic type triples for now
                query = text("""
                    INSERT INTO guideline_semantic_triples
                    (guideline_id, subject_uri, predicate, object_uri, 
                     confidence, inference_type, explanation)
                    VALUES
                    (:guideline_id, :subject, :predicate, :object,
                     :confidence, :inference_type, :explanation)
                """)
                
                db.session.execute(query, {
                    'guideline_id': guideline_id,
                    'subject': triple['subject'],
                    'predicate': triple['predicate'],
                    'object': triple['object'],
                    'confidence': triple.get('confidence', 1.0),
                    'inference_type': triple.get('inference_type', 'explicit'),
                    'explanation': triple.get('explanation', '')
                })
        
        db.session.commit()
        logger.info(f"Saved {len(triples)} semantic triples for guideline {guideline_id}")