"""
Service for orchestrating the conversion of cases to scenarios through deconstruction.

This service coordinates the entire pipeline:
1. Case deconstruction using domain-specific adapters
2. Scenario template generation
3. Background processing with progress tracking
4. Human validation workflow
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from app.models import Document
from app.models.deconstructed_case import DeconstructedCase as DBDeconstructedCase
from app.models.scenario_template import ScenarioTemplate
from app.models.scenario import Scenario
from app.services.case_deconstruction.base_adapter import BaseCaseDeconstructionAdapter
from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter
from app.services.task_queue import BackgroundTaskQueue
from app import db

logger = logging.getLogger(__name__)


class CaseToScenarioService:
    """
    Orchestrates the conversion of cases to scenarios through deconstruction.
    
    Provides both synchronous and asynchronous processing modes with
    human validation workflow and confidence-based auto-approval.
    """
    
    # Adapter registry for different domains
    ADAPTERS = {
        'engineering': EngineeringEthicsAdapter,
    }
    
    # Confidence thresholds for auto-approval
    CONFIDENCE_THRESHOLDS = {
        'stakeholders': 0.8,
        'decision_points': 0.75,
        'reasoning_chain': 0.8,
        'overall': 0.8
    }

    def __init__(self):
        self.task_queue = BackgroundTaskQueue()

    def get_adapter_for_case(self, case: Document) -> Optional[BaseCaseDeconstructionAdapter]:
        """
        Get the appropriate adapter for a case based on its world/domain.
        
        Args:
            case: The document/case to analyze
            
        Returns:
            Adapter instance or None if no suitable adapter found
        """
        if not case.world:
            logger.warning(f"Case {case.id} has no world assigned")
            return None
            
        world_name = case.world.name.lower()
        
        # Map world names to adapter types
        if 'engineering' in world_name or 'nspe' in world_name:
            return self.ADAPTERS['engineering']()
            
        logger.warning(f"No adapter found for world: {world_name}")
        return None

    def can_deconstruct_case(self, case: Document) -> Tuple[bool, str]:
        """
        Check if a case can be deconstructed.
        
        Args:
            case: The document/case to check
            
        Returns:
            Tuple of (can_deconstruct, reason)
        """
        if not case:
            return False, "Case not found"
            
        if not case.world:
            return False, "Case has no world/domain assigned"
            
        adapter = self.get_adapter_for_case(case)
        if not adapter:
            return False, f"No adapter available for world: {case.world.name}"
            
        # Check if case has required content
        if not case.doc_metadata:
            return False, "Case has no content metadata"
            
        sections = case.doc_metadata.get('sections', {})
        if not sections:
            return False, "Case has no extracted sections"
            
        return True, "Case can be deconstructed"

    def deconstruct_case_sync(self, case: Document) -> Optional[DBDeconstructedCase]:
        """
        Synchronously deconstruct a case using the appropriate adapter.
        
        Args:
            case: The document/case to deconstruct
            
        Returns:
            DeconstructedCase instance or None if failed
        """
        can_process, reason = self.can_deconstruct_case(case)
        if not can_process:
            logger.error(f"Cannot deconstruct case {case.id}: {reason}")
            return None
            
        adapter = self.get_adapter_for_case(case)
        
        try:
            logger.info(f"Starting deconstruction of case {case.id} with {adapter.__class__.__name__}")
            
            # Prepare case content dictionary for adapter
            case_content = {
                'id': case.id,
                'title': case.title,
                'content': case.content,
                'doc_metadata': case.doc_metadata or {}
            }
            
            # Run the deconstruction
            deconstructed = adapter.deconstruct_case(case_content)
            
            # Save to database
            analysis_dict = deconstructed.analysis.to_dict()
            
            # Extract confidence scores
            confidence_scores = {
                'stakeholder_confidence': deconstructed.analysis.stakeholder_confidence,
                'decision_points_confidence': deconstructed.analysis.decision_points_confidence,
                'reasoning_confidence': deconstructed.analysis.reasoning_confidence
            }
            
            db_deconstructed = DBDeconstructedCase(
                case_id=case.id,
                adapter_type=adapter.__class__.__name__,
                stakeholders=analysis_dict['stakeholders'],
                decision_points=analysis_dict['decision_points'],
                reasoning_chain=analysis_dict['reasoning_chain'],
                stakeholder_confidence=deconstructed.analysis.stakeholder_confidence,
                decision_points_confidence=deconstructed.analysis.decision_points_confidence,
                reasoning_confidence=deconstructed.analysis.reasoning_confidence,
                human_validated=self._should_auto_approve(confidence_scores),
                adapter_version=deconstructed.analysis.adapter_version,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(db_deconstructed)
            db.session.commit()
            
            logger.info(f"Successfully deconstructed case {case.id}")
            return db_deconstructed
            
        except Exception as e:
            logger.error(f"Failed to deconstruct case {case.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            return None

    def deconstruct_case_async(self, case_id: int) -> str:
        """
        Asynchronously deconstruct a case with progress tracking.
        
        Args:
            case_id: ID of the case to deconstruct
            
        Returns:
            Task ID for tracking progress
        """
        def deconstruction_task():
            """Background task for case deconstruction."""
            try:
                # Import app creation to get proper context
                from app import create_app
                import os
                
                # Ensure environment is set
                os.environ.setdefault('ENVIRONMENT', 'development')
                
                # Create app context for database access
                app = create_app()
                with app.app_context():
                    # Update progress: Starting
                    self._update_case_progress(case_id, 10, "ANALYZING", "Loading case data...")
                    
                    case = Document.query.get(case_id)
                    if not case:
                        raise ValueError(f"Case {case_id} not found")
                    
                    # Update progress: Checking prerequisites  
                    self._update_case_progress(case_id, 20, "ANALYZING", "Checking case structure...")
                    
                    can_process, reason = self.can_deconstruct_case(case)
                    if not can_process:
                        raise ValueError(f"Cannot deconstruct case: {reason}")
                    
                    # Update progress: Running deconstruction
                    self._update_case_progress(case_id, 40, "DECONSTRUCTING", "Extracting stakeholders and decision points...")
                    
                    deconstructed = self.deconstruct_case_sync(case)
                    if not deconstructed:
                        raise ValueError("Deconstruction failed")
                    
                    # Update progress: Completed
                    self._update_case_progress(case_id, 100, "COMPLETED", "Deconstruction completed successfully")
                    
                    return {"success": True, "deconstructed_case_id": deconstructed.id}
                    
            except Exception as e:
                logger.error(f"Deconstruction task failed for case {case_id}: {str(e)}", exc_info=True)
                # Try to update progress in a new app context if needed
                try:
                    from app import create_app
                    import os
                    os.environ.setdefault('ENVIRONMENT', 'development')
                    app = create_app()
                    with app.app_context():
                        self._update_case_progress(case_id, 0, "FAILED", f"Error: {str(e)}")
                except:
                    pass
                return {"success": False, "error": str(e)}
        
        # Start background task
        task_id = self.task_queue.process_task_async(deconstruction_task)
        
        # Initialize progress tracking
        self._update_case_progress(case_id, 0, "QUEUED", "Task queued for processing")
        
        return task_id

    def get_deconstruction_progress(self, case_id: int) -> Dict[str, Any]:
        """
        Get the progress of case deconstruction.
        
        Args:
            case_id: ID of the case being deconstructed
            
        Returns:
            Progress information
        """
        case = Document.query.get(case_id)
        if not case or not case.doc_metadata:
            return {"status": "NOT_FOUND", "progress": 0}
            
        metadata = case.doc_metadata
        return {
            "status": metadata.get('deconstruction_status', 'UNKNOWN'),
            "progress": metadata.get('deconstruction_progress', 0),
            "phase": metadata.get('deconstruction_phase', ''),
            "message": metadata.get('deconstruction_message', ''),
            "updated_at": metadata.get('deconstruction_updated_at')
        }

    def generate_scenario_from_deconstruction(self, deconstructed_case: DBDeconstructedCase) -> Optional[ScenarioTemplate]:
        """
        Generate a scenario template from a deconstructed case.
        
        Args:
            deconstructed_case: The deconstructed case to convert
            
        Returns:
            ScenarioTemplate instance or None if failed
        """
        try:
            # Get the original case
            case = deconstructed_case.case
            if not case:
                logger.error(f"Cannot find case for deconstructed case {deconstructed_case.id}")
                return None
            
            # Create scenario template
            template = ScenarioTemplate(
                deconstructed_case_id=deconstructed_case.id,
                title=f"Scenario: {case.title}",
                description=f"Interactive scenario based on {case.title}",
                world_id=case.world_id,
                template_data=self._build_scenario_template_data(deconstructed_case),
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(template)
            db.session.commit()
            
            logger.info(f"Generated scenario template {template.id} from deconstructed case {deconstructed_case.id}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to generate scenario template: {str(e)}")
            db.session.rollback()
            return None

    def create_playable_scenario(self, template: ScenarioTemplate, user_id: int) -> Optional[Scenario]:
        """
        Create a playable scenario instance from a template.
        
        Args:
            template: The scenario template to instantiate
            user_id: ID of the user creating the scenario
            
        Returns:
            Scenario instance or None if failed
        """
        try:
            # Create scenario instance
            scenario = Scenario(
                name=template.title,
                description=template.description,
                world_id=template.world_id,
                scenario_metadata=self._build_scenario_metadata(template),
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(scenario)
            db.session.commit()
            
            logger.info(f"Created playable scenario {scenario.id} from template {template.id}")
            return scenario
            
        except Exception as e:
            logger.error(f"Failed to create playable scenario: {str(e)}")
            db.session.rollback()
            return None

    def _should_auto_approve(self, confidence_scores: Dict[str, float]) -> bool:
        """
        Determine if deconstruction results should be auto-approved based on confidence.
        
        Args:
            confidence_scores: Confidence scores for different components
            
        Returns:
            True if should auto-approve, False if needs human review
        """
        if not confidence_scores:
            return False
            
        # Check individual component thresholds
        for component, threshold in self.CONFIDENCE_THRESHOLDS.items():
            if component == 'overall':
                continue
            score = confidence_scores.get(component, 0.0)
            if score < threshold:
                return False
        
        # Check overall threshold
        overall_score = confidence_scores.get('overall', 0.0)
        return overall_score >= self.CONFIDENCE_THRESHOLDS['overall']

    def _update_case_progress(self, case_id: int, progress: int, status: str, message: str):
        """
        Update the progress tracking for a case deconstruction.
        
        Args:
            case_id: ID of the case being processed
            progress: Progress percentage (0-100)
            status: Current status
            message: Status message
        """
        try:
            # Use a new session to avoid conflicts with the main session
            from sqlalchemy.orm import scoped_session
            from app import db as app_db
            
            # Create a new session for this update
            Session = scoped_session(app_db.session.session_factory)
            session = Session()
            
            try:
                case = session.query(Document).get(case_id)
                if case:
                    if not case.doc_metadata:
                        case.doc_metadata = {}
                    
                    case.doc_metadata.update({
                        'deconstruction_status': status,
                        'deconstruction_progress': progress,
                        'deconstruction_phase': status,
                        'deconstruction_message': message,
                        'deconstruction_updated_at': datetime.now(timezone.utc).isoformat()
                    })
                    
                    session.commit()
                    logger.info(f"Updated progress for case {case_id}: {progress}% - {status}")
            finally:
                session.close()
                Session.remove()
                
        except Exception as e:
            logger.error(f"Failed to update progress for case {case_id}: {str(e)}", exc_info=True)

    def _build_scenario_template_data(self, deconstructed_case: DBDeconstructedCase) -> Dict[str, Any]:
        """
        Build scenario template data from deconstructed case.
        
        Args:
            deconstructed_case: The deconstructed case
            
        Returns:
            Template data structure
        """
        return {
            "characters": self._convert_stakeholders_to_characters(deconstructed_case.stakeholders),
            "decision_points": deconstructed_case.decision_points,
            "reasoning_chain": deconstructed_case.reasoning_chain,
            "initial_conditions": self._extract_initial_conditions(deconstructed_case),
            "learning_objectives": self._extract_learning_objectives(deconstructed_case),
            "assessment_criteria": self._build_assessment_criteria(deconstructed_case)
        }

    def _build_scenario_metadata(self, template: ScenarioTemplate) -> Dict[str, Any]:
        """
        Build scenario metadata from template.
        
        Args:
            template: The scenario template
            
        Returns:
            Scenario metadata structure
        """
        template_data = template.template_data or {}
        
        return {
            "source_case_id": template.deconstructed_case.case_id if template.deconstructed_case else None,
            "characters": template_data.get("characters", []),
            "decision_points": template_data.get("decision_points", []),
            "initial_conditions": template_data.get("initial_conditions", {}),
            "learning_objectives": template_data.get("learning_objectives", []),
            "assessment_criteria": template_data.get("assessment_criteria", []),
            "current_state": "initialized",
            "user_decisions": [],
            "progress": {
                "current_decision_point": 0,
                "completed_decisions": [],
                "reasoning_quality_scores": []
            }
        }

    def _convert_stakeholders_to_characters(self, stakeholders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert stakeholders to scenario characters."""
        characters = []
        
        for stakeholder in stakeholders:
            character = {
                "name": stakeholder.get("name", "Unknown"),
                "role": stakeholder.get("role", "Stakeholder"),
                "interests": stakeholder.get("interests", []),
                "power_level": stakeholder.get("power_level", "medium"),
                "ethical_stance": stakeholder.get("ethical_stance", "neutral"),
                "background": stakeholder.get("description", ""),
                "objectives": stakeholder.get("objectives", [])
            }
            characters.append(character)
            
        return characters

    def _extract_initial_conditions(self, deconstructed_case: DBDeconstructedCase) -> Dict[str, Any]:
        """Extract initial scenario conditions from deconstructed case."""
        reasoning = deconstructed_case.reasoning_chain or {}
        
        return {
            "facts": reasoning.get("facts", []),
            "context": reasoning.get("context", ""),
            "constraints": reasoning.get("constraints", []),
            "available_resources": reasoning.get("resources", []),
            "time_pressure": reasoning.get("urgency", "normal"),
            "regulatory_environment": reasoning.get("regulations", [])
        }

    def _extract_learning_objectives(self, deconstructed_case: DBDeconstructedCase) -> List[str]:
        """Extract learning objectives from deconstructed case."""
        objectives = []
        
        # Extract from decision points
        for decision in deconstructed_case.decision_points or []:
            principles = decision.get("ethical_principles", [])
            for principle in principles:
                objective = f"Apply {principle} in professional decision-making"
                if objective not in objectives:
                    objectives.append(objective)
        
        # Add general objectives
        objectives.extend([
            "Identify and analyze ethical decision points",
            "Consider multiple stakeholder perspectives",
            "Apply professional codes of ethics",
            "Evaluate consequences of decisions"
        ])
        
        return objectives

    def _build_assessment_criteria(self, deconstructed_case: DBDeconstructedCase) -> List[Dict[str, Any]]:
        """Build assessment criteria for the scenario."""
        criteria = []
        
        # Use stakeholder count to customize criteria weights
        stakeholder_count = len(deconstructed_case.stakeholders or [])
        
        # Stakeholder consideration (adjust weight based on complexity)
        stakeholder_weight = 0.3 if stakeholder_count > 3 else 0.25
        criteria.append({
            "criterion": "Stakeholder Analysis",
            "description": "Identifies and considers all relevant stakeholders",
            "weight": stakeholder_weight,
            "rubric": {
                "excellent": "Identifies all stakeholders and their interests",
                "good": "Identifies most relevant stakeholders",
                "fair": "Identifies some stakeholders",
                "poor": "Fails to identify key stakeholders"
            }
        })
        
        # Ethical reasoning
        criteria.append({
            "criterion": "Ethical Reasoning",
            "description": "Applies relevant ethical principles and codes",
            "weight": 0.30,
            "rubric": {
                "excellent": "Correctly applies multiple ethical frameworks",
                "good": "Applies relevant ethical principles",
                "fair": "Shows basic ethical awareness",
                "poor": "Lacks ethical reasoning"
            }
        })
        
        # Decision quality
        criteria.append({
            "criterion": "Decision Quality",
            "description": "Makes sound professional decisions",
            "weight": 0.25,
            "rubric": {
                "excellent": "Makes optimal decisions with strong justification",
                "good": "Makes appropriate decisions with good reasoning",
                "fair": "Makes acceptable decisions",
                "poor": "Makes poor or unjustified decisions"
            }
        })
        
        # Communication
        criteria.append({
            "criterion": "Professional Communication",
            "description": "Communicates decisions effectively",
            "weight": 0.20,
            "rubric": {
                "excellent": "Clear, professional, and persuasive communication",
                "good": "Good communication with minor issues",
                "fair": "Adequate communication",
                "poor": "Poor or unprofessional communication"
            }
        })
        
        return criteria