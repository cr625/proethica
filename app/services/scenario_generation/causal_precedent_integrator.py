"""
Stage 5: Causal Chain Integration & Precedent Discovery

Combines two critical functions:
1. Link decision points to their consequences via causal chains
2. Discover similar decision precedents across the case database

For each decision point:
- Maps to causal chains showing decision → consequence
- Generates OpenAI embedding (text-embedding-3-small, 1536-dim)
- Searches for similar decisions in other cases
- Uses Claude to classify precedents (supporting/distinguishable/analogous/contra)
- Attaches precedent analysis for interactive scenario display

Documentation: docs/SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md (Stage 5)
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from app.models import db
from app.utils.llm_utils import get_llm_client
import openai

logger = logging.getLogger(__name__)


@dataclass
class CausalLink:
    """Link between a decision and its consequences."""
    decision_id: str
    causal_chain_uri: str
    cause: str  # Decision/action
    effect: str  # Consequence
    causal_language: str  # How they're connected
    responsible_agent: str
    responsibility_type: str  # direct/indirect
    counterfactual: str  # What would have happened otherwise
    sequence: List[Dict]  # Step-by-step causal sequence

    def to_dict(self) -> Dict:
        return {
            'decision_id': self.decision_id,
            'causal_chain_uri': self.causal_chain_uri,
            'cause': self.cause,
            'effect': self.effect,
            'causal_language': self.causal_language,
            'responsible_agent': self.responsible_agent,
            'responsibility_type': self.responsibility_type,
            'counterfactual': self.counterfactual,
            'sequence': self.sequence
        }


@dataclass
class PrecedentCase:
    """A precedent decision from another case."""
    case_id: int
    case_title: str
    decision_id: str
    decision_question: str
    similarity_score: float
    precedent_type: str  # supporting, distinguishable, analogous, contra

    # Claude's analysis
    reasoning: str  # Why this is similar/different
    distinguishing_factors: List[str]  # Key differences
    key_similarities: List[str]  # What's the same
    teaching_narrative: str  # Pedagogical explanation

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'case_title': self.case_title,
            'decision_id': self.decision_id,
            'decision_question': self.decision_question,
            'similarity_score': self.similarity_score,
            'precedent_type': self.precedent_type,
            'reasoning': self.reasoning,
            'distinguishing_factors': self.distinguishing_factors,
            'key_similarities': self.key_similarities,
            'teaching_narrative': self.teaching_narrative
        }


@dataclass
class CausalPrecedentResult:
    """Result of Stage 5: causal links + precedents for all decisions."""
    causal_links: List[CausalLink]
    precedents_by_decision: Dict[str, List[PrecedentCase]]  # decision_id -> precedents
    embeddings_generated: int
    precedent_searches_performed: int
    total_precedents_found: int

    def to_dict(self) -> Dict:
        return {
            'causal_links_count': len(self.causal_links),
            'causal_links': [cl.to_dict() for cl in self.causal_links],
            'precedents_by_decision': {
                dec_id: [p.to_dict() for p in precs]
                for dec_id, precs in self.precedents_by_decision.items()
            },
            'embeddings_generated': self.embeddings_generated,
            'precedent_searches_performed': self.precedent_searches_performed,
            'total_precedents_found': self.total_precedents_found
        }


class CausalPrecedentIntegrator:
    """
    Stage 5: Integrate causal chains and discover precedents.

    Workflow:
    1. Link decisions to causal consequences
    2. Generate decision embeddings (OpenAI)
    3. Search for similar decisions (pgvector)
    4. Classify precedents (Claude)
    5. Return enriched decision points
    """

    def __init__(self):
        """Initialize with OpenAI and Claude clients."""
        self.llm_client = get_llm_client()

        # Initialize OpenAI client for embeddings
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.info("[Causal/Precedent] OpenAI client initialized for embeddings")
        else:
            self.openai_client = None
            logger.warning("[Causal/Precedent] No OpenAI API key found - precedent discovery will be limited")

        logger.info("[Causal/Precedent] Integrator initialized")

    def integrate(
        self,
        case_id: int,
        decision_points: List[Any],  # DecisionPoint objects from Stage 4
        causal_chains: List[Any],  # RDFEntity objects
        enable_precedent_discovery: bool = True
    ) -> CausalPrecedentResult:
        """
        Integrate causal chains and discover precedents for decision points.

        Args:
            case_id: Current case ID
            decision_points: Decision points from Stage 4
            causal_chains: Causal chain entities from Step 3
            enable_precedent_discovery: Whether to search for precedents

        Returns:
            CausalPrecedentResult with causal links and precedents
        """
        logger.info(
            f"[Causal/Precedent] Processing case {case_id}: "
            f"{len(decision_points)} decisions, {len(causal_chains)} causal chains"
        )

        # Step 1: Link decisions to causal chains
        causal_links = self._link_decisions_to_chains(decision_points, causal_chains)
        logger.info(f"[Causal/Precedent] Created {len(causal_links)} causal links")

        # Step 2-5: Precedent discovery
        precedents_by_decision = {}
        embeddings_generated = 0
        searches_performed = 0
        total_precedents = 0

        if enable_precedent_discovery and self.openai_client:
            for decision in decision_points:
                try:
                    # Generate embedding
                    embedding = self._generate_decision_embedding(case_id, decision)
                    if embedding:
                        embeddings_generated += 1

                        # Search for similar decisions
                        similar_decisions = self._search_similar_decisions(
                            case_id,
                            decision.id,
                            embedding
                        )
                        searches_performed += 1

                        # Classify precedents
                        precedents = self._classify_precedents(
                            decision,
                            similar_decisions
                        )

                        precedents_by_decision[decision.id] = precedents
                        total_precedents += len(precedents)

                        logger.info(
                            f"[Causal/Precedent] Decision '{decision.id}': "
                            f"found {len(precedents)} precedents"
                        )

                except Exception as e:
                    logger.error(f"[Causal/Precedent] Error processing decision {decision.id}: {e}")
                    precedents_by_decision[decision.id] = []
        else:
            logger.info("[Causal/Precedent] Precedent discovery disabled or no OpenAI client")

        result = CausalPrecedentResult(
            causal_links=causal_links,
            precedents_by_decision=precedents_by_decision,
            embeddings_generated=embeddings_generated,
            precedent_searches_performed=searches_performed,
            total_precedents_found=total_precedents
        )

        logger.info(
            f"[Causal/Precedent] Complete: {len(causal_links)} causal links, "
            f"{total_precedents} total precedents across {len(precedents_by_decision)} decisions"
        )

        return result

    def _link_decisions_to_chains(
        self,
        decision_points: List[Any],
        causal_chains: List[Any]
    ) -> List[CausalLink]:
        """
        Link decision points to their causal consequences.

        Matches decisions to causal chains by action/event labels.
        """
        causal_links = []

        for decision in decision_points:
            # Try to find causal chains where the cause matches this decision
            decision_label = decision.decision_question.lower()

            for chain in causal_chains:
                try:
                    rdf_data = chain.rdf_json_ld if hasattr(chain, 'rdf_json_ld') else {}
                    cause = rdf_data.get('proeth:cause', '')
                    effect = rdf_data.get('proeth:effect', '')

                    # Simple matching: if decision label contains cause or vice versa
                    if cause and (cause.lower() in decision_label or
                                  any(opt.label.lower() in cause.lower() for opt in decision.options)):

                        link = CausalLink(
                            decision_id=decision.id,
                            causal_chain_uri=chain.uri if hasattr(chain, 'uri') else '',
                            cause=cause,
                            effect=effect,
                            causal_language=rdf_data.get('proeth:causalLanguage', ''),
                            responsible_agent=rdf_data.get('proeth:responsibleAgent', ''),
                            responsibility_type=rdf_data.get('proeth:responsibilityType', ''),
                            counterfactual=rdf_data.get('proeth:counterfactual', ''),
                            sequence=rdf_data.get('proeth:causalSequence', [])
                        )
                        causal_links.append(link)
                        logger.debug(f"[Causal/Precedent] Linked {decision.id} to {cause} → {effect}")

                except Exception as e:
                    logger.error(f"[Causal/Precedent] Error linking chain {chain.label}: {e}")
                    continue

        return causal_links

    def _generate_decision_embedding(
        self,
        case_id: int,
        decision: Any
    ) -> Optional[List[float]]:
        """
        Generate OpenAI embedding for a decision point.

        Uses text-embedding-3-small (1536 dimensions) for semantic similarity.
        """
        if not self.openai_client:
            return None

        try:
            # Compose rich decision context for embedding
            context_parts = [
                f"Decision: {decision.decision_question}",
                f"Context: {decision.situation_context}",
                f"Ethical Tension: {decision.ethical_tension}",
                f"Stakes: {decision.stakes}",
                f"Competing Values: {', '.join(decision.competing_values)}",
                f"Decision Maker: {decision.decision_maker}"
            ]

            decision_text = "\n".join(context_parts)

            # Generate embedding using OpenAI
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=decision_text
            )

            embedding = response.data[0].embedding

            # Store in database
            self._store_decision_embedding(
                case_id=case_id,
                decision_id=decision.id,
                decision_question=decision.decision_question,
                decision_context={
                    'ethical_tension': decision.ethical_tension,
                    'stakes': decision.stakes,
                    'competing_values': decision.competing_values,
                    'decision_maker': decision.decision_maker,
                    'situation_context': decision.situation_context
                },
                embedding=embedding
            )

            logger.debug(f"[Causal/Precedent] Generated embedding for {decision.id}")
            return embedding

        except Exception as e:
            logger.error(f"[Causal/Precedent] Error generating embedding for {decision.id}: {e}")
            return None

    def _store_decision_embedding(
        self,
        case_id: int,
        decision_id: str,
        decision_question: str,
        decision_context: Dict,
        embedding: List[float]
    ):
        """Store decision embedding in database."""
        try:
            # Insert or update
            query = """
                INSERT INTO decision_embeddings
                    (case_id, decision_id, decision_question, decision_context, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (case_id, decision_id)
                DO UPDATE SET
                    decision_question = EXCLUDED.decision_question,
                    decision_context = EXCLUDED.decision_context,
                    embedding = EXCLUDED.embedding,
                    updated_at = CURRENT_TIMESTAMP
            """

            db.session.execute(
                query,
                (case_id, decision_id, decision_question, json.dumps(decision_context), embedding)
            )
            db.session.commit()

        except Exception as e:
            logger.error(f"[Causal/Precedent] Error storing embedding: {e}")
            db.session.rollback()

    def _search_similar_decisions(
        self,
        current_case_id: int,
        current_decision_id: str,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for similar decisions using pgvector cosine similarity.

        Args:
            current_case_id: Current case (to exclude from results)
            current_decision_id: Current decision ID
            query_embedding: Embedding vector to search with
            similarity_threshold: Minimum similarity (0-1)
            limit: Max results

        Returns:
            List of similar decisions with similarity scores
        """
        try:
            query = """
                SELECT
                    de.case_id,
                    de.decision_id,
                    de.decision_question,
                    de.decision_context,
                    d.title as case_title,
                    1 - (de.embedding <=> %s::vector) as similarity
                FROM decision_embeddings de
                JOIN documents d ON de.case_id = d.id
                WHERE de.case_id != %s
                    AND 1 - (de.embedding <=> %s::vector) > %s
                ORDER BY similarity DESC
                LIMIT %s
            """

            # Convert embedding to string format for pgvector
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

            result = db.session.execute(
                query,
                (embedding_str, current_case_id, embedding_str, similarity_threshold, limit)
            )

            similar_decisions = []
            for row in result:
                similar_decisions.append({
                    'case_id': row[0],
                    'decision_id': row[1],
                    'decision_question': row[2],
                    'decision_context': row[3],
                    'case_title': row[4],
                    'similarity': float(row[5])
                })

            return similar_decisions

        except Exception as e:
            logger.error(f"[Causal/Precedent] Error searching similar decisions: {e}")
            return []

    def _classify_precedents(
        self,
        current_decision: Any,
        similar_decisions: List[Dict]
    ) -> List[PrecedentCase]:
        """
        Use Claude to classify precedent relationships.

        Classifications:
        - supporting: Same decision, same outcome
        - distinguishable: Similar facts, different decision
        - analogous: Different facts, same ethical principle
        - contra: Opposite outcome, analyze why

        Args:
            current_decision: Current DecisionPoint
            similar_decisions: Similar decisions from search

        Returns:
            List of classified PrecedentCase objects
        """
        if not similar_decisions or not self.llm_client:
            return []

        precedents = []

        for similar in similar_decisions:
            try:
                # Create prompt for Claude to classify
                prompt = self._create_classification_prompt(current_decision, similar)

                # Call Claude (using existing LLM client)
                # Note: This assumes get_llm_client() returns a Claude client
                # If it returns something else, we may need to adjust
                response = self.llm_client.generate(prompt, max_tokens=800)

                # Parse response (expecting JSON)
                analysis = self._parse_classification_response(response)

                precedent = PrecedentCase(
                    case_id=similar['case_id'],
                    case_title=similar['case_title'],
                    decision_id=similar['decision_id'],
                    decision_question=similar['decision_question'],
                    similarity_score=similar['similarity'],
                    precedent_type=analysis.get('type', 'analogous'),
                    reasoning=analysis.get('reasoning', ''),
                    distinguishing_factors=analysis.get('distinguishing_factors', []),
                    key_similarities=analysis.get('key_similarities', []),
                    teaching_narrative=analysis.get('teaching_narrative', '')
                )

                precedents.append(precedent)

                # Store in database
                self._store_precedent_discovery(current_decision, precedent)

            except Exception as e:
                logger.error(f"[Causal/Precedent] Error classifying precedent: {e}")
                continue

        return precedents

    def _create_classification_prompt(
        self,
        current_decision: Any,
        similar_decision: Dict
    ) -> str:
        """Create prompt for Claude to classify precedent relationship."""
        return f"""You are analyzing precedent relationships in engineering ethics cases for educational purposes.

CURRENT CASE DECISION:
Question: {current_decision.decision_question}
Context: {current_decision.situation_context}
Ethical Tension: {current_decision.ethical_tension}
Stakes: {current_decision.stakes}
Competing Values: {', '.join(current_decision.competing_values)}

SIMILAR CASE FOUND (similarity: {similar_decision['similarity']:.2f}):
Case: {similar_decision['case_title']}
Question: {similar_decision['decision_question']}
Context: {json.dumps(similar_decision['decision_context'], indent=2)}

TASK: Classify this precedent relationship and explain for teaching purposes.

Classify as ONE of:
- "supporting": Same decision approach and outcome (reinforces the principle)
- "distinguishable": Similar facts but importantly different (teaches nuance)
- "analogous": Different surface facts but same underlying ethical principle
- "contra": Opposite outcome (teaches when principles apply differently)

Respond ONLY with valid JSON:
{{
  "type": "supporting|distinguishable|analogous|contra",
  "reasoning": "2-3 sentence explanation of the relationship",
  "key_similarities": ["similarity 1", "similarity 2", "similarity 3"],
  "distinguishing_factors": ["difference 1", "difference 2"],
  "teaching_narrative": "2-3 sentences explaining what students learn by comparing these cases"
}}"""

    def _parse_classification_response(self, response: str) -> Dict:
        """Parse Claude's JSON response."""
        try:
            # Find JSON in response (Claude sometimes adds explanation text)
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
            return {}
        except Exception as e:
            logger.error(f"[Causal/Precedent] Error parsing classification: {e}")
            return {}

    def _store_precedent_discovery(
        self,
        current_decision: Any,
        precedent: PrecedentCase
    ):
        """Store precedent discovery in database."""
        try:
            query = """
                INSERT INTO precedent_discoveries
                    (source_case_id, source_decision_id, target_case_id, target_decision_id,
                     similarity_score, precedent_type, llm_analysis, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (source_case_id, source_decision_id, target_case_id, target_decision_id)
                DO UPDATE SET
                    similarity_score = EXCLUDED.similarity_score,
                    precedent_type = EXCLUDED.precedent_type,
                    llm_analysis = EXCLUDED.llm_analysis,
                    updated_at = CURRENT_TIMESTAMP
            """

            # Get source case ID from decision's related_action_uri or use a lookup
            # For now, we'll extract from the decision ID pattern
            source_case_id = int(current_decision.id.split('_')[0].replace('decision', '')) if 'decision' in current_decision.id else 0

            llm_analysis = {
                'reasoning': precedent.reasoning,
                'distinguishing_factors': precedent.distinguishing_factors,
                'key_similarities': precedent.key_similarities,
                'teaching_narrative': precedent.teaching_narrative
            }

            db.session.execute(
                query,
                (source_case_id, current_decision.id, precedent.case_id, precedent.decision_id,
                 precedent.similarity_score, precedent.precedent_type, json.dumps(llm_analysis))
            )
            db.session.commit()

        except Exception as e:
            logger.error(f"[Causal/Precedent] Error storing precedent: {e}")
            db.session.rollback()
