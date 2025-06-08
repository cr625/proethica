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
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.models.guideline_term_candidate import GuidelineTermCandidate
from app.models.guideline_semantic_triple import GuidelineSemanticTriple
from app.models.ontology_import import OntologyImport
# Type mapping models (added 2025-01-08)
from app.models.pending_concept_type import PendingConceptType
from app.models.custom_concept_type import CustomConceptType
from app.models.concept_type_mapping import ConceptTypeMapping
