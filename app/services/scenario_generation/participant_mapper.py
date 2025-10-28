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
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.utils.llm_utils import get_llm_client

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

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'participant_count': len(self.participants),
            'participants': [p.to_dict() for p in self.participants],
            'relationship_map': self.relationship_map,
            'protagonist_id': self.protagonist_id,
            'supporting_cast': self.supporting_cast
        }


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
        if self.llm_client and len(participants) > 0:
            try:
                enhanced = self._enhance_with_llm(participants, relationship_map)
                if enhanced:
                    participants = enhanced.get('participants', participants)
            except Exception as e:
                logger.warning(f"[Participant Mapper] LLM enhancement failed: {e}")

        result = ParticipantMappingResult(
            participants=participants,
            relationship_map=relationship_map,
            protagonist_id=protagonist_id,
            supporting_cast=supporting_cast
        )

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
        Optional LLM enhancement of participant profiles.

        Uses Claude to:
        - Enrich character backgrounds
        - Suggest additional motivations
        - Enhance character arc narratives

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
            response = self.llm_client.generate(prompt, max_tokens=2000)

            # For now, just log the response
            # TODO: Parse and apply enhancements
            logger.debug(f"[Participant Mapper] LLM enhancement response: {response[:200]}...")

            return None  # No enhancements applied yet

        except Exception as e:
            logger.error(f"[Participant Mapper] LLM enhancement error: {e}")
            return None

    def _create_enhancement_prompt(
        self,
        participants: List[ParticipantProfile],
        relationship_map: Dict[str, List[str]]
    ) -> str:
        """Create prompt for LLM enhancement."""
        prompt_parts = [
            "You are analyzing participants in an engineering ethics case for educational purposes.",
            "Review these character profiles and suggest narrative enhancements:",
            ""
        ]

        for p in participants:
            prompt_parts.append(f"## {p.name} ({p.role_type})")
            prompt_parts.append(f"Background: {p.background}")
            prompt_parts.append(f"Motivations: {', '.join(p.motivations)}")
            prompt_parts.append(f"Obligations: {', '.join(p.obligations[:3])}")
            prompt_parts.append(f"Tensions: {', '.join(p.ethical_tensions)}")
            prompt_parts.append(f"Arc: {p.character_arc}")
            prompt_parts.append("")

        prompt_parts.append("Provide brief character arc enhancements (2-3 sentences each):")

        return "\n".join(prompt_parts)
