"""
Participant Mapper - Step 5 Stage 3

Maps role entities to rich scenario participants with LLM enhancement.

Implements participant mapping as described in CLAUDE.md:
- Extracts participant motivations from case context
- Identifies ethical tensions each participant faces
- Maps relationships between participants
- Generates character arcs showing development through case

Uses new centralized LLM manager for consistent handling.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.llm import get_llm_manager
from app.models import Document

logger = logging.getLogger(__name__)


class ParticipantMapper:
    """
    Maps role entities to scenario participants with LLM enhancement.

    Takes basic role entities from extraction and enriches them with:
    - Background and professional context
    - Motivations and goals
    - Ethical tensions and conflicts
    - Relationships with other participants
    - Character development arc through the case
    """

    def __init__(self):
        """Initialize participant mapper with LLM manager."""
        self.llm = get_llm_manager()

    def create_participants(
        self,
        case_id: int,
        roles: List[Any],
        timeline: Optional[Any] = None,
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Create enhanced participant profiles from role entities.

        Args:
            case_id: Case ID for context
            roles: List of Role entities from extraction
            timeline: Optional timeline for temporal context
            db_session: Optional database session for queries

        Returns:
            List of participant dictionaries with rich metadata
        """
        if not roles:
            logger.warning(f"[Participant Mapper] No roles provided for case {case_id}")
            return []

        logger.info(f"[Participant Mapper] Creating participants from {len(roles)} roles for case {case_id}")

        # Get case text for context
        case_text = self._get_case_text(case_id, db_session)
        if not case_text:
            logger.error(f"[Participant Mapper] Could not load case text for {case_id}")
            return []

        # Build LLM prompt
        prompt = self._build_participant_prompt(roles, case_text, timeline)

        # Call LLM
        try:
            response = self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system="You are analyzing an engineering ethics case to create detailed participant profiles for teaching purposes.",
                max_tokens=4000,
                metadata={
                    "stage": "participant_mapping",
                    "case_id": case_id,
                    "role_count": len(roles)
                }
            )

            logger.info(f"[Participant Mapper] LLM response received ({response.usage.total_tokens} tokens)")

            # Parse response
            participants = self._parse_participant_response(response.text, roles, case_id)

            logger.info(f"[Participant Mapper] Created {len(participants)} participant profiles")

            # Log usage for monitoring
            logger.info(
                f"[Participant Mapper] Token usage: {response.usage.input_tokens} in, "
                f"{response.usage.output_tokens} out, "
                f"cost: ${response.usage.estimated_cost_usd:.4f}"
            )

            return participants

        except Exception as e:
            logger.error(f"[Participant Mapper] Error creating participants: {str(e)}", exc_info=True)
            return []

    def _get_case_text(self, case_id: int, db_session: Optional[Session] = None) -> Optional[str]:
        """
        Get case text for context.

        Args:
            case_id: Case ID
            db_session: Optional database session

        Returns:
            Case text (Facts + Discussion sections) or None
        """
        try:
            # Query for case document
            if db_session:
                case = db_session.query(Document).filter_by(id=case_id).first()
            else:
                case = Document.query.get(case_id)

            if not case:
                return None

            # Combine Facts and Discussion sections
            sections = []
            if hasattr(case, 'facts') and case.facts:
                sections.append(f"FACTS:\n{case.facts}")
            if hasattr(case, 'discussion') and case.discussion:
                sections.append(f"DISCUSSION:\n{case.discussion}")

            return "\n\n".join(sections) if sections else case.content

        except Exception as e:
            logger.error(f"[Participant Mapper] Error loading case text: {str(e)}")
            return None

    def _build_participant_prompt(
        self,
        roles: List[Any],
        case_text: str,
        timeline: Optional[Any] = None
    ) -> str:
        """
        Build LLM prompt for participant extraction.

        Uses short IDs instead of full URIs to avoid prompt bloat
        (lesson from CLAUDE.md: URIs cause massive overhead).

        Args:
            roles: List of role entities
            case_text: Full case text for context
            timeline: Optional timeline with actions/events

        Returns:
            Prompt string for LLM
        """
        # Limit roles to avoid excessive prompt size (use first 15)
        limited_roles = roles[:15]

        # Build role descriptions with short IDs (not URIs)
        role_descriptions = []
        for idx, role in enumerate(limited_roles):
            label = getattr(role, 'label', getattr(role, 'entity_label', 'Unknown'))
            definition = getattr(role, 'definition', getattr(role, 'entity_definition', 'No description'))

            role_descriptions.append(f"  r{idx}: {label}\n    Definition: {definition}")

        # Truncate case text to avoid excessive tokens (use first 3000 chars)
        case_excerpt = case_text[:3000]
        if len(case_text) > 3000:
            case_excerpt += "\n\n[... case continues ...]"

        # Build timeline context if available
        timeline_context = ""
        if timeline and hasattr(timeline, 'entries'):
            timeline_context = f"\nTIMELINE CONTEXT:\n{len(timeline.entries)} timepoints identified\n"
            if hasattr(timeline, 'phases'):
                timeline_context += f"Phases: {', '.join([p.name for p in timeline.phases[:5]])}\n"

        prompt = f"""
Analyze this engineering ethics case and create detailed participant profiles for teaching purposes.

ROLES IDENTIFIED:
{chr(10).join(role_descriptions)}
{timeline_context}
CASE TEXT (excerpt):
{case_excerpt}

For each role that plays a significant part in the case, create a participant profile with:

1. **Name/Identifier**: How they're referred to in the case (e.g., "Engineer A", "Client X", "Supervisor")
2. **Title**: Professional role/position
3. **Background**: Professional experience, expertise level, relevant context
4. **Motivations**: What drives their decisions and actions (list 2-4 motivations)
5. **Ethical Tensions**: Competing obligations or values they face (list 2-4 tensions)
6. **Character Arc**: How they develop or change through the case
7. **Key Relationships**: Their connections to other participants

GUIDELINES:
- Focus on participants who make decisions or face ethical dilemmas
- Extract motivations and tensions from case text (don't invent)
- Be specific about relationships (who reports to whom, who conflicts with whom)
- Character arcs should show growth, change, or development
- Include both professionals (engineers) and stakeholders (clients, public, etc.)

OUTPUT FORMAT:
Return a JSON array (ONLY the JSON, no markdown):
[
  {{
    "role_id": "r0",
    "name": "Engineer A",
    "title": "Senior Structural Engineer",
    "background": "20 years experience in commercial construction projects",
    "motivations": [
      "Professional integrity and reputation",
      "Concern for public safety",
      "Career advancement"
    ],
    "ethical_tensions": [
      "Loyalty to employer vs duty to public",
      "Professional standards vs cost constraints",
      "Whistleblowing vs job security"
    ],
    "character_arc": "Initially hesitant to challenge employer, grows more assertive about safety concerns, ultimately reports violations despite personal cost",
    "key_relationships": [
      {{"participant_id": "r1", "relationship": "reports to", "description": "Client pressures Engineer A for faster approval"}},
      {{"participant_id": "r2", "relationship": "collaborates with", "description": "Works alongside other engineers"}}
    ]
  }}
]

IMPORTANT: Return ONLY the JSON array, no other text. Include 5-12 participants (focus on quality over quantity).
"""
        return prompt

    def _parse_participant_response(
        self,
        response_text: str,
        roles: List[Any],
        case_id: int
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM response into participant data.

        Args:
            response_text: Raw LLM response
            roles: Original role entities
            case_id: Case ID

        Returns:
            List of participant dictionaries
        """
        try:
            # Parse JSON (handles markdown-wrapped responses)
            participants = self.llm.parse_json_response(response_text)

            if not isinstance(participants, list):
                logger.error(f"[Participant Mapper] Response is not a list: {type(participants)}")
                return []

            # Map short role IDs back to role objects
            role_map = {}
            for idx, role in enumerate(roles[:15]):  # Match limit from prompt
                role_map[f"r{idx}"] = role

            # Enrich each participant
            enriched_participants = []
            for participant in participants:
                try:
                    # Map role_id to role entity
                    role_id = participant.get("role_id")
                    if role_id and role_id in role_map:
                        role = role_map[role_id]
                        participant["role_entity_uri"] = getattr(role, 'uri', getattr(role, 'entity_uri', None))
                        participant["role_entity_label"] = getattr(role, 'label', getattr(role, 'entity_label', None))

                    # Add case context
                    participant["case_id"] = case_id

                    # Normalize relationship IDs
                    if "key_relationships" in participant:
                        for rel in participant["key_relationships"]:
                            if "participant_id" in rel and rel["participant_id"] in role_map:
                                # Optionally map to role entity
                                related_role = role_map[rel["participant_id"]]
                                rel["role_entity_uri"] = getattr(related_role, 'uri', getattr(related_role, 'entity_uri', None))

                    enriched_participants.append(participant)

                except Exception as e:
                    logger.warning(f"[Participant Mapper] Error enriching participant: {str(e)}")
                    continue

            logger.info(f"[Participant Mapper] Successfully parsed {len(enriched_participants)} participants")
            return enriched_participants

        except json.JSONDecodeError as e:
            logger.error(f"[Participant Mapper] Failed to parse JSON: {str(e)}")
            logger.error(f"[Participant Mapper] Response text: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"[Participant Mapper] Error parsing response: {str(e)}", exc_info=True)
            return []

    def save_participants_to_db(
        self,
        participants: List[Dict[str, Any]],
        db_session: Session
    ) -> List[Any]:
        """
        Save participants to database using actual schema (22 columns).

        Args:
            participants: List of participant dictionaries
            db_session: Database session

        Returns:
            List of saved ScenarioParticipant model instances
        """
        from app.models.scenario_participant import ScenarioParticipant

        saved_participants = []

        try:
            for participant_data in participants:
                # Extract LLM-generated content for llm_enrichment JSONB
                llm_enrichment = {
                    "motivations": participant_data.get("motivations", []),
                    "ethical_tensions": participant_data.get("ethical_tensions", []),
                    "character_arc": participant_data.get("character_arc"),
                    "role_id": participant_data.get("role_id"),
                    "role_entity_label": participant_data.get("role_entity_label")
                }

                # Create model instance matching actual database schema
                participant = ScenarioParticipant(
                    case_id=participant_data["case_id"],
                    participant_id=participant_data.get("role_id"),  # Short ID like "r0"
                    source_role_uri=participant_data.get("role_entity_uri"),  # Correct column name
                    name=participant_data["name"],
                    title=participant_data.get("title"),
                    role_type=None,  # Could infer from role classification
                    background=participant_data.get("background"),

                    # Structured JSONB fields
                    expertise=None,  # Future: extract from background
                    qualifications=None,  # Future: extract from background
                    goals=participant_data.get("motivations", []),  # Map motivations → goals
                    obligations=participant_data.get("ethical_tensions", []),  # Map tensions → obligations
                    constraints=None,  # Future: extract constraints

                    # Narrative
                    narrative_role=None,  # Future: determine from role/actions
                    relationships=participant_data.get("key_relationships", []),  # Correct column name

                    # LLM tracking
                    llm_enhanced=True,  # This was LLM-generated
                    llm_enrichment=llm_enrichment,  # Correct column name (not metadata)
                    llm_model=self.llm.model  # Track which model was used
                )

                db_session.add(participant)
                saved_participants.append(participant)

            db_session.commit()
            logger.info(f"[Participant Mapper] Saved {len(saved_participants)} participants to database")

        except Exception as e:
            db_session.rollback()
            logger.error(f"[Participant Mapper] Error saving participants: {str(e)}", exc_info=True)
            raise

        return saved_participants
