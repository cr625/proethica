"""
Provenance Service for PROV-O compliant tracking of LLM interactions and extractions.

This service implements the PROV-O provenance tracking pattern described in the
OntExtract paper, capturing the complete lineage of prompts, responses, and
analytical operations in ProEthica.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from contextlib import contextmanager
from sqlalchemy.orm import Session

from app.models import db
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle
)


class ProvenanceService:
    """
    Service for tracking PROV-O provenance of LLM interactions and extractions.
    
    Usage:
        prov = ProvenanceService()
        
        # Track an LLM interaction
        with prov.track_activity("llm_query", "role_extraction", case_id=123) as activity:
            prompt_entity = prov.record_prompt(prompt_text, activity)
            # ... call LLM ...
            response_entity = prov.record_response(response_text, activity, derived_from=prompt_entity)
    """
    
    def __init__(self, session: Optional[Session] = None):
        """Initialize the provenance service."""
        self.session = session or db.session
        self._agent_cache = {}  # Cache agents to avoid duplicate lookups
        
    def get_or_create_agent(self, agent_type: str, agent_name: str, 
                           agent_version: Optional[str] = None,
                           agent_metadata: Optional[Dict] = None) -> ProvenanceAgent:
        """
        Get or create a provenance agent.
        
        Args:
            agent_type: Type of agent ('user', 'llm_model', 'extraction_service', 'system')
            agent_name: Name of the agent (e.g., 'claude-3-opus', 'RolesExtractor')
            agent_version: Version of the agent
            agent_metadata: Additional metadata about the agent
            
        Returns:
            ProvenanceAgent instance
        """
        cache_key = f"{agent_type}:{agent_name}:{agent_version}"
        
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]
        
        # Look for existing agent
        agent = ProvenanceAgent.query.filter_by(
            agent_type=agent_type,
            agent_name=agent_name,
            agent_version=agent_version
        ).first()
        
        if not agent:
            agent = ProvenanceAgent(
                agent_type=agent_type,
                agent_name=agent_name,
                agent_version=agent_version,
                agent_metadata=agent_metadata or {}
            )
            self.session.add(agent)
            self.session.flush()
        
        self._agent_cache[cache_key] = agent
        return agent
    
    @contextmanager
    def track_activity(self, activity_type: str, activity_name: str,
                      case_id: Optional[int] = None,
                      session_id: Optional[str] = None,
                      agent_type: str = 'system',
                      agent_name: str = 'proethica',
                      execution_plan: Optional[Dict] = None):
        """
        Context manager for tracking an activity with automatic timing.
        
        Args:
            activity_type: Type of activity ('llm_query', 'extraction', 'analysis')
            activity_name: Name of the activity (e.g., 'role_extraction')
            case_id: Associated case/document ID
            session_id: Session identifier for grouping
            agent_type: Type of agent performing the activity
            agent_name: Name of the agent
            execution_plan: Execution strategy/parameters
            
        Yields:
            ProvenanceActivity instance
            
        Example:
            with prov.track_activity("extraction", "entities_pass", case_id=123) as activity:
                # Do work...
                pass  # activity is automatically completed with timing
        """
        # Get or create agent
        agent = self.get_or_create_agent(agent_type, agent_name)
        
        # Create activity
        activity = ProvenanceActivity(
            activity_type=activity_type,
            activity_name=activity_name,
            case_id=case_id,
            session_id=session_id,
            agent_id=agent.id,
            execution_plan=execution_plan or {},
            started_at=datetime.utcnow(),
            status='started'
        )
        self.session.add(activity)
        self.session.flush()
        
        try:
            yield activity
            # Success - mark as completed
            activity.ended_at = datetime.utcnow()
            activity.duration_ms = int((activity.ended_at - activity.started_at).total_seconds() * 1000)
            activity.status = 'completed'
        except Exception as e:
            # Failure - mark as failed
            activity.ended_at = datetime.utcnow()
            activity.duration_ms = int((activity.ended_at - activity.started_at).total_seconds() * 1000)
            activity.status = 'failed'
            activity.error_message = str(e)
            raise
        finally:
            self.session.flush()
    
    def record_prompt(self, prompt_text: str, activity: ProvenanceActivity,
                     entity_name: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> ProvenanceEntity:
        """
        Record a prompt as a provenance entity.
        
        Args:
            prompt_text: The prompt text
            activity: The activity using this prompt
            entity_name: Optional name for the entity
            metadata: Additional metadata (token count, etc.)
            
        Returns:
            ProvenanceEntity instance
        """
        # Calculate content hash
        content_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        
        # Create entity
        entity = ProvenanceEntity(
            entity_type='prompt',
            entity_name=entity_name or f"prompt_{activity.activity_name}",
            case_id=activity.case_id,
            content=prompt_text,
            content_hash=content_hash,
            content_size=len(prompt_text.encode()),
            generating_activity_id=activity.id,
            generation_time=datetime.utcnow(),
            entity_metadata=metadata or {}
        )
        self.session.add(entity)
        self.session.flush()
        
        # Record usage
        usage = ProvenanceUsage(
            activity_id=activity.id,
            entity_id=entity.id,
            usage_role='input',
            usage_metadata={'purpose': 'llm_prompt'}
        )
        self.session.add(usage)
        self.session.flush()
        
        return entity
    
    def record_response(self, response_text: str, activity: ProvenanceActivity,
                       derived_from: Optional[ProvenanceEntity] = None,
                       entity_name: Optional[str] = None,
                       confidence_score: Optional[float] = None,
                       metadata: Optional[Dict] = None) -> ProvenanceEntity:
        """
        Record a response as a provenance entity.
        
        Args:
            response_text: The response text
            activity: The activity generating this response
            derived_from: The prompt entity this was derived from
            entity_name: Optional name for the entity
            confidence_score: Confidence score for the response
            metadata: Additional metadata
            
        Returns:
            ProvenanceEntity instance
        """
        # Calculate content hash
        content_hash = hashlib.sha256(response_text.encode()).hexdigest()
        
        # Create entity
        entity = ProvenanceEntity(
            entity_type='response',
            entity_name=entity_name or f"response_{activity.activity_name}",
            case_id=activity.case_id,
            content=response_text,
            content_hash=content_hash,
            content_size=len(response_text.encode()),
            generating_activity_id=activity.id,
            generation_time=datetime.utcnow(),
            confidence_score=confidence_score,
            entity_metadata=metadata or {}
        )
        self.session.add(entity)
        self.session.flush()
        
        # Record derivation if source provided
        if derived_from:
            derivation = ProvenanceDerivation(
                derived_entity_id=entity.id,
                source_entity_id=derived_from.id,
                derivation_type='generation',
                derivation_metadata={'method': 'llm_generation'}
            )
            self.session.add(derivation)
            self.session.flush()
        
        return entity
    
    def record_extraction_results(self, results: Union[List, Dict], 
                                 activity: ProvenanceActivity,
                                 entity_type: str,
                                 derived_from: Optional[List[ProvenanceEntity]] = None,
                                 metadata: Optional[Dict] = None) -> ProvenanceEntity:
        """
        Record extraction results (roles, resources, etc.) as a provenance entity.
        
        Args:
            results: The extraction results (list or dict)
            activity: The activity that performed the extraction
            entity_type: Type of extracted entities (e.g., 'extracted_roles')
            derived_from: List of entities these were derived from
            metadata: Additional metadata
            
        Returns:
            ProvenanceEntity instance
        """
        # Serialize results
        content = json.dumps(results, indent=2)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Calculate quality metrics
        quality_metrics = {}
        if isinstance(results, list):
            quality_metrics['count'] = len(results)
            if results and isinstance(results[0], dict):
                # Calculate average confidence if available
                confidences = [r.get('confidence', 0) for r in results if 'confidence' in r]
                if confidences:
                    quality_metrics['avg_confidence'] = sum(confidences) / len(confidences)
        
        # Create entity
        entity = ProvenanceEntity(
            entity_type=entity_type,
            entity_name=f"{entity_type}_{activity.activity_name}",
            case_id=activity.case_id,
            content=content,
            content_hash=content_hash,
            content_size=len(content.encode()),
            generating_activity_id=activity.id,
            generation_time=datetime.utcnow(),
            quality_metrics=quality_metrics,
            entity_metadata=metadata or {}
        )
        self.session.add(entity)
        self.session.flush()
        
        # Record derivations if sources provided
        if derived_from:
            for source in derived_from:
                derivation = ProvenanceDerivation(
                    derived_entity_id=entity.id,
                    source_entity_id=source.id,
                    derivation_type='extraction',
                    derivation_metadata={'extraction_type': entity_type}
                )
                self.session.add(derivation)
        
        self.session.flush()
        return entity
    
    def link_activities(self, informed: ProvenanceActivity, 
                       informing: ProvenanceActivity,
                       communication_type: str = 'dependency'):
        """
        Create a wasInformedBy relationship between activities.
        
        Args:
            informed: The activity that was informed
            informing: The activity that did the informing
            communication_type: Type of communication ('dependency', 'sequence', 'trigger')
        """
        communication = ProvenanceCommunication(
            informed_activity_id=informed.id,
            informing_activity_id=informing.id,
            communication_type=communication_type
        )
        self.session.add(communication)
        self.session.flush()
    
    def create_bundle(self, bundle_name: str, bundle_type: str,
                     case_id: Optional[int] = None,
                     session_id: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> ProvenanceBundle:
        """
        Create a provenance bundle to group related records.
        
        Args:
            bundle_name: Name of the bundle
            bundle_type: Type of bundle ('extraction_workflow', 'analysis_session')
            case_id: Associated case ID
            session_id: Session identifier
            metadata: Additional metadata
            
        Returns:
            ProvenanceBundle instance
        """
        bundle = ProvenanceBundle(
            bundle_name=bundle_name,
            bundle_type=bundle_type,
            case_id=case_id,
            session_id=session_id,
            bundle_metadata=metadata or {},
            started_at=datetime.utcnow()
        )
        self.session.add(bundle)
        self.session.flush()
        return bundle
    
    def get_provenance_graph(self, case_id: int) -> Dict[str, Any]:
        """
        Retrieve the complete provenance graph for a case.
        
        Args:
            case_id: The case ID to retrieve provenance for
            
        Returns:
            Dictionary containing nodes and edges of the provenance graph
        """
        # Get all activities for this case
        activities = ProvenanceActivity.query.filter_by(case_id=case_id).all()
        
        # Get all entities for this case
        entities = ProvenanceEntity.query.filter_by(case_id=case_id).all()
        
        # Build graph structure
        graph = {
            'nodes': {
                'agents': [],
                'activities': [],
                'entities': []
            },
            'edges': {
                'wasGeneratedBy': [],
                'wasDerivedFrom': [],
                'wasAssociatedWith': [],
                'used': [],
                'wasInformedBy': []
            }
        }
        
        # Add agents
        agent_ids = set()
        for activity in activities:
            if activity.agent_id not in agent_ids:
                agent_ids.add(activity.agent_id)
                agent = activity.agent
                graph['nodes']['agents'].append({
                    'id': f"agent_{agent.id}",
                    'type': agent.agent_type,
                    'name': agent.agent_name,
                    'version': agent.agent_version
                })
        
        # Add activities
        for activity in activities:
            graph['nodes']['activities'].append({
                'id': f"activity_{activity.id}",
                'type': activity.activity_type,
                'name': activity.activity_name,
                'status': activity.status,
                'duration_ms': activity.duration_ms
            })
            
            # Add wasAssociatedWith edges
            graph['edges']['wasAssociatedWith'].append({
                'from': f"activity_{activity.id}",
                'to': f"agent_{activity.agent_id}"
            })
        
        # Add entities and relationships
        for entity in entities:
            graph['nodes']['entities'].append({
                'id': f"entity_{entity.id}",
                'type': entity.entity_type,
                'name': entity.entity_name,
                'confidence': entity.confidence_score
            })
            
            # Add wasGeneratedBy edges
            if entity.generating_activity_id:
                graph['edges']['wasGeneratedBy'].append({
                    'from': f"entity_{entity.id}",
                    'to': f"activity_{entity.generating_activity_id}"
                })
        
        # Add derivations
        derivations = ProvenanceDerivation.query.join(
            ProvenanceEntity, ProvenanceDerivation.derived_entity_id == ProvenanceEntity.id
        ).filter(ProvenanceEntity.case_id == case_id).all()
        
        for derivation in derivations:
            graph['edges']['wasDerivedFrom'].append({
                'from': f"entity_{derivation.derived_entity_id}",
                'to': f"entity_{derivation.source_entity_id}",
                'type': derivation.derivation_type
            })
        
        # Add usage relationships
        usages = ProvenanceUsage.query.join(
            ProvenanceActivity
        ).filter(ProvenanceActivity.case_id == case_id).all()
        
        for usage in usages:
            graph['edges']['used'].append({
                'from': f"activity_{usage.activity_id}",
                'to': f"entity_{usage.entity_id}",
                'role': usage.usage_role
            })
        
        # Add communication relationships
        communications = ProvenanceCommunication.query.join(
            ProvenanceActivity, ProvenanceCommunication.informed_activity_id == ProvenanceActivity.id
        ).filter(ProvenanceActivity.case_id == case_id).all()
        
        for comm in communications:
            graph['edges']['wasInformedBy'].append({
                'from': f"activity_{comm.informed_activity_id}",
                'to': f"activity_{comm.informing_activity_id}",
                'type': comm.communication_type
            })
        
        return graph


# Singleton instance
_provenance_service = None

def get_provenance_service(session: Optional[Session] = None) -> ProvenanceService:
    """Get or create the provenance service singleton."""
    global _provenance_service
    if _provenance_service is None:
        _provenance_service = ProvenanceService(session)
    return _provenance_service