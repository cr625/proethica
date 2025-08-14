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
from app.utils.label_normalization import normalize_role_label

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
        self._label_index = {}
        # Common predicate IRIs (intermediate ontology)
        self.PREDICATES = {
            'hasObligation': 'http://proethica.org/ontology/intermediate#hasObligation',
            'adheresToPrinciple': 'http://proethica.org/ontology/intermediate#adheresToPrinciple',
            'pursuesEnd': 'http://proethica.org/ontology/intermediate#pursuesEnd',
            'governedByCode': 'http://proethica.org/ontology/intermediate#governedByCode'
        }
        
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
                # Persist discovered relationship triples as part of extraction for downstream aggregation
                try:
                    if relationships:
                        self._save_semantic_triples(guideline_id, relationships)
                except Exception as save_tri_err:
                    logger.debug(f"Saving semantic triples during extraction failed: {save_tri_err}")
            # Record extraction progress for tracking
            try:
                self._record_extraction_progress(
                    world_id=world_id,
                    guideline_id=guideline_id,
                    concepts=matched_concepts,
                    relationships=relationships,
                    stats=result.get('stats', {})
                )
            except Exception as rec_err:
                logger.debug(f"Progress logging failed: {rec_err}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in v2 concept extraction: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _record_extraction_progress(self, world_id: Optional[int], guideline_id: Optional[int],
                                    concepts: List[Dict[str, Any]],
                                    relationships: List[Dict[str, Any]],
                                    stats: Dict[str, Any]) -> None:
        """Append a JSONL record with extraction summary for progress tracking.

        Fields captured: timestamp, world_id, guideline_id, totals, counts_by_type, matched_by_type.
        """
        from collections import Counter
        ts = datetime.utcnow().isoformat()
        type_counts = Counter(((c.get('type') or c.get('primary_type') or '').lower() or 'unknown') for c in concepts)
        matched_by_type = Counter(((c.get('type') or c.get('primary_type') or '').lower() or 'unknown')
                                  for c in concepts if not c.get('is_new'))
        record = {
            'timestamp': ts,
            'world_id': world_id,
            'guideline_id': guideline_id,
            'totals': {
                'concepts': len(concepts),
                'relationships': len(relationships),
                'matched_concepts': stats.get('matched_concepts'),
                'new_terms': stats.get('new_terms')
            },
            'counts_by_type': dict(type_counts),
            'matched_by_type': dict(matched_by_type)
        }
        try:
            os.makedirs('logs', exist_ok=True)
            path = os.path.join('logs', 'extraction_runs.jsonl')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
            logger.info(f"Recorded extraction progress to {path}")
        except Exception as e:
            logger.debug(f"Failed to write extraction progress: {e}")
    
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
                self._build_label_index()
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
        self._build_label_index()

    def _build_label_index(self):
        """Build a case-insensitive, normalized label index for fast exact matches.

        For roles, use normalize_role_label (strips 'role' suffix, articles, etc.).
        For others, use a simple normalization (lowercase, trim, collapse spaces).
        """
        self._label_index = {}
        if not self._ontology_index:
            return

        import re

        def simple_norm(s: str) -> str:
            if not s:
                return ""
            s = re.sub(r"[\-_]+", " ", s)
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        for ent in self._ontology_index:
            label = (ent.get('label') or '').strip()
            if not label:
                continue
            etype = (ent.get('category') or ent.get('type') or '').lower()
            key = normalize_role_label(label) if etype == 'role' else simple_norm(label)
            # Prefer domain-specific over intermediate if duplicates occur
            prev = self._label_index.get(key)
            if not prev:
                self._label_index[key] = {
                    'uri': ent.get('uri'),
                    'label': label,
                    'category': etype
                }
            else:
                # Heuristic: prefer URIs not in intermediate namespace when available
                try:
                    if str(prev.get('uri','')).startswith('http://proethica.org/ontology/intermediate#') \
                       and not str(ent.get('uri','')).startswith('http://proethica.org/ontology/intermediate#'):
                        self._label_index[key] = {
                            'uri': ent.get('uri'),
                            'label': label,
                            'category': etype
                        }
                except Exception:
                    pass
        
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

        # If response doesn't have expected structure or empty, try a lightweight heuristic roles extraction
        logger.warning(f"Unexpected or empty response from parent extract_concepts (type={type(response)}); trying heuristic roles extraction")
        try:
            roles = self._extract_roles_heuristic(content)
            if roles:
                logger.info(f"Heuristic roles extraction produced {len(roles)} roles as fallback")
                return roles
        except Exception as _heur_err:
            logger.debug(f"Heuristic roles fallback failed: {_heur_err}")
        return []
    
    def _match_concepts_to_ontology(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match extracted concepts to existing ontology terms using embeddings."""
        matched_concepts = []
        
        def simple_norm(s: str) -> str:
            if not s:
                return ""
            s = re.sub(r"[\-_]+", " ", s)
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        # If embeddings are missing, still try exact label match via label index first
        if not self._ontology_embeddings:
            logger.warning("No ontology embeddings available; attempting exact label matches before marking new")
            for concept in concepts:
                try:
                    c_label = concept.get('label', '')
                    c_type = (concept.get('type') or concept.get('category') or '').lower()
                    key = normalize_role_label(c_label) if c_type == 'role' else simple_norm(c_label)
                    exact = self._label_index.get(key)
                    if exact:
                        concept['ontology_match'] = {
                            'uri': exact['uri'],
                            'label': exact['label'],
                            'category': exact['category'],
                            'similarity': 0.99
                        }
                        concept['is_new'] = False
                        concept['match_confidence'] = 0.99
                        logger.info(f"Exact label match (no-embeddings): '{concept['label']}' -> '{exact['label']}' ({exact['uri']})")
                    else:
                        # Fallback: known role canonical mapping (e.g., Engineer)
                        fallback = self._role_label_fallback_match(concept)
                        if fallback:
                            concept['ontology_match'] = fallback
                            concept['is_new'] = False
                            concept['match_confidence'] = fallback.get('similarity', 0.9)
                            logger.info(f"Role fallback match (no-embeddings): '{concept['label']}' -> '{fallback['label']}' ({fallback['uri']})")
                        else:
                            concept['is_new'] = True
                            concept['suggested_parent'] = self._suggest_parent_class(concept, [])
                    matched_concepts.append(concept)
                except Exception as e:
                    logger.error(f"Error in exact-match (no-embeddings) for '{concept.get('label','Unknown')}': {e}")
                    concept['is_new'] = True
                    concept['suggested_parent'] = self._suggest_parent_class(concept, [])
                    matched_concepts.append(concept)
            return matched_concepts

        for concept in concepts:
            try:
                # 0) Fast path: exact normalized label match
                c_label = concept.get('label', '')
                c_type = (concept.get('type') or concept.get('category') or '').lower()
                key = normalize_role_label(c_label) if c_type == 'role' else simple_norm(c_label)
                exact = self._label_index.get(key)
                if exact:
                    concept['ontology_match'] = {
                        'uri': exact['uri'],
                        'label': exact['label'],
                        'category': exact['category'],
                        'similarity': 0.99
                    }
                    concept['is_new'] = False
                    concept['match_confidence'] = 0.99
                    logger.info(f"Exact label match: '{concept['label']}' -> '{exact['label']}' ({exact['uri']})")
                    matched_concepts.append(concept)
                    continue
                else:
                    # Try fallback canonical mapping for roles before embeddings
                    fallback = self._role_label_fallback_match(concept)
                    if fallback:
                        concept['ontology_match'] = fallback
                        concept['is_new'] = False
                        concept['match_confidence'] = fallback.get('similarity', 0.9)
                        logger.info(f"Role fallback match: '{concept['label']}' -> '{fallback['label']}' ({fallback['uri']})")
                        matched_concepts.append(concept)
                        continue

                # 1) Embedding-based match
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
                    # Safely format best-match similarity when present
                    best_sim_str = f"{best_match['similarity']:.2f}" if best_match else "0.00"
                    logger.info(f"'{concept['label']}' is a new concept (best match: {best_sim_str})")
                    
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

    def _role_label_fallback_match(self, concept: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fallback exact matching for common Role labels when embeddings/index are weak.

        - Normalizes role label using normalize_role_label.
        - Attempts to find best candidate within label index keys for roles.
        - Prefers domain URIs over intermediate if both exist.
        """
        try:
            c_type = (concept.get('type') or concept.get('category') or '').lower()
            if c_type != 'role':
                return None

            raw = concept.get('label') or ''
            key = normalize_role_label(raw)
            if not key:
                return None

            exact = self._label_index.get(key)
            if exact and (exact.get('category') == 'role'):
                return {
                    'uri': exact['uri'],
                    'label': exact['label'],
                    'category': 'role',
                    'similarity': 0.95
                }

            # Some additional canonical mappings
            canonical = {
                'engineer': ['Engineer', 'Engineer Role', 'http://proethica.org/ontology/engineering-ethics#Engineer',
                             'http://proethica.org/ontology/intermediate#EngineerRole'],
            }
            if key in canonical:
                # Try to resolve the first matching candidate in the label index by URI
                candidates = canonical[key]
                for cand in candidates:
                    # try URI lookup via embeddings metadata or build a temp
                    # First, attempt to find by label index entries with same normalized key
                    ex = self._label_index.get(key)
                    if ex:
                        return {
                            'uri': ex['uri'],
                            'label': ex['label'],
                            'category': 'role',
                            'similarity': 0.93
                        }
                # If still nothing, but we know typical URIs, choose domain-first
                for cand in candidates:
                    if isinstance(cand, str) and cand.startswith('http://'):
                        # choose domain-first
                        if 'engineering-ethics#Engineer' in cand:
                            return {
                                'uri': cand,
                                'label': 'Engineer',
                                'category': 'role',
                                'similarity': 0.9
                            }
                # Fallback to intermediate EngineerRole URI
                return {
                    'uri': 'http://proethica.org/ontology/intermediate#EngineerRole',
                    'label': 'Engineer Role',
                    'category': 'role',
                    'similarity': 0.88
                }
        except Exception:
            return None
        return None
    
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

        # First, add role-centric ontology relationships using proximity heuristics
        relationships.extend(self._discover_role_relationships(concepts, content))

        # Check each concept pair
        for i, concept1 in enumerate(concepts):
            for j, concept2 in enumerate(concepts[i + 1 :], i + 1):
                # Look for relationships in text references
                rel = self._find_relationship_in_text(
                    concept1, concept2, content, patterns
                )

                if rel:
                    relationships.append({
                        'subject': concept1.get('ontology_match', {}).get('uri',
                                                self._generate_uri(concept1['label'])),
                        'predicate': rel['type'],
                        'object': concept2.get('ontology_match', {}).get('uri',
                                               self._generate_uri(concept2['label'])),
                        'confidence': rel['confidence'],
                        'inference_type': rel['inference_type'],
                        'explanation': rel['explanation']
                    })

        return relationships

    def _discover_role_relationships(self, concepts: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
        """Link Role concepts to Obligations, Principles, Ends, and Codes using simple proximity heuristics.

        Strategy:
        - For each Role, find nearest mentions of obligations/principles/ends/codes by label proximity in content.
        - Create up to top_k links per predicate with moderate confidence.
        """
        content_lower = content.lower() if content else ""
        if not content_lower:
            return []

        # Partition concepts by normalized type/category
        def ctype(c):
            return (c.get('type') or c.get('category') or '').lower()

        roles = [c for c in concepts if ctype(c) == 'role']
        obligations = [c for c in concepts if ctype(c) == 'obligation']
        principles = [c for c in concepts if ctype(c) == 'principle']
        # Ends may appear as 'end', 'goal', or sometimes principle/state; keep it narrow and also allow label keyword match
        ends = [c for c in concepts if ctype(c) in ('end', 'goal')]
        # Codes are resources often labeled with 'Code' or 'Standard' (e.g., NSPE Code)
        resources = [c for c in concepts if ctype(c) == 'resource']

        def first_index(lbl: str) -> int:
            if not lbl:
                return 10**9
            i = content_lower.find(lbl.lower())
            return i if i >= 0 else 10**9

        def uri_for(c: Dict[str, Any]) -> str:
            return c.get('ontology_match', {}).get('uri', self._generate_uri(c['label']))

        links = []
        top_k = 2

        for role in roles:
            r_uri = uri_for(role)
            r_label = role.get('label', '')
            r_pos = first_index(r_label)
            role_class = (role.get('role_classification') or '').lower()
            is_stakeholder = role_class == 'stakeholder'
            allow_stakeholder_principles = os.environ.get('ALLOW_STAKEHOLDER_PRINCIPLE_LINKS', 'false').lower() in ('1','true','yes')

            # Helper to pick nearest concepts to role mention
            def nearest(candidates: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
                scored = []
                for c in candidates:
                    # Bias by distance to role mention; if role not found, fall back to concept index
                    pos = first_index(c.get('label', ''))
                    dist = abs(pos - r_pos) if r_pos < 10**9 and pos < 10**9 else pos
                    scored.append((dist, c))
                scored.sort(key=lambda t: t[0])
                return scored[:top_k]

            # hasObligation — only attach to professional/agent roles, not stakeholder-only
            if not is_stakeholder:
                for _, obl in nearest(obligations):
                    links.append({
                        'subject': r_uri,
                        'predicate': self.PREDICATES['hasObligation'],
                        'object': uri_for(obl),
                        'confidence': 0.65,
                        'inference_type': 'proximity',
                        'explanation': 'Linked by textual proximity in guideline'
                    })

            # adheresToPrinciple
            if not is_stakeholder:
                for _, pr in nearest(principles):
                    links.append({
                        'subject': r_uri,
                        'predicate': self.PREDICATES['adheresToPrinciple'],
                        'object': uri_for(pr),
                        'confidence': 0.6,
                        'inference_type': 'proximity',
                        'explanation': 'Linked by textual proximity in guideline'
                    })
            else:
                # Optionally allow stakeholder→principle only when explicit textual signal is present
                if allow_stakeholder_principles and r_pos < 10**9:
                    def explicit_principle(pr_c):
                        p_label = (pr_c.get('label') or '').lower()
                        p_pos = first_index(p_label)
                        if p_pos >= 10**9:
                            return False
                        # Check a window covering both mentions
                        start = max(0, min(r_pos, p_pos) - 120)
                        end = min(len(content_lower), max(r_pos, p_pos) + 120)
                        window = content_lower[start:end]
                        return any(v in window for v in ['should', 'must', 'shall', 'adhere', 'uphold', 'follow', 'respect'])
                    for _, pr in nearest(principles):
                        if explicit_principle(pr):
                            links.append({
                                'subject': r_uri,
                                'predicate': self.PREDICATES['adheresToPrinciple'],
                                'object': uri_for(pr),
                                'confidence': 0.5,
                                'inference_type': 'explicit_text',
                                'explanation': 'Stakeholder linked to principle via explicit modal/verb near both mentions'
                            })

            # pursuesEnd
            # If no explicit ends extracted, detect simple goal keywords near role label to avoid spurious links
            ends_candidates = ends
            if not ends and r_pos < 10**9:
                window = content_lower[max(0, r_pos - 200) : r_pos + 200]
                if any(k in window for k in ['goal', 'goals', 'end', 'objective', 'aim']):
                    ends_candidates = []  # avoid creating anonymous ends without extraction
            if not is_stakeholder:
                for _, e in nearest(ends_candidates):
                    links.append({
                        'subject': r_uri,
                        'predicate': self.PREDICATES['pursuesEnd'],
                        'object': uri_for(e),
                        'confidence': 0.55,
                        'inference_type': 'proximity',
                        'explanation': 'Linked by textual proximity in guideline'
                    })

            # governedByCode — detect resources whose labels contain 'code' or 'standard' (professional roles only)
            code_like = [
                c
                for c in resources
                if re.search(r'\b(code|standard|guideline|policy)\b', c.get('label', ''), flags=re.I)
            ]
            if not is_stakeholder:
                for _, res in nearest(code_like):
                    links.append({
                        'subject': r_uri,
                        'predicate': self.PREDICATES['governedByCode'],
                        'object': uri_for(res),
                        'confidence': 0.6,
                        'inference_type': 'proximity',
                        'explanation': 'Linked to nearby code/standard mention'
                    })

        return links
    
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
        try:
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
        except Exception as e:
            logger.debug(f"Saving term candidates failed: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
    
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
        # Remove existing triples for this guideline for the key predicates to avoid duplicates
        try:
            del_q = text(
                """
                DELETE FROM guideline_semantic_triples
                WHERE guideline_id = :guideline_id AND predicate IN (
                    'http://proethica.org/ontology/intermediate#hasObligation',
                    'http://proethica.org/ontology/intermediate#adheresToPrinciple',
                    'http://proethica.org/ontology/intermediate#pursuesEnd',
                    'http://proethica.org/ontology/intermediate#governedByCode'
                )
                """
            )
            db.session.execute(del_q, { 'guideline_id': guideline_id })
        except Exception as del_err:
            logger.debug(f"Could not clear previous triples: {del_err}")

        try:
            # Dedupe incoming triples by (s,p,o)
            seen = set()
            for triple in triples:
                if triple.get('predicate') != 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type':
                    # Skip basic type triples for now
                    key = (triple.get('subject'), triple.get('predicate'), triple.get('object'))
                    if key in seen:
                        continue
                    seen.add(key)
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
        except Exception as ins_err:
            logger.debug(f"Inserting semantic triples failed: {ins_err}")
            try:
                db.session.rollback()
            except Exception:
                pass