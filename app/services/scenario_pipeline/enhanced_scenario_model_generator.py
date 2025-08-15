"""
Enhanced Scenario Model Generator Service.

Converts enhanced timeline data from LLM into proper database models
(Character, Resource, Event, Action) that work with the existing scenario template.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.event import Event, Action
from app.models.document import Document
from app.services.case_role_matching_service import CaseRoleMatchingService
from app.services.ontology_entity_service import OntologyEntityService

logger = logging.getLogger(__name__)

class EnhancedScenarioModelGenerator:
    """Generates proper database models from enhanced timeline data."""
    
    def __init__(self):
        self.logger = logger
    
    def create_scenario_from_enhanced_timeline(
        self, 
        case: Document, 
        enhanced_timeline: Dict[str, Any]
    ) -> int:
        """
        Create a complete scenario with proper database models from enhanced timeline data.
        
        Args:
            case: The source case document
            enhanced_timeline: Enhanced timeline data from EnhancedLLMScenarioService
            
        Returns:
            scenario_id: ID of the created scenario
        """
        try:
            # Create the main scenario record
            scenario = self._create_scenario_record(case, enhanced_timeline)
            db.session.add(scenario)
            db.session.flush()  # Get the ID
            
            # Create Character records from participants
            characters = self._create_characters(scenario.id, enhanced_timeline)
            for character in characters:
                db.session.add(character)
            
            # Create Resource records from timeline and decisions
            resources = self._create_resources(scenario.id, enhanced_timeline)
            for resource in resources:
                db.session.add(resource)
            
            # Use a shared base time for consistent interleaving between events and decisions
            from datetime import timedelta
            base_time = datetime.utcnow()

            # Create Event records from timeline_events (even-minute slots)
            events = self._create_events(scenario.id, enhanced_timeline, characters, base_time)
            for event in events:
                db.session.add(event)
            
            # Create Action records from enhanced_decisions (odd-minute slots)
            actions = self._create_actions(scenario.id, enhanced_timeline, characters, base_time)
            for action in actions:
                db.session.add(action)

            # Phase 1 guardrail: ensure context exists before any decisions
            self._ensure_context_before_decisions(scenario.id, base_time)
            
            # Update scenario metadata with ontology summary
            scenario.scenario_metadata.update({
                'ontology_summary': self._build_ontology_summary(enhanced_timeline, characters, resources, events, actions),
                'model_counts': {
                    'characters': len(characters),
                    'resources': len(resources), 
                    'events': len(events),
                    'actions': len(actions)
                }
            })
            
            db.session.commit()
            
            logger.info(f"Created scenario {scenario.id} with {len(characters)} characters, {len(resources)} resources, {len(events)} events, {len(actions)} actions")
            return scenario.id
            
        except Exception as e:
            logger.error(f"Failed to create scenario from enhanced timeline: {e}")
            db.session.rollback()
            raise
    
    def _create_scenario_record(self, case: Document, enhanced_timeline: Dict[str, Any]) -> Scenario:
        """Create the main scenario database record."""
        
        # Extract key info from enhanced timeline
        stats = enhanced_timeline.get('stats', {})
        participants = enhanced_timeline.get('participants', [])
        
        # Generate scenario name from case title
        scenario_name = f"{case.title}"
        if len(scenario_name) > 255:
            scenario_name = scenario_name[:252] + "..."
            
        # Create description from case content
        description = f"Interactive ethical decision scenario generated from case {case.id}. "
        description += f"Contains {stats.get('event_count', 0)} events and {stats.get('decision_count', 0)} decisions."
        
        if participants:
            description += f" Key participants: {', '.join([p['name'] for p in participants[:3]])}."
        
        scenario = Scenario(
            name=scenario_name,
            description=description,
            world_id=case.world_id or 1,  # Default to world 1 if not set
            scenario_metadata={
                'source_case_id': case.id,
                'generation_method': 'enhanced_llm_models',
                'pipeline_version': enhanced_timeline.get('extraction_metadata', {}).get('llm_model', 'enhanced_llm_v1'),
                'generated_at': datetime.utcnow().isoformat(),
                'stats': stats,
                'participants': participants,
                'ontology_enrichment_status': enhanced_timeline.get('ontology_enrichment_status'),
                'temporal_evidence_count': len(enhanced_timeline.get('temporal_evidence', []))
            }
        )
        
        return scenario
    
    def _create_characters(self, scenario_id: int, enhanced_timeline: Dict[str, Any]) -> List[Character]:
        """Create Character records from participants with intelligent role matching."""
        
        characters = []
        participants = enhanced_timeline.get('participants', [])
        
        if not participants:
            return characters
        
    # Initialize role matching service and get ontology roles
        role_matcher = CaseRoleMatchingService()
        ontology_service = OntologyEntityService.get_instance()
        
        # Get the world from scenario to load ontology roles
        scenario = db.session.get(Scenario, scenario_id)
        role_matches_by_index = {}
        ontology_roles = []
        world = None
        if scenario and scenario.world_id:
            from app.models.world import World
            world = db.session.get(World, scenario.world_id)
            if world:
                # Aggregate roles across base + derived ontologies for this world
                ontology_roles = ontology_service.get_roles_across_world(world)

                # Match each participant using the LLM-extracted ontology label (fallback to name)
                for idx, p in enumerate(participants):
                    llm_term = (p.get('ontology_label') or p.get('name') or '').strip()
                    role_matches_by_index[idx] = role_matcher.match_role_to_ontology(llm_term, ontology_roles, world=world)
                logger.info(f"Role matching completed for {len(participants)} participants (per-participant matching)")
        
        for participant in participants:
            name = participant.get('name', 'Unknown Participant')
            
            # Get ontology label if available (from ParticipantMapping)
            original_llm_role = participant.get('ontology_label', '')
            
            # Try to match role to ontology
            # Retrieve the match result computed above for this participant
            role_match = role_matches_by_index.get(participants.index(participant), {})
            if role_match.get('matched_role'):
                # Use matched ontology role
                matched_role = role_match['matched_role']['label']
                matched_ontology_id = role_match['matched_role']['id']
                matching_confidence = role_match.get('semantic_confidence', 0.0)
                matching_reasoning = role_match.get('llm_reasoning', '')
                
                logger.info(f"✅ Role matched: {name} ({original_llm_role}) → {matched_role}")
            else:
                # No match found - use original LLM role
                matched_role = original_llm_role or self._extract_professional_role(name, original_llm_role)
                matched_ontology_id = None
                matching_confidence = None
                matching_reasoning = "No ontology match found"
                
                logger.info(f"❌ No role match: {name} → keeping '{matched_role}'")
            
            # Create attributes from ontology enrichment
            attributes = {
                'participation_type': participant.get('role_type', 'stakeholder'),
                'ontology_label': original_llm_role
            }
            
            character = Character(
                scenario_id=scenario_id,
                name=name,
                role=matched_role,  # Use matched role or fallback
                original_llm_role=original_llm_role,  # Store original LLM extraction
                matched_ontology_role_id=matched_ontology_id,  # Ontology role ID if matched
                matching_confidence=matching_confidence,  # Confidence score
                matching_method='semantic_llm_validated' if matched_ontology_id else None,
                matching_reasoning=matching_reasoning,  # LLM reasoning
                attributes=attributes,
                bfo_class='BFO_0000040',  # material entity (agent)
                proethica_category='role',
                ontology_uri=None  # MCP server can populate this later
            )
            
            characters.append(character)
        
        return characters
    
    def _extract_professional_role(self, participant_name: str, ontology_label: str) -> str:
        """Extract professional role - prioritizes LLM-extracted role from ontology_label."""
        
        # Primary: Use LLM-extracted role if available
        if ontology_label and ontology_label.strip():
            logger.info(f"Using LLM-extracted role for {participant_name}: {ontology_label}")
            return ontology_label
        
        # Fallback: Basic role inference (minimal pattern matching)
        name_lower = participant_name.lower()
        
        if 'county' in name_lower:
            return 'County/Government Client'
        elif 'engineer' in name_lower:
            return 'Professional Engineer'  
        elif 'firm' in name_lower or 'company' in name_lower:
            return 'Engineering Firm'
        else:
            # Generic fallback - should rarely be used with proper LLM extraction
            return 'Stakeholder'
    
    def _create_resources(self, scenario_id: int, enhanced_timeline: Dict[str, Any]) -> List[Resource]:
        """Create Resource records from timeline and decisions."""
        
        resources = []
        resource_names = set()
        
        # Extract resources from timeline events
        timeline_events = enhanced_timeline.get('timeline_events', [])
        for event in timeline_events:
            # Look for resource-related keywords
            event_text = event.get('description', '') + ' ' + event.get('text', '')
            potential_resources = self._extract_resources_from_text(event_text)
            resource_names.update(potential_resources)
        
        # Extract resources from decisions
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        for decision in decisions:
            decision_text = decision.question + ' ' + decision.context
            potential_resources = self._extract_resources_from_text(decision_text)
            resource_names.update(potential_resources)
        
        # Create Resource records
        for resource_name in resource_names:
            resource = Resource(
                scenario_id=scenario_id,
                name=resource_name,
                type='extracted',  # Legacy field
                quantity=1,
                description=f"Resource identified from case analysis: {resource_name}"
            )
            resources.append(resource)
        
        return resources
    
    def _extract_resources_from_text(self, text: str) -> List[str]:
        """Extract potential resources from text."""
        
        resource_keywords = [
            'software', 'system', 'database', 'application', 'platform',
            'tool', 'equipment', 'hardware', 'server', 'network',
            'budget', 'funding', 'money', 'cost', 'payment',
            'document', 'report', 'specification', 'manual', 'guide',
            'data', 'information', 'analysis', 'study', 'research',
            'code', 'algorithm', 'model', 'design', 'plan'
        ]
        
        resources = []
        text_lower = text.lower()
        
        for keyword in resource_keywords:
            if keyword in text_lower:
                # Try to extract the full resource name
                import re
                # Look for patterns like "the [keyword]", "[adjective] [keyword]", etc.
                patterns = [
                    rf'(?:the\s+)?(?:\w+\s+)?{keyword}(?:\s+\w+)?',
                    rf'{keyword}(?:\s+\w+)?'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text_lower)
                    for match in matches:
                        clean_match = match.strip().title()
                        if len(clean_match) > 2 and clean_match not in resources:
                            resources.append(clean_match)
                            break  # Only take the first good match per keyword
        
        return resources[:5]  # Limit to 5 resources to avoid noise

    def _ensure_context_before_decisions(self, scenario_id: int, base_time: datetime) -> None:
        """Ensure at least one context event exists before the first decision.

        If the earliest timeline item would be a decision, insert a synthetic context event
        just before it in an even-minute slot aligned with our interleaving scheme.
        """
        from datetime import timedelta
        # Import here to avoid circulars at module import time
        from app.models.event import Event, Action
        from app import db as _db

        decisions = _db.session.query(Action).filter_by(scenario_id=scenario_id, is_decision=True).order_by(Action.action_time.asc()).all()
        if not decisions:
            return
        events = _db.session.query(Event).filter_by(scenario_id=scenario_id).order_by(Event.event_time.asc()).all()

        # Build context text once
        scenario = _db.session.get(Scenario, scenario_id)
        def build_context_text(decision_name: str) -> str:
            txt = ""
            try:
                if scenario and scenario.description:
                    import re
                    first_sentence = re.split(r"(?<=[.!?])\s+", scenario.description.strip())[0]
                    txt = first_sentence[:160]
            except Exception:
                txt = ""
            if not txt:
                txt = f"Context: Situation leading to decision '{decision_name}'"
            return txt

        for decision in decisions:
            if any(ev.event_time and ev.event_time < decision.action_time for ev in events):
                continue

            seq = 0
            try:
                if decision.parameters and 'decision_sequence' in decision.parameters:
                    seq = max(int(decision.parameters.get('decision_sequence')) - 1, 0)
            except Exception:
                seq = 0

            synthetic_time = base_time + timedelta(minutes=2 * seq)
            if synthetic_time >= decision.action_time:
                synthetic_time = decision.action_time - timedelta(minutes=1)

            synthetic_event = Event(
                scenario_id=scenario_id,
                event_time=synthetic_time,
                description=build_context_text(decision.name),
                parameters={
                    'name': 'Context',
                    'event_type': 'context',
                    'synthetic': True,
                    'origin': 'system',
                    'llm_generated': False
                },
                bfo_class='BFO_0000015',
                proethica_category='event'
            )
            _db.session.add(synthetic_event)
            events.append(synthetic_event)
    
    def _create_events(self, scenario_id: int, enhanced_timeline: Dict[str, Any], characters: List[Character], base_time: datetime) -> List[Event]:
        """Create Event records grouped to precede their associated decisions with justifications."""
        
        events = []
        timeline_events = enhanced_timeline.get('timeline_events', [])
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        
        # Create character name to ID mapping
        character_map = {char.name.lower(): char.id for char in characters}

        from datetime import timedelta
        D = len(decisions)
        N = len(timeline_events)
        # Track per-group event counters
        group_event_counters = [0] * D if D > 0 else []
        for idx, timeline_event in enumerate(timeline_events):
            description = timeline_event.get('description', timeline_event.get('text', ''))
            
            # Try to find associated character
            character_id = None
            participants = timeline_event.get('participants', [])
            if participants:
                participant_name = participants[0].lower()  # Use first participant
                character_id = character_map.get(participant_name)
            
            # Create event time in even-minute slots based on sequence order
            if D > 0:
                group_index = min(int(idx * D / max(N, 1)), D - 1)
            else:
                group_index = 0
            group_id = f"group_{group_index+1}" if D > 0 else "group_1"
            intra_seq = (group_event_counters[group_index] if D > 0 else idx)
            if D > 0:
                group_event_counters[group_index] += 1
            # Offset groups by 10 minutes each; events at even offsets
            event_time = base_time + timedelta(minutes=(group_index * 10 + 2 * intra_seq))
            
            event = Event(
                scenario_id=scenario_id,
                character_id=character_id,
                description=description,
                event_time=event_time,
                parameters={
                    'sequence_number': timeline_event.get('sequence_number', idx),
                    'event_type': timeline_event.get('event_type', 'action'),
                    'section_source': timeline_event.get('section_source', ''),
                    'extraction_method': timeline_event.get('extraction_method', 'llm_semantic'),
                    'participants': timeline_event.get('participants', []),
                    'timeline_sequence': 2 * idx,
                    'origin': 'llm',
                    'llm_generated': True,
                    'group_index': group_index,
                    'group_id': group_id,
                    'intra_group_sequence': intra_seq,
                    'justification': f"Provides context for decision group {group_index+1}",
                    'justification_source': {'method': 'heuristic'}
                },
                bfo_class='BFO_0000015',  # process
                proethica_category='event',
                ontology_uri=timeline_event.get('ontology_uri')
            )
            
            events.append(event)
        
        return events
    
    def _create_actions(self, scenario_id: int, enhanced_timeline: Dict[str, Any], characters: List[Character], base_time: datetime) -> List[Action]:
        """Create Action records from enhanced_decisions with interleaved timestamps and LLM origin flags."""
        
        actions = []
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        
        # Create character name to ID mapping
        character_map = {char.name.lower(): char.id for char in characters}

        from datetime import timedelta
        # Determine how many events belong to each decision group to place the decision at the end
        D = len(decisions)
        timeline_events = enhanced_timeline.get('timeline_events', [])
        N = len(timeline_events)
        events_per_group = [0] * D if D > 0 else []
        if D > 0 and N > 0:
            for s in range(N):
                g = min(int(s * D / max(N, 1)), D - 1)
                events_per_group[g] += 1

        for i, decision in enumerate(decisions):
            name = decision.title or f"Decision {i+1}"
            description = decision.question
            
            # Try to find associated character (usually the first participant mentioned)
            character_id = None
            context_text = decision.context.lower()
            for char_name, char_id in character_map.items():
                if char_name in context_text:
                    character_id = char_id
                    break
            
            # Create decision options from enhanced decision
            options = self._create_decision_options(decision, enhanced_timeline)
            
            group_index = i
            group_id = f"group_{i+1}"
            intra_group_sequence = (events_per_group[i] if i < len(events_per_group) else 0)
            action = Action(
                scenario_id=scenario_id,
                character_id=character_id,
                name=name,
                description=description,
                is_decision=True,
                options=options,
                action_type='ethical_decision',  # Legacy field
                bfo_class='BFO_0000016',  # disposition (decision)
                proethica_category='action',  # Could be 'decision' based on classification
                ontology_uri=getattr(decision, 'ontology_uri', None),
                parameters={
                    'question': decision.question,
                    'context': decision.context,
                    'section_source': decision.section_source,
                    'temporal_triggers': decision.temporal_triggers,
                    'ontology_categories': decision.ontology_categories,
                    'evidence_text': decision.evidence_text,
                    'decision_sequence': i + 1,
                    'timeline_sequence': 2 * i + 1,
                    'origin': 'llm',
                    'llm_generated': True,
                    'group_index': group_index,
                    'group_id': group_id,
                    'intra_group_sequence': intra_group_sequence,
                    'justification': f"Decision follows from the preceding context for group {i+1}",
                    'justification_source': {'method': 'heuristic'}
                },
                action_time=(base_time + timedelta(minutes=(group_index * 10 + 2 * intra_group_sequence + 1)))
            )
            
            actions.append(action)
        
        return actions
    
    def _create_decision_options(self, decision, enhanced_timeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create decision options from enhanced decision."""
        
        # Start with context-appropriate options
        question_text = decision.question.lower()
        
        if 'disclose' in question_text or 'ai' in question_text:
            return [
                {
                    'id': 'full_disclosure',
                    'label': 'Full Disclosure',
                    'description': 'Explicitly disclose all AI assistance used in the analysis',
                    'color': 'green',
                    'ethical_analysis': 'Maintains professional integrity and client trust through complete transparency',
                    'nspe_references': ['I.4 - Act with honesty and integrity']
                },
                {
                    'id': 'general_disclosure',
                    'label': 'General Disclosure',
                    'description': 'Provide general statement about computational tools used',
                    'color': 'yellow', 
                    'ethical_analysis': 'Provides transparency while maintaining focus on engineering analysis',
                    'nspe_references': ['III.1 - Client relations']
                },
                {
                    'id': 'no_disclosure',
                    'label': 'No Disclosure',
                    'description': 'Continue without explicitly mentioning AI assistance',
                    'color': 'red',
                    'ethical_analysis': 'May compromise transparency expectations and professional integrity',
                    'nspe_references': ['I.4 - Honesty requirement']
                }
            ]
        
        elif 'safety' in question_text or 'public' in question_text:
            return [
                {
                    'id': 'prioritize_safety',
                    'label': 'Prioritize Public Safety',
                    'description': 'Take all necessary measures to ensure public welfare',
                    'color': 'green',
                    'ethical_analysis': 'Aligns with the paramount obligation to protect public safety',
                    'nspe_references': ['I.1 - Hold paramount public safety and welfare']
                },
                {
                    'id': 'seek_guidance',
                    'label': 'Seek Professional Guidance', 
                    'description': 'Consult with supervisors or professional ethics committee',
                    'color': 'yellow',
                    'ethical_analysis': 'Demonstrates professional responsibility and ensures informed decision-making',
                    'nspe_references': ['II.1 - Professional development and guidance']
                },
                {
                    'id': 'document_concerns',
                    'label': 'Document and Monitor',
                    'description': 'Document concerns while continuing with enhanced monitoring',
                    'color': 'yellow',
                    'ethical_analysis': 'Creates accountability while allowing measured progress',
                    'nspe_references': ['II.5 - Maintain records and documentation']
                }
            ]
        
        else:
            # Generic options for other types of decisions
            return [
                {
                    'id': 'ethical_approach',
                    'label': 'Take Ethical Approach',
                    'description': 'Prioritize ethical considerations and professional standards',
                    'color': 'green', 
                    'ethical_analysis': 'Upholds professional integrity and ethical obligations',
                    'nspe_references': ['I.1 - Public welfare', 'I.4 - Honesty and integrity']
                },
                {
                    'id': 'balanced_approach',
                    'label': 'Seek Balanced Solution',
                    'description': 'Find a solution that addresses multiple stakeholder concerns',
                    'color': 'yellow',
                    'ethical_analysis': 'Attempts to balance competing interests and obligations',
                    'nspe_references': ['III.1 - Client relations', 'I.1 - Public welfare']
                },
                {
                    'id': 'pragmatic_approach',
                    'label': 'Take Pragmatic Approach',
                    'description': 'Focus on practical considerations and contractual obligations',
                    'color': 'orange',
                    'ethical_analysis': 'Prioritizes practical outcomes but may compromise ethical ideals',
                    'nspe_references': ['III.1 - Be faithful to client or employer']
                }
            ]
    
    def _build_ontology_summary(self, enhanced_timeline: Dict[str, Any], characters: List[Character], 
                              resources: List[Resource], events: List[Event], actions: List[Action]) -> Dict[str, List[str]]:
        """Build ontology summary showing all 9 categories."""
        
        summary = {}
        
        # Role - from characters
        summary['Role'] = [char.role for char in characters if char.role]
        
        # Resource - from resources
        summary['Resource'] = [res.name for res in resources]
        
        # Event - from events 
        summary['Event'] = [f"{event.description[:30]}..." for event in events]
        
        # Action - from actions
        summary['Action'] = [action.name for action in actions]
        
        # Extract other categories from enhanced decisions
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        for category in ['Principle', 'Obligation', 'State', 'Capability', 'Constraint']:
            category_items = []
            for decision in decisions:
                ontology_cats = getattr(decision, 'ontology_categories', {})
                if isinstance(ontology_cats, dict) and category.lower() in ontology_cats:
                    category_items.extend([item['label'] for item in ontology_cats[category.lower()]])
            summary[category] = list(set(category_items))
        
        # Ensure all 9 categories are present
        for category in ['Role', 'Principle', 'Obligation', 'State', 'Resource', 'Action', 'Event', 'Capability', 'Constraint']:
            if category not in summary:
                summary[category] = []
        
        return summary