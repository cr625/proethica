"""
Data models for scenario generation pipeline.

These models represent the complete data package collected from:
- ProEthica temporary_rdf_storage (case-specific extractions)
- OntServe ontology_entities (committed ontology entities)
- Step 3 temporal dynamics (7-stage analysis)
- Step 4 synthesis (code provisions, Q&A)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json


@dataclass
class RDFEntity:
    """
    Single RDF entity from either temporary or committed storage.

    Source can be:
    - 'temporary': From ProEthica temporary_rdf_storage (case-specific)
    - 'committed': From OntServe ontology_entities (formal ontology)
    """
    uri: str
    label: str
    entity_type: str  # Role, Principle, Obligation, State, Resource, Action, Event, Capability, Constraint

    # Source tracking
    source: str  # 'temporary' or 'committed'

    # Content
    definition: Optional[str] = None

    # RDF representations
    rdf_turtle: Optional[str] = None
    rdf_json_ld: Optional[Dict] = None

    # Temporary entity fields (from ProEthica)
    case_id: Optional[int] = None
    section_type: Optional[str] = None  # 'facts', 'discussion', 'questions', 'conclusions'
    extraction_session_id: Optional[str] = None
    is_committed: bool = False
    is_selected: bool = False
    is_reviewed: bool = False
    provenance: Optional[Dict] = None

    # Committed entity fields (from OntServe)
    ontserve_id: Optional[int] = None
    parent_uri: Optional[str] = None
    ontology_properties: Optional[Dict] = None

    # Enrichment tracking
    enrichment_source: Optional[str] = None  # 'committed_ontology' if added from OntServe

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'uri': self.uri,
            'label': self.label,
            'entity_type': self.entity_type,
            'source': self.source,
            'definition': self.definition,
            'section_type': self.section_type,
            'is_committed': self.is_committed
        }


@dataclass
class TemporalMarker:
    """Temporal marker from Step 3 Stage 2."""
    marker_type: str  # 'absolute_date', 'relative_time', 'duration', 'allen_relation'
    value: str
    iso_format: Optional[str] = None
    confidence: float = 1.0


@dataclass
class AllenRelation:
    """Allen interval relation from Step 3 Stage 2."""
    relation_type: str  # 'before', 'after', 'during', 'overlaps', 'meets', etc.
    entity1_uri: str
    entity2_uri: str
    confidence: float = 1.0


@dataclass
class TimelineEntry:
    """Single entry in timeline from Step 3 Stage 6."""
    sequence_number: int
    timepoint: str  # Human-readable timepoint (e.g., "During preliminary design phase")
    iso_duration: str = ""  # ISO 8601 duration if available
    is_interval: bool = False  # Whether this is a time interval vs instant
    elements: List[Dict] = field(default_factory=list)  # Actions/events at this timepoint
    element_count: int = 0
    phase: Optional[str] = None  # 'introduction', 'development', 'resolution'


@dataclass
class ScenarioTimeline:
    """Complete scenario timeline with phases."""
    entries: List[TimelineEntry] = field(default_factory=list)
    phases: Dict[str, any] = field(default_factory=dict)  # TimelinePhase objects
    total_actions: int = 0
    total_events: int = 0
    duration_description: str = ""
    temporal_consistency: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'total_entries': len(self.entries),
            'total_actions': self.total_actions,
            'total_events': self.total_events,
            'duration': self.duration_description,
            'phases': {
                name: {
                    'name': phase.name,
                    'description': phase.description,
                    'entry_count': len(phase.timepoints),
                    'start_index': phase.start_index,
                    'end_index': phase.end_index
                }
                for name, phase in self.phases.items()
            },
            'entries': [
                {
                    'sequence': entry.sequence_number,
                    'timepoint': entry.timepoint,
                    'phase': entry.phase,
                    'element_count': entry.element_count,
                    'elements': entry.elements
                }
                for entry in self.entries
            ],
            'temporal_consistency': self.temporal_consistency
        }


@dataclass
class Action:
    """Action entity from Step 3 Stage 3."""
    uri: str
    label: str
    description: str
    volitional: bool = False
    intention: Optional[str] = None  # 'intended' or 'foreseen'
    mental_state: Optional[str] = None  # 'deliberate', 'negligent', 'accidental'
    competing_priorities: List[str] = field(default_factory=list)
    agent_uri: Optional[str] = None


@dataclass
class Event:
    """Event entity from Step 3 Stage 4."""
    uri: str
    label: str
    description: str
    is_emergency: bool = False
    participants: List[str] = field(default_factory=list)


@dataclass
class NESSPrecondition:
    """NESS test precondition from Step 3 Stage 5."""
    condition: str
    is_necessary: bool
    is_sufficient_element: bool


@dataclass
class ResponsibilityAttribution:
    """Responsibility attribution from Step 3 Stage 5."""
    agent_uri: str
    responsibility_type: str  # 'direct', 'contributory', 'vicarious'
    justification: str


@dataclass
class CausalChain:
    """Causal relationship from Step 3 Stage 5."""
    cause_entity_uri: str
    effect_entity_uri: str
    causal_relation_type: str  # 'direct_cause', 'contributing_factor', etc.
    ness_test_result: bool
    ness_preconditions: List[NESSPrecondition] = field(default_factory=list)
    responsibility_attribution: Optional[ResponsibilityAttribution] = None
    confidence: float = 1.0


@dataclass
class TemporalDynamicsData:
    """Complete temporal dynamics data from Step 3."""
    timeline: List[TimelineEntry] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    temporal_markers: List[TemporalMarker] = field(default_factory=list)
    allen_relations: List[AllenRelation] = field(default_factory=list)
    causal_chains: List[CausalChain] = field(default_factory=list)


@dataclass
class CodeProvision:
    """Code provision from Step 4."""
    code_section: str
    provision_text: str
    linked_entities: List[str] = field(default_factory=list)  # Entity URIs


@dataclass
class EthicalQuestion:
    """Ethical question from Step 4."""
    id: str
    label: str
    question_text: str
    description: str
    tagged_entities: List[str] = field(default_factory=list)  # Entity URIs
    linked_conclusion_id: Optional[str] = None


@dataclass
class EthicalConclusion:
    """Ethical conclusion from Step 4."""
    id: str
    label: str
    conclusion_text: str
    description: str
    linked_question_id: Optional[str] = None


@dataclass
class QuestionConclusionLink:
    """Question to conclusion link from Step 4."""
    question_id: str
    conclusion_id: str


@dataclass
class ProvisionEntityLink:
    """Code provision to entity link from Step 4."""
    provision_code_section: str
    entity_uri: str
    link_type: str  # Type of relationship


@dataclass
class SynthesisData:
    """Complete synthesis data from Step 4."""
    code_provisions: List[CodeProvision] = field(default_factory=list)
    questions: List[EthicalQuestion] = field(default_factory=list)
    conclusions: List[EthicalConclusion] = field(default_factory=list)
    qa_links: List[QuestionConclusionLink] = field(default_factory=list)
    provision_entity_links: List[ProvisionEntityLink] = field(default_factory=list)


@dataclass
class CaseMetadata:
    """Metadata about the case."""
    case_id: int
    title: str
    case_number: Optional[str] = None
    year: Optional[int] = None
    domain: str = "engineering_ethics"


@dataclass
class ProvenanceData:
    """Provenance data from extraction_prompts."""
    extraction_sessions: List[str] = field(default_factory=list)
    pass_completion: Dict[str, bool] = field(default_factory=dict)
    step4_complete: bool = False


@dataclass
class ScenarioSourceData:
    """
    Complete data package for scenario generation.

    Collected from:
    - temporary_rdf_storage (ProEthica ai_ethical_dm database)
    - ontology_entities (OntServe ontserve database)
    - Temporal dynamics outputs (Step 3)
    - Synthesis outputs (Step 4)
    """
    # Entity data (dual-source: temporary + committed)
    temporary_entities: Dict[str, List[RDFEntity]]  # Case-specific extractions
    committed_entities: Dict[str, List[RDFEntity]]  # Ontology-committed entities
    merged_entities: Dict[str, List[RDFEntity]]  # Combined entity set

    # Temporal dynamics data
    temporal_dynamics: TemporalDynamicsData

    # Synthesis data
    synthesis_data: SynthesisData

    # Metadata
    case_metadata: CaseMetadata
    provenance: ProvenanceData

    def get_entities_by_type(self, entity_type: str, source: str = 'merged') -> List[RDFEntity]:
        """
        Get entities of a specific type.

        Args:
            entity_type: Entity type (Role, Principle, etc.)
            source: 'temporary', 'committed', or 'merged' (default)
        """
        if source == 'temporary':
            return self.temporary_entities.get(entity_type, [])
        elif source == 'committed':
            return self.committed_entities.get(entity_type, [])
        else:
            return self.merged_entities.get(entity_type, [])

    def count_entities(self, source: str = 'merged') -> Dict[str, int]:
        """Count entities by type."""
        entities = {
            'temporary': self.temporary_entities,
            'committed': self.committed_entities,
            'merged': self.merged_entities
        }.get(source, self.merged_entities)

        return {entity_type: len(ents) for entity_type, ents in entities.items()}


@dataclass
class PassCompletionStatus:
    """Status of pass completion."""
    pass_number: int
    complete: bool
    entity_count: int
    sections_complete: List[str]


@dataclass
class EligibilityReport:
    """
    Eligibility report for scenario generation.

    A case is eligible if:
    - Pass 1 complete (Roles, States, Resources in facts+discussion)
    - Pass 2 complete (Principles, Obligations, Constraints, Capabilities)
    - Pass 3 complete (Actions, Events with temporal dynamics)
    - Step 4 complete (Provisions, Q&A synthesis)
    """
    case_id: int
    eligible: bool

    # Pass completion status
    pass_completion: Dict[str, PassCompletionStatus]

    # Entity counts
    entity_counts: Dict[str, int]

    # Temporal dynamics availability
    has_temporal_dynamics: bool
    temporal_summary: Dict[str, Any]

    # Step 4 completion
    step4_complete: bool
    step4_summary: Dict[str, Any]

    # Overall summary
    summary: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'case_id': self.case_id,
            'eligible': self.eligible,
            'pass_completion': {
                pass_name: {
                    'pass_number': status.pass_number,
                    'complete': status.complete,
                    'entity_count': status.entity_count,
                    'sections_complete': status.sections_complete
                }
                for pass_name, status in self.pass_completion.items()
            },
            'entity_counts': self.entity_counts,
            'has_temporal_dynamics': self.has_temporal_dynamics,
            'temporal_summary': self.temporal_summary,
            'step4_complete': self.step4_complete,
            'step4_summary': self.step4_summary,
            'summary': self.summary
        }
