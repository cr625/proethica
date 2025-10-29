"""
Stage 3: Participant Mapping

Transforms extracted role entities into scenario participants (characters) with:
- Character profiles and backgrounds
- Motivations and goals
- Character arcs through the timeline
- Relationships with other participants

Uses role extraction data (from Pass 1) which already includes:
- caseInvolvement: narrative of character's actions
- hasActiveObligation: duties and responsibilities
- hasEthicalTension: internal/external conflicts
- relationships: connections to other roles

Documentation: docs/SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md (Stage 3)
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.utils.llm_utils import get_llm_client
from app.models import db

logger = logging.getLogger(__name__)


@dataclass
class ParticipantProfile:
    """
    Character profile for a scenario participant.

    Built from extracted role entities with LLM enhancement.
    """
    # Identity
    id: str  # Entity URI
    name: str  # Role label (e.g., "Engineer L", "Client X")
    role_type: str  # Professional role (e.g., "Stormwater Control Design Specialist")

    # Profile
    background: str  # Professional background and experience
    expertise: List[str]  # Areas of expertise
    qualifications: List[str]  # Licenses, certifications

    # Character arc
    motivations: List[str]  # What drives this character
    goals: List[str]  # What they want to achieve
    obligations: List[str]  # What duties they must fulfill
    constraints: List[str]  # What limits their actions

    # Narrative elements
    ethical_tensions: List[str]  # Internal/external conflicts
    character_arc: str  # How this character changes/is challenged
    narrative_role: str  # Protagonist, antagonist, supporting, etc.

    # Relationships
    relationships: List[Dict[str, str]]  # Connections to other participants

    # Metadata
    source_uri: str  # Original role entity URI
    extracted_data: Dict[str, Any]  # Original role RDF data

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'role_type': self.role_type,
            'background': self.background,
            'expertise': self.expertise,
            'qualifications': self.qualifications,
            'motivations': self.motivations,
            'goals': self.goals,
            'obligations': self.obligations,
            'constraints': self.constraints,
            'ethical_tensions': self.ethical_tensions,
            'character_arc': self.character_arc,
            'narrative_role': self.narrative_role,
            'relationships': self.relationships
        }


@dataclass
class ParticipantMappingResult:
    """Result of participant mapping stage."""
    participants: List[ParticipantProfile]
    relationship_map: Dict[str, List[str]]  # participant_id -> [connected_participant_ids]
    protagonist_id: Optional[str]  # Primary decision-maker
    supporting_cast: List[str]  # Supporting character IDs
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    teaching_notes: Optional[Dict] = None  # Pedagogical guidance for instructors
    llm_enrichment: Optional[Dict] = None  # Full LLM enhancement data

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        result = {
            'participant_count': len(self.participants),
            'participants': [p.to_dict() for p in self.participants],
            'relationship_map': self.relationship_map,
            'protagonist_id': self.protagonist_id,
            'supporting_cast': self.supporting_cast
        }

        # Include teaching notes if available
        if self.teaching_notes:
            result['teaching_notes'] = self.teaching_notes

        return result


class ParticipantMapper:
    """
    Stage 3: Transform roles into scenario participants.

    Takes role entities from Pass 1 extraction and enriches them into
    full character profiles suitable for interactive teaching scenarios.
    """

    def __init__(self):
        """Initialize participant mapper with LLM client."""
        self.llm_client = get_llm_client()
        logger.info("[Participant Mapper] Initialized")

    def map_participants(
        self,
        roles: List[Any],  # RDFEntity objects from data collection
        timeline_data: Optional[Dict] = None
    ) -> ParticipantMappingResult:
        """
        Map role entities to scenario participants.

        Args:
            roles: List of RDFEntity objects with type 'Role' or 'Roles'
            timeline_data: Optional timeline data for arc mapping

        Returns:
            ParticipantMappingResult with enriched character profiles
        """
        logger.info(f"[Participant Mapper] Mapping {len(roles)} roles to participants")

        if not roles:
            logger.warning("[Participant Mapper] No roles provided")
            return ParticipantMappingResult(
                participants=[],
                relationship_map={},
                protagonist_id=None,
                supporting_cast=[]
            )

        # Extract participant data from roles
        participants = []
        for role in roles:
            try:
                participant = self._create_participant_profile(role, timeline_data)
                participants.append(participant)
                logger.debug(f"[Participant Mapper] Created profile for {participant.name}")
            except Exception as e:
                logger.error(f"[Participant Mapper] Error creating participant from role {role.label}: {e}")
                continue

        # Build relationship map
        relationship_map = self._build_relationship_map(participants)

        # Identify protagonist (primary decision-maker with most obligations/tensions)
        protagonist_id = self._identify_protagonist(participants)

        # Identify supporting cast
        supporting_cast = [p.id for p in participants if p.id != protagonist_id]

        # Enhance with LLM if needed (optional enrichment)
        teaching_notes = None
        llm_enrichment = None
        if self.llm_client and len(participants) > 0:
            try:
                enhanced = self._enhance_with_llm(participants, relationship_map)
                if enhanced:
                    participants = enhanced.get('participants', participants)
                    teaching_notes = enhanced.get('teaching_notes')
                    llm_enrichment = enhanced.get('llm_response')
            except Exception as e:
                logger.warning(f"[Participant Mapper] LLM enhancement failed: {e}")

        result = ParticipantMappingResult(
            participants=participants,
            relationship_map=relationship_map,
            protagonist_id=protagonist_id,
            supporting_cast=supporting_cast
        )

        # Store teaching notes if available
        if teaching_notes:
            result.teaching_notes = teaching_notes
        if llm_enrichment:
            result.llm_enrichment = llm_enrichment

        logger.info(
            f"[Participant Mapper] Mapped {len(participants)} participants, "
            f"protagonist: {protagonist_id}"
        )

        return result

    def _create_participant_profile(
        self,
        role: Any,  # RDFEntity
        timeline_data: Optional[Dict]
    ) -> ParticipantProfile:
        """
        Create participant profile from role entity.

        Args:
            role: RDFEntity with role data
            timeline_data: Optional timeline context

        Returns:
            ParticipantProfile
        """
        # Parse RDF JSON-LD
        rdf_data = role.rdf_json_ld if hasattr(role, 'rdf_json_ld') else {}
        properties = rdf_data.get('properties', {})

        # Extract basic identity
        name = role.label
        role_type = self._extract_role_type(rdf_data)

        # Extract background from definition or properties
        background = role.definition or properties.get('definition', [''])[0]
        if not background and 'hasExperience' in properties:
            background = '; '.join(properties['hasExperience'])

        # Extract expertise
        expertise = []
        if 'hasSpecialization' in properties:
            expertise.extend(properties['hasSpecialization'])
        if 'professionalScope' in properties:
            scopes = properties['professionalScope']
            if isinstance(scopes, list) and len(scopes) > 0:
                # Split comma-separated scopes
                expertise.extend(scopes[0].split(', ') if isinstance(scopes[0], str) else scopes)

        # Extract qualifications
        qualifications = []
        if 'hasLicense' in properties:
            qualifications.extend(properties['hasLicense'])
        if 'typicalQualification' in properties:
            qualifications.extend(properties['typicalQualification'])

        # Extract motivations from case involvement and financial status
        motivations = self._extract_motivations(properties)

        # Extract goals (implicit from obligations and involvement)
        goals = self._extract_goals(properties)

        # Extract obligations
        obligations = properties.get('hasActiveObligation', [])
        if isinstance(obligations, str):
            obligations = [obligations]

        # Extract constraints (financial, professional, etc.)
        constraints = self._extract_constraints(properties)

        # Extract ethical tensions
        tensions = properties.get('hasEthicalTension', [])
        if isinstance(tensions, str):
            tensions = [tensions]
        ethical_tensions = tensions

        # Generate character arc
        character_arc = self._generate_character_arc(properties, timeline_data)

        # Determine narrative role
        narrative_role = self._determine_narrative_role(
            name,
            obligations,
            ethical_tensions,
            properties
        )

        # Extract relationships
        relationships = rdf_data.get('relationships', [])

        return ParticipantProfile(
            id=role.uri,
            name=name,
            role_type=role_type,
            background=background,
            expertise=expertise,
            qualifications=qualifications,
            motivations=motivations,
            goals=goals,
            obligations=obligations,
            constraints=constraints,
            ethical_tensions=ethical_tensions,
            character_arc=character_arc,
            narrative_role=narrative_role,
            relationships=relationships,
            source_uri=role.uri,
            extracted_data=rdf_data
        )

    def _extract_role_type(self, rdf_data: Dict) -> str:
        """Extract professional role type from RDF data."""
        types = rdf_data.get('types', [])
        if types:
            # Get last part of URI after #
            role_uri = types[0] if isinstance(types, list) else types
            if '#' in role_uri:
                return role_uri.split('#')[-1].replace('_', ' ')

        # Fallback to label
        return rdf_data.get('label', 'Unknown Role')

    def _extract_motivations(self, properties: Dict) -> List[str]:
        """Extract character motivations from properties."""
        motivations = []

        # Professional motivations from involvement
        involvement = properties.get('caseInvolvement', [])
        if involvement:
            # Infer motivations from actions
            involvement_text = ' '.join(involvement) if isinstance(involvement, list) else involvement
            if 'protect' in involvement_text.lower():
                motivations.append("Protect public safety and welfare")
            if 'comply' in involvement_text.lower() or 'standard' in involvement_text.lower():
                motivations.append("Maintain professional standards and compliance")

        # Financial motivations
        if 'hasFinancialStatus' in properties:
            status = properties['hasFinancialStatus']
            if 'setback' in str(status).lower() or 'limitation' in str(status).lower():
                motivations.append("Overcome financial constraints")

        # If no specific motivations found, add generic professional motivation
        if not motivations:
            motivations.append("Fulfill professional responsibilities")

        return motivations

    def _extract_goals(self, properties: Dict) -> List[str]:
        """Extract character goals from properties."""
        goals = []

        # Goals from active obligations (what they need to accomplish)
        obligations = properties.get('hasActiveObligation', [])
        if obligations:
            # Take first 2-3 most concrete obligations as goals
            if isinstance(obligations, list):
                goals.extend(obligations[:3])
            else:
                goals.append(obligations)

        # Goals from case involvement (desired outcomes)
        involvement = properties.get('caseInvolvement', [])
        if involvement:
            involvement_text = ' '.join(involvement) if isinstance(involvement, list) else involvement
            if 'complete' in involvement_text.lower() or 'design' in involvement_text.lower():
                goals.append("Successfully complete the project")

        return goals

    def _extract_constraints(self, properties: Dict) -> List[str]:
        """Extract constraints limiting character's actions."""
        constraints = []

        # Financial constraints
        if 'hasFinancialStatus' in properties:
            status = properties['hasFinancialStatus']
            if 'setback' in str(status).lower() or 'limitation' in str(status).lower():
                constraints.append("Limited budget and financial resources")

        # Professional constraints from involvement
        involvement = properties.get('caseInvolvement', [])
        if involvement:
            involvement_text = ' '.join(involvement) if isinstance(involvement, list) else involvement
            if 'resist' in involvement_text.lower():
                constraints.append("Client resistance to recommendations")
            if 'suspend' in involvement_text.lower() or 'delay' in involvement_text.lower():
                constraints.append("Project delays and interruptions")

        return constraints

    def _generate_character_arc(
        self,
        properties: Dict,
        timeline_data: Optional[Dict]
    ) -> str:
        """Generate character arc narrative."""
        involvement = properties.get('caseInvolvement', [])
        if not involvement:
            return "Character arc to be determined"

        involvement_text = ' '.join(involvement) if isinstance(involvement, list) else involvement

        # Create a narrative summary of how character progresses
        arc_parts = []
        if 'contract' in involvement_text.lower() or 'began' in involvement_text.lower():
            arc_parts.append("Initially engaged")
        if 'suspend' in involvement_text.lower() or 'challenge' in involvement_text.lower():
            arc_parts.append("faced challenges")
        if 'resume' in involvement_text.lower() or 'additional' in involvement_text.lower():
            arc_parts.append("persisted with additional efforts")
        if 'advise' in involvement_text.lower() or 'recommend' in involvement_text.lower():
            arc_parts.append("took professional stance")

        if arc_parts:
            return f"{', '.join(arc_parts)} throughout the case"

        return involvement_text[:200] if len(involvement_text) > 200 else involvement_text

    def _determine_narrative_role(
        self,
        name: str,
        obligations: List[str],
        ethical_tensions: List[str],
        properties: Dict
    ) -> str:
        """Determine character's narrative role in scenario."""
        # Engineer roles with most obligations/tensions are typically protagonists
        if 'engineer' in name.lower():
            if len(obligations) > 2 or len(ethical_tensions) > 0:
                return "protagonist"
            return "supporting"

        # Clients/stakeholders are typically supporting or antagonist
        if 'client' in name.lower() or 'stakeholder' in properties.get('hasEntityType', [''])[0].lower():
            # If they resist or create tension, they're antagonist
            involvement = properties.get('caseInvolvement', [])
            involvement_text = ' '.join(involvement) if isinstance(involvement, list) else involvement
            if 'resist' in involvement_text.lower() or 'insist' in involvement_text.lower():
                return "antagonist"
            return "supporting"

        return "supporting"

    def _build_relationship_map(
        self,
        participants: List[ParticipantProfile]
    ) -> Dict[str, List[str]]:
        """Build bidirectional relationship map between participants."""
        relationship_map = {p.id: [] for p in participants}

        # Build URI to ID mapping
        uri_to_id = {p.source_uri: p.id for p in participants}

        for participant in participants:
            for rel in participant.relationships:
                target_uri = rel.get('target_uri', '')
                if target_uri in uri_to_id:
                    target_id = uri_to_id[target_uri]
                    # Add bidirectional relationship
                    if target_id not in relationship_map[participant.id]:
                        relationship_map[participant.id].append(target_id)
                    if participant.id not in relationship_map[target_id]:
                        relationship_map[target_id].append(participant.id)

        return relationship_map

    def _identify_protagonist(
        self,
        participants: List[ParticipantProfile]
    ) -> Optional[str]:
        """
        Identify the protagonist (primary decision-maker).

        Heuristics:
        - Has narrative_role == 'protagonist'
        - Has most obligations
        - Has most ethical tensions
        - Is an engineer (professional role)
        """
        if not participants:
            return None

        # Score each participant
        scores = []
        for p in participants:
            score = 0
            if p.narrative_role == 'protagonist':
                score += 10
            score += len(p.obligations) * 2
            score += len(p.ethical_tensions) * 3
            if 'engineer' in p.name.lower():
                score += 5
            scores.append((score, p.id))

        # Return participant with highest score
        scores.sort(reverse=True)
        return scores[0][1]

    def _enhance_with_llm(
        self,
        participants: List[ParticipantProfile],
        relationship_map: Dict[str, List[str]]
    ) -> Optional[Dict]:
        """
        LLM enhancement of participant profiles.

        Uses Claude to:
        - Enrich character backgrounds with teaching-relevant details
        - Enhance character arc narratives with pedagogical framing
        - Suggest additional motivations that illuminate ethical tensions
        - Provide teaching notes for instructors

        Args:
            participants: List of participant profiles
            relationship_map: Relationship connections

        Returns:
            Enhanced participant data or None if enhancement fails
        """
        try:
            # Create prompt for LLM
            prompt = self._create_enhancement_prompt(participants, relationship_map)

            # Call LLM
            logger.info("[Participant Mapper] Calling LLM for character enhancement...")
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text from response
            response_text = response.content[0].text

            # Parse JSON response
            enhanced_data = json.loads(response_text)

            # Apply enhancements to participants
            for participant in participants:
                participant_enhancements = enhanced_data.get('participants', {}).get(participant.id, {})

                if participant_enhancements:
                    # Enhance character arc with fuller narrative
                    if 'enhanced_arc' in participant_enhancements:
                        participant.character_arc = participant_enhancements['enhanced_arc']

                    # Add teaching-relevant background details
                    if 'enhanced_background' in participant_enhancements:
                        participant.background = participant_enhancements['enhanced_background']

                    # Merge suggested motivations
                    if 'suggested_motivations' in participant_enhancements:
                        new_motivations = participant_enhancements['suggested_motivations']
                        participant.motivations.extend([m for m in new_motivations if m not in participant.motivations])

                    logger.debug(f"[Participant Mapper] Enhanced {participant.name}")

            logger.info(f"[Participant Mapper] LLM enhancement complete for {len(participants)} participants")

            return {
                'participants': participants,
                'llm_response': enhanced_data,
                'teaching_notes': enhanced_data.get('teaching_notes', {})
            }

        except json.JSONDecodeError as e:
            logger.error(f"[Participant Mapper] Failed to parse LLM JSON response: {e}")
            logger.debug(f"[Participant Mapper] Raw response: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"[Participant Mapper] LLM enhancement error: {e}")
            return None

    def _create_enhancement_prompt(
        self,
        participants: List[ParticipantProfile],
        relationship_map: Dict[str, List[str]]
    ) -> str:
        """Create prompt for LLM enhancement with JSON output."""
        import json

        # Build participant summaries
        participant_summaries = []
        for p in participants:
            participant_summaries.append({
                'id': p.id,
                'name': p.name,
                'role_type': p.role_type,
                'background': p.background,
                'motivations': p.motivations,
                'goals': p.goals[:3] if len(p.goals) > 3 else p.goals,
                'obligations': p.obligations[:3] if len(p.obligations) > 3 else p.obligations,
                'ethical_tensions': p.ethical_tensions,
                'character_arc': p.character_arc,
                'narrative_role': p.narrative_role
            })

        prompt = f"""You are enhancing character profiles for an interactive engineering ethics teaching scenario.

**Input Data**:
{json.dumps(participant_summaries, indent=2)}

**Task**: For each participant, enhance their profile with teaching-relevant details:
1. **Enhanced Arc**: Rewrite character_arc as a compelling 2-3 sentence narrative that:
   - Shows how the character's professional obligations create tension
   - Highlights the ethical dilemma they face
   - Makes the character relatable to students learning professional ethics

2. **Enhanced Background**: Expand background (if minimal) with realistic professional details that:
   - Establish credibility and expertise
   - Connect to the ethical tensions they'll face
   - Stay grounded in the extracted data (don't invent contradictory facts)

3. **Suggested Motivations**: Identify 1-2 additional motivations that:
   - Illuminate why this character's choices matter ethically
   - Make ethical tensions more vivid for teaching
   - Connect to NSPE Code principles

4. **Teaching Notes**: For the protagonist only, provide instructor guidance:
   - What ethical principle is most challenged for this character?
   - What makes this character's dilemma pedagogically valuable?
   - What discussion questions emerge from their arc?

**Output Format** (JSON only, no markdown):
{{
  "participants": {{
    "participant_id": {{
      "enhanced_arc": "2-3 sentence narrative...",
      "enhanced_background": "Expanded background if needed, or null",
      "suggested_motivations": ["motivation 1", "motivation 2"]
    }}
  }},
  "teaching_notes": {{
    "protagonist_id": {{
      "key_principle": "Principle name",
      "pedagogical_value": "Why this character's journey teaches ethics",
      "discussion_questions": ["Q1", "Q2", "Q3"]
    }}
  }}
}}

Respond with valid JSON only."""

        return prompt

    def save_to_database(
        self,
        case_id: int,
        result: ParticipantMappingResult,
        llm_model: Optional[str] = None
    ) -> int:
        """
        Save participant mapping results to database.

        Args:
            case_id: Case ID
            result: ParticipantMappingResult with participants and relationships
            llm_model: LLM model used for enhancement

        Returns:
            Number of participants saved
        """
        from sqlalchemy import text

        try:
            # Clear existing participants for this case
            delete_query = text("""
                DELETE FROM scenario_participants WHERE case_id = :case_id
            """)
            db.session.execute(delete_query, {'case_id': case_id})

            # Clear existing relationships
            delete_rel_query = text("""
                DELETE FROM scenario_relationship_map WHERE case_id = :case_id
            """)
            db.session.execute(delete_rel_query, {'case_id': case_id})

            # Insert participants
            insert_query = text("""
                INSERT INTO scenario_participants (
                    case_id, participant_id, source_role_uri, name, role_type,
                    background, expertise, qualifications,
                    motivations, goals, obligations, constraints,
                    ethical_tensions, character_arc, narrative_role,
                    relationships, llm_enhanced, llm_enrichment, llm_model
                ) VALUES (
                    :case_id, :participant_id, :source_role_uri, :name, :role_type,
                    :background, :expertise, :qualifications,
                    :motivations, :goals, :obligations, :constraints,
                    :ethical_tensions, :character_arc, :narrative_role,
                    :relationships, :llm_enhanced, :llm_enrichment, :llm_model
                )
            """)

            saved_count = 0
            for participant in result.participants:
                # Prepare JSONB fields
                params = {
                    'case_id': case_id,
                    'participant_id': participant.id,
                    'source_role_uri': participant.source_uri,
                    'name': participant.name,
                    'role_type': participant.role_type,
                    'background': participant.background,
                    'expertise': json.dumps(participant.expertise),
                    'qualifications': json.dumps(participant.qualifications),
                    'motivations': json.dumps(participant.motivations),
                    'goals': json.dumps(participant.goals),
                    'obligations': json.dumps(participant.obligations),
                    'constraints': json.dumps(participant.constraints),
                    'ethical_tensions': json.dumps(participant.ethical_tensions),
                    'character_arc': participant.character_arc,
                    'narrative_role': participant.narrative_role,
                    'relationships': json.dumps(participant.relationships),
                    'llm_enhanced': result.llm_enrichment is not None,
                    'llm_enrichment': json.dumps(result.llm_enrichment) if result.llm_enrichment else None,
                    'llm_model': llm_model
                }

                db.session.execute(insert_query, params)
                saved_count += 1

            # Insert relationships
            insert_rel_query = text("""
                INSERT INTO scenario_relationship_map (
                    case_id, source_participant_id, target_participant_id,
                    relationship_type, is_bidirectional
                ) VALUES (
                    :case_id, :source_participant_id, :target_participant_id,
                    :relationship_type, :is_bidirectional
                )
            """)

            for source_id, target_ids in result.relationship_map.items():
                for target_id in target_ids:
                    # Avoid duplicate bidirectional relationships
                    # Only insert if source < target (alphabetically) to prevent duplicates
                    if source_id < target_id:
                        rel_params = {
                            'case_id': case_id,
                            'source_participant_id': source_id,
                            'target_participant_id': target_id,
                            'relationship_type': 'connected',  # Generic type
                            'is_bidirectional': True
                        }
                        db.session.execute(insert_rel_query, rel_params)

            db.session.commit()

            logger.info(f"[Participant Mapper] Saved {saved_count} participants to database for case {case_id}")
            return saved_count

        except Exception as e:
            logger.error(f"[Participant Mapper] Error saving to database: {e}")
            db.session.rollback()
            raise
