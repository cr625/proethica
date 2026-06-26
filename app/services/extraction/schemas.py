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
    """proethica-intermediate.ttl Role subclass hierarchy.

    Kong et al. (2020) identity role categories (professional roles)
    plus participant/stakeholder distinction.
    """
    provider_client = "provider_client"
    professional_peer = "professional_peer"
    employer_relationship = "employer_relationship"
    public_responsibility = "public_responsibility"
    participant = "participant"
    stakeholder = "stakeholder"


class CandidateRoleClass(BaseCandidate):
    """A new role class discovered in case text."""
    role_category: Optional[RoleCategory] = None
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
    generated_obligations: List[str] = Field(
        default_factory=list,
        description="Specific duties this role creates (hasObligation -> Obligation; professional roles)")
    adheres_to_principles: List[str] = Field(
        default_factory=list,
        description="Principles this role serves/adheres to (adheresToPrinciple -> Principle; the P side "
                    "of R->P->O, sibling of generated_obligations; professional roles)")
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
        None, description="Kong framework category for this individual"
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
    # Role-individual normative fields (Chapter 3, Section 3.3.1). Restored
    # 2026-06-22 for dissertation fidelity. The role->obligation substance is
    # also materialized as first-class R->P->O edges (hasObligation); these
    # capture the per-individual view the chapter describes.
    active_obligations: List[str] = Field(
        default_factory=list,
        description="Obligations that apply to this individual given the role")
    ethical_tensions: List[str] = Field(
        default_factory=list,
        description="Tensions arising when this individual's role obligations conflict")
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
    """A new principle class discovered in case text."""
    principle_category: Optional[PrincipleCategory] = None
    abstract_nature: Optional[str] = Field(
        None, description="Ethical foundation (McLaren open-textured terms)"
    )
    extensional_examples: List[str] = Field(
        default_factory=list,
        description="Concrete application examples (McLaren extensional definition)"
    )
    value_basis: Optional[str] = Field(
        None, description="Core moral value grounding the principle"
    )
    operationalization: Optional[str] = Field(
        None, description="How the principle is made concrete (Coeckelbergh)"
    )
    derived_obligations: List[str] = Field(
        default_factory=list,
        description="Obligations derived from this principle (P->O linkage)"
    )
    potential_conflicts: List[str] = Field(
        default_factory=list,
        description="Principles this may conflict with (Taddeo balancing)"
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
    """A new obligation class discovered in case text."""
    obligation_type: Optional[ObligationType] = None
    enforcement_level: Optional[EnforcementLevel] = None
    derived_from_principle: Optional[str] = Field(
        None, description="Source principle (P->O linkage)"
    )
    violation_consequences: Optional[str] = None
    stakeholders_affected: List[str] = Field(default_factory=list)
    monitoring_criteria: Optional[str] = Field(
        None, description="How fulfillment is assessed (Dennis et al. verifiability)"
    )
    nspe_reference: Optional[str] = Field(
        None, description="Code provision reference (e.g., 'III.4')"
    )


class ObligationIndividual(BaseIndividual):
    """A specific obligation instance in the case."""
    obligation_class: str = Field("", description="Obligation class label or URI", alias="instance_of")
    obligated_party: Optional[str] = Field(
        None, description="Who bears the obligation (Dennis: 'by whom')"
    )
    obligation_statement: Optional[str] = Field(
        None, description="The specific duty statement"
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
    """proethica-intermediate.ttl State archetypes (deontic-function axis).

    A state's kind is grounded by its deontic function on a role-derived obligation:
    activating it (risk, emergency), constraining the action it governs (regulatory),
    putting obligations in conflict/defeat (conflict), conditioning a duty on capacity
    (competence) or on knowledge (information), scoping it to a relationship
    (relationship), bounding it in time (temporal), or conditioning its feasibility
    (resource). Grounding: Berreby et al. (2017) Event-Calculus fluents that trigger/
    terminate obligations, Almpani et al. (2023) context-driven obligation priorities,
    Stenseke (2024) obligation-presupposes-capacity, Govindarajulu & Bringsjord (2017)
    obligation-depends-on-knowledge -- NOT Jones (1991), whose moral intensity SCORES a
    situation's salience (a state attribute, e.g. urgency_level) rather than typing it.
    """
    conflict = "conflict"
    risk = "risk"
    competence = "competence"
    relationship = "relationship"
    information = "information"
    emergency = "emergency"
    regulatory = "regulatory"
    temporal = "temporal"
    resource = "resource"


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
    """proethica-intermediate.ttl Resource subclass hierarchy.

    McLaren/Frankel professional knowledge typology.
    """
    professional_code = "professional_code"
    case_precedent = "case_precedent"
    expert_interpretation = "expert_interpretation"
    technical_standard = "technical_standard"
    legal_resource = "legal_resource"
    decision_tool = "decision_tool"
    reference_material = "reference_material"


class CandidateResourceClass(BaseCandidate):
    """A new resource class discovered in case text."""
    resource_category: Optional[ResourceCategory] = None
    authority_source: Optional[str] = Field(
        None, description="Creator or maintaining body"
    )
    extensional_function: Optional[str] = Field(
        None, description="How the resource functions in professional practice (McLaren)"
    )
    usage_context: List[str] = Field(
        default_factory=list, description="Contexts where this resource type is used"
    )


class ResourceIndividual(BaseIndividual):
    """A specific resource instance in the case."""
    resource_class: str = Field("", description="Resource class label or URI", alias="instance_of")
    document_title: Optional[str] = Field(
        None, description="Official document/resource name"
    )
    created_by: Optional[str] = None
    version: Optional[str] = None
    used_by: Optional[str] = Field(
        None, description="Who used this resource in the case"
    )
    used_in_context: Optional[str] = Field(
        None, description="How the resource was applied"
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
    """
    action_category: Optional[ActionCategory] = None
    volitional_nature: Optional[str] = Field(
        None,
        description="How this reflects deliberate professional choice (Sarmiento)"
    )
    professional_context: Optional[str] = None
    obligations_fulfilled: List[str] = Field(
        default_factory=list,
        description="Obligations this action type fulfills (A->O linkage)"
    )
    causal_implications: List[str] = Field(
        default_factory=list,
        description="Consequences of this action type"
    )
    temporal_constraints: List[str] = Field(
        default_factory=list,
        description="Timing requirements for this action type"
    )


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
    """
    event_category: Optional[EventCategory] = None
    automatic_nature: Optional[str] = Field(
        None,
        description="How this occurs without volitional agency (Berreby automatic events)"
    )
    ethical_salience: Optional[str] = Field(
        None, description="Why this event is ethically significant"
    )
    causal_position: Optional[CausalPosition] = None
    constraint_activation: List[str] = Field(
        default_factory=list,
        description="Constraints this event activates (E->Cs linkage)"
    )
    obligation_transformation: Optional[str] = Field(
        None, description="How this event changes obligations (E->O linkage)"
    )
    state_transitions: List[str] = Field(
        default_factory=list,
        description="State changes this event causes (E->S linkage)"
    )


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

    # Classification. eventType is the Event Calculus agent-caused (outcome) / external
    # (exogenous) / precondition-triggered (automatic_trigger) distinction (Berreby et al.
    # 2017). severity is a heuristic triage indicator of how serious the occurrence is, NOT
    # a formal ontology category. The former emergency_status was renamed to severity and
    # the separate urgency_level field dropped 2026-05-31 (it duplicated severity in every
    # case).
    event_type: Optional[str] = Field(None, alias="proeth:eventType")
    severity: Optional[str] = Field(None, alias="proeth:severity")

    # State change. The former proeth:activatesConstraint and proeth:createsObligation
    # event links were dropped 2026-05-31: an event activates a constraint or makes an
    # obligation apply only via the State it initiates (the Event-Calculus path State
    # proeth-core:activatesConstraint / activatesObligation, materialised by fluent_edges.py
    # + state_edges.py), so the direct event links named free-text obligations/constraints
    # that resolved to no extracted individual and duplicated that grounded path. See
    # rdf_converter._add_fluent_and_time.
    causes_state_change: Optional[str] = Field(None, alias="proeth:causesStateChange")
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
    """A new capability class discovered in case text."""
    capability_category: Optional[CapabilityCategory] = None
    enables_actions: List[str] = Field(
        default_factory=list,
        description="Actions this capability makes possible (Ca->A linkage)"
    )
    required_for_obligations: List[str] = Field(
        default_factory=list,
        description="Obligations requiring this capability (Ca->O linkage)"
    )
    skill_level: Optional[SkillLevel] = None
    domain_specificity: Optional[str] = Field(
        None, description="How domain-specific this capability is (Stenseke)"
    )


class CapabilityIndividual(BaseIndividual):
    """A specific capability instance in the case."""
    capability_class: str = Field("", description="Capability class label or URI", alias="instance_of")
    possessed_by: Optional[str] = Field(
        None, description="Who possesses this capability"
    )
    capability_statement: Optional[str] = Field(
        None, description="Competency description"
    )
    demonstrated_through: Optional[str] = Field(
        None, description="How this capability was evidenced in the case"
    )
    proficiency_level: Optional[SkillLevel] = None
    case_context: Optional[str] = None


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
    """A new constraint class discovered in case text."""
    constraint_type: Optional[ConstraintType] = None
    flexibility: Optional[Flexibility] = Field(
        None, description="Defeasibility level (Ganascia)"
    )
    violation_impact: Optional[str] = None
    mitigation_strategies: List[str] = Field(
        default_factory=list,
        description="Ways to work within the constraint"
    )
    affected_stakeholders: List[str] = Field(default_factory=list)


class ConstraintIndividual(BaseIndividual):
    """A specific constraint instance in the case."""
    constraint_class: str = Field("", description="Constraint class label or URI", alias="instance_of")
    constrained_entity: Optional[str] = Field(
        None, description="What/who is constrained"
    )
    constraint_statement: Optional[str] = Field(
        None, description="Specific limitation statement"
    )
    source: Optional[str] = Field(
        None, description="Where the constraint comes from"
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
    # R: Role categories -> intermediate subclass IRIs
    'roles': {
        'provider_client': f'{INTERMEDIATE_NS}ProviderClientRole',
        'professional_peer': f'{INTERMEDIATE_NS}ProfessionalPeerRole',
        'employer_relationship': f'{INTERMEDIATE_NS}EmployerRelationshipRole',
        'public_responsibility': f'{INTERMEDIATE_NS}PublicResponsibilityRole',
        # participant/stakeholder are generic involvement, not duty-relationships,
        # and ParticipantRole/StakeholderRole live on the (occupational) Participant
        # side, which is disjoint with ProfessionalRole. Map them to the generic
        # relational head so the occupational archetype carries the classification
        # and the relational parent never crosses the occupational disjointness.
        'participant': f'{INTERMEDIATE_NS}RelationalRole',
        'stakeholder': f'{INTERMEDIATE_NS}RelationalRole',
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
    'obligation_enforcement': {
        'mandatory': f'{INTERMEDIATE_NS}MandatoryObligation',
        'defeasible': f'{INTERMEDIATE_NS}DefeasibleObligation',
        'conditional': f'{INTERMEDIATE_NS}ConditionalObligation',
        'prima_facie': f'{INTERMEDIATE_NS}PrimaFacieObligation',
    },
    # S: State categories -> base class (individual states are specific subclasses)
    # The match_decision field handles mapping to specific state subclasses
    # (ConflictOfInterest, PublicSafetyAtRisk, etc.)
    'states': {
        # Deontic-function state archetypes (proethica-intermediate, 2026-05-30): a
        # state's kind is its function on a role-derived obligation. Was all -> core:State.
        'conflict': f'{INTERMEDIATE_NS}ConflictState',
        'risk': f'{INTERMEDIATE_NS}RiskState',
        'competence': f'{INTERMEDIATE_NS}CompetenceState',
        'relationship': f'{INTERMEDIATE_NS}RelationshipState',
        'information': f'{INTERMEDIATE_NS}InformationState',
        'emergency': f'{INTERMEDIATE_NS}EmergencyState',
        'regulatory': f'{INTERMEDIATE_NS}RegulatoryState',
        'temporal': f'{INTERMEDIATE_NS}TemporalState',
        'resource': f'{INTERMEDIATE_NS}ResourceAvailabilityState',
    },
    # Rs: Resource categories -> intermediate subclass IRIs
    'resources': {
        'professional_code': f'{INTERMEDIATE_NS}ProfessionalCode',
        'case_precedent': f'{INTERMEDIATE_NS}CasePrecedent',
        'expert_interpretation': f'{INTERMEDIATE_NS}ExpertInterpretation',
        'technical_standard': f'{INTERMEDIATE_NS}TechnicalStandard',
        'legal_resource': f'{INTERMEDIATE_NS}LegalResource',
        'decision_tool': f'{INTERMEDIATE_NS}DecisionTool',
        'reference_material': f'{INTERMEDIATE_NS}ReferenceMaterial',
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
    'constraint_flexibility': {
        'hard': f'{INTERMEDIATE_NS}InviolableConstraint',
        'soft': f'{INTERMEDIATE_NS}DefeasibleConstraint',
        'negotiable': f'{INTERMEDIATE_NS}DefeasibleConstraint',
    },
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
