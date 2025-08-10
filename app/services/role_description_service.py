"""
Service to generate standardized role descriptions and anticipated obligations/duties.

Uses available ontology context (if any) and guidelines knowledge via LLM to produce
consistent, domain-aware descriptions suitable for role-based ethics.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from app.models.world import World
from app.services.llm_service import LLMService
from app.services.ontology_entity_service import OntologyEntityService

logger = logging.getLogger(__name__)


class RoleDescriptionService:
    """Generate standardized descriptions for roles, with obligations hints."""

    def __init__(self):
        self.llm = LLMService()
        self.ontology_service = OntologyEntityService.get_instance()

    def generate(self, role_label: str, world: Optional[World] = None) -> Dict:
        """Generate a standardized description for a role.

        Returns dict with keys:
          - description: str
          - obligations: list[str]
          - parent_suggestion: Optional[str]
        """
        role_label = (role_label or '').strip()
        if not role_label:
            return {
                "description": "",
                "obligations": [],
                "parent_suggestion": None,
            }

        # Gather minimal ontology hints for the world
        ontology_hint = ""
        parent_suggestion = self._heuristic_parent(role_label)
        try:
            if world:
                entities = self.ontology_service.get_entities_for_world(world)
                roles = entities.get("entities", {}).get("roles", []) or entities.get("entities", {}).get("role", [])
                # Use role labels to give LLM context of nearby concepts
                nearby = sorted({r.get('label') for r in roles if r.get('label')})
                if nearby:
                    ontology_hint = f"Known roles in this world include: {', '.join(nearby[:20])}."
        except Exception as e:
            logger.warning(f"Ontology hint extraction failed: {e}")

        # Ask LLM for a concise standardized description and duties
        prompt = f"""
You are helping define a standardized professional role for role-based ethics analysis.

ROLE: {role_label}
CONTEXT: {ontology_hint}

REQUIREMENTS:
- Write a concise, neutral description (2-4 sentences) that captures purpose, scope, and responsibilities.
- Include anticipated obligations/duties as 4-7 bullet points, phrased generally and suitable for ethics evaluation.
- If the role is engineering-related, reflect common engineering ethics (e.g., public safety, competence, integrity, disclosure of conflicts) without citing specific organizations by name.
- Keep it domain-agnostic when uncertain; avoid speculative details.

OUTPUT JSON ONLY:
{{
  "description": "...",  
  "obligations": ["...", "...", "..." ]
}}
"""

        description = ""
        obligations = []
        try:
            raw = self.llm.generate_response(prompt)
            text = raw.get('analysis', raw.get('response', '')) if isinstance(raw, dict) else str(raw)
            cleaned = text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            description = (data.get('description') or '').strip()
            obligations = [o for o in (data.get('obligations') or []) if isinstance(o, str) and o.strip()]
        except Exception as e:
            logger.warning(f"LLM role description generation failed: {e}")
            # Fallback template
            description = f"Participant serving as {role_label}. Responsible for fulfilling the typical duties and ethical responsibilities associated with this role."
            obligations = [
                "Act with honesty and integrity",
                "Exercise due care and professional competence",
                "Communicate risks and material facts to relevant stakeholders",
                "Respect applicable laws, standards, and organizational policies",
            ]

        return {
            "description": description,
            "obligations": obligations,
            "parent_suggestion": parent_suggestion,
        }

    def _heuristic_parent(self, role_label: str) -> Optional[str]:
        """Lightweight parent suggestion heuristic (non-binding)."""
        label = role_label.lower()
        if 'engineer' in label and 'structural' in label:
            return 'Structural Engineer'
        if 'engineer' in label:
            return 'Professional Engineer'
        if 'manager' in label:
            return 'Manager'
        if 'client' in label:
            return 'Client Representative'
        if 'inspector' in label:
            return 'Inspector'
        return None
