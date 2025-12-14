"""
Principle-Provision Aligner (Step F1)

Aligns extracted Principles with Code Provisions to establish backing
for Toulmin-structured arguments. This mapping shows which authoritative
provisions support which ethical principles.

Based on McLaren's insight: "Principles achieve meaning through extensional
definition via precedents."
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config

logger = logging.getLogger(__name__)


@dataclass
class PrincipleAlignment:
    """Alignment between a principle and its supporting provisions."""
    principle_uri: str
    principle_label: str
    principle_definition: str
    universal_category: Optional[str] = None  # Beauchamp & Childress category
    provision_uris: List[str] = field(default_factory=list)
    provision_labels: List[str] = field(default_factory=list)
    provision_sections: List[str] = field(default_factory=list)
    support_type: str = "unclassified"  # pro_disclosure, pro_competence, pro_safety, etc.
    key_terms: List[str] = field(default_factory=list)
    extensional_precedents: List[str] = field(default_factory=list)  # Case IDs
    alignment_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvisionDetail:
    """Details of a code provision for alignment."""
    uri: str
    label: str
    section: str
    text: str
    level: str  # fundamental_canons, rules_of_practice, professional_obligations
    key_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlignmentMap:
    """Complete alignment map for a case."""
    case_id: int
    alignments: List[PrincipleAlignment] = field(default_factory=list)
    unaligned_principles: List[str] = field(default_factory=list)
    unaligned_provisions: List[str] = field(default_factory=list)
    total_principles: int = 0
    total_provisions: int = 0
    alignment_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'alignments': [a.to_dict() for a in self.alignments],
            'unaligned_principles': self.unaligned_principles,
            'unaligned_provisions': self.unaligned_provisions,
            'total_principles': self.total_principles,
            'total_provisions': self.total_provisions,
            'alignment_rate': self.alignment_rate
        }


# Map principle keywords to support types
SUPPORT_TYPE_KEYWORDS = {
    'pro_disclosure': ['disclosure', 'transparency', 'inform', 'notify', 'honesty', 'truth'],
    'pro_competence': ['competence', 'qualified', 'skill', 'expertise', 'capability'],
    'pro_safety': ['safety', 'welfare', 'public', 'harm', 'protection', 'health'],
    'pro_confidentiality': ['confidential', 'privacy', 'secret', 'proprietary'],
    'pro_attribution': ['credit', 'attribution', 'recognition', 'acknowledge'],
    'pro_integrity': ['integrity', 'honest', 'faithful', 'trustworthy'],
}

# NSPE Code section prefixes for level detection
PROVISION_LEVELS = {
    'I': 'fundamental_canons',
    'II': 'rules_of_practice',
    'III': 'professional_obligations',
}


class PrincipleProvisionAligner:
    """
    Aligns principles with code provisions for argument backing.

    Step F1 in the entity-grounded argument pipeline.
    """

    def __init__(self, domain_config: Optional[DomainConfig] = None):
        """
        Initialize with optional domain configuration.

        Args:
            domain_config: Domain-specific config. Defaults to engineering.
        """
        self.domain = domain_config or get_domain_config('engineering')
        self.principle_mapping = self.domain.principle_mapping
        self.provision_structure = self.domain.provision_structure

    def align_principles_provisions(self, case_id: int) -> AlignmentMap:
        """
        Create alignment map between principles and provisions.

        Args:
            case_id: The case to analyze

        Returns:
            AlignmentMap with principle-provision alignments
        """
        logger.info(f"Aligning principles and provisions for case {case_id}")

        # Load entities
        principles_raw = self._load_principles(case_id)
        provisions_raw = self._load_provisions(case_id)

        # Parse provisions with details
        provisions = self._parse_provisions(provisions_raw, case_id)

        # Create alignments
        alignments = []
        aligned_provision_uris = set()

        for principle in principles_raw:
            alignment = self._align_principle(principle, provisions, case_id)
            alignments.append(alignment)
            aligned_provision_uris.update(alignment.provision_uris)

        # Find unaligned items
        unaligned_principles = [
            a.principle_label for a in alignments
            if not a.provision_uris
        ]
        unaligned_provisions = [
            p.label for p in provisions
            if p.uri not in aligned_provision_uris
        ]

        # Calculate alignment rate
        aligned_count = sum(1 for a in alignments if a.provision_uris)
        alignment_rate = aligned_count / len(alignments) if alignments else 0.0

        result = AlignmentMap(
            case_id=case_id,
            alignments=alignments,
            unaligned_principles=unaligned_principles,
            unaligned_provisions=unaligned_provisions,
            total_principles=len(principles_raw),
            total_provisions=len(provisions),
            alignment_rate=alignment_rate
        )

        logger.info(
            f"Alignment complete: {aligned_count}/{len(alignments)} principles aligned, "
            f"{len(unaligned_provisions)} provisions unused"
        )

        return result

    def _load_principles(self, case_id: int) -> List[TemporaryRDFStorage]:
        """Load principle entities from database."""
        return TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type='Principles'
        ).all()

    def _load_provisions(self, case_id: int) -> List[TemporaryRDFStorage]:
        """Load code provision entities from database."""
        return TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()

    def _parse_provisions(
        self,
        provisions_raw: List[TemporaryRDFStorage],
        case_id: int
    ) -> List[ProvisionDetail]:
        """Parse provisions into detailed structures."""
        provisions = []

        for p in provisions_raw:
            label = p.entity_label
            section = self._extract_section(label)
            level = self._determine_level(section)
            key_terms = self._extract_key_terms(label, p.entity_definition or "")

            provision = ProvisionDetail(
                uri=p.entity_uri or f"case-{case_id}#{label.replace(' ', '_')}",
                label=label,
                section=section,
                text=p.entity_definition or "",
                level=level,
                key_terms=key_terms
            )
            provisions.append(provision)

        return provisions

    def _extract_section(self, label: str) -> str:
        """Extract section number from provision label."""
        import re
        # Match patterns like "II.1.c", "III.9", "I.2"
        match = re.search(r'([IVX]+\.[\d]+(?:\.[a-z])?)', label)
        if match:
            return match.group(1)

        # Try just Roman numeral + number
        match = re.search(r'([IVX]+)[\s_]?(\d+)', label)
        if match:
            return f"{match.group(1)}.{match.group(2)}"

        return ""

    def _determine_level(self, section: str) -> str:
        """Determine provision level from section prefix."""
        if not section:
            return "unknown"

        prefix = section.split('.')[0] if '.' in section else section
        return PROVISION_LEVELS.get(prefix, "unknown")

    def _extract_key_terms(self, label: str, definition: str) -> List[str]:
        """Extract key terms from provision text."""
        text = f"{label} {definition}".lower()
        terms = []

        # Check for support type keywords
        for support_type, keywords in SUPPORT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text and kw not in terms:
                    terms.append(kw)

        return terms[:5]  # Limit to 5 terms

    def _align_principle(
        self,
        principle: TemporaryRDFStorage,
        provisions: List[ProvisionDetail],
        case_id: int
    ) -> PrincipleAlignment:
        """Align a single principle with matching provisions."""
        label = principle.entity_label
        definition = principle.entity_definition or ""
        uri = principle.entity_uri or f"case-{case_id}#{label.replace(' ', '_')}"

        # Determine universal category (Beauchamp & Childress)
        universal_category = self._map_to_universal(label, definition)

        # Find support type
        support_type = self._determine_support_type(label, definition)

        # Find matching provisions
        matched_provisions = self._find_matching_provisions(
            label, definition, provisions
        )

        # Extract key terms
        key_terms = self._extract_principle_key_terms(label, definition)

        # Calculate confidence
        confidence = self._calculate_alignment_confidence(
            label, definition, matched_provisions
        )

        return PrincipleAlignment(
            principle_uri=uri,
            principle_label=label,
            principle_definition=definition,
            universal_category=universal_category,
            provision_uris=[p.uri for p in matched_provisions],
            provision_labels=[p.label for p in matched_provisions],
            provision_sections=[p.section for p in matched_provisions],
            support_type=support_type,
            key_terms=key_terms,
            alignment_confidence=confidence
        )

    def _map_to_universal(self, label: str, definition: str) -> Optional[str]:
        """Map principle to Beauchamp & Childress universal category."""
        text = f"{label} {definition}".lower()

        # Use domain's principle mapping
        for principle_name, bc_category in self.principle_mapping.items():
            if principle_name.lower() in text:
                return bc_category

        # Fallback keyword matching
        bc_keywords = {
            'beneficence': ['benefit', 'welfare', 'good', 'safety', 'protect'],
            'non_maleficence': ['harm', 'risk', 'damage', 'injury', 'prevent'],
            'autonomy': ['consent', 'choice', 'inform', 'decision', 'rights'],
            'justice': ['fair', 'equal', 'credit', 'attribution', 'distribute'],
        }

        for category, keywords in bc_keywords.items():
            if any(kw in text for kw in keywords):
                return category

        return None

    def _determine_support_type(self, label: str, definition: str) -> str:
        """Determine what ethical stance this principle supports."""
        text = f"{label} {definition}".lower()

        for support_type, keywords in SUPPORT_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return support_type

        return "unclassified"

    def _find_matching_provisions(
        self,
        principle_label: str,
        principle_def: str,
        provisions: List[ProvisionDetail]
    ) -> List[ProvisionDetail]:
        """Find provisions that support this principle."""
        matched = []
        principle_text = f"{principle_label} {principle_def}".lower()
        principle_terms = set(self._extract_key_terms(principle_label, principle_def))

        for provision in provisions:
            score = self._calculate_provision_match_score(
                principle_text, principle_terms, provision
            )
            if score > 0.3:
                matched.append((provision, score))

        # Sort by score and return provisions only
        matched.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in matched[:3]]  # Limit to top 3

    def _calculate_provision_match_score(
        self,
        principle_text: str,
        principle_terms: set,
        provision: ProvisionDetail
    ) -> float:
        """Calculate how well a provision matches a principle."""
        score = 0.0
        provision_text = f"{provision.label} {provision.text}".lower()
        provision_terms = set(provision.key_terms)

        # Term overlap
        term_overlap = len(principle_terms & provision_terms)
        score += term_overlap * 0.2

        # Check for section-based matching (from provision_structure)
        # Higher level provisions (I) are more fundamental
        level_weights = {
            'fundamental_canons': 0.3,
            'rules_of_practice': 0.2,
            'professional_obligations': 0.15,
            'unknown': 0.1,
        }
        score += level_weights.get(provision.level, 0.1)

        # Direct keyword matching
        principle_words = set(principle_text.split())
        provision_words = set(provision_text.split())
        word_overlap = len(principle_words & provision_words)
        score += word_overlap * 0.02

        return min(score, 1.0)

    def _extract_principle_key_terms(self, label: str, definition: str) -> List[str]:
        """Extract key terms from principle for argument formulation."""
        text = f"{label} {definition}".lower()
        terms = []

        # Extract meaningful terms
        for support_type, keywords in SUPPORT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text and kw not in terms:
                    terms.append(kw)

        # Also extract from label directly
        label_parts = label.replace('_', ' ').split()
        for part in label_parts:
            part_lower = part.lower()
            if len(part_lower) > 3 and part_lower not in ['principle', 'the', 'and', 'for']:
                if part_lower not in terms:
                    terms.append(part_lower)

        return terms[:6]  # Limit

    def _calculate_alignment_confidence(
        self,
        label: str,
        definition: str,
        matched_provisions: List[ProvisionDetail]
    ) -> float:
        """Calculate confidence in the alignment."""
        if not matched_provisions:
            return 0.0

        confidence = 0.3  # Base confidence for having any match

        # More provisions = higher confidence
        confidence += min(len(matched_provisions) * 0.15, 0.3)

        # Higher-level provisions = higher confidence
        has_fundamental = any(p.level == 'fundamental_canons' for p in matched_provisions)
        if has_fundamental:
            confidence += 0.2

        # Strong term overlap
        principle_terms = set(self._extract_key_terms(label, definition))
        for p in matched_provisions:
            provision_terms = set(p.key_terms)
            if len(principle_terms & provision_terms) >= 2:
                confidence += 0.1
                break

        return min(confidence, 1.0)

    def get_alignment_for_principle(
        self,
        alignment_map: AlignmentMap,
        principle_uri: str
    ) -> Optional[PrincipleAlignment]:
        """Get alignment for a specific principle URI."""
        for alignment in alignment_map.alignments:
            if alignment.principle_uri == principle_uri:
                return alignment
        return None

    def get_provisions_for_support_type(
        self,
        alignment_map: AlignmentMap,
        support_type: str
    ) -> List[PrincipleAlignment]:
        """Get all alignments that support a particular stance."""
        return [
            a for a in alignment_map.alignments
            if a.support_type == support_type
        ]


def get_principle_provision_alignment(
    case_id: int,
    domain: str = 'engineering'
) -> AlignmentMap:
    """
    Convenience function to get principle-provision alignment.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)

    Returns:
        AlignmentMap with alignment results
    """
    domain_config = get_domain_config(domain)
    aligner = PrincipleProvisionAligner(domain_config)
    return aligner.align_principles_provisions(case_id)
