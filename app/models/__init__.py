# Import models to make them available when importing from app.models
# Import db first to avoid circular imports
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models after db is defined
from app.models.domain import Domain
from app.models.world import World
from app.models.role import Role
from app.models.resource_type import ResourceType
from app.models.condition_type import ConditionType
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.resource import Resource
from app.models.entity import Entity
from app.models.event_entity import event_entity
from app.models.event import Event, Action
from app.models.evaluation import Evaluation
from app.models.decision import Decision
from app.models.document import Document, DocumentChunk
from app.models.simulation_session import SimulationSession
from app.models.simulation_state import SimulationState
# STUB MODELS: Ontology functionality moved to OntServe - these are stubs to prevent import errors
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.models.guideline_section import GuidelineSection
from app.models.guideline_term_candidate import GuidelineTermCandidate
from app.models.guideline_semantic_triple import GuidelineSemanticTriple
# STUB MODEL: OntologyImport moved to OntServe - this is a stub to prevent import errors
from app.models.ontology_import import OntologyImport
# Type mapping models (added 2025-01-08)
from app.models.pending_concept_type import PendingConceptType
from app.models.custom_concept_type import CustomConceptType
from app.models.concept_type_mapping import ConceptTypeMapping
# Deconstructed case models (added 2025-01-27)
from app.models.deconstructed_case import DeconstructedCase
from app.models.scenario_template import ScenarioTemplate
# Temporary concept storage (added 2025-01-21)
from app.models.temporary_concept import TemporaryConcept

# ProEthica 9-category models (added 2025-09-04)
from app.models.principle import Principle
from app.models.obligation import Obligation
from app.models.state import State
from app.models.capability import Capability
from app.models.constraint import Constraint

# Reasoning trace models (added 2025-09-04)
from app.models.reasoning_trace import ReasoningTrace, ReasoningStep

# Prompt builder models (added 2025-09-09)
from app.models.prompt_templates import SectionPromptTemplate, SectionPromptInstance, PromptTemplateVersion

# Provenance models (added 2025-11-11)
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle, VersionEnvironment, VersionStatus
)

# Provenance versioning models (added 2025-11-11)
from app.models.provenance_versioning import (
    ProvenanceRevision, ProvenanceVersion, ProvenanceAlternate,
    VersionConfiguration
)

# Candidate validation models (added 2025-09-22)
from app.models.candidate_role_class import CandidateRoleClass, CandidateRoleIndividual

# Temporary RDF storage (added 2025-09-24)
from app.models.temporary_rdf_storage import TemporaryRDFStorage

# Extraction prompt storage (added 2025-09-24)
from app.models.extraction_prompt import ExtractionPrompt

# Scenario generation models (added 2025-11-16)
from app.models.scenario_participant import ScenarioParticipant
