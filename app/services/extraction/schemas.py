"""
Unified Pydantic schemas for D-Tuple extraction.

These schemas reconcile three sources:
1. Dual extractor dataclasses (app/services/extraction/dual_*_extractor.py)
2. DB prompt template output_schemas (extraction_prompt_templates table)
3. Enhanced prompt extraction schemas (NINE_COMPONENT_DEFINITIONS.md)

All schemas are grounded in the D-Tuple formalization D = (R, P, O, S, Rs, A, E, Ca, Cs)
from Chapter 2 of the dissertation.

Schema structure per concept:
- Candidate{Concept}Class: new ontology class discovered in case text
- {Concept}Individual: specific case instance of a class
- {Concept}ExtractionResult: top-level wrapper for LLM output

Ontology alignment (v2.3.0):
- Category enums derived from proethica-intermediate.ttl subclass hierarchy
- CATEGORY_TO_ONTOLOGY_IRI maps enum values to rdfs:subClassOf targets
- Core namespace: http://proethica.org/ontology/core#
- Intermediate namespace: http://proethica.org/ontology/intermediate#

Cross-references:
- Ontology: OntServe/ontologies/proethica-core.ttl (v2.3.0)
- Intermediate: OntServe/ontologies/proethica-intermediate.ttl
- Definitions: docs-internal/conferences_submissions/iccbr/NINE_COMPONENT_DEFINITIONS.md
- D-Tuple formalization: docs-internal/references/chapter2.md Section 2.2.4
"""

from __future__ import annotations

import copy
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Ontology namespaces
# ---------------------------------------------------------------------------

CORE_NS = "http://proethica.org/ontology/core#"
INTERMEDIATE_NS = "http://proethica.org/ontology/intermediate#"


# ---------------------------------------------------------------------------
# Common models
# ---------------------------------------------------------------------------

class MatchDecision(BaseModel):
    """Standardized ontology match decision across all 9 component types.

    Determines whether a candidate class maps to an existing class in the
    OntServe ontology (proethica-intermediate or proethica-core).
    """
    matches_existing: bool = False
    matched_uri: Optional[str] = None
    matched_label: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None


class BaseCandidate(BaseModel):
    """Fields common to all candidate class schemas."""
    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(..., description="Concept class name")
    definition: str = Field(
        ..., description="Concept definition",
        validation_alias=AliasChoices('definition', 'description'),
    )
    text_references: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices('text_references', 'examples_from_case'),
        description="Direct quotes from case text where this concept appears",
    )
    source_text: Optional[str] = Field(None, max_length=500)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    match_decision: MatchDecision = Field(default_factory=MatchDecision)


class BaseIndividual(BaseModel):
    """Fields common to all individual schemas."""
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    identifier: str = Field("", description="Unique instance descriptor")
    text_references: List[str] = Field(
        default_factory=list,
        description="Direct quotes from case text where this individual appears",
    )
    source_text: Optional[str] = Field(None, max_length=500)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    match_decision: MatchDecision = Field(default_factory=MatchDecision)

    @model_validator(mode='before')
    @classmethod
    def _normalize_individual_fields(cls, data: Any) -> Any:
        """Map common LLM field name variants to the expected names."""
        if not isinstance(data, dict):
            return data
        # identifier / name can come from 'label'
        if not data.get('identifier') and not data.get('name'):
            data['identifier'] = data.get('label', '')
            data['name'] = data.get('label', '')
        elif not data.get('identifier'):
            data['identifier'] = data.get('name', '')
        elif not data.get('name'):
            data['name'] = data.get('identifier', '')
        return data


# ---------------------------------------------------------------------------
# R (Roles) -- Contextual Grounding
# ---------------------------------------------------------------------------
# "Professional positions with associated duties, responsibilities, and
#  decision-making authority" (Chapter 2, Table 2.1)
# BFO: bfo:0000023 (role)
# Ontology: ProfessionalRole (ProviderClient, ProfessionalPeer,
#   EmployerRelationship, PublicResponsibility), ParticipantRole, StakeholderRole
# Literature: Oakley & Cocking, Kong et al., Doernberg & Truog
# ---------------------------------------------------------------------------

class RoleCategory(str, Enum):
    """The four Kong et al. (2020) RELATIONAL identity-role categories (extraction-architecture
    spec, R section / decision R1).

    A role's relational archetype is edge-PRIMARY: it is materialized at commit from the actor edge
    the role bears (hasClient -> ProviderClientRole, professionalPeerOf -> ProfessionalPeerRole,
    employedBy -> EmployerRelationshipRole, owesDutyToward -> PublicResponsibilityRole). role_category
    is the FALLBACK relational signal, used only when no actor edge is extracted (the edge wins on
    conflict). It is nullable (a role may bear no relational category) and is a commit routing input,
    not stored as a literal. participant and stakeholder were removed from this enum (they are
    occupational, not relational; stakeholder collapses into participant); the occupational
    professional/participant axis is carried by role_kind.
    """
    provider_client = "provider_client"
    professional_peer = "professional_peer"
    employer_relationship = "employer_relationship"
    public_responsibility = "public_responsibility"


class RoleKind(str, Enum):
    """The occupational professional/participant backstop (extraction-architecture spec, R section,
    decision A2 / professional-participant typing).

    Drives ProfessionalRole vs ParticipantRole typing when the ontology-driven occupational resolver
    matches no head (e.g. a novel label such as "Affected Citizen"). Omitted when the case text does
    not state the judgment, so absence is three-state-capable (the earlier is_professional boolean was
    dropped because a boolean cannot represent the unstated case, which is exactly when the backstop
    must stay silent). A commit routing input, not stored as a literal.
    """
    professional = "professional"
    participant = "participant"


class CandidateRoleClass(BaseCandidate):
    """A new role class discovered in case text.

    Field set aligned to the extraction-architecture spec (R section, 2026-06-28). role_category is the
    nullable relational fallback (the four Kong categories; the relational archetype is edge-primary at
    commit, R1) and role_kind is the occupational professional/participant backstop. The earlier
    generated_obligations and adheres_to_principles class fields were dropped (spec "Remove" / "Not stored":
    they are R->P->O routing inputs owned by the dedicated R->P->O pass, materialized as the
    hasObligation/adheresToPrinciple edges, not stored as class literals).
    """
    role_category: Optional[RoleCategory] = None
    role_kind: Optional[RoleKind] = None
    # Structured role-class attributes (Chapter 3, Section 3.3.1). Restored
    # 2026-06-22 for dissertation fidelity; populated by the Roles prompt.
    distinguishing_features: List[str] = Field(
        default_factory=list,
        description="What makes this role distinct from related roles")
    professional_scope: Optional[str] = Field(
        None, description="Areas of responsibility and authority")
    typical_qualifications: List[str] = Field(
        default_factory=list,
        description="Required education, licensing, and experience")
    associated_virtues: List[str] = Field(
        default_factory=list,
        description="Virtues or qualities expected of this role (professional roles)")


class RoleIndividual(BaseIndividual):
    """A specific person or entity filling a role in the case."""
    name: str = Field("", description="Person/entity identifier")
    actor: Optional[str] = Field(
        None,
        description=(
            "The stable underlying agent this role facet belongs to, e.g. "
            "'Engineer A', 'Owner', 'City of X'. The SAME actor seen in a "
            "different section under a different role facet must reuse this "
            "exact value. Used to mint one proeth-core:Agent per actor that "
            "bears each facet via hasRole; do not invent a parallel actor for "
            "someone already identified in an earlier section."
        ),
    )
    role_class: str = Field(
        "", description="Role class label or URI",
        alias="instance_of",
    )
    role_category: Optional[RoleCategory] = Field(
        None, description="The relational Kong category for this individual (the four relational "
                          "archetypes; nullable). Relational typing is edge-primary at commit (R1); this "
                          "is the fallback used only when no actor edge is extracted. A routing input."
    )
    role_kind: Optional[RoleKind] = Field(
        None, description="The occupational professional/participant backstop; drives "
                          "ProfessionalRole/ParticipantRole typing when the occupational resolver matches "
                          "no head. Omitted when unstated (three-state via absence). A routing input."
    )
    # Professional-role bearer data (ProfessionalRolePropertyShape). Extract only for a PROFESSIONAL
    # role-bearer (engineer/architect/...); a participant/stakeholder role-bearer has none of these.
    license: Optional[str] = Field(None, description="Professional license / licensure")
    specialty: Optional[str] = Field(None, description="Area of specialisation")
    experience_level: Optional[str] = Field(None, description="Professional experience")
    employer: Optional[str] = Field(None, description="Employer / affiliation")
    technical_background: Optional[str] = Field(None, description="Technical background")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overflow 'key: value' bag for case-specific bearer attributes outside the named fields above"
    )
    relationships: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Employment, collaboration, client relationships"
    )
    additional_relationships: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Overflow bag: relationships the case states that fit NO controlled relationship type; "
                    "each {type, target, quote}. Staged (not mapped to a controlled edge) for periodic review "
                    "and possible promotion to a real ontology property."
    )
    # active_obligations and ethical_tensions were dropped (extraction-architecture spec, R section,
    # 2026-06-28): they are R->P->O routing inputs owned by the dedicated R->P->O pass and the
    # obligation-layer defeasibility edges, materialized as first-class edges rather than stored as
    # per-individual role literals (spec "Remove" / "Not stored").
    case_involvement: Optional[str] = None


class RoleExtractionResult(BaseModel):
    """Top-level LLM output for role extraction."""
    new_role_classes: List[CandidateRoleClass] = Field(default_factory=list)
    role_individuals: List[RoleIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# P (Principles) -- Normative Structure
# ---------------------------------------------------------------------------
# "High-level ethical guidelines that establish professional ideals"
# BFO: iao:0000033 (directive information entity)
# Ontology: FundamentalEthicalPrinciple, ProfessionalVirtuePrinciple,
#   RelationalPrinciple, DomainSpecificPrinciple
# Literature: McLaren (extensional definition), Frankel (aspirational level),
#   Taddeo (constitutional interpretation), Prem (abstraction problem)
# ---------------------------------------------------------------------------

class PrincipleCategory(str, Enum):
    """proethica-intermediate.ttl Principle subclass hierarchy.

    Chapter 2.2.2 literature analysis.
    """
    fundamental_ethical = "fundamental_ethical"
    professional_virtue = "professional_virtue"
    relational = "relational"
    domain_specific = "domain_specific"


class CandidatePrincipleClass(BaseCandidate):
    """A new principle class discovered in case text.

    Field set aligned to the extraction-architecture spec (P section, 2026-06):
    principle_category drives the four-kind subClassOf typing when a new leaf is minted and
    the canonical leaf label (BaseCandidate.label) becomes the rdf:type. extensional_examples
    is retained as an optional class-mint field (McLaren extensional grounding). The earlier
    abstract_nature, value_basis, operationalization, derived_obligations, and potential_conflicts
    fields were dropped (spec "Not stored": folded into the class definition or carried by edges).
    """
    principle_category: Optional[PrincipleCategory] = None
    extensional_examples: List[str] = Field(
        default_factory=list,
        description="Concrete application examples (McLaren extensional definition); optional class-mint field"
    )


class PrincipleIndividual(BaseIndividual):
    """A specific principle invocation in the case."""
    principle_class: str = Field("", description="Principle class label or URI", alias="instance_of")
    concrete_expression: Optional[str] = Field(
        None, description="How the principle appears in this case"
    )
    invoked_by: List[str] = Field(
        default_factory=list,
        description="Roles/parties invoking this principle"
    )
    applied_to: List[str] = Field(
        default_factory=list,
        description="Situations or decisions this principle is applied to"
    )
    interpretation: Optional[str] = Field(
        None, description="Context-specific interpretation"
    )
    balancing_with: List[str] = Field(
        default_factory=list,
        description="Competing principles in this case"
    )
    tension_resolution: Optional[str] = Field(
        None, description="How the tension was resolved"
    )


class PrincipleExtractionResult(BaseModel):
    """Top-level LLM output for principle extraction."""
    new_principle_classes: List[CandidatePrincipleClass] = Field(default_factory=list)
    principle_individuals: List[PrincipleIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# O (Obligations) -- Normative Structure
# ---------------------------------------------------------------------------
# "Specific requirements for action or restraint"
# BFO: iao:0000033 (directive information entity)
# Ontology: DisclosureObligation, SafetyObligation, CompetenceObligation,
#   ConfidentialityObligation, ReportingObligation, CollegialObligation,
#   LegalObligation, EthicalObligation
# Literature: Dennis et al. (specification requirements), Anderson (duty
#   quantification), Donohue (ICBO 2017, DIE classification)
# ---------------------------------------------------------------------------

class ObligationType(str, Enum):
    """proethica-intermediate.ttl Obligation subclass hierarchy.

    Domain-based obligation classification from NSPE Code structure
    and Dennis et al. (2016) specification requirements.
    """
    disclosure = "disclosure"
    safety = "safety"
    competence = "competence"
    confidentiality = "confidentiality"
    reporting = "reporting"
    collegial = "collegial"
    legal = "legal"
    ethical = "ethical"


class EnforcementLevel(str, Enum):
    """Deontic modality (orthogonal to obligation type).

    Maps to ontology: mandatory -> MandatoryObligation,
    conditional -> ConditionalObligation, prima_facie -> PrimaFacieObligation,
    defeasible -> DefeasibleObligation.
    """
    mandatory = "mandatory"
    defeasible = "defeasible"
    conditional = "conditional"
    prima_facie = "prima_facie"


class ComplianceStatus(str, Enum):
    met = "met"
    unmet = "unmet"
    partial = "partial"
    unclear = "unclear"


class CandidateObligationClass(BaseCandidate):
    """A new obligation class discovered in case text.

    Field set aligned to the extraction-architecture spec (O section, 2026-06):
    obligation_type drives the subClassOf core:Obligation typing and derived_from_principle
    resolves to the O->P edge. The earlier enforcement_level (the retired modality axis),
    violation_consequences, stakeholders_affected, monitoring_criteria, and nspe_reference
    fields were dropped (all 0/59 populated, spec "Not stored").
    """
    obligation_type: Optional[ObligationType] = None
    derived_from_principle: Optional[str] = Field(
        None, description="Source principle (P->O linkage)"
    )


class ObligationIndividual(BaseIndividual):
    """A specific obligation instance in the case."""
    obligation_class: str = Field("", description="Obligation class label or URI", alias="instance_of")
    obligated_party: Optional[str] = Field(
        None, description="Who bears the obligation (Dennis: 'by whom'); resolves to the obligatedParty edge"
    )
    obligation_statement: Optional[str] = Field(
        None, description="The specific duty statement"
    )
    derived_from_principle: Optional[str] = Field(
        None, description="Principle the duty operationalizes (derivedFromPrinciple edge; the P side of R->P->O)"
    )
    case_context: Optional[str] = None
    temporal_scope: Optional[str] = Field(
        None, description="When the obligation applies (Dennis: 'when')"
    )
    compliance_status: Optional[ComplianceStatus] = None


class ObligationExtractionResult(BaseModel):
    """Top-level LLM output for obligation extraction."""
    new_obligation_classes: List[CandidateObligationClass] = Field(default_factory=list)
    obligation_individuals: List[ObligationIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# S (States) -- Contextual Grounding
# ---------------------------------------------------------------------------
# "Situational context including facts, environmental conditions, and
#  system status" (Chapter 2, Table 2.1)
# BFO: bfo:0000020 (specifically dependent continuant)
# Ontology groups: conflict (ConflictOfInterest, CompetingDuties),
#   risk (PublicSafetyAtRisk, EnvironmentalHazard),
#   competence (OutsideCompetence, QualifiedToPerform),
#   relationship (ClientRelationship, EmploymentTerminated),
#   information (ConfidentialInformation, PublicInformation),
#   emergency (EmergencySituation, CrisisConditions),
#   regulatory (RegulatoryCompliance, NonCompliant),
#   temporal (DeadlineApproaching, ExtendedTimeframe),
#   resource (ResourceConstrained, ResourceAvailable)
# Literature: Jones (moral intensity), Berreby (fluents), Almpani (Event Calculus)
# ---------------------------------------------------------------------------

class StateCategory(str, Enum):
    """The closed nine CONTENT archetypes of a state (extraction-architecture spec, S section, B1).

    A state's kind is a classification of the condition's CONTENT in the world, explicitly NOT the
    activatesObligation relation the edge layer records: a RiskState is hazard exposure, an
    EpistemicState is the agent's knowledge condition (the responsibility epistemic condition, C2),
    a ConflictOfInterestState is a clash of duties, a DisclosureState is an information-disclosure
    condition. Each archetype is subClassOf core:State; a discovered compound class chains through
    its archetype. Grounding: Berreby et al. (2017) Event-Calculus fluents, with Jones (1991) moral
    intensity carried separately as urgency_level (a state attribute), not as the typing axis.

    Replaces the earlier deontic-function framing (conflict/relationship/information): conflict ->
    conflict_of_interest, relationship is dropped, and information splits into epistemic +
    disclosure.
    """
    epistemic = "epistemic"
    risk = "risk"
    competence = "competence"
    emergency = "emergency"
    conflict_of_interest = "conflict_of_interest"
    regulatory = "regulatory"
    temporal = "temporal"
    resource = "resource"
    disclosure = "disclosure"


class PersistenceType(str, Enum):
    """Berreby et al. (2017) fluent classification."""
    inertial = "inertial"
    non_inertial = "non_inertial"


class UrgencyLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CandidateStateClass(BaseCandidate):
    """A new state class discovered in case text."""
    state_category: Optional[StateCategory] = None
    persistence_type: Optional[PersistenceType] = Field(
        PersistenceType.inertial,
        description="Berreby fluent classification"
    )
    activation_conditions: List[str] = Field(
        default_factory=list,
        description="Triggering events (Event Calculus)"
    )
    termination_conditions: List[str] = Field(
        default_factory=list,
        description="Ending conditions (Event Calculus)"
    )
    obligation_activation: List[str] = Field(
        default_factory=list,
        description="Which obligations this state activates (S->O linkage)"
    )
    action_constraints: List[str] = Field(
        default_factory=list,
        description="How this state constrains available actions (S->Cs linkage)"
    )
    principle_transformation: Optional[str] = Field(
        None,
        description="How this state transforms abstract principles into concrete obligations (S->P->O pathway)"
    )


class StateIndividual(BaseIndividual):
    """A specific state instance in the case."""
    state_class: str = Field("", description="State class label or URI", alias="instance_of")
    subject: Optional[str] = Field(
        None, description="Who/what is in this state"
    )
    active_period: Optional[str] = None
    triggering_event: Optional[str] = None
    terminated_by: Optional[str] = None
    affected_parties: List[str] = Field(default_factory=list)
    urgency_level: Optional[UrgencyLevel] = None


class StateExtractionResult(BaseModel):
    """Top-level LLM output for state extraction."""
    new_state_classes: List[CandidateStateClass] = Field(default_factory=list)
    state_individuals: List[StateIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rs (Resources) -- Contextual Grounding
# ---------------------------------------------------------------------------
# "Accumulated professional knowledge including codes, precedents, and
#  practices" (Chapter 2, Table 2.1)
# BFO: iao:0000030 (information content entity)
# Ontology: ProfessionalCode, CasePrecedent, ExpertInterpretation,
#   TechnicalStandard, LegalResource, DecisionTool, ReferenceMaterial
# Literature: McLaren (precedents), Davis & Frankel (codes), Harris et al.
# ---------------------------------------------------------------------------

class ResourceCategory(str, Enum):
    """The closed six SOURCE KINDS of a resource (extraction-architecture spec, Rs section).

    The canonical identity of a resource is its source kind; topic, who-used, and which-document
    are context, not class identity. ethical_code is typed EthicalCode subClassOf Guideline
    subClassOf Resource; the other four subClassOf Resource. professional_code was MERGED into
    ethical_code (2026-07-01): both denoted a profession's code of ethics as a document; the legacy
    value still maps to EthicalCode but the LLM is no longer offered it.
    """
    ethical_code = "ethical_code"
    technical_standard = "technical_standard"
    case_precedent = "case_precedent"
    legal_resource = "legal_resource"
    reference_material = "reference_material"


class CandidateResourceClass(BaseCandidate):
    """A new resource class discovered in case text.

    Field set aligned to the extraction-architecture spec (Rs section, 2026-06): the source kind
    (resource_category) is the canonical class identity and drives the six-kind subClassOf typing.
    The earlier authority_source, extensional_function, and usage_context class fields were dropped
    (spec "Not stored"; not carried on the Resource).
    """
    resource_category: Optional[ResourceCategory] = None


class ResourceIndividual(BaseIndividual):
    """A specific resource instance in the case.

    Field set aligned to the extraction-architecture spec (Rs section, 2026-06): document_title and
    topic are literals; used_by (the Facts-section reliance signal) resolves to availableTo and
    cited_by (the Discussion-section authority signal) resolves to citedByAgent; provision_codes
    resolve to refersToDocument nspe# IRIs for a code. The earlier created_by, version, and
    used_in_context fields were dropped, and the conflated used_by was split into used_by + cited_by.
    """
    resource_class: str = Field("", description="Resource class label or URI", alias="instance_of")
    document_title: Optional[str] = Field(
        None, description="Official document/resource name"
    )
    topic: Optional[str] = Field(
        None, description="Subject the resource addresses (proeth:topic datatype property)"
    )
    used_by: Optional[str] = Field(
        None, description="Case actor who relied on the resource (Facts signal); resolves to the availableTo edge"
    )
    cited_by: Optional[str] = Field(
        None, description="Agent who cited the resource as authority (Discussion signal); resolves to the citedByAgent edge"
    )
    provision_codes: List[str] = Field(
        default_factory=list,
        description="For a code/regulation, provision code(s) cited (e.g. 'I.1'); resolve to refersToDocument nspe# IRIs"
    )


class ResourceExtractionResult(BaseModel):
    """Top-level LLM output for resource extraction."""
    new_resource_classes: List[CandidateResourceClass] = Field(default_factory=list)
    resource_individuals: List[ResourceIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# A (Actions) -- Temporal Dynamics
# ---------------------------------------------------------------------------
# "Volitional professional interventions that carry ethical weight"
# BFO: bfo:0000015 (process)
# Ontology: CommunicationAction, PreventionAction, MaintenanceAction,
#   PerformanceAction, EvaluationAction, CollaborationAction, CreationAction,
#   MonitoringAction (+ sub-types: Decision, DisclosureAction, CompetenceAction)
# Literature: Sarmiento (volitional nature), Bonnemains (multi-framework),
#   Govindarajulu (intentional status), Allen (interval algebra)
# ---------------------------------------------------------------------------

class ActionCategory(str, Enum):
    """proethica-intermediate.ttl Action subclass hierarchy.

    First-level subclasses of proeth-core:Action.
    """
    communication = "communication"
    prevention = "prevention"
    maintenance = "maintenance"
    performance = "performance"
    evaluation = "evaluation"
    collaboration = "collaboration"
    creation = "creation"
    monitoring = "monitoring"


class CandidateActionClass(BaseCandidate):
    """A new action class discovered in case text.

    NOTE (HO-006): Step-3 temporal dynamics commits no action *class* rows
    (``storage_type='class'``) - only individuals via the LangGraph path. This
    candidate-class model is retained for API symmetry with Steps 1-2 but is not
    populated by the live temporal pass.

    Field set slimmed 2026-06-29 so the actions structured-output grammar fits the
    Anthropic compiled-grammar ceiling (the 400 "compiled grammar is too large"; see
    ``unified_dual_extractor/llm_calls.py``). The earlier volitional_nature,
    professional_context, obligations_fulfilled, causal_implications, and
    temporal_constraints fields were dropped: all are absent from the spec's Action
    "Stored" set (extraction spec A section: actions carry no subtype and the A->O
    linkage is the action-individual fulfills/violates/raises edge, not a class field),
    none are read by any emitter/edge/temporal pass as a candidate-class field (the
    rdf_converter ``obligations_fulfilled``/``professional_context`` reads are of the
    Step-3 LangGraph nested ethical_context/professional_context dicts, a different data
    structure), and all are 0-populated across the corpus (no action class rows exist).
    action_category is retained as the typing axis the commit service reads (it falls
    back to bare proeth-core:Action when absent, the spec's no-subtype outcome).
    """
    action_category: Optional[ActionCategory] = None


class ActionIndividual(BaseModel):
    """A specific action instance in the case.

    CONFORMED to the emitted vocabulary (HO-006, 2026-05-26). Step-3 temporal
    dynamics does NOT validate through this model: actions are produced by the
    LangGraph temporal pass and serialised directly to ``proeth:`` JSON-LD by
    ``app/services/temporal_dynamics/utils/rdf_converter.convert_action_to_rdf``.
    The committed JSON-LD (``temporary_rdf_storage.rdf_json_ld`` for
    ``extraction_type='temporal_dynamics_enhanced'``, ``entity_type='actions'``) is the
    canonical ground truth; this model mirrors those keys via aliases so it can
    round-trip committed output. The earlier snake_case fields (``performed_by``,
    ``temporal_interval``, ``sequence_order``, ``obligations_fulfilled`` ...) never
    matched what was emitted and were removed. The ``proeth-scenario:`` scenario-metadata
    fields were removed 2026-05-31: that narrative gloss is derivable on demand from the
    committed entities at scenario/lesson-generation time, so the extractor no longer
    produces it. See memory ``feedback_schema-vs-emitted-vocabulary``.
    """
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    # JSON-LD framing
    id: Optional[str] = Field(None, alias="@id")
    type: str = Field("proeth:Action", alias="@type")
    label: Optional[str] = Field(None, alias="rdfs:label")

    # Core descriptive fields (always emitted)
    description: Optional[str] = Field(None, alias="proeth:description")
    has_agent: Optional[str] = Field(None, alias="proeth:hasAgent")
    event_role_context: Optional[str] = Field(None, alias="proeth:eventRoleContext")
    temporal_marker: Optional[str] = Field(None, alias="proeth:temporalMarker")

    # Intention block
    has_mental_state: Optional[str] = Field(None, alias="proeth:hasMentalState")
    intended_outcome: Optional[str] = Field(None, alias="proeth:intendedOutcome")
    foreseen_unintended_effects: List[str] = Field(
        default_factory=list, alias="proeth:foreseenUnintendedEffects"
    )

    # Ethical context
    fulfills_obligation: List[str] = Field(default_factory=list, alias="proeth:fulfillsObligation")
    violates_obligation: List[str] = Field(default_factory=list, alias="proeth:violatesObligation")
    guided_by_principle: List[str] = Field(default_factory=list, alias="proeth:guidedByPrinciple")
    # has_competing_priorities (proeth:hasCompetingPriorities) was dropped from Step-3
    # extraction 2026-06-01 (no real consumer; nested object dropped at commit; tension is
    # durably captured by the defeasibility edges). See review-vs-synthesis-fields.md.

    # Professional context
    within_competence: Optional[bool] = Field(None, alias="proeth:withinCompetence")
    requires_capability: List[str] = Field(default_factory=list, alias="proeth:requiresCapability")

    # Fluent transitions + OWL-Time extent (Event Calculus)
    initiates: List[str] = Field(default_factory=list, alias="proeth:initiates")
    terminates: List[str] = Field(default_factory=list, alias="proeth:terminates")
    temporal_extent: Optional[str] = Field(None, alias="proeth:temporalExtent")

    # Added by the wired temporal_sequence / obligation apply-hooks at commit time
    raises_obligation: List[str] = Field(default_factory=list, alias="proeth:raisesObligation")
    temporal_sequence: Optional[int] = Field(None, alias="proeth:temporalSequence")


class ActionExtractionResult(BaseModel):
    """Top-level LLM output for action extraction."""
    new_action_classes: List[CandidateActionClass] = Field(default_factory=list)
    action_individuals: List[ActionIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# E (Events) -- Temporal Dynamics
# ---------------------------------------------------------------------------
# "Occurrences originating outside agent control that affect evaluation"
# BFO: bfo:0000015 (process)
# Ontology: CrisisEvent, ComplianceEvent, ConflictEvent, ProjectEvent,
#   SafetyEvent, EvaluationEvent, DiscoveryEvent, ChangeEvent
#   (+ sub-types: Violation, EmergencyEvent, DeadlineEvent, SafetyIncident)
# Literature: Berreby (automatic events, Event Calculus), Arkin (emergency
#   overrides), Almpani (obligation dynamics)
# ---------------------------------------------------------------------------

class EventCategory(str, Enum):
    """proethica-intermediate.ttl Event subclass hierarchy.

    First-level subclasses of proeth-core:Event.
    """
    crisis = "crisis"
    compliance = "compliance"
    conflict = "conflict"
    project = "project"
    safety = "safety"
    evaluation = "evaluation"
    discovery = "discovery"
    change = "change"


class CausalPosition(str, Enum):
    """Position in the causal chain (orthogonal to event category)."""
    trigger = "trigger"
    intermediate = "intermediate"
    outcome = "outcome"


class CandidateEventClass(BaseCandidate):
    """A new event class discovered in case text.

    NOTE (HO-006): As with :class:`CandidateActionClass`, Step-3 commits no event
    *class* rows; the LangGraph temporal pass emits individuals only. Retained for
    symmetry, not populated by the live pass.

    Field set aligned to the extraction-architecture spec (E section, 2026-06): events are
    origin-typed light individuals and this pass mints no event classes, so the earlier
    event_category, automatic_nature, ethical_salience, causal_position, constraint_activation,
    obligation_transformation, and state_transitions fields were dropped (spec "Not stored").
    """
    pass


class EventIndividual(BaseModel):
    """A specific event instance in the case.

    CONFORMED to the emitted vocabulary (HO-006, 2026-05-26). Like
    :class:`ActionIndividual`, Step-3 events are serialised directly to JSON-LD by
    ``rdf_converter.build_event_rdf``, NOT validated through this model. The committed
    JSON-LD (``temporary_rdf_storage`` ``temporal_dynamics_enhanced`` /
    ``entity_type='events'``) is canonical; this model mirrors those keys via aliases.
    The earlier snake_case fields (``occurred_to``, ``temporal_interval``,
    ``obligations_triggered`` ...) never matched the emitted output and were removed.
    See memory ``feedback_schema-vs-emitted-vocabulary``.
    """
    model_config = ConfigDict(populate_by_name=True, extra='allow')

    # JSON-LD framing
    id: Optional[str] = Field(None, alias="@id")
    type: str = Field("proeth:Event", alias="@type")
    label: Optional[str] = Field(None, alias="rdfs:label")

    # Core descriptive fields
    description: Optional[str] = Field(None, alias="proeth:description")
    temporal_marker: Optional[str] = Field(None, alias="proeth:temporalMarker")

    # Classification (extraction-architecture spec, E section, 2026-06). eventType is the
    # load-bearing ORIGIN signal and drives the three-way subClassOf typing: outcome ->
    # AgentCausedEvent (agent-caused), exogenous -> ExogenousEvent (external), automatic ->
    # AutomaticEvent (precondition-triggered) (Berreby/Sarmiento). The earlier severity field
    # was dropped (spec: severity is dropped for events; emergency salience is structural, via
    # the RiskState/EmergencyState an emergency event initiates).
    event_type: Optional[str] = Field(None, alias="proeth:eventType")

    # State change. The earlier causes_state_change prose was dropped (spec "Not stored"; folded
    # into the description). An event activates a constraint or makes an obligation apply only via
    # the State it initiates (the Event-Calculus path State proeth-core:activatesConstraint /
    # activatesObligation, materialised by fluent_edges.py + state_edges.py).
    caused_by_action: Optional[str] = Field(None, alias="proeth:causedByAction")

    # Fluent transitions + OWL-Time extent (Event Calculus)
    initiates: List[str] = Field(default_factory=list, alias="proeth:initiates")
    terminates: List[str] = Field(default_factory=list, alias="proeth:terminates")
    temporal_extent: Optional[str] = Field(None, alias="proeth:temporalExtent")

    # Added by the wired temporal_sequence apply-hook at commit time
    temporal_sequence: Optional[int] = Field(None, alias="proeth:temporalSequence")


class EventExtractionResult(BaseModel):
    """Top-level LLM output for event extraction."""
    new_event_classes: List[CandidateEventClass] = Field(default_factory=list)
    event_individuals: List[EventIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ca (Capabilities) -- Normative Structure
# ---------------------------------------------------------------------------
# "Competencies spanning norm competence, situational awareness, learning,
#  and explanation abilities" (Chapter 2, Table 2.1)
# BFO: bfo:0000016 (disposition)
# Ontology groups:
#   norm_management: NormCompetence, ConflictResolution
#   awareness: SituationalAwareness, EthicalPerception
#   learning: EthicalLearning, PrincipleRefinement
#   reasoning: EthicalReasoning, CausalReasoning, TemporalReasoning
#   communication: ExplanationGeneration, JustificationCapability,
#     ResponsibilityDocumentation
#   domain_specific: DomainExpertise, ProfessionalCompetence
#   retrieval: PrecedentRetrieval
# Literature: Narvaez & Rest (Four Component Model), Tolmeijer et al.
#   (four requirements), Berreby (Action Model), Epstein (domain-specific)
# ---------------------------------------------------------------------------

class CapabilityCategory(str, Enum):
    """proethica-intermediate.ttl Capability groupings.

    Tolmeijer et al. (2021) capability requirements, aligned to
    ontology comment-section groups.
    """
    norm_management = "norm_management"
    awareness = "awareness"
    learning = "learning"
    reasoning = "reasoning"
    communication = "communication"
    domain_specific = "domain_specific"
    retrieval = "retrieval"


class SkillLevel(str, Enum):
    basic = "basic"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


class CandidateCapabilityClass(BaseCandidate):
    """A new capability class discovered in case text.

    Field set aligned to the extraction-architecture spec (Ca section, 2026-06): the canonical
    competence kind (BaseCandidate.label) drives the subClassOf typing, and required_for_obligations
    is the Ca->O capacity linkage that resolves to the requiresCapability edge (Obligation->Capability).
    The earlier capability_category, enables_actions, skill_level, and domain_specificity fields were
    dropped (spec "Not stored"). Only a competence the agent possesses or exercises is a Capability;
    a lacked competence is dropped here and captured downstream as a CompetenceGapState.
    """
    required_for_obligations: List[str] = Field(
        default_factory=list,
        description="Obligations requiring this capability (Ca->O linkage; resolves to requiresCapability)"
    )


class CapabilityIndividual(BaseIndividual):
    """A specific capability instance in the case.

    Field set aligned to the extraction-architecture spec (Ca section, 2026-06): possessed_by
    resolves to the possessedBy edge and case_context is the grounding-context literal. The earlier
    capability_statement, demonstrated_through, and proficiency_level fields were dropped (spec
    "Not stored").
    """
    capability_class: str = Field("", description="Capability class label or URI", alias="instance_of")
    possessed_by: Optional[str] = Field(
        None, description="Who possesses this capability; resolves to the possessedBy edge"
    )
    case_context: Optional[str] = Field(
        None, description="Grounding-context literal: how this capability manifests in the case"
    )


class CapabilityExtractionResult(BaseModel):
    """Top-level LLM output for capability extraction."""
    new_capability_classes: List[CandidateCapabilityClass] = Field(default_factory=list)
    capability_individuals: List[CapabilityIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cs (Constraints) -- Normative Structure
# ---------------------------------------------------------------------------
# "Inviolable boundaries that cannot be crossed regardless of benefits"
# BFO: iao:0000033 (directive information entity)
# Ontology boundary types: LegalConstraint, RegulatoryConstraint,
#   ResourceConstraint, CompetenceConstraint, JurisdictionalConstraint,
#   ProceduralConstraint, SafetyConstraint, ConfidentialityConstraint,
#   EthicalConstraint, TemporalConstraint, PriorityConstraint
# Ontology defeasibility types (orthogonal): DefeasibleConstraint,
#   InviolableConstraint (mapped via flexibility field)
# Literature: Ganascia (defeasible logic), Dennis et al. (hierarchical
#   management), Arkin (behavioral constraints)
#
# STATUS (verified 2026-05-24): `flexibility` is EXTRACTED and STORED but
# NOT a live reasoning input. Class rows in temporary_rdf_storage carry
# varied values (~584 hard / 373 soft / 1 negotiable), and the
# hard->InviolableConstraint, soft/negotiable->DefeasibleConstraint mapping
# exists in CATEGORY_TO_ONTOLOGY_IRI and is wired into the commit config
# (ontserve_commit_service.py _CONCEPT_CATEGORY_CONFIG). However, zero
# committed proethica-case-*.ttl files actually carry Inviolable/
# DefeasibleConstraint, and no retrieval, scoring, precedent, or
# defeasibility-reasoning code reads the value or branches on it. Live
# defeasibility reasoning is carried at the OBLIGATION layer instead
# (proethica-core competesWith / prevailsOver / defeasibleUnder edges).
# Do not treat constraint flexibility as a reasoning signal without first
# closing the commit-emission gap and re-validating the corpus with Pellet.
# ---------------------------------------------------------------------------

class ConstraintType(str, Enum):
    """proethica-intermediate.ttl Constraint subclass hierarchy.

    Boundary-type classification. Defeasibility is captured separately
    by the flexibility field (maps to DefeasibleConstraint / InviolableConstraint).
    """
    legal = "legal"
    regulatory = "regulatory"
    resource = "resource"
    competence = "competence"
    jurisdictional = "jurisdictional"
    procedural = "procedural"
    safety = "safety"
    confidentiality = "confidentiality"
    ethical = "ethical"
    temporal = "temporal"
    priority = "priority"


class Flexibility(str, Enum):
    """Ganascia (2007) defeasibility spectrum.

    Maps to ontology: hard -> InviolableConstraint,
    soft/negotiable -> DefeasibleConstraint.
    """
    hard = "hard"
    soft = "soft"
    negotiable = "negotiable"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CandidateConstraintClass(BaseCandidate):
    """A new constraint class discovered in case text.

    Field set aligned to the extraction-architecture spec (Cs section, 2026-06): constraint_type is
    the controlled boundary type and drives the subClassOf typing. The earlier flexibility (a dead
    shadow of the obligation-layer defeasibility edges), violation_impact, mitigation_strategies, and
    affected_stakeholders fields were dropped (spec "Not stored").
    """
    constraint_type: Optional[ConstraintType] = None


class ConstraintIndividual(BaseIndividual):
    """A specific constraint instance in the case.

    Field set aligned to the extraction-architecture spec (Cs section, 2026-06): constraint_statement
    is the prohibition (skos:definition), applicability_condition is the Dennis complete-specification
    condition, severity is a genuine attribute, constrained_entity resolves to the constrainedEntity
    edge, and source resolves to establishedBy.
    """
    constraint_class: str = Field("", description="Constraint class label or URI", alias="instance_of")
    constrained_entity: Optional[str] = Field(
        None, description="The agent whose conduct is limited; resolves to the constrainedEntity edge"
    )
    constraint_statement: Optional[str] = Field(
        None, description="The prohibition (the operative 'must not' clause); becomes skos:definition"
    )
    applicability_condition: Optional[str] = Field(
        None, description="Temporal and contextual circumstances under which the prohibition applies (Dennis)"
    )
    source: Optional[str] = Field(
        None, description="Provision or authority establishing the prohibition; resolves to establishedBy"
    )
    temporal_scope: Optional[str] = None
    severity: Optional[Severity] = None
    case_context: Optional[str] = None


class ConstraintExtractionResult(BaseModel):
    """Top-level LLM output for constraint extraction."""
    new_constraint_classes: List[CandidateConstraintClass] = Field(default_factory=list)
    constraint_individuals: List[ConstraintIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Defeasibility edges (proethica-core v2.5.0 object properties)
# ---------------------------------------------------------------------------
# Object-property triples between extracted Obligation and State individuals.
# Unlike the nine concept extractors, the defeasibility extractor does not
# emit individuals -- it emits IRI-valued edges that participate in the
# D-tuple competition pattern (KI2026 Fig. 1).
#
# Property axioms (from OntServe/ontologies/proethica-core.ttl):
#   competesWith     -- symmetric, Obligation <-> Obligation
#   prevailsOver     -- directed,  Obligation -> Obligation (winner -> loser)
#   defeasibleUnder  -- directed,  Obligation -> State (the defeating context)
# ---------------------------------------------------------------------------

class DefeasibilityEdge(BaseModel):
    """A single defeasibility edge proposed by the LLM.

    The Literal types prevent drift on the predicate (only the three v2.5.0
    object properties are valid) and on the source_field (which keys
    PROV-O provenance back to the originating narrative datatype).
    Symmetric closure of competesWith is added in code, not by the LLM
    (see DefeasibilityEdgeExtractor.extract).
    """
    model_config = ConfigDict(populate_by_name=True)

    predicate: Literal["competesWith", "prevailsOver", "defeasibleUnder"]
    subject_iri: str = Field(
        ..., description="Full IRI of the subject Obligation individual"
    )
    object_iri: str = Field(
        ...,
        description=(
            "Full IRI of the object: an Obligation for competesWith/prevailsOver, "
            "a State for defeasibleUnder"
        ),
    )
    source_field: Literal[
        "tensionresolution",
        "balancingwith",
        "constraintstatement",
        "concreteexpression",
        "interpretation",
        "obligationstatement",
        "casecontext",
    ] = Field(
        ...,
        description=(
            "Datatype field whose narrative supplied evidence for the edge. "
            "Used as PROV-O provenance key on the emitted triple."
        ),
    )
    source_text: str = Field(
        ...,
        description="Verbatim quote from the source_field that justifies the edge",
    )
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    source_individual_iri: Optional[str] = Field(
        None,
        description=(
            "IRI of the individual whose datatype field supplied source_text. "
            "May differ from subject_iri (e.g. a Principle's interpretation "
            "field justifying an Obligation-Obligation edge)."
        ),
    )


class DefeasibilityEdgeExtractionResult(BaseModel):
    """Top-level LLM output for defeasibility edge extraction."""
    edges: List[DefeasibilityEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Combined Actions & Events (Temporal Dynamics pass)
# ---------------------------------------------------------------------------

class TemporalDynamicsExtractionResult(BaseModel):
    """Combined extraction result for the temporal dynamics pass."""
    new_action_classes: List[CandidateActionClass] = Field(default_factory=list)
    action_individuals: List[ActionIndividual] = Field(default_factory=list)
    new_event_classes: List[CandidateEventClass] = Field(default_factory=list)
    event_individuals: List[EventIndividual] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ontology IRI Mapping
# ---------------------------------------------------------------------------
# Maps category enum values to their corresponding ontology subclass IRIs.
# Used by the commit service to set rdfs:subClassOf when creating new classes.
# For concepts with multi-axis classification (e.g., obligations have both
# domain type and deontic modality), each axis maps independently.

CATEGORY_TO_ONTOLOGY_IRI: Dict[str, Dict[str, str]] = {
    # R: the four Kong RELATIONAL archetypes (extraction-architecture spec, R1). These are the
    # role_category -> subClassOf/rdf:type targets used only as the FALLBACK when no actor edge is
    # extracted; the relational archetype is otherwise materialized edge-primary from the actor edge at
    # commit (the edge wins on conflict). participant/stakeholder were removed (they are occupational, not
    # relational; the occupational axis is carried by role_kind -> ProfessionalRole/ParticipantRole).
    'roles': {
        'provider_client': f'{INTERMEDIATE_NS}ProviderClientRole',
        'professional_peer': f'{INTERMEDIATE_NS}ProfessionalPeerRole',
        'employer_relationship': f'{INTERMEDIATE_NS}EmployerRelationshipRole',
        'public_responsibility': f'{INTERMEDIATE_NS}PublicResponsibilityRole',
    },
    # P: Principle categories -> intermediate subclass IRIs
    'principles': {
        'fundamental_ethical': f'{INTERMEDIATE_NS}FundamentalEthicalPrinciple',
        'professional_virtue': f'{INTERMEDIATE_NS}ProfessionalVirtuePrinciple',
        'relational': f'{INTERMEDIATE_NS}RelationalPrinciple',
        'domain_specific': f'{INTERMEDIATE_NS}DomainSpecificPrinciple',
    },
    # O: Obligation domain types -> intermediate subclass IRIs
    'obligations': {
        'disclosure': f'{INTERMEDIATE_NS}DisclosureObligation',
        'safety': f'{INTERMEDIATE_NS}SafetyObligation',
        'competence': f'{INTERMEDIATE_NS}CompetenceObligation',
        'confidentiality': f'{INTERMEDIATE_NS}ConfidentialityObligation',
        'reporting': f'{INTERMEDIATE_NS}ReportingObligation',
        'collegial': f'{INTERMEDIATE_NS}CollegialObligation',
        'legal': f'{INTERMEDIATE_NS}LegalObligation',
        'ethical': f'{INTERMEDIATE_NS}EthicalObligation',
    },
    # O: Obligation deontic modality -> intermediate subclass IRIs
    # (orthogonal axis, applied in addition to domain type)
    # S: State categories -> base class (individual states are specific subclasses)
    # The match_decision field handles mapping to specific state subclasses
    # (ConflictOfInterest, PublicSafetyAtRisk, etc.)
    'states': {
        # The nine CONTENT state archetypes (decision B1, 2026-06-28): a state's kind is its content,
        # NOT the activatesObligation relation. Keys match StateCategory; all subClassOf proeth-core:State.
        'epistemic': f'{INTERMEDIATE_NS}EpistemicState',
        'risk': f'{INTERMEDIATE_NS}RiskState',
        'competence': f'{INTERMEDIATE_NS}CompetenceState',
        'emergency': f'{INTERMEDIATE_NS}EmergencyState',
        'conflict_of_interest': f'{INTERMEDIATE_NS}ConflictOfInterestState',
        'regulatory': f'{INTERMEDIATE_NS}RegulatoryState',
        'temporal': f'{INTERMEDIATE_NS}TemporalState',
        'resource': f'{INTERMEDIATE_NS}ResourceState',
        'disclosure': f'{INTERMEDIATE_NS}DisclosureState',
    },
    # Rs: the six closed source kinds (spec, 2026-06-28); ethical_code added, expert_interpretation +
    # decision_tool retired. EthicalCode subClassOf Guideline subClassOf Resource.
    'resources': {
        'professional_code': f'{INTERMEDIATE_NS}EthicalCode',  # legacy alias: merged into EthicalCode 2026-07-01
        'technical_standard': f'{INTERMEDIATE_NS}TechnicalStandard',
        'case_precedent': f'{INTERMEDIATE_NS}CasePrecedent',
        'legal_resource': f'{INTERMEDIATE_NS}LegalResource',
        'reference_material': f'{INTERMEDIATE_NS}ReferenceMaterial',
        'ethical_code': f'{INTERMEDIATE_NS}EthicalCode',
    },
    # A: Action categories -> intermediate subclass IRIs
    'actions': {
        'communication': f'{INTERMEDIATE_NS}CommunicationAction',
        'prevention': f'{INTERMEDIATE_NS}PreventionAction',
        'maintenance': f'{INTERMEDIATE_NS}MaintenanceAction',
        'performance': f'{INTERMEDIATE_NS}PerformanceAction',
        'evaluation': f'{INTERMEDIATE_NS}EvaluationAction',
        'collaboration': f'{INTERMEDIATE_NS}CollaborationAction',
        'creation': f'{INTERMEDIATE_NS}CreationAction',
        'monitoring': f'{INTERMEDIATE_NS}MonitoringAction',
    },
    # E: Event categories -> intermediate subclass IRIs
    'events': {
        'crisis': f'{INTERMEDIATE_NS}CrisisEvent',
        'compliance': f'{INTERMEDIATE_NS}ComplianceEvent',
        'conflict': f'{INTERMEDIATE_NS}ConflictEvent',
        'project': f'{INTERMEDIATE_NS}ProjectEvent',
        'safety': f'{INTERMEDIATE_NS}SafetyEvent',
        'evaluation': f'{INTERMEDIATE_NS}EvaluationEvent',
        'discovery': f'{INTERMEDIATE_NS}DiscoveryEvent',
        'change': f'{INTERMEDIATE_NS}ChangeEvent',
    },
    # Ca: Capability categories -> base class (individual capabilities
    # are specific subclasses resolved via match_decision)
    'capabilities': {
        'norm_management': f'{CORE_NS}Capability',
        'awareness': f'{CORE_NS}Capability',
        'learning': f'{CORE_NS}Capability',
        'reasoning': f'{CORE_NS}Capability',
        'communication': f'{CORE_NS}Capability',
        'domain_specific': f'{CORE_NS}Capability',
        'retrieval': f'{CORE_NS}Capability',
    },
    # Cs: Constraint boundary types -> intermediate subclass IRIs
    'constraints': {
        'legal': f'{INTERMEDIATE_NS}LegalConstraint',
        'regulatory': f'{INTERMEDIATE_NS}RegulatoryConstraint',
        'resource': f'{INTERMEDIATE_NS}ResourceConstraint',
        'competence': f'{INTERMEDIATE_NS}CompetenceConstraint',
        'jurisdictional': f'{INTERMEDIATE_NS}JurisdictionalConstraint',
        'procedural': f'{INTERMEDIATE_NS}ProceduralConstraint',
        'safety': f'{INTERMEDIATE_NS}SafetyConstraint',
        'confidentiality': f'{INTERMEDIATE_NS}ConfidentialityConstraint',
        'ethical': f'{INTERMEDIATE_NS}EthicalConstraint',
        'temporal': f'{INTERMEDIATE_NS}TemporalConstraint',
        'priority': f'{INTERMEDIATE_NS}PriorityConstraint',
    },
    # Cs: Constraint defeasibility -> intermediate subclass IRIs
    # (orthogonal axis, applied in addition to boundary type)
}

# Specific ontology state subclasses grouped by category.
# Used when the commit service needs to suggest a more specific subclass
# based on the category enum. The LLM's match_decision takes priority.
STATE_SUBCLASSES: Dict[str, List[str]] = {
    'conflict': [
        f'{INTERMEDIATE_NS}ConflictOfInterest',
        f'{INTERMEDIATE_NS}CompetingDuties',
    ],
    'risk': [
        f'{INTERMEDIATE_NS}PublicSafetyAtRisk',
        f'{INTERMEDIATE_NS}EnvironmentalHazard',
    ],
    'competence': [
        f'{INTERMEDIATE_NS}OutsideCompetence',
        f'{INTERMEDIATE_NS}QualifiedToPerform',
    ],
    'relationship': [
        f'{INTERMEDIATE_NS}ClientRelationship',
        f'{INTERMEDIATE_NS}EmploymentTerminated',
    ],
    'information': [
        f'{INTERMEDIATE_NS}ConfidentialInformation',
        f'{INTERMEDIATE_NS}PublicInformation',
    ],
    'emergency': [
        f'{INTERMEDIATE_NS}EmergencySituation',
        f'{INTERMEDIATE_NS}CrisisConditions',
    ],
    'regulatory': [
        f'{INTERMEDIATE_NS}RegulatoryCompliance',
        f'{INTERMEDIATE_NS}NonCompliant',
    ],
    'temporal': [
        f'{INTERMEDIATE_NS}DeadlineApproaching',
        f'{INTERMEDIATE_NS}ExtendedTimeframe',
    ],
    'resource': [
        f'{INTERMEDIATE_NS}ResourceConstrained',
        f'{INTERMEDIATE_NS}ResourceAvailable',
    ],
}

# Specific ontology capability subclasses grouped by category.
CAPABILITY_SUBCLASSES: Dict[str, List[str]] = {
    'norm_management': [
        f'{INTERMEDIATE_NS}NormCompetence',
        f'{INTERMEDIATE_NS}ConflictResolution',
    ],
    'awareness': [
        f'{INTERMEDIATE_NS}SituationalAwareness',
        f'{INTERMEDIATE_NS}EthicalPerception',
    ],
    'learning': [
        f'{INTERMEDIATE_NS}EthicalLearning',
        f'{INTERMEDIATE_NS}PrincipleRefinement',
    ],
    'reasoning': [
        f'{INTERMEDIATE_NS}EthicalReasoning',
        f'{INTERMEDIATE_NS}CausalReasoning',
        f'{INTERMEDIATE_NS}TemporalReasoning',
    ],
    'communication': [
        f'{INTERMEDIATE_NS}ExplanationGeneration',
        f'{INTERMEDIATE_NS}JustificationCapability',
        f'{INTERMEDIATE_NS}ResponsibilityDocumentation',
    ],
    'domain_specific': [
        f'{INTERMEDIATE_NS}DomainExpertise',
        f'{INTERMEDIATE_NS}ProfessionalCompetence',
    ],
    'retrieval': [
        f'{INTERMEDIATE_NS}PrecedentRetrieval',
    ],
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Maps concept name to its ExtractionResult model class.
CONCEPT_SCHEMAS: Dict[str, type[BaseModel]] = {
    'roles': RoleExtractionResult,
    'principles': PrincipleExtractionResult,
    'obligations': ObligationExtractionResult,
    'states': StateExtractionResult,
    'resources': ResourceExtractionResult,
    'actions': ActionExtractionResult,
    'events': EventExtractionResult,
    'capabilities': CapabilityExtractionResult,
    'constraints': ConstraintExtractionResult,
    'actions_events': TemporalDynamicsExtractionResult,
}

#: Maps concept name to its (CandidateClass, Individual) model pair.
CONCEPT_MODELS: Dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    'roles': (CandidateRoleClass, RoleIndividual),
    'principles': (CandidatePrincipleClass, PrincipleIndividual),
    'obligations': (CandidateObligationClass, ObligationIndividual),
    'states': (CandidateStateClass, StateIndividual),
    'resources': (CandidateResourceClass, ResourceIndividual),
    'actions': (CandidateActionClass, ActionIndividual),
    'events': (CandidateEventClass, EventIndividual),
    'capabilities': (CandidateCapabilityClass, CapabilityIndividual),
    'constraints': (CandidateConstraintClass, ConstraintIndividual),
}

# ---------------------------------------------------------------------------
# Structured-output schema cleaning
# ---------------------------------------------------------------------------
# Anthropic structured outputs (output_config.format = json_schema) constrains
# the model so it cannot emit unparseable JSON, but the grammar accepts only a
# subset of JSON Schema. model_json_schema() emits several keywords the grammar
# rejects: Pydantic Field constraints (ge/le -> minimum/maximum, max_length ->
# maxLength, ...) and the implicit additionalProperties. to_structured_output_schema
# rewrites a model's emitted schema into the accepted subset so it can be passed
# as output_config.format.schema. $defs/$ref, enum, const, anyOf/allOf/oneOf, and
# string format are supported and are preserved unchanged.

#: JSON Schema constraint keywords the structured-outputs grammar does not accept.
_STRUCTURED_OUTPUT_UNSUPPORTED_KEYS = frozenset({
    'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf',
    'minLength', 'maxLength', 'pattern',
    'minItems', 'maxItems',
})

#: Schema keys whose values are themselves schema nodes (or maps/lists of them)
#: and must be walked recursively.
_STRUCTURED_OUTPUT_MAP_KEYS = ('properties', '$defs', 'definitions', 'patternProperties')
_STRUCTURED_OUTPUT_LIST_KEYS = ('anyOf', 'allOf', 'oneOf', 'prefixItems')
_STRUCTURED_OUTPUT_NODE_KEYS = ('items', 'additionalProperties', 'not')


def _clean_structured_output_node(node: Any) -> Any:
    """Recursively strip unsupported constraints and enforce object closure.

    Drops every key in _STRUCTURED_OUTPUT_UNSUPPORTED_KEYS, descends into
    $defs/properties/items/anyOf/allOf/oneOf, and on every object node (``type``
    == ``object`` or a node carrying ``properties``) sets ``additionalProperties``
    to ``False`` and lists every property in ``required``. The Anthropic grammar
    is OpenAI-style strict: an object's ``required`` must name all of its
    properties (verified empirically against the API, 2026-06-29). Pydantic
    encodes ``Optional`` fields as ``anyOf[..., {"type": "null"}]``, so requiring
    them is safe -- the value may still be null. $ref/enum/const/format/
    description/title are preserved.
    """
    if isinstance(node, list):
        return [_clean_structured_output_node(child) for child in node]
    if not isinstance(node, dict):
        return node

    cleaned: Dict[str, Any] = {}
    for key, value in node.items():
        if key in _STRUCTURED_OUTPUT_UNSUPPORTED_KEYS:
            continue
        if key in _STRUCTURED_OUTPUT_MAP_KEYS and isinstance(value, dict):
            cleaned[key] = {
                name: _clean_structured_output_node(sub)
                for name, sub in value.items()
            }
        elif key in _STRUCTURED_OUTPUT_LIST_KEYS and isinstance(value, list):
            cleaned[key] = [_clean_structured_output_node(sub) for sub in value]
        elif key in _STRUCTURED_OUTPUT_NODE_KEYS and isinstance(value, (dict, list)):
            cleaned[key] = _clean_structured_output_node(value)
        else:
            cleaned[key] = value

    is_object = cleaned.get('type') == 'object' or 'properties' in cleaned
    if is_object:
        cleaned['additionalProperties'] = False
        cleaned['required'] = list(cleaned.get('properties', {}).keys())

    return cleaned


def to_structured_output_schema(model: type[BaseModel]) -> Dict[str, Any]:
    """Return ``model.model_json_schema()`` rewritten for Anthropic structured outputs.

    The returned dict is a deep copy with unsupported numeric/string/array
    constraints removed and ``additionalProperties: false`` + all-properties-
    ``required`` set on every object node, ready to pass as the schema in
    ``output_config={"format": {"type": "json_schema", "schema": ...}}``.
    """
    raw = copy.deepcopy(model.model_json_schema())
    return _clean_structured_output_node(raw)


#: D-Tuple extraction step groupings.
EXTRACTION_STEPS = {
    1: ['roles', 'states', 'resources'],       # Contextual Grounding
    2: ['principles', 'obligations', 'constraints', 'capabilities'],  # Normative Structure
    3: ['actions', 'events'],                   # Temporal Dynamics
}

#: Maps concept name to its extraction_type string for temporary_rdf_storage.
CONCEPT_EXTRACTION_TYPES: Dict[str, str] = {
    'roles': 'roles',
    'principles': 'principles',
    'obligations': 'obligations',
    'states': 'states',
    'resources': 'resources',
    'actions': 'temporal_dynamics_enhanced',
    'events': 'temporal_dynamics_enhanced',
    'capabilities': 'capabilities',
    'constraints': 'constraints',
}


# ---------------------------------------------------------------------------
# Temporal sequencing
#
# Step-3 emits Action and Event individuals in extractor-pass order (all
# Actions, then all Events) which is non-chronological. This schema lets a
# follow-on LLM pass return a chronological permutation of the case's
# Action/Event IRIs; the pipeline writes the permutation index back to each
# row's rdf_json_ld as `proeth:temporalSequence`. The view layer sorts on
# that field. Returning a list (rather than per-IRI integers) makes
# validation trivial (set-equality with the input IRI list) and prevents
# the LLM from emitting non-permutations.
# ---------------------------------------------------------------------------

class TemporalSequenceResult(BaseModel):
    """LLM output for a single case's chronological ordering pass.

    `ordered_iris` must be a permutation of the case's Action+Event IRIs.
    The pipeline rejects responses that miss or duplicate IRIs.
    """
    model_config = ConfigDict(populate_by_name=True)

    ordered_iris: List[str] = Field(
        ...,
        description=(
            "Action and Event IRIs in chronological order, earliest first. "
            "Must include every IRI from the input list exactly once."
        ),
    )
    rationale: Optional[str] = Field(
        None,
        description=(
            "Brief free-text explanation of the chosen ordering. Optional; "
            "kept for audit but not consumed by the pipeline."
        ),
    )


# ---------------------------------------------------------------------------
# Obligation engagement classification
#
# Step-3 emits two obligation lists per Action: fulfillsObligation and
# violatesObligation. In practice the LLM often double-attributes the same
# obligation: at the upstream choice (the moment of choice raises the
# concern) AND at the downstream resolution (the review/submission
# fulfills or violates it). Rendering both as fulfills/violates produces
# contradictory pairs (same obligation green on one row, red on the next).
#
# This pass reclassifies the existing pool of fulfills+violates into three
# buckets per Action: fulfills, violates, raises. The union must equal the
# input pool exactly (no obligations invented or dropped). The pipeline
# writes back proeth:raisesObligation alongside the existing fulfills and
# violates fields, with the upstream-only obligations migrated out of
# fulfills/violates and into raises.
# ---------------------------------------------------------------------------

class PerActionEngagement(BaseModel):
    """Reclassified obligation lists for a single Action."""
    model_config = ConfigDict(populate_by_name=True)

    action_iri: str = Field(..., description="IRI of the Action being reclassified")
    fulfills: List[str] = Field(
        default_factory=list,
        description=(
            "Obligations that this action directly satisfies. Must be a "
            "subset of the action's input fulfills+violates pool."
        ),
    )
    violates: List[str] = Field(
        default_factory=list,
        description=(
            "Obligations that this action directly breaches. Must be a "
            "subset of the action's input fulfills+violates pool."
        ),
    )
    raises: List[str] = Field(
        default_factory=list,
        description=(
            "Obligations that this action puts in play but does not itself "
            "resolve; resolution happens at a downstream action. Must be "
            "a subset of the action's input fulfills+violates pool."
        ),
    )


class ObligationEngagementResult(BaseModel):
    """LLM output for a single case's obligation-engagement pass."""
    model_config = ConfigDict(populate_by_name=True)

    actions: List[PerActionEngagement] = Field(
        ...,
        description=(
            "One entry per Action in the case (Events are skipped — they "
            "do not carry fulfills/violates). The action_iri must be "
            "present in the input list exactly once."
        ),
    )
    rationale: Optional[str] = Field(
        None,
        description="Brief free-text summary; not consumed by the pipeline.",
    )


# ---------------------------------------------------------------------------
# Board-conclusion extraction
#
# Some BER opinions roll multiple board-question rulings into one combined
# Discussion paragraph. The original extraction pipeline often captured
# only the last per-question conclusion (or one combined block), leaving
# other board questions without an extracted Board ruling. This pass
# generates one Conclusion per missing board Question, grounded in the
# Discussion text. Output is constrained to the question numbers requested.
# ---------------------------------------------------------------------------

class BoardConclusionForQuestion(BaseModel):
    """One board conclusion paired to one board question."""
    model_config = ConfigDict(populate_by_name=True)

    question_number: int = Field(
        ...,
        description="Integer question number (e.g., 1 for Question_1).",
    )
    conclusion_text: str = Field(
        ...,
        description=(
            "The Board's ruling on this question, paraphrased from the "
            "Discussion section. One to three sentences. State only the "
            "Board's position, not analytical commentary."
        ),
    )
    cited_provisions: List[str] = Field(
        default_factory=list,
        description=(
            "Code provisions the Board cites in support of this ruling "
            "(e.g., 'I.1', 'II.2.b'). Empty list when none are explicit."
        ),
    )


class BoardConclusionExtractionResult(BaseModel):
    """LLM output for a per-case board-conclusion gap-fill pass."""
    model_config = ConfigDict(populate_by_name=True)

    conclusions: List[BoardConclusionForQuestion] = Field(
        ...,
        description=(
            "One conclusion per requested question number. Length must "
            "equal the input gap list."
        ),
    )
