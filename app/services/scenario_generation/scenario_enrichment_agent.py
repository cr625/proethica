"""
Scenario Enrichment Agent

LLM-powered agent for validating and enriching scenario components.
Uses Claude Sonnet 4 with case context to fill missing data and validate coherence.

Created: November 3, 2025
Architecture: proethica/docs/SCENARIO_ENRICHMENT_ARCHITECTURE.md
"""

import json
import logging
from dataclasses import asdict
from typing import Dict, List, Optional
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


class ScenarioEnrichmentAgent:
    """
    LLM-powered agent for validating and enriching scenario components.

    Uses Claude Sonnet 4 with case context to:
    1. Fill missing data (descriptions, agents)
    2. Validate coherence (timeline -> participants -> decisions)
    3. Enrich with case-specific narrative
    4. Identify gaps and suggest fixes
    """

    def __init__(self, llm_client=None):
        """
        Initialize enrichment agent.

        Args:
            llm_client: Optional pre-initialized LLM client. If None, will get one via get_llm_client().
        """
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = get_llm_client()
        self.model = "claude-sonnet-4-20250514"  # Sonnet 4, not 4.5 (timeout issues)
        logger.info(f"[ScenarioEnrichmentAgent] Initialized with model: {self.model}")

    def enrich_timeline(
        self,
        case_id: int,
        case_text: str,
        timeline_entries: List[Dict],
        participants: List[Dict]
    ) -> Dict:
        """
        Enrich timeline entries with case-specific context.

        For each timeline entry:
        1. Fill description from case narrative
        2. Identify agent from participants list
        3. Validate temporal markers make sense
        4. Add narrative context

        Args:
            case_id: Case ID for logging
            case_text: Full case narrative text
            timeline_entries: List of timeline entry dicts (from temporal dynamics)
            participants: List of participant dicts (from Pass 1 Roles)

        Returns:
            Dict with:
                - enriched_timeline: List of enriched timeline entries
                - validation_notes: List of validation observations
                - missing_events: List of suggested missing events
        """
        logger.info(f"[ScenarioEnrichmentAgent] Enriching timeline for case {case_id}")
        logger.info(f"[ScenarioEnrichmentAgent] Input: {len(timeline_entries)} entries, {len(participants)} participants")

        # Extract participant names for prompt (participants are ParticipantProfile objects)
        participant_names = [p.name for p in participants]

        # Convert timeline entries to dictionaries (they are TimelineEntry dataclass objects)
        timeline_entries_dicts = [asdict(entry) for entry in timeline_entries]

        # Build enrichment prompt
        prompt = self._build_timeline_enrichment_prompt(
            case_text=case_text,
            timeline_entries=timeline_entries_dicts,
            participant_names=participant_names
        )

        # Call LLM
        try:
            logger.info(f"[ScenarioEnrichmentAgent] Calling LLM for timeline enrichment...")
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,  # Lower for consistency
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"[ScenarioEnrichmentAgent] Response length: {len(response_text)} chars")

            # Strip markdown code fences if present
            cleaned_response = self._strip_code_fence(response_text)

            # Parse JSON response
            result = json.loads(cleaned_response)

            logger.info(f"[ScenarioEnrichmentAgent] Enrichment complete: {len(result.get('enriched_timeline', []))} entries enriched")
            logger.info(f"[ScenarioEnrichmentAgent] Validation notes: {len(result.get('validation_notes', []))}")
            logger.info(f"[ScenarioEnrichmentAgent] Missing events suggested: {len(result.get('missing_events', []))}")

            # Add prompt and response for provenance tracking
            result['llm_prompt'] = prompt
            result['llm_response'] = response_text
            result['llm_model'] = self.model

            return result

        except json.JSONDecodeError as e:
            logger.error(f"[ScenarioEnrichmentAgent] Failed to parse LLM response as JSON: {e}")
            logger.error(f"[ScenarioEnrichmentAgent] Response text: {response_text[:500]}...")
            # Return original timeline as fallback (as dicts)
            return {
                'enriched_timeline': timeline_entries_dicts,
                'validation_notes': [f"Error parsing enrichment response: {str(e)}"],
                'missing_events': []
            }
        except Exception as e:
            logger.error(f"[ScenarioEnrichmentAgent] Error during timeline enrichment: {e}", exc_info=True)
            # Return original timeline as fallback (as dicts)
            return {
                'enriched_timeline': timeline_entries_dicts,
                'validation_notes': [f"Error during enrichment: {str(e)}"],
                'missing_events': []
            }

    def _build_timeline_enrichment_prompt(
        self,
        case_text: str,
        timeline_entries: List[Dict],
        participant_names: List[str]
    ) -> str:
        """
        Build prompt for timeline enrichment.

        Args:
            case_text: Full case narrative
            timeline_entries: Timeline entries to enrich
            participant_names: List of known participant names

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are analyzing an NSPE Board of Ethical Review case to enrich timeline events with narrative context.

CASE TEXT:
{case_text}

TIMELINE ENTRIES (existing structure from Step 3):
{json.dumps(timeline_entries, indent=2)}

KNOWN PARTICIPANTS:
{json.dumps(participant_names, indent=2)}

TASK:
For each timeline entry's ELEMENTS (actions/events), enrich with:
1. **description**: 2-3 sentence narrative from case text explaining what happened and why
2. **agent**: Match agent to a participant name from the list above (for actions only)
3. Validate timeline coherence and identify any missing critical events

The timeline already exists - your job is to:
- Fill empty "description" fields with narrative context from the case
- Replace "Unknown" agents with actual participant names where possible
- Validate the timeline makes sense as an ethical narrative

Return the COMPLETE timeline structure with enriched elements:
{{
  "enriched_timeline": [
    {{
      "sequence": 1,
      "timepoint": "...",
      "phase": "introduction",
      "element_count": 1,
      "elements": [
        {{
          "type": "action",
          "label": "Withhold Risk Concerns",
          "agent": "Engineer L",
          "description": "During the work suspension, Engineer L became aware of potential risks to the community drinking water but chose not to immediately alert Client X, balancing professional judgment with client relationship concerns.",
          "temporal_marker": "During work suspension",
          "volitional": true
        }}
      ]
    }}
  ],
  "validation_notes": [
    "Timeline shows clear ethical progression",
    "All critical decision points captured"
  ],
  "missing_events": []
}}

IMPORTANT:
- Return the EXACT timeline structure (sequence, timepoint, phase, element_count, elements)
- Only enrich the "description" and "agent" fields within elements
- Use exact participant names from KNOWN PARTICIPANTS
- Keep all other fields unchanged
- Return valid JSON only"""

        return prompt

    def _strip_code_fence(self, text: str) -> str:
        """
        Strip markdown code fences from LLM response.

        Claude sometimes wraps JSON in ```json ... ``` which needs to be removed.

        Args:
            text: Raw response text

        Returns:
            Cleaned text without code fences
        """
        text = text.strip()

        # Check for markdown code fence
        if text.startswith('```'):
            # Find the first newline (end of opening fence)
            first_newline = text.find('\n')
            if first_newline != -1:
                # Find the closing fence
                closing_fence = text.rfind('```')
                if closing_fence != -1 and closing_fence > first_newline:
                    # Extract content between fences
                    return text[first_newline + 1:closing_fence].strip()

        return text

    def validate_decisions(
        self,
        case_id: int,
        case_text: str,
        decision_points: List[Dict],
        timeline: List[Dict],
        participants: List[Dict]
    ) -> Dict:
        """
        Validate decision points make sense in context.

        Checks:
        1. Deliberating actor is a known participant
        2. Decision aligns with timeline events
        3. Options are realistic given case context
        4. Stakes are accurately identified

        Args:
            case_id: Case ID for logging
            case_text: Full case narrative
            decision_points: List of decision point dicts
            timeline: Timeline entries for context
            participants: Known participants

        Returns:
            Dict with enriched decisions and validation notes
        """
        logger.info(f"[ScenarioEnrichmentAgent] Decision validation for case {case_id} not yet implemented")
        # TODO: Implement in Phase 2
        return {
            'enriched_decisions': decision_points,
            'validation_notes': ['Decision validation not yet implemented']
        }

    def validate_coherence(
        self,
        case_id: int,
        assembled_scenario: Dict
    ) -> Dict:
        """
        Holistic validation of assembled scenario.

        Checks:
        1. Timeline participants match participant list
        2. Decisions reference timeline events
        3. Causal chains match timeline sequence
        4. Normative framework aligns with decisions
        5. No contradictions or gaps

        Args:
            case_id: Case ID for logging
            assembled_scenario: Complete assembled scenario dict

        Returns:
            Dict with:
                - coherence_score: 0.0-1.0
                - issues: List of identified issues
                - suggestions: List of improvement suggestions
        """
        logger.info(f"[ScenarioEnrichmentAgent] Coherence validation for case {case_id} not yet implemented")
        # TODO: Implement in Phase 3
        return {
            'coherence_score': 0.85,
            'issues': [],
            'suggestions': ['Coherence validation not yet implemented']
        }
