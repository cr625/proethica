"""
Enhanced Guideline Analysis Service v2 - Ontology-aware concept extraction and triple generation.
This extends the base GuidelineAnalysisService with advanced features while maintaining compatibility.

NEW: MCP Integration for real-time ontology exploration during concept extraction.
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
# Removed circular import - no longer needed
from app.services.embedding_service import EmbeddingService
from app.models.guideline import Guideline
from app.models.ontology import Ontology
from sqlalchemy import text

# MCP Integration
try:
    from app.services.ontserve_mcp_client import get_ontserve_mcp_client, MCPClientError, ONTSERVE_MCP_TOOLS
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP client not available - falling back to static ontology index")

logger = logging.getLogger(__name__)


class GuidelineAnalysisService:
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
        
    def extract_concepts(self, content: str, guideline_id: Optional[int] = None, 
                           world_id: Optional[int] = None, 
                           use_temp_storage: bool = True) -> Dict[str, Any]:
        """
        Enhanced concept extraction with ontology awareness.
        
        Args:
            content: Guideline text content
            guideline_id: Optional guideline ID for tracking
            world_id: Optional world ID for context (default: Engineering World)
            use_temp_storage: If True, store concepts in temporary storage
            
        Returns:
            Dict with extracted concepts, ontology matches, new term candidates, and session_id
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

            # Phase 4b (optional, modular pass): Obligations extraction and linking
            try:
                from app import config as app_config
            except Exception:
                app_config = None
            enable_ob = False
            if app_config and hasattr(app_config, 'ENABLE_OBLIGATIONS_EXTRACTION'):
                enable_ob = bool(getattr(app_config, 'ENABLE_OBLIGATIONS_EXTRACTION'))
            elif os.environ.get('ENABLE_OBLIGATIONS_EXTRACTION'):
                enable_ob = os.environ.get('ENABLE_OBLIGATIONS_EXTRACTION', 'false').lower() in ('1','true','yes')

            if enable_ob:
                try:
                    from app.services.extraction.obligations import ObligationsExtractor, ObligationsLinker, SimpleObligationMatcher
                    from app.services.extraction.base import NoopPostProcessor
                except Exception as imp_err:
                    logger.debug(f"Obligations module not available: {imp_err}\n")
                else:
                    provider = None
                    if app_config and hasattr(app_config, 'OBLIGATIONS_EXTRACTOR_PROVIDER'):
                        provider = getattr(app_config, 'OBLIGATIONS_EXTRACTOR_PROVIDER')
                    extractor = ObligationsExtractor(provider=provider)
                    post = NoopPostProcessor()
                    matcher = SimpleObligationMatcher()

                    ob_raw = extractor.extract(content, world_id=world_id, guideline_id=guideline_id) or []
                    ob_clean = post.process(ob_raw)
                    ob_matches = matcher.match(ob_clean, world_id=world_id)

                    # Merge matches for linking perspective (roles + obligations)
                    link_input = []
                    # Convert existing matched_concepts (dicts) into MatchedConcept-like dicts where we have URIs
                    for c in matched_concepts:
                        if c.get('ontology_match') and c['ontology_match'].get('uri'):
                            # shim into the fields obligations linker expects
                            link_input.append(type('MC', (), {
                                'candidate': type('Cand', (), {
                                    'primary_type': (c.get('type') or c.get('primary_type'))
                                })(),
                                'ontology_match': {'uri': c['ontology_match']['uri']}
                            }))

                    link_input.extend(ob_matches)

                    linker = ObligationsLinker()
                    new_triples = linker.link(link_input, world_id=world_id, guideline_id=guideline_id)
                    # Map to the format used by _save_semantic_triples
                    rel_triples = [
                        {
                            'subject': t.subject_uri,
                            'predicate': self.PREDICATES.get('hasObligation', 'http://proethica.org/ontology/intermediate#hasObligation'),
                            'object': t.object_uri,
                            'confidence': 1.0,
                            'inference_type': 'extracted',
                            'explanation': ''
                        }
                        for t in new_triples
                    ]
                    relationships.extend(rel_triples)
                    logger.info(f"Obligations pass added {len(rel_triples)} hasObligation triples")

            # Phase 4c (optional): Principles extraction and linking
            enable_pr = False
            if app_config and hasattr(app_config, 'ENABLE_PRINCIPLES_EXTRACTION'):
                enable_pr = bool(getattr(app_config, 'ENABLE_PRINCIPLES_EXTRACTION'))
            elif os.environ.get('ENABLE_PRINCIPLES_EXTRACTION'):
                enable_pr = os.environ.get('ENABLE_PRINCIPLES_EXTRACTION', 'false').lower() in ('1','true','yes')

            if enable_pr:
                try:
                    from app.services.extraction.principles import PrinciplesExtractor, SimplePrincipleMatcher, PrinciplesLinker
                    from app.services.extraction.base import NoopPostProcessor
                except Exception as imp_err:
                    logger.debug(f"Principles module not available: {imp_err}\n")
                else:
                    pr_provider = None
                    if app_config and hasattr(app_config, 'PRINCIPLES_EXTRACTOR_PROVIDER'):
                        pr_provider = getattr(app_config, 'PRINCIPLES_EXTRACTOR_PROVIDER')
                    pr_extractor = PrinciplesExtractor(provider=pr_provider)
                    pr_post = NoopPostProcessor()
                    pr_matcher = SimplePrincipleMatcher()

                    pr_raw = pr_extractor.extract(content, world_id=world_id, guideline_id=guideline_id) or []
                    pr_clean = pr_post.process(pr_raw)
                    pr_matches = pr_matcher.match(pr_clean, world_id=world_id)

                    # Prepare link input including roles from matched_concepts
                    pr_link_input = []
                    for c in matched_concepts:
                        if c.get('ontology_match') and c['ontology_match'].get('uri'):
                            pr_link_input.append(type('MC', (), {
                                'candidate': type('Cand', (), {
                                    'primary_type': (c.get('type') or c.get('primary_type'))
                                })(),
                                'ontology_match': {'uri': c['ontology_match']['uri']}
                            }))
                    pr_link_input.extend(pr_matches)

                    pr_linker = PrinciplesLinker()
                    pr_triples = pr_linker.link(pr_link_input, world_id=world_id, guideline_id=guideline_id)
                    pr_rel_triples = [
                        {
                            'subject': t.subject_uri,
                            'predicate': self.PREDICATES.get('adheresToPrinciple', 'http://proethica.org/ontology/intermediate#adheresToPrinciple'),
                            'object': t.object_uri,
                            'confidence': 1.0,
                            'inference_type': 'extracted',
                            'explanation': ''
                        }
                        for t in pr_triples
                    ]
                    relationships.extend(pr_rel_triples)
                    logger.info(f"Principles pass added {len(pr_rel_triples)} adheresToPrinciple triples")
            
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
            
            # Store in temporary storage if enabled
            if use_temp_storage and guideline_id and world_id:
                try:
                    # Enhance concepts with their suggested predicates from relationships
                    enhanced_concepts = self._add_predicates_to_concepts(matched_concepts, relationships)
                    
                    # Use draft ontology service if enabled, otherwise use traditional TemporaryConcept
                    # Always store in temporary storage first for pending workflow
                    # OntServe integration happens later when user saves/finalizes concepts
                    from app.services.temporary_concept_service import TemporaryConceptService
                    
                    session_id = TemporaryConceptService.store_concepts(
                        concepts=enhanced_concepts,
                        document_id=guideline_id,
                        world_id=world_id,
                        extraction_method='llm'
                    )
                    logger.info(f"Stored {len(enhanced_concepts)} concepts with predicates in temporary storage with session {session_id}")
                    logger.info("Concepts stored as 'pending' - user can navigate away and return to review")
                    
                    result['session_id'] = session_id
                except Exception as store_err:
                    logger.error(f"Failed to store concepts in temporary storage: {store_err}")
                    # Don't fail the extraction if storage fails
            
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
            # Use factory pattern to get appropriate ontology service (ProEthica or OntServe)
            from app.services.ontology_service_factory import get_ontology_service
            from app.models.world import World
            
            world = World.query.get(world_id)
            if world:
                ontology_service = get_ontology_service()
                result = ontology_service.get_entities_for_world(world)
                
                # Log which service was used
                source = result.get('source', 'unknown')
                logger.info(f"Using {source} service for ontology index building")
                
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
        """Multi-pass concept extraction integrating 5 working extractors.
        
        Implements Checkpoint 4: Multi-pass orchestration
        - Pass 1: Entities (Roles, Resources) - WHO and WHAT
        - Pass 2: Normative (Principles, Obligations) - SHOULD/MUST
        - Pass 3: Contextual (States) - WHEN/WHERE conditions
        """
        # Check if multi-pass extraction is enabled
        extraction_mode = os.environ.get('EXTRACTION_MODE', 'single_pass')
        if extraction_mode == 'multi_pass':
            logger.info("Starting multi-pass concept extraction (5 extractors)")
            return self._extract_multi_pass(content)
        else:
            logger.info("Using single-pass role extraction (legacy mode)")
            return self._extract_single_pass_roles(content)
    
    def _extract_multi_pass(self, content: str) -> List[Dict[str, Any]]:
        """Multi-pass extraction with all 9 working extractors organized in 3 logical passes."""
        all_concepts = []
        
        try:
            # Pass 1: Entities (Roles + Resources) - WHO and WHAT
            logger.info("=== PASS 1: ENTITIES (Roles + Resources) ===")
            entities_concepts = self._extract_entities_pass(content)
            all_concepts.extend(entities_concepts)
            logger.info(f"Pass 1 complete: {len(entities_concepts)} entity concepts")
            
            # Pass 2: Normative (Principles + Obligations + Constraints) - SHOULD/MUST/CAN'T  
            logger.info("=== PASS 2: NORMATIVE (Principles + Obligations + Constraints) ===")
            normative_concepts = self._extract_normative_pass(content)
            all_concepts.extend(normative_concepts)
            logger.info(f"Pass 2 complete: {len(normative_concepts)} normative concepts")
            
            # Pass 3: Behavioral (Actions + Events + Capabilities + States) - HOW/WHEN/WHERE
            logger.info("=== PASS 3: BEHAVIORAL (Actions + Events + Capabilities + States) ===") 
            behavioral_concepts = self._extract_behavioral_pass(content)
            all_concepts.extend(behavioral_concepts)
            logger.info(f"Pass 3 complete: {len(behavioral_concepts)} behavioral concepts")
            
            logger.info(f"Complete 9-concept extraction: {len(all_concepts)} total concepts")
            return all_concepts
            
        except Exception as e:
            logger.error(f"Error in 9-concept extraction: {e}", exc_info=True)
            # Fallback to 5-concept extraction
            logger.warning("Falling back to 5-concept extraction")
            return self._extract_5_concept_fallback(content)
    
    def _extract_entities_pass(self, content: str) -> List[Dict[str, Any]]:
        """Pass 1: Extract entities (Roles + Resources) - WHO and WHAT."""
        entities = []
        
        # Extract Roles
        try:
            from app.services.extraction.roles import RolesExtractor, RoleClassificationPostProcessor
            
            roles_extractor = RolesExtractor()
            post_processor = RoleClassificationPostProcessor()
            
            role_candidates = roles_extractor.extract(content)
            processed_roles = post_processor.process(role_candidates)
            
            for role in processed_roles:
                entities.append({
                    'label': role.label,
                    'description': role.description or f"Role: {role.label}",
                    'type': 'role',
                    'category': 'role', 
                    'primary_type': 'role',
                    'confidence': role.confidence or 0.7,
                    'importance': role.debug.get('importance', 'medium'),
                    'role_classification': role.debug.get('role_classification', 'professional'),
                    'text_references': role.debug.get('text_references', []),
                    'related_concepts': []
                })
                
            logger.info(f"Roles: {len(processed_roles)} extracted")
            
        except Exception as e:
            logger.error(f"Error extracting roles in entities pass: {e}")
        
        # Extract Resources if enabled
        if os.environ.get('ENABLE_RESOURCES_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.resources import ResourcesExtractor
                
                resources_extractor = ResourcesExtractor()
                resource_candidates = resources_extractor.extract(content)
                
                for resource in resource_candidates:
                    entities.append({
                        'label': resource.label,
                        'description': resource.description or f"Resource: {resource.label}",
                        'type': 'resource',
                        'category': 'resource',
                        'primary_type': 'resource', 
                        'confidence': resource.confidence or 0.65,
                        'resource_type': resource.debug.get('resource_type', 'general'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Resources: {len(resource_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting resources in entities pass: {e}")
        
        return entities
    
    def _extract_normative_pass(self, content: str) -> List[Dict[str, Any]]:
        """Pass 2: Extract normative concepts (Principles + Obligations + Constraints) - SHOULD/MUST/CAN'T."""
        normative = []
        
        # Extract Principles if enabled  
        if os.environ.get('ENABLE_PRINCIPLES_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.principles import PrinciplesExtractor
                
                principles_extractor = PrinciplesExtractor()
                principle_candidates = principles_extractor.extract(content)
                
                for principle in principle_candidates:
                    normative.append({
                        'label': principle.label,
                        'description': principle.description or f"Principle: {principle.label}",
                        'type': 'principle',
                        'category': 'principle',
                        'primary_type': 'principle',
                        'confidence': principle.confidence or 0.65,
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Principles: {len(principle_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting principles in normative pass: {e}")
        
        # Extract Obligations if enabled (with atomic splitting)
        if os.environ.get('ENABLE_OBLIGATIONS_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.obligations import ObligationsExtractor
                
                obligations_extractor = ObligationsExtractor()
                obligation_candidates = obligations_extractor.extract(content)
                
                for obligation in obligation_candidates:
                    normative.append({
                        'label': obligation.label,
                        'description': obligation.description or f"Obligation: {obligation.label}",
                        'type': 'obligation',
                        'category': 'obligation',
                        'primary_type': 'obligation',
                        'confidence': obligation.confidence or 0.7,
                        'original_compound': obligation.debug.get('original_compound'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Obligations: {len(obligation_candidates)} extracted (with atomic splitting)")
                
            except Exception as e:
                logger.error(f"Error extracting obligations in normative pass: {e}")
        
        # Extract Constraints if enabled
        if os.environ.get('ENABLE_CONSTRAINTS_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.constraints import ConstraintsExtractor
                
                constraints_extractor = ConstraintsExtractor()
                constraint_candidates = constraints_extractor.extract(content)
                
                for constraint in constraint_candidates:
                    normative.append({
                        'label': constraint.label,
                        'description': constraint.description or f"Constraint: {constraint.label}",
                        'type': 'constraint',
                        'category': 'constraint',
                        'primary_type': 'constraint',
                        'confidence': constraint.confidence or 0.65,
                        'constraint_type': constraint.debug.get('constraint_type', 'general'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Constraints: {len(constraint_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting constraints in normative pass: {e}")
        
        return normative
    
    def _extract_behavioral_pass(self, content: str) -> List[Dict[str, Any]]:
        """Pass 3: Extract behavioral concepts (Actions + Events + Capabilities + States) - HOW/WHEN/WHERE."""
        behavioral = []
        
        # Extract Actions if enabled
        if os.environ.get('ENABLE_ACTIONS_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.actions import ActionsExtractor
                
                actions_extractor = ActionsExtractor()
                action_candidates = actions_extractor.extract(content)
                
                for action in action_candidates:
                    behavioral.append({
                        'label': action.label,
                        'description': action.description or f"Action: {action.label}",
                        'type': 'action',
                        'category': 'action',
                        'primary_type': 'action',
                        'confidence': action.confidence or 0.6,
                        'action_type': action.debug.get('action_type', 'general'),
                        'original_compound': action.debug.get('original_compound'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Actions: {len(action_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting actions in behavioral pass: {e}")
        
        # Extract Events if enabled
        if os.environ.get('ENABLE_EVENTS_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.events import EventsExtractor
                
                events_extractor = EventsExtractor()
                event_candidates = events_extractor.extract(content)
                
                for event in event_candidates:
                    behavioral.append({
                        'label': event.label,
                        'description': event.description or f"Event: {event.label}",
                        'type': 'event',
                        'category': 'event',
                        'primary_type': 'event',
                        'confidence': event.confidence or 0.55,
                        'event_type': event.debug.get('event_type', 'general'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Events: {len(event_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting events in behavioral pass: {e}")
        
        # Extract Capabilities if enabled
        if os.environ.get('ENABLE_CAPABILITIES_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.capabilities import CapabilitiesExtractor
                
                capabilities_extractor = CapabilitiesExtractor()
                capability_candidates = capabilities_extractor.extract(content)
                
                for capability in capability_candidates:
                    behavioral.append({
                        'label': capability.label,
                        'description': capability.description or f"Capability: {capability.label}",
                        'type': 'capability',
                        'category': 'capability',
                        'primary_type': 'capability',
                        'confidence': capability.confidence or 0.6,
                        'capability_type': capability.debug.get('capability_type', 'general'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"Capabilities: {len(capability_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting capabilities in behavioral pass: {e}")
        
        # Extract States if enabled
        if os.environ.get('ENABLE_STATES_EXTRACTION', 'false').lower() == 'true':
            try:
                from app.services.extraction.states import StatesExtractor
                
                states_extractor = StatesExtractor()
                state_candidates = states_extractor.extract(content)
                
                for state in state_candidates:
                    behavioral.append({
                        'label': state.label,
                        'description': state.description or f"State: {state.label}",
                        'type': 'state',
                        'category': 'state',
                        'primary_type': 'state',
                        'confidence': state.confidence or 0.55,
                        'state_type': state.debug.get('state_type', 'general'),
                        'text_references': [],
                        'related_concepts': []
                    })
                    
                logger.info(f"States: {len(state_candidates)} extracted")
                
            except Exception as e:
                logger.error(f"Error extracting states in behavioral pass: {e}")
        
        return behavioral
    
    def _extract_5_concept_fallback(self, content: str) -> List[Dict[str, Any]]:
        """Fallback to 5-concept extraction if 9-concept extraction fails."""
        logger.info("Using 5-concept fallback extraction")
        all_concepts = []
        
        try:
            # Extract the 5 working extractors
            entities_concepts = self._extract_entities_pass(content)
            all_concepts.extend(entities_concepts)
            
            # Only extract principles and obligations from normative pass
            os.environ['ENABLE_CONSTRAINTS_EXTRACTION'] = 'false'  # Temporarily disable
            normative_concepts = self._extract_normative_pass(content)
            all_concepts.extend(normative_concepts)
            
            # Only extract states from behavioral pass  
            os.environ['ENABLE_ACTIONS_EXTRACTION'] = 'false'      # Temporarily disable
            os.environ['ENABLE_EVENTS_EXTRACTION'] = 'false'       # Temporarily disable
            os.environ['ENABLE_CAPABILITIES_EXTRACTION'] = 'false' # Temporarily disable
            behavioral_concepts = self._extract_behavioral_pass(content)
            all_concepts.extend(behavioral_concepts)
            
            logger.info(f"5-concept fallback complete: {len(all_concepts)} concepts")
            return all_concepts
            
        except Exception as e:
            logger.error(f"Error in 5-concept fallback: {e}")
            return self._extract_single_pass_roles(content)
    
    def _extract_single_pass_roles(self, content: str) -> List[Dict[str, Any]]:
        """Legacy single-pass role extraction for backward compatibility."""
        try:
            # Phase 1: Extract ROLES only using specialized extractor
            from app.services.extraction.roles import RolesExtractor, RoleClassificationPostProcessor
            
            roles_extractor = RolesExtractor()
            post_processor = RoleClassificationPostProcessor()
            
            # Extract role candidates
            role_candidates = roles_extractor.extract(content)
            logger.info(f"RolesExtractor returned {len(role_candidates)} candidates")
            
            # Post-process for classification
            processed_roles = post_processor.process(role_candidates)
            logger.info(f"Post-processing classified {len(processed_roles)} roles")
            
            # Convert ConceptCandidate objects to dict format expected by pipeline
            concepts = []
            for role in processed_roles:
                concept_dict = {
                    'label': role.label,
                    'description': role.description or f"Role: {role.label}",
                    'type': 'role',
                    'category': 'role',
                    'primary_type': 'role',
                    'confidence': role.confidence or 0.7,
                    'importance': role.debug.get('importance', 'medium'),
                    'role_classification': role.debug.get('role_classification', 'professional'),
                    'text_references': role.debug.get('text_references', []),
                    'related_concepts': []
                }
                concepts.append(concept_dict)
                
            logger.info(f"Single-pass complete: {len(concepts)} role concepts ready for matching")
            return concepts
            
        except Exception as e:
            logger.error(f"Error in single-pass extraction: {e}", exc_info=True)
            # Fallback to simple heuristic if new extraction fails
            logger.warning("Falling back to heuristic role extraction")
            return self._extract_roles_heuristic(content)
    
    def _extract_with_mcp_exploration(self, content: str) -> List[Dict[str, Any]]:
        """Extract concepts using MCP tools for real-time ontology exploration."""
        try:
            mcp_client = get_ontserve_mcp_client()
            
            # Phase 1: Let Claude explore the ontology first
            exploration_prompt = f"""
            You are analyzing an ethical guideline for concept extraction. 
            
            IMPORTANT: You have access to tools that let you explore the existing ontology 
            before extracting concepts. Use these tools to understand what concepts already 
            exist in each category, then extract concepts that either:
            1. Match existing ontology concepts (high confidence)
            2. Are genuinely new and should be added
            
            Available tools:
            - explore_ontology_category: Get existing concepts in a category
            - query_ontology_relationships: Query relationships between concepts  
            - check_concept_exists: Check if a specific concept exists
            
            Process:
            1. First explore the 9 ProEthica categories: Role, Principle, Obligation, 
               State, Resource, Action, Event, Capability, Constraint
            2. Then analyze the guideline and extract concepts
            3. For each extracted concept, indicate if it matches an existing concept 
               or is new
            
            Guideline to analyze:
            {content}
            
            Start by exploring the ontology categories, then extract concepts.
            Return a JSON array of extracted concepts with these fields:
            - label: The concept name  
            - description: A clear definition
            - type: Category (role, principle, obligation, etc.)
            - confidence: Your confidence in this extraction (0-1)
            - is_existing: true if matches existing ontology concept, false if new
            - ontology_match: If existing, the matched concept info
            - text_references: Supporting quotes from guideline
            """
            
            # Use tool-calling LLM (this would require Anthropic API with MCP integration)
            # For now, fall back to standard extraction with ontology context
            logger.info("MCP exploration requested but external API integration needed")
            return self._extract_with_ontology_context(content, mcp_client)
            
        except Exception as e:
            logger.error(f"MCP extraction failed: {e}, falling back to standard")
            return self._extract_concepts_standard(content)
    
    def _extract_with_ontology_context(self, content: str, mcp_client) -> List[Dict[str, Any]]:
        """Extract concepts with ontology context from MCP client."""
        try:
            # Get all existing categories to provide context
            all_entities = mcp_client.get_all_categories_sync()
            
            # Build context string for LLM
            ontology_context = "EXISTING ONTOLOGY CONCEPTS:\n"
            total_concepts = 0
            for category, entities in all_entities.items():
                if entities:
                    ontology_context += f"\n{category.upper()}:\n"
                    for entity in entities[:5]:  # Show first 5 examples
                        ontology_context += f"- {entity.get('label', 'No label')}: {entity.get('description', 'No description')[:100]}\n"
                    if len(entities) > 5:
                        ontology_context += f"... and {len(entities) - 5} more {category} concepts\n"
                    total_concepts += len(entities)
                else:
                    ontology_context += f"\n{category.upper()}: (no existing concepts)\n"
            
            logger.info(f"Providing context of {total_concepts} existing ontology concepts to LLM")
            
            # Enhanced prompt with ontology context
            enhanced_prompt = f"""
            {ontology_context}
            
            Now extract concepts from this guideline, being aware of existing concepts above.
            
            For each concept you extract:
            1. Check if it matches or is very similar to an existing concept
            2. If similar, mark as existing and reference the match
            3. If genuinely new, mark as new
            
            Focus on these categories: Role, Principle, Obligation, State, Resource, Action, Event, Capability, Constraint
            
            Guideline:
            {content}
            
            Return JSON array with fields:
            - label, description, type, confidence, is_existing, ontology_match, text_references
            """
            
            return self._call_llm_for_extraction(enhanced_prompt)
            
        except Exception as e:
            logger.error(f"Ontology context extraction failed: {e}")
            return self._extract_concepts_standard(content)
    
    def _extract_concepts_standard(self, content: str) -> List[Dict[str, Any]]:
        """Standard concept extraction without MCP integration."""
        prompt = f"""
        Analyze the following professional ethics guideline and extract key concepts.
        Focus on identifying concepts in these ontology categories:
        
        1. **Roles** - Professional positions, stakeholders (e.g., Engineer, Client, Public)
        2. **Principles** - Fundamental ethical values (e.g., Integrity, Honesty, Safety)
        3. **Obligations** - Duties, requirements, responsibilities
        4. **States** - Circumstances, constraints, situations
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
        
        return self._call_llm_for_extraction(prompt)
    
    def _call_llm_for_extraction(self, prompt: str) -> List[Dict[str, Any]]:
        """Call LLM for concept extraction with given prompt."""
        try:
            from app.utils.llm_utils import get_llm_client
            
            llm_client = get_llm_client()
            
            # Handle different LLM client types  
            if hasattr(llm_client, 'messages') and hasattr(llm_client.messages, 'create'):
                # Anthropic client
                response = llm_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
            elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                # OpenAI client
                response = llm_client.chat.completions.create(
                    model="gpt-4",
                    messages=[{
                        "role": "user", 
                        "content": prompt
                    }],
                    max_tokens=4000
                )
            else:
                raise RuntimeError(f"Unsupported LLM client type: {type(llm_client)}")
            
            # Extract and parse the response based on client type
            response_text = ""
            if hasattr(llm_client, 'messages'):
                # Anthropic response format
                if response and hasattr(response, 'content') and response.content:
                    response_text = response.content[0].text if response.content else ""
            elif hasattr(llm_client, 'chat'):
                # OpenAI response format
                if response and hasattr(response, 'choices') and response.choices:
                    response_text = response.choices[0].message.content
            
            # Parse JSON response for all client types
            try:
                import json
                import re
                
                # First, try to extract JSON from markdown code blocks
                code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
                if code_block_match:
                    response_text = code_block_match.group(1).strip()
                
                # Try to parse JSON directly
                if response_text.strip().startswith('['):
                    concepts = json.loads(response_text)
                    parsed_response = {"concepts": concepts}
                elif response_text.strip().startswith('{'):
                    parsed_response = json.loads(response_text)
                else:
                    # Look for JSON in the text
                    json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                    if json_match:
                        concepts = json.loads(json_match.group())
                        parsed_response = {"concepts": concepts}
                    else:
                        parsed_response = {"concepts": []}
            except json.JSONDecodeError:
                logger.warning(f"Could not parse LLM response as JSON: {response_text[:200]}...")
                parsed_response = {"concepts": []}
            
            # Check if we got concepts
            if parsed_response and isinstance(parsed_response, dict):
                if parsed_response.get('concepts'):
                    # Surface debug info if present (provider, guard stats)
                    try:
                        if 'debug_info' in parsed_response:
                            logger.info(f"Extraction debug_info: {parsed_response['debug_info']}")
                    except Exception:
                        pass
                    logger.info(f"Raw concept extraction returned {len(parsed_response['concepts'])} concepts")
                    # Log first concept for debugging
                    if parsed_response['concepts']:
                        first = parsed_response['concepts'][0]
                        logger.info(f"First concept structure: {list(first.keys())}")
                    return parsed_response['concepts']
                elif parsed_response.get('success') is False:
                    logger.warning(f"Raw concept extraction failed: {parsed_response.get('error', 'Unknown error')}")
                    return []
            
            logger.warning(f"Unexpected or empty response structure: {type(parsed_response)}")
            return []
            
        except Exception as e:
            logger.error(f"Error calling LLM for concept extraction: {e}")
            return []
    
    def _extract_roles_heuristic(self, content: str) -> List[Dict[str, Any]]:
        """Simple heuristic extraction of role concepts as fallback."""
        role_keywords = [
            'engineer', 'client', 'contractor', 'supervisor', 'manager', 
            'public', 'employer', 'employee', 'professional', 'stakeholder'
        ]
        
        roles = []
        content_lower = content.lower()
        
        for keyword in role_keywords:
            if keyword in content_lower:
                roles.append({
                    'label': f"{keyword.title()} Role",
                    'description': f"Professional or stakeholder role: {keyword}",
                    'type': 'role',
                    'importance': 'medium',
                    'text_references': [f"Inferred from mention of '{keyword}' in text"],
                    'related_concepts': []
                })
        
        return roles
    
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

                # 1) Embedding-based match - FIXED: Use consistent local model for concept embeddings
                concept_text = f"{concept['label']}. {concept.get('description', '')}"
                try:
                    # Force use of local embedding model (384 dims) to match ontology embeddings
                    concept_embedding = self.embedding_service._get_local_embedding(concept_text)
                except Exception as local_err:
                    logger.warning(f"Local embedding failed for concept '{concept['label']}': {local_err}")
                    # Fallback to exact match only
                    concept['is_new'] = True
                    concept['suggested_parent'] = self._suggest_parent_class(concept, [])
                    matched_concepts.append(concept)
                    continue
                
                # Find similar ontology terms
                similarities = []
                for uri, data in self._ontology_embeddings.items():
                    try:
                        similarity = self._calculate_similarity(concept_embedding, data['embedding'])
                        similarities.append({
                            'uri': uri,
                            'label': data['label'],
                            'category': data['category'],
                            'similarity': similarity
                        })
                    except Exception as sim_err:
                        logger.warning(f"Similarity calculation failed for {uri}: {sim_err}")
                        continue
                
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
        """Calculate cosine similarity between two embeddings, handling dimension mismatches."""
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Handle dimension mismatch by skipping incompatible embeddings
        if vec1.shape != vec2.shape:
            logger.debug(f"Dimension mismatch: {vec1.shape} vs {vec2.shape} - returning 0.0 similarity")
            return 0.0
        
        # Check for empty vectors
        if len(vec1) == 0 or len(vec2) == 0:
            return 0.0
        
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
                    'category': concept.get('category') or concept.get('type', 'concept'),
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

    def _add_predicates_to_concepts(self, concepts: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add suggested predicates to concepts based on discovered relationships.
        
        Args:
            concepts: List of extracted concepts
            relationships: List of discovered relationships between concepts
            
        Returns:
            Enhanced concepts with suggested_predicates field
        """
        # Create a mapping from concept URI to concept for fast lookup
        concept_uri_map = {}
        for concept in concepts:
            uri = concept.get('ontology_match', {}).get('uri')
            if not uri:
                uri = self._generate_uri(concept['label'])
            concept_uri_map[uri] = concept
        
        # Initialize suggested_predicates for all concepts
        enhanced_concepts = []
        for concept in concepts:
            enhanced_concept = dict(concept)
            enhanced_concept['suggested_predicates'] = {
                'as_subject': [],  # Predicates where this concept is the subject
                'as_object': []    # Predicates where this concept is the object
            }
            enhanced_concepts.append(enhanced_concept)
        
        # Map relationships to concepts
        for relationship in relationships:
            subject_uri = relationship.get('subject')
            object_uri = relationship.get('object')
            predicate = relationship.get('predicate')
            confidence = relationship.get('confidence', 0.0)
            explanation = relationship.get('explanation', '')
            
            # Add predicate suggestion to subject concept
            if subject_uri in concept_uri_map:
                # Find the enhanced concept that corresponds to this URI
                subject_concept = None
                for concept in enhanced_concepts:
                    concept_uri = concept.get('ontology_match', {}).get('uri') or self._generate_uri(concept['label'])
                    if concept_uri == subject_uri:
                        subject_concept = concept
                        break
                
                if subject_concept:
                    subject_concept['suggested_predicates']['as_subject'].append({
                        'predicate': predicate,
                        'target_concept': object_uri,
                        'target_label': self._get_concept_label_by_uri(object_uri, enhanced_concepts),
                        'confidence': confidence,
                        'explanation': explanation,
                        'predicate_type': self._get_predicate_type(predicate)
                    })
            
            # Add predicate suggestion to object concept
            if object_uri in concept_uri_map:
                # Find the enhanced concept that corresponds to this URI
                object_concept = None
                for concept in enhanced_concepts:
                    concept_uri = concept.get('ontology_match', {}).get('uri') or self._generate_uri(concept['label'])
                    if concept_uri == object_uri:
                        object_concept = concept
                        break
                
                if object_concept:
                    object_concept['suggested_predicates']['as_object'].append({
                        'predicate': predicate,
                        'source_concept': subject_uri,
                        'source_label': self._get_concept_label_by_uri(subject_uri, enhanced_concepts),
                        'confidence': confidence,
                        'explanation': explanation,
                        'predicate_type': self._get_predicate_type(predicate)
                    })
        
        return enhanced_concepts
    
    def _get_concept_label_by_uri(self, uri: str, concepts: List[Dict[str, Any]]) -> str:
        """Get concept label by URI from concepts list."""
        for concept in concepts:
            concept_uri = concept.get('ontology_match', {}).get('uri') or self._generate_uri(concept['label'])
            if concept_uri == uri:
                return concept['label']
        return uri  # Fallback to URI if label not found
    
    def _get_predicate_type(self, predicate: str) -> str:
        """Get human-readable type of predicate."""
        predicate_types = {
            'http://proethica.org/ontology/intermediate#hasObligation': 'has obligation',
            'http://proethica.org/ontology/intermediate#adheresToPrinciple': 'adheres to principle',
            'http://proethica.org/ontology/intermediate#pursuesEnd': 'pursues end',
            'http://proethica.org/ontology/intermediate#governedByCode': 'governed by code'
        }
        return predicate_types.get(predicate, predicate.split('#')[-1] if '#' in predicate else predicate)
