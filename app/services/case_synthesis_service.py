"""
Case Synthesis Service

Step 4 Part C: Integrates all extraction passes into unified case representation.

Architecture implements STEP4_SYNTHESIS_ARCHITECTURE.md design:
- Phase 1: Entity Graph Construction
- Phase 2: Causal-Normative Integration
- Phase 3: Case Pattern Extraction
- Phase 4: Scenario Generation Framework
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from app.models import TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class EntityNode:
    """Represents a single entity in the knowledge graph"""
    entity_id: str
    entity_type: str  # roles, states, resources, etc.
    label: str
    definition: str
    section_type: str  # facts, discussion, questions, conclusions
    extraction_session_id: str
    rdf_json_ld: Dict

    # Graph relationships
    related_entities: List[str] = field(default_factory=list)
    causal_links: List[str] = field(default_factory=list)
    normative_links: List[str] = field(default_factory=list)
    temporal_links: List[str] = field(default_factory=list)


@dataclass
class EntityGraph:
    """Complete knowledge graph of all case entities"""
    nodes: Dict[str, EntityNode]  # entity_id -> EntityNode

    # Index by type for fast lookup
    by_type: Dict[str, List[str]] = field(default_factory=dict)

    # Index by section for cross-section analysis
    by_section: Dict[str, List[str]] = field(default_factory=dict)

    def add_node(self, node: EntityNode):
        """Add node to graph with indexing"""
        self.nodes[node.entity_id] = node

        # Index by type
        if node.entity_type not in self.by_type:
            self.by_type[node.entity_type] = []
        self.by_type[node.entity_type].append(node.entity_id)

        # Index by section
        if node.section_type not in self.by_section:
            self.by_section[node.section_type] = []
        self.by_section[node.section_type].append(node.entity_id)

    def get_nodes_by_type(self, entity_type: str) -> List[EntityNode]:
        """Get all nodes of a specific type"""
        entity_ids = self.by_type.get(entity_type, [])
        return [self.nodes[eid] for eid in entity_ids]

    def get_nodes_by_section(self, section_type: str) -> List[EntityNode]:
        """Get all nodes from a specific section"""
        entity_ids = self.by_section.get(section_type, [])
        return [self.nodes[eid] for eid in entity_ids]


@dataclass
class CausalNormativeLink:
    """Links causal chains to normative requirements"""
    action_id: str
    action_label: str

    # Normative context
    fulfills_obligations: List[str] = field(default_factory=list)
    violates_obligations: List[str] = field(default_factory=list)
    guided_by_principles: List[str] = field(default_factory=list)
    constrained_by: List[str] = field(default_factory=list)
    enabled_by_capabilities: List[str] = field(default_factory=list)

    # Agent context
    agent_role: Optional[str] = None
    agent_state: Optional[str] = None

    # Resources
    used_resources: List[str] = field(default_factory=list)

    # LLM reasoning
    reasoning: str = ""
    confidence: float = 0.0


@dataclass
class QuestionEmergence:
    """Analysis of WHY a question emerged from the case"""
    question_id: str
    question_text: str
    question_number: int

    # Precipitating factors
    triggered_by_events: List[str] = field(default_factory=list)
    triggered_by_actions: List[str] = field(default_factory=list)
    involves_states: List[str] = field(default_factory=list)
    involves_roles: List[str] = field(default_factory=list)

    # Competing considerations
    competing_obligations: List[str] = field(default_factory=list)
    competing_principles: List[str] = field(default_factory=list)

    # Temporal context
    temporal_sequence: List[str] = field(default_factory=list)

    # LLM analysis
    emergence_narrative: str = ""
    confidence: float = 0.0


@dataclass
class ResolutionPattern:
    """Pattern of HOW board resolved ethical question"""
    conclusion_id: str
    conclusion_text: str
    conclusion_number: int
    answers_questions: List[int] = field(default_factory=list)

    # Determinative factors
    determinative_principles: List[str] = field(default_factory=list)
    determinative_facts: List[str] = field(default_factory=list)
    cited_provisions: List[str] = field(default_factory=list)

    # Weighing process
    weighed_obligations: List[Tuple[str, str, str]] = field(default_factory=list)  # (obl1, obl2, resolution)

    # Pattern classification
    pattern_type: str = ""  # e.g., "CompetenceObligationConflict"
    generalizable_structure: Dict = field(default_factory=dict)

    # LLM analysis
    resolution_narrative: str = ""
    confidence: float = 0.0


@dataclass
class CaseSynthesis:
    """Complete synthesis result for a case"""
    case_id: int
    entity_graph: EntityGraph
    causal_normative_links: List[CausalNormativeLink]
    question_emergence: List[QuestionEmergence]
    resolution_patterns: List[ResolutionPattern]

    # Statistics
    synthesis_timestamp: datetime = field(default_factory=datetime.utcnow)
    total_nodes: int = 0
    total_links: int = 0


class CaseSynthesisService:
    """
    Step 4 Part C: Whole-Case Synthesis

    Integrates all extraction passes into unified case representation
    for future case reuse and experiment generation.
    """

    def __init__(self, llm_client = None):
        """
        Initialize synthesis service.

        Args:
            llm_client: LLM client from get_llm_client(). If None, uses heuristics.
        """
        self.llm_client = llm_client

    def synthesize_case(self, case_id: int) -> CaseSynthesis:
        """
        Main synthesis orchestration

        Returns:
            CaseSynthesis with complete integration results
        """
        logger.info(f"Starting case synthesis for case {case_id}")

        # Phase 1: Build entity graph
        logger.info("Phase 1: Building entity graph")
        entity_graph = self._build_entity_graph(case_id)

        # Phase 2: Link causal chains to normative requirements
        logger.info("Phase 2: Linking causal to normative")
        causal_normative_links = self._link_causal_to_normative(
            case_id,
            entity_graph
        )

        # Phase 3: Analyze question emergence
        logger.info("Phase 3: Analyzing question emergence")
        question_emergence = self._analyze_question_emergence(
            case_id,
            entity_graph
        )

        # Phase 4: Extract resolution patterns
        logger.info("Phase 4: Extracting resolution patterns")
        resolution_patterns = self._extract_resolution_patterns(
            case_id,
            entity_graph,
            question_emergence
        )

        # Create synthesis result
        synthesis = CaseSynthesis(
            case_id=case_id,
            entity_graph=entity_graph,
            causal_normative_links=causal_normative_links,
            question_emergence=question_emergence,
            resolution_patterns=resolution_patterns,
            total_nodes=len(entity_graph.nodes),
            total_links=len(causal_normative_links)
        )

        logger.info(
            f"Case synthesis complete: {synthesis.total_nodes} nodes, "
            f"{synthesis.total_links} causal-normative links, "
            f"{len(question_emergence)} questions analyzed"
        )

        return synthesis

    def _build_entity_graph(self, case_id: int) -> EntityGraph:
        """
        Phase 1: Build complete entity knowledge graph

        Loads all entities from Passes 1-3 and constructs unified graph.
        """
        graph = EntityGraph(nodes={})

        # Load all entities from temporary storage
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            storage_type='individual'
        ).all()

        logger.info(f"Loaded {len(entities)} entities for graph construction")

        for entity in entities:
            # Create unique ID
            entity_id = f"{entity.entity_type}_{entity.id}"

            # Determine section type from extraction session
            section_type = self._get_section_type(entity.extraction_session_id)

            # Create node
            node = EntityNode(
                entity_id=entity_id,
                entity_type=entity.entity_type.lower(),
                label=entity.entity_label,
                definition=entity.entity_definition or "",
                section_type=section_type,
                extraction_session_id=entity.extraction_session_id,
                rdf_json_ld=entity.rdf_json_ld or {}
            )

            # Extract initial relationships from RDF JSON-LD
            if entity.rdf_json_ld:
                node.related_entities = self._extract_entity_references(
                    entity.rdf_json_ld
                )

            graph.add_node(node)

        logger.info(
            f"Built entity graph: {len(graph.nodes)} nodes, "
            f"{len(graph.by_type)} types, {len(graph.by_section)} sections"
        )

        return graph

    def _get_section_type(self, extraction_session_id: str) -> str:
        """
        Determine section type from extraction session

        Queries ExtractionPrompt to find section_type for this session.
        """
        prompt = ExtractionPrompt.query.filter_by(
            extraction_session_id=extraction_session_id
        ).first()

        if prompt and prompt.section_type:
            return prompt.section_type

        return "unknown"

    def _extract_entity_references(self, rdf_json_ld: Dict) -> List[str]:
        """
        Extract entity references from RDF JSON-LD

        Looks for common relationship properties that reference other entities.
        """
        references = []

        # Common relationship properties
        rel_properties = [
            'mentionedEntities', 'relatedProvisions', 'citedProvisions',
            'answersQuestions', 'triggeredBy', 'causedBy', 'hasAgent',
            'involves', 'usedResource', 'constrainedBy', 'enabledBy'
        ]

        for prop in rel_properties:
            if prop in rdf_json_ld:
                value = rdf_json_ld[prop]
                if isinstance(value, list):
                    references.extend(value)
                elif isinstance(value, str):
                    references.append(value)

        return references

    def _link_causal_to_normative(
        self,
        case_id: int,
        entity_graph: EntityGraph
    ) -> List[CausalNormativeLink]:
        """
        Phase 2: Link causal chains to normative requirements

        For each action/event, identify:
        - Which obligations it fulfills/violates
        - Which principles guide it
        - Which constraints limit it
        - Which capabilities enable it
        - Agent roles and states
        """
        links = []

        # Get actions and events
        actions = entity_graph.get_nodes_by_type('actions')
        events = entity_graph.get_nodes_by_type('events')

        # Get normative entities
        obligations = entity_graph.get_nodes_by_type('obligations')
        principles = entity_graph.get_nodes_by_type('principles')
        constraints = entity_graph.get_nodes_by_type('constraints')
        capabilities = entity_graph.get_nodes_by_type('capabilities')

        # Get contextual entities
        roles = entity_graph.get_nodes_by_type('roles')
        states = entity_graph.get_nodes_by_type('states')
        resources = entity_graph.get_nodes_by_type('resources')

        logger.info(
            f"Linking {len(actions)} actions to {len(obligations)} obligations, "
            f"{len(principles)} principles"
        )

        # For each action, create causal-normative link
        for action in actions:
            link = self._create_causal_normative_link(
                action,
                obligations,
                principles,
                constraints,
                capabilities,
                roles,
                states,
                resources
            )
            links.append(link)

        # Also process events
        for event in events:
            link = self._create_causal_normative_link(
                event,
                obligations,
                principles,
                constraints,
                capabilities,
                roles,
                states,
                resources
            )
            links.append(link)

        logger.info(f"Created {len(links)} causal-normative links")

        return links

    def _create_causal_normative_link(
        self,
        action_node: EntityNode,
        obligations: List[EntityNode],
        principles: List[EntityNode],
        constraints: List[EntityNode],
        capabilities: List[EntityNode],
        roles: List[EntityNode],
        states: List[EntityNode],
        resources: List[EntityNode]
    ) -> CausalNormativeLink:
        """
        Create causal-normative link for a single action/event

        Uses LLM if available, otherwise uses heuristics.
        """
        link = CausalNormativeLink(
            action_id=action_node.entity_id,
            action_label=action_node.label
        )

        # Use LLM for sophisticated analysis if available
        if self.llm_client:
            link = self._llm_analyze_causal_normative(
                action_node,
                obligations,
                principles,
                constraints,
                capabilities,
                roles,
                states,
                resources
            )
        else:
            # Heuristic: Simple text matching
            action_text = f"{action_node.label} {action_node.definition}".lower()

            for obligation in obligations:
                obl_text = f"{obligation.label} {obligation.definition}".lower()
                if any(word in action_text for word in obl_text.split()[:3]):
                    link.fulfills_obligations.append(obligation.entity_id)

            for principle in principles:
                prin_text = f"{principle.label} {principle.definition}".lower()
                if any(word in action_text for word in prin_text.split()[:3]):
                    link.guided_by_principles.append(principle.entity_id)

            link.reasoning = "Heuristic text matching (LLM not available)"
            link.confidence = 0.5

        return link

    def _llm_analyze_causal_normative(
        self,
        action_node: EntityNode,
        obligations: List[EntityNode],
        principles: List[EntityNode],
        constraints: List[EntityNode],
        capabilities: List[EntityNode],
        roles: List[EntityNode],
        states: List[EntityNode],
        resources: List[EntityNode]
    ) -> CausalNormativeLink:
        """
        Use LLM to analyze causal-normative relationships

        This is a placeholder for future LLM integration.
        """
        # TODO: Implement LLM-based analysis
        # For now, return basic link
        return CausalNormativeLink(
            action_id=action_node.entity_id,
            action_label=action_node.label,
            reasoning="LLM analysis not yet implemented",
            confidence=0.0
        )

    def _analyze_question_emergence(
        self,
        case_id: int,
        entity_graph: EntityGraph
    ) -> List[QuestionEmergence]:
        """
        Phase 3: Analyze WHY each question emerged

        Traces each question back to:
        - Precipitating events/actions
        - Competing obligations/principles
        - Temporal sequence that led to question
        """
        analyses = []

        # Get questions
        questions = entity_graph.get_nodes_by_type('questions')

        if not questions:
            logger.info("No questions found for emergence analysis")
            return analyses

        logger.info(f"Analyzing emergence for {len(questions)} questions")

        for question in questions:
            analysis = QuestionEmergence(
                question_id=question.entity_id,
                question_text=question.definition,
                question_number=question.rdf_json_ld.get('questionNumber', 0)
            )

            # Analyze what triggered this question
            analysis = self._trace_question_triggers(
                question,
                entity_graph
            )

            analyses.append(analysis)

        logger.info(f"Completed {len(analyses)} question emergence analyses")

        return analyses

    def _trace_question_triggers(
        self,
        question: EntityNode,
        entity_graph: EntityGraph
    ) -> QuestionEmergence:
        """
        Trace what events/actions/states led to this question
        """
        analysis = QuestionEmergence(
            question_id=question.entity_id,
            question_text=question.definition,
            question_number=question.rdf_json_ld.get('questionNumber', 0)
        )

        # Get mentioned entities from question RDF
        mentioned = question.rdf_json_ld.get('mentionedEntities', [])

        # Categorize mentioned entities by type
        for entity_ref in mentioned:
            # Find entity in graph
            for node in entity_graph.nodes.values():
                if node.label in entity_ref or entity_ref in node.label:
                    if node.entity_type == 'events':
                        analysis.triggered_by_events.append(node.entity_id)
                    elif node.entity_type == 'actions':
                        analysis.triggered_by_actions.append(node.entity_id)
                    elif node.entity_type == 'states':
                        analysis.involves_states.append(node.entity_id)
                    elif node.entity_type == 'roles':
                        analysis.involves_roles.append(node.entity_id)
                    elif node.entity_type == 'obligations':
                        analysis.competing_obligations.append(node.entity_id)
                    elif node.entity_type == 'principles':
                        analysis.competing_principles.append(node.entity_id)

        # Generate narrative
        analysis.emergence_narrative = self._generate_emergence_narrative(
            analysis,
            entity_graph
        )

        analysis.confidence = 0.7  # Heuristic confidence

        return analysis

    def _generate_emergence_narrative(
        self,
        analysis: QuestionEmergence,
        entity_graph: EntityGraph
    ) -> str:
        """Generate human-readable narrative of question emergence"""
        parts = []

        if analysis.triggered_by_events:
            events = [entity_graph.nodes[eid].label for eid in analysis.triggered_by_events[:3]]
            parts.append(f"Triggered by events: {', '.join(events)}")

        if analysis.triggered_by_actions:
            actions = [entity_graph.nodes[eid].label for eid in analysis.triggered_by_actions[:3]]
            parts.append(f"Following actions: {', '.join(actions)}")

        if analysis.competing_obligations:
            obls = [entity_graph.nodes[eid].label for eid in analysis.competing_obligations[:3]]
            parts.append(f"Competing obligations: {', '.join(obls)}")

        if not parts:
            return "Question emergence analysis pending detailed LLM analysis."

        return ". ".join(parts) + "."

    def _extract_resolution_patterns(
        self,
        case_id: int,
        entity_graph: EntityGraph,
        question_emergence: List[QuestionEmergence]
    ) -> List[ResolutionPattern]:
        """
        Phase 4: Extract HOW board resolved each question

        For each conclusion:
        - Identify determinative principles/facts
        - Show how competing obligations were weighed
        - Extract generalizable pattern
        """
        patterns = []

        # Get conclusions
        conclusions = entity_graph.get_nodes_by_type('conclusions')

        if not conclusions:
            logger.info("No conclusions found for pattern extraction")
            return patterns

        logger.info(f"Extracting resolution patterns for {len(conclusions)} conclusions")

        for conclusion in conclusions:
            pattern = ResolutionPattern(
                conclusion_id=conclusion.entity_id,
                conclusion_text=conclusion.definition,
                conclusion_number=conclusion.rdf_json_ld.get('conclusionNumber', 0),
                answers_questions=conclusion.rdf_json_ld.get('answersQuestions', [])
            )

            # Extract determinative factors
            pattern = self._extract_determinative_factors(
                conclusion,
                entity_graph
            )

            # Classify pattern type
            pattern = self._classify_resolution_pattern(
                pattern,
                entity_graph
            )

            patterns.append(pattern)

        logger.info(f"Extracted {len(patterns)} resolution patterns")

        return patterns

    def _extract_determinative_factors(
        self,
        conclusion: EntityNode,
        entity_graph: EntityGraph
    ) -> ResolutionPattern:
        """Extract which factors were determinative in resolution"""
        pattern = ResolutionPattern(
            conclusion_id=conclusion.entity_id,
            conclusion_text=conclusion.definition,
            conclusion_number=conclusion.rdf_json_ld.get('conclusionNumber', 0)
        )

        # Get mentioned entities and cited provisions
        mentioned = conclusion.rdf_json_ld.get('mentionedEntities', [])
        cited = conclusion.rdf_json_ld.get('citedProvisions', [])

        pattern.cited_provisions = cited

        # Categorize mentioned entities
        for entity_ref in mentioned:
            for node in entity_graph.nodes.values():
                if node.label in entity_ref or entity_ref in node.label:
                    if node.entity_type == 'principles':
                        pattern.determinative_principles.append(node.entity_id)
                    elif node.entity_type in ['actions', 'events', 'states']:
                        pattern.determinative_facts.append(node.entity_id)

        # Generate resolution narrative
        pattern.resolution_narrative = self._generate_resolution_narrative(
            pattern,
            entity_graph
        )

        pattern.confidence = 0.7  # Heuristic confidence

        return pattern

    def _generate_resolution_narrative(
        self,
        pattern: ResolutionPattern,
        entity_graph: EntityGraph
    ) -> str:
        """Generate human-readable narrative of resolution"""
        parts = []

        if pattern.determinative_principles:
            prins = [entity_graph.nodes[eid].label for eid in pattern.determinative_principles[:3]]
            parts.append(f"Based on principles: {', '.join(prins)}")

        if pattern.cited_provisions:
            parts.append(f"Citing NSPE provisions: {', '.join(pattern.cited_provisions[:3])}")

        if pattern.determinative_facts:
            facts = [entity_graph.nodes[eid].label for eid in pattern.determinative_facts[:3]]
            parts.append(f"Considering facts: {', '.join(facts)}")

        if not parts:
            return "Resolution analysis pending detailed LLM analysis."

        return ". ".join(parts) + "."

    def _classify_resolution_pattern(
        self,
        pattern: ResolutionPattern,
        entity_graph: EntityGraph
    ) -> ResolutionPattern:
        """
        Classify resolution into pattern type

        Common patterns:
        - CompetenceObligationConflict
        - PublicSafetyVsEmployerDuty
        - ConfidentialityVsDisclosure
        - etc.
        """
        # Simple heuristic classification
        conclusion_text = pattern.conclusion_text.lower()

        if 'competence' in conclusion_text or 'expertise' in conclusion_text:
            pattern.pattern_type = 'CompetenceObligationConflict'
        elif 'safety' in conclusion_text and ('employer' in conclusion_text or 'duty' in conclusion_text):
            pattern.pattern_type = 'PublicSafetyVsEmployerDuty'
        elif 'confidential' in conclusion_text:
            pattern.pattern_type = 'ConfidentialityVsDisclosure'
        else:
            pattern.pattern_type = 'GeneralEthicalResolution'

        # Create generalizable structure (placeholder)
        pattern.generalizable_structure = {
            'pattern_type': pattern.pattern_type,
            'conclusion_summary': pattern.conclusion_text[:200],
            'key_principles': pattern.determinative_principles[:3],
            'key_provisions': pattern.cited_provisions[:3]
        }

        return pattern
