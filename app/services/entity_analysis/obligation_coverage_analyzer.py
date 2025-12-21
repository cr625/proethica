"""
Obligation Coverage Analyzer (Step E1)

Analyzes which extracted Obligations/Constraints create decision-relevant
ethical tension. This is the first step in the entity-grounded argument pipeline.

Based on Oakley & Cocking (2001): "Good professional roles generate specific
obligations tied to key human goods."
"""

import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config

logger = logging.getLogger(__name__)


@dataclass
class ObligationAnalysis:
    """Analysis result for a single obligation."""
    entity_uri: str
    entity_label: str
    entity_definition: str
    bound_role: Optional[str] = None  # Role this obligation binds to
    bound_role_uri: Optional[str] = None
    decision_type: str = "unclassified"  # disclosure, action, delegation, verification, competence
    related_provisions: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)  # URIs of conflicting obligations
    serves_founding_good: bool = True  # Does this serve public safety?
    decision_relevant: bool = False  # Is this relevant for decision point composition?
    is_instantiated: bool = False  # Is this a role-bound instantiation?
    parent_obligation: Optional[str] = None  # URI of generic parent if instantiated

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConstraintAnalysis:
    """Analysis result for a single constraint."""
    entity_uri: str
    entity_label: str
    entity_definition: str
    constrained_role: Optional[str] = None
    constrained_role_uri: Optional[str] = None
    restricts_actions: List[str] = field(default_factory=list)  # Action URIs this constrains
    founding_value_limit: bool = False  # Does this represent a founding value limit?
    decision_relevant: bool = False
    is_instantiated: bool = False
    parent_constraint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMTraceE1:
    """Record of an LLM interaction during E1 analysis."""
    stage: str
    prompt: str
    response: str
    model: str = 'claude-sonnet-4-20250514'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage,
            'prompt': self.prompt,
            'response': self.response,
            'model': self.model
        }


@dataclass
class CoverageMatrix:
    """Complete coverage analysis for a case."""
    case_id: int
    obligations: List[ObligationAnalysis] = field(default_factory=list)
    constraints: List[ConstraintAnalysis] = field(default_factory=list)
    role_obligation_map: Dict[str, List[str]] = field(default_factory=dict)  # role -> obligation URIs
    conflict_pairs: List[Tuple[str, str]] = field(default_factory=list)  # pairs of conflicting URIs
    decision_relevant_count: int = 0
    llm_traces: List[LLMTraceE1] = field(default_factory=list)  # LLM interactions if fallback used
    used_llm_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'obligations': [o.to_dict() for o in self.obligations],
            'constraints': [c.to_dict() for c in self.constraints],
            'role_obligation_map': self.role_obligation_map,
            'conflict_pairs': self.conflict_pairs,
            'decision_relevant_count': self.decision_relevant_count,
            'llm_traces': [t.to_dict() for t in self.llm_traces],
            'used_llm_fallback': self.used_llm_fallback
        }


# Decision type keywords for classification
DECISION_TYPE_KEYWORDS = {
    'disclosure': ['disclosure', 'disclose', 'inform', 'notify', 'transparency', 'reveal', 'tell'],
    'verification': ['verification', 'verify', 'review', 'check', 'audit', 'validate', 'assurance'],
    'competence': ['competence', 'competent', 'qualified', 'expertise', 'skill', 'training'],
    'confidentiality': ['confidential', 'privacy', 'private', 'protect', 'secret'],
    'safety': ['safety', 'safe', 'harm', 'risk', 'danger', 'hazard', 'welfare'],
    'attribution': ['attribution', 'credit', 'acknowledge', 'source'],
    'delegation': ['delegation', 'delegate', 'assign', 'responsible charge', 'supervision'],
}

# Potential conflict pairs based on ethical tension patterns
CONFLICT_PATTERNS = [
    ('disclosure', 'confidentiality'),  # Transparency vs privacy
    ('disclosure', 'competence'),  # Reveal vs hide incompetence
    ('safety', 'competence'),  # Safety requires competence
    ('delegation', 'verification'),  # Can't delegate what needs personal verification
]


class ObligationCoverageAnalyzer:
    """
    Analyzes which obligations create decision-relevant ethical tension.

    Step E1 in the entity-grounded argument pipeline.
    """

    def __init__(self, domain_config: Optional[DomainConfig] = None):
        """
        Initialize with optional domain configuration.

        Args:
            domain_config: Domain-specific config. Defaults to engineering.
        """
        self.domain = domain_config or get_domain_config('engineering')
        self.role_vocabulary = [r.lower() for r in self.domain.role_vocabulary]

    def analyze_coverage(
        self,
        case_id: int,
        questions: List[Dict] = None,
        conclusions: List[Dict] = None
    ) -> CoverageMatrix:
        """
        Analyze obligation and constraint coverage for a case.

        Returns obligations with decision potential, identifying:
        - Role bindings (which role has this obligation)
        - Decision types (disclosure, verification, etc.)
        - Conflicts with other obligations/constraints
        - Decision relevance (can this create ethical tension?)

        Args:
            case_id: The case to analyze
            questions: Optional Q&C questions for LLM fallback
            conclusions: Optional Q&C conclusions for LLM fallback

        Returns:
            CoverageMatrix with analyzed obligations and constraints
        """
        logger.info(f"Analyzing obligation coverage for case {case_id}")

        # Load entities from database
        obligations_raw = self._load_entities(case_id, 'Obligations')
        constraints_raw = self._load_entities(case_id, 'Constraints')
        roles_raw = self._load_entities(case_id, 'Roles')

        # Build role lookup
        role_lookup = self._build_role_lookup(roles_raw)

        # Analyze obligations
        obligations = []
        for entity in obligations_raw:
            analysis = self._analyze_obligation(entity, role_lookup)
            obligations.append(analysis)

        # Analyze constraints
        constraints = []
        for entity in constraints_raw:
            analysis = self._analyze_constraint(entity, role_lookup)
            constraints.append(analysis)

        # Identify conflicts
        conflict_pairs = self._identify_conflicts(obligations, constraints)

        # Mark decision-relevant based on conflicts and type
        self._mark_decision_relevant(obligations, constraints, conflict_pairs)

        # Build role -> obligation map
        role_obligation_map = {}
        for obl in obligations:
            if obl.bound_role:
                if obl.bound_role not in role_obligation_map:
                    role_obligation_map[obl.bound_role] = []
                role_obligation_map[obl.bound_role].append(obl.entity_uri)

        decision_relevant_count = sum(
            1 for o in obligations if o.decision_relevant
        ) + sum(
            1 for c in constraints if c.decision_relevant
        )

        llm_traces = []
        used_llm_fallback = False

        # LLM fallback if no decision-relevant obligations found
        if decision_relevant_count == 0 and (questions or conclusions):
            logger.info("No decision-relevant obligations found algorithmically, using LLM fallback")
            relevant_uris, trace = self._llm_identify_decision_relevant(
                obligations, constraints, questions or [], conclusions or []
            )
            if trace:
                llm_traces.append(trace)
                used_llm_fallback = True

            # Mark the LLM-identified items as decision-relevant
            for obl in obligations:
                if obl.entity_uri in relevant_uris:
                    obl.decision_relevant = True
            for con in constraints:
                if con.entity_uri in relevant_uris:
                    con.decision_relevant = True

            # Recount
            decision_relevant_count = sum(
                1 for o in obligations if o.decision_relevant
            ) + sum(
                1 for c in constraints if c.decision_relevant
            )

            logger.info(f"LLM fallback identified {decision_relevant_count} decision-relevant items")

        matrix = CoverageMatrix(
            case_id=case_id,
            obligations=obligations,
            constraints=constraints,
            role_obligation_map=role_obligation_map,
            conflict_pairs=conflict_pairs,
            decision_relevant_count=decision_relevant_count,
            llm_traces=llm_traces,
            used_llm_fallback=used_llm_fallback
        )

        logger.info(
            f"Coverage analysis complete: {len(obligations)} obligations, "
            f"{len(constraints)} constraints, {decision_relevant_count} decision-relevant"
            f"{' (LLM fallback)' if used_llm_fallback else ''}"
        )

        return matrix

    def _load_entities(self, case_id: int, entity_type: str) -> List[TemporaryRDFStorage]:
        """Load entities of a specific type from the database."""
        return TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=entity_type
        ).all()

    def _build_role_lookup(self, roles: List[TemporaryRDFStorage]) -> Dict[str, str]:
        """
        Build a lookup from role name variants to canonical role label.

        E.g., 'engineera' -> 'Engineer A', 'engineer_a' -> 'Engineer A'
        """
        lookup = {}
        for role in roles:
            label = role.entity_label
            # Add the label itself
            lookup[label.lower()] = label
            # Add without spaces
            lookup[label.lower().replace(' ', '')] = label
            # Add with underscore
            lookup[label.lower().replace(' ', '_')] = label

        return lookup

    def _analyze_obligation(
        self,
        entity: TemporaryRDFStorage,
        role_lookup: Dict[str, str]
    ) -> ObligationAnalysis:
        """Analyze a single obligation entity."""
        label = entity.entity_label
        definition = entity.entity_definition or ""
        uri = entity.entity_uri or f"case-{entity.case_id}#{label.replace(' ', '_')}"

        # Detect if this is an instantiated (role-bound) obligation
        is_instantiated = self._is_instantiated_label(label)

        # Extract bound role (passing definition for fallback matching)
        bound_role, bound_role_uri = self._extract_role_binding(
            label, role_lookup, entity.case_id, definition
        )

        # Classify decision type
        decision_type = self._classify_decision_type(label, definition)

        # Extract related provisions (from JSON-LD if available)
        related_provisions = self._extract_provisions(entity)

        return ObligationAnalysis(
            entity_uri=uri,
            entity_label=label,
            entity_definition=definition,
            bound_role=bound_role,
            bound_role_uri=bound_role_uri,
            decision_type=decision_type,
            related_provisions=related_provisions,
            is_instantiated=is_instantiated,
            serves_founding_good=self._serves_founding_good(label, definition)
        )

    def _analyze_constraint(
        self,
        entity: TemporaryRDFStorage,
        role_lookup: Dict[str, str]
    ) -> ConstraintAnalysis:
        """Analyze a single constraint entity."""
        label = entity.entity_label
        definition = entity.entity_definition or ""
        uri = entity.entity_uri or f"case-{entity.case_id}#{label.replace(' ', '_')}"

        is_instantiated = self._is_instantiated_label(label)
        constrained_role, constrained_role_uri = self._extract_role_binding(
            label, role_lookup, entity.case_id, definition
        )

        # Check if this is a founding value limit (safety, welfare constraints)
        founding_value_limit = any(
            kw in label.lower() or kw in definition.lower()
            for kw in ['safety', 'welfare', 'public', 'harm', 'risk']
        )

        return ConstraintAnalysis(
            entity_uri=uri,
            entity_label=label,
            entity_definition=definition,
            constrained_role=constrained_role,
            constrained_role_uri=constrained_role_uri,
            founding_value_limit=founding_value_limit,
            is_instantiated=is_instantiated
        )

    def _is_instantiated_label(self, label: str) -> bool:
        """
        Check if a label represents an instantiated (role-bound) entity.

        Instantiated labels typically follow patterns like:
        - EngineerA_AI_Disclosure_ClientW
        - Responsible_Charge_Constraint_EngineerA
        """
        # Contains underscore and has a role-like prefix or suffix
        if '_' not in label:
            return False

        parts = label.split('_')
        # Check if any part looks like a role reference
        for part in parts:
            part_lower = part.lower()
            # Check against role vocabulary
            for role in self.role_vocabulary:
                if role in part_lower or part_lower in role:
                    return True

        return False

    def _extract_role_binding(
        self,
        label: str,
        role_lookup: Dict[str, str],
        case_id: int,
        definition: str = ""
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract role binding from an entity label or definition.

        Returns (role_label, role_uri) or (None, None) if no binding found.
        """
        label_lower = label.lower()
        definition_lower = definition.lower() if definition else ""

        # Try to find a role reference in the label first
        for role_key, role_label in role_lookup.items():
            if role_key in label_lower:
                role_uri = f"case-{case_id}#{role_label.replace(' ', '_')}"
                return role_label, role_uri

        # Fallback: check for common role prefixes in label
        for role in self.role_vocabulary:
            if role in label_lower:
                # Capitalize for display
                role_display = role.title()
                role_uri = f"case-{case_id}#{role_display.replace(' ', '_')}"
                return role_display, role_uri

        # Second pass: check definition text for role references
        if definition_lower:
            for role_key, role_label in role_lookup.items():
                if role_key in definition_lower:
                    role_uri = f"case-{case_id}#{role_label.replace(' ', '_')}"
                    return role_label, role_uri

        # Final fallback for engineering domain: generic obligations likely apply to Engineer A
        # (the primary role being evaluated in NSPE cases)
        if 'Engineer A' in role_lookup.values():
            # Check if this is an engineering-related obligation
            combined = f"{label_lower} {definition_lower}"
            eng_keywords = ['engineer', 'design', 'review', 'verification', 'safety',
                           'disclosure', 'competence', 'ai', 'technical']
            if any(kw in combined for kw in eng_keywords):
                role_uri = f"case-{case_id}#Engineer_A"
                return 'Engineer A', role_uri

        return None, None

    def _classify_decision_type(self, label: str, definition: str) -> str:
        """Classify the decision type based on keywords."""
        text = f"{label} {definition}".lower()

        for dtype, keywords in DECISION_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return dtype

        return "unclassified"

    def _extract_provisions(self, entity: TemporaryRDFStorage) -> List[str]:
        """Extract related code provisions from entity JSON-LD."""
        provisions = []

        json_ld = entity.rdf_json_ld or {}
        relationships = json_ld.get('relationships', [])

        for rel in relationships:
            if rel.get('type') in ['proeth:appliesProvision', 'proeth:citesProvision']:
                target = rel.get('target_label') or rel.get('target_uri', '')
                if target:
                    provisions.append(target)

        return provisions

    def _serves_founding_good(self, label: str, definition: str) -> bool:
        """
        Check if this obligation serves the profession's founding good.

        For engineering, this is public safety/welfare.
        """
        text = f"{label} {definition}".lower()

        # Check for alignment with founding good
        if self.domain.founding_good == 'public_safety':
            positive_indicators = ['safety', 'welfare', 'public', 'protect', 'harm prevention']
            return any(ind in text for ind in positive_indicators) or True  # Default to true

        return True  # Default assumption

    def _identify_conflicts(
        self,
        obligations: List[ObligationAnalysis],
        constraints: List[ConstraintAnalysis]
    ) -> List[Tuple[str, str]]:
        """
        Identify potential conflicts between obligations/constraints.

        Conflicts arise when:
        - Two obligations have conflicting decision types
        - Same role has competing obligations
        - Constraint restricts action required by obligation
        """
        conflicts = []

        # Check obligation-obligation conflicts
        for i, obl1 in enumerate(obligations):
            for obl2 in obligations[i+1:]:
                if self._are_conflicting(obl1, obl2):
                    conflicts.append((obl1.entity_uri, obl2.entity_uri))
                    obl1.conflicts_with.append(obl2.entity_uri)
                    obl2.conflicts_with.append(obl1.entity_uri)

        # Check obligation-constraint conflicts
        for obl in obligations:
            for con in constraints:
                if self._obligation_constraint_conflict(obl, con):
                    conflicts.append((obl.entity_uri, con.entity_uri))
                    obl.conflicts_with.append(con.entity_uri)

        return conflicts

    def _are_conflicting(
        self,
        obl1: ObligationAnalysis,
        obl2: ObligationAnalysis
    ) -> bool:
        """Check if two obligations are potentially conflicting."""
        # Same role with different types that conflict
        if obl1.bound_role and obl1.bound_role == obl2.bound_role:
            type_pair = (obl1.decision_type, obl2.decision_type)
            reverse_pair = (obl2.decision_type, obl1.decision_type)
            if type_pair in CONFLICT_PATTERNS or reverse_pair in CONFLICT_PATTERNS:
                return True

        return False

    def _obligation_constraint_conflict(
        self,
        obl: ObligationAnalysis,
        con: ConstraintAnalysis
    ) -> bool:
        """Check if an obligation conflicts with a constraint."""
        # Same role, and constraint is a founding value limit
        if obl.bound_role and obl.bound_role == con.constrained_role:
            if con.founding_value_limit:
                return True

        return False

    def _mark_decision_relevant(
        self,
        obligations: List[ObligationAnalysis],
        constraints: List[ConstraintAnalysis],
        conflict_pairs: List[Tuple[str, str]]
    ) -> None:
        """
        Mark obligations/constraints as decision-relevant.

        Decision-relevant means it could be part of a decision point.
        """
        conflicting_uris = set()
        for uri1, uri2 in conflict_pairs:
            conflicting_uris.add(uri1)
            conflicting_uris.add(uri2)

        for obl in obligations:
            # Relevant if: has conflicts, is instantiated, or is a key decision type
            obl.decision_relevant = (
                obl.entity_uri in conflicting_uris or
                obl.is_instantiated or
                obl.decision_type in ['disclosure', 'verification', 'safety']
            )

        for con in constraints:
            con.decision_relevant = (
                con.entity_uri in conflicting_uris or
                con.founding_value_limit or
                con.is_instantiated
            )

    def _llm_identify_decision_relevant(
        self,
        obligations: List[ObligationAnalysis],
        constraints: List[ConstraintAnalysis],
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> Tuple[List[str], LLMTraceE1]:
        """
        Use LLM to identify decision-relevant obligations when algorithmic approach fails.

        Args:
            obligations: List of analyzed obligations
            constraints: List of analyzed constraints
            questions: Questions from Phase 2B
            conclusions: Conclusions from Phase 2B

        Returns:
            Tuple of (list of decision-relevant URIs, LLM trace)
        """
        from app.utils.llm_utils import get_llm_client

        llm_client = get_llm_client()
        if not llm_client:
            logger.warning("No LLM client available for decision relevance fallback")
            return [], None

        # Build prompt
        obligations_text = "\n".join([
            f"- [{i+1}] {o.entity_label}: {o.entity_definition[:200]}"
            for i, o in enumerate(obligations)
        ])

        constraints_text = "\n".join([
            f"- [{len(obligations)+i+1}] {c.entity_label}: {c.entity_definition[:200]}"
            for i, c in enumerate(constraints)
        ])

        questions_text = "\n".join([
            f"Q{i+1}: {q.get('text', q.get('question_text', ''))[:150]}"
            for i, q in enumerate(questions[:5])  # Limit to first 5
        ])

        conclusions_text = "\n".join([
            f"C{i+1}: {c.get('text', c.get('conclusion_text', ''))[:150]}"
            for i, c in enumerate(conclusions[:5])  # Limit to first 5
        ])

        prompt = f"""Analyze these ethical obligations and constraints from an NSPE ethics case.

OBLIGATIONS:
{obligations_text}

CONSTRAINTS:
{constraints_text}

QUESTIONS THE BOARD CONSIDERED:
{questions_text}

BOARD'S CONCLUSIONS:
{conclusions_text}

TASK: Identify which obligations/constraints are DECISION-RELEVANT - meaning they are central to the ethical dilemma and the board's analysis.

Return a JSON object with this structure:
{{
  "decision_relevant_indices": [1, 3, 5],  // Indices from the lists above
  "reasoning": "Brief explanation of why these are central to the case"
}}

Focus on obligations that:
1. Are directly referenced in the questions or conclusions
2. Create ethical tension or conflict
3. Require the engineer to make a difficult choice

Return ONLY the JSON object, no other text."""

        try:
            response = llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse response
            import json
            # Try to extract JSON from response
            if response_text.startswith('{'):
                result = json.loads(response_text)
            else:
                # Try to find JSON in response
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.warning(f"Could not parse LLM response: {response_text[:200]}")
                    result = {"decision_relevant_indices": list(range(1, min(6, len(obligations) + 1)))}

            indices = result.get('decision_relevant_indices', [])

            # Map indices to URIs
            all_items = obligations + constraints
            relevant_uris = []
            for idx in indices:
                if 1 <= idx <= len(all_items):
                    item = all_items[idx - 1]
                    relevant_uris.append(item.entity_uri)

            trace = LLMTraceE1(
                stage='E1_decision_relevance_fallback',
                prompt=prompt,
                response=response_text,
                model='claude-sonnet-4-20250514'
            )

            logger.info(f"LLM identified {len(relevant_uris)} decision-relevant items")
            return relevant_uris, trace

        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")
            return [], None


def get_obligation_coverage(
    case_id: int,
    domain: str = 'engineering',
    questions: List[Dict] = None,
    conclusions: List[Dict] = None
) -> CoverageMatrix:
    """
    Convenience function to get obligation coverage analysis.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)
        questions: Optional Q&C questions for LLM fallback
        conclusions: Optional Q&C conclusions for LLM fallback

    Returns:
        CoverageMatrix with analysis results
    """
    domain_config = get_domain_config(domain)
    analyzer = ObligationCoverageAnalyzer(domain_config)
    return analyzer.analyze_coverage(case_id, questions=questions, conclusions=conclusions)
