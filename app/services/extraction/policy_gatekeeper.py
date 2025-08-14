from __future__ import annotations

import os
from typing import Optional


class RelationshipPolicyGatekeeper:
    """Centralizes relationship gating and env toggles.

    Usage: gate.can_link_has_obligation(subject_type, object_type) -> bool
    """

    def __init__(self) -> None:
        self.allow_stakeholder_principle = os.getenv("ALLOW_STAKEHOLDER_PRINCIPLE_LINKS", "false").lower() == "true"
        self.allow_stakeholder_obligations = os.getenv("ALLOW_STAKEHOLDER_OBLIGATIONS", "false").lower() == "true"

    @staticmethod
    def is_professional_role(t: Optional[str]) -> bool:
        return (t or "").lower() in {"professionalrole", "professional_role", "professional"}

    @staticmethod
    def is_participant_role(t: Optional[str]) -> bool:
        return (t or "").lower() in {"participantrole", "participant_role", "stakeholder", "stakeholderrole"}

    def can_link_has_obligation(self, subject_type: Optional[str], object_type: Optional[str]) -> bool:
        # Only ProfessionalRole subjects; object must be obligation
        if not self.is_professional_role(subject_type):
            return False
        return (object_type or "").lower() in {"obligation"}

    def can_link_adheres_to_principle(self, subject_type: Optional[str], object_type: Optional[str]) -> bool:
        if self.is_professional_role(subject_type):
            return (object_type or "").lower() in {"principle"}
        if self.is_participant_role(subject_type) and self.allow_stakeholder_principle:
            return (object_type or "").lower() in {"principle"}
        return False

    def can_link_pursues_end(self, subject_type: Optional[str], object_type: Optional[str]) -> bool:
        return self.is_professional_role(subject_type) and (object_type or "").lower() in {"end", "goal", "end/goal"}

    def can_link_governed_by_code(self, subject_type: Optional[str], object_type: Optional[str]) -> bool:
        return self.is_professional_role(subject_type) and (object_type or "").lower() in {"ethicalcode", "code", "ethical_code"}
