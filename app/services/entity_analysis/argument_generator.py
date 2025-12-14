"""
Argument Generator (Step F2)

Generates Toulmin-structured arguments grounded in extracted entities.
Each argument component (claim, warrant, backing, data, qualifier, rebuttal)
is linked to specific entity URIs from the extraction pipeline.

Toulmin Structure (1958):
- CLAIM: What we're arguing for
- WARRANT: The principle/rule that authorizes the claim (from Obligations)
- BACKING: Authority supporting the warrant (from Code Provisions)
- DATA/GROUNDS: Facts supporting the claim (from Actions/Events)
- QUALIFIER: Conditions limiting the claim (from Constraints/Capabilities)
- REBUTTAL: Conditions under which claim doesn't hold (from conflicting Obligations)

Based on Oakley & Cocking (2001): Professional obligations as warrants,
Code provisions as backing.
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config
from app.services.entity_analysis.decision_point_composer import (
    EntityGroundedDecisionPoint,
    DecisionPointOption,
    ComposedDecisionPoints,
    compose_decision_points
)
from app.services.entity_analysis.principle_provision_aligner import (
    AlignmentMap,
    PrincipleAlignment,
    get_principle_provision_alignment
)

logger = logging.getLogger(__name__)


@dataclass
class ArgumentComponent:
    """A single component of a Toulmin argument."""
    text: str
    entity_uri: Optional[str] = None
    entity_label: Optional[str] = None
    entity_type: Optional[str] = None  # obligation, provision, action, etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityGroundedArgument:
    """A complete Toulmin-structured argument grounded in entities."""
    argument_id: str
    argument_type: str  # 'pro' or 'con'
    decision_point_id: str
    option_id: str
    option_description: str

    # Toulmin components
    claim: ArgumentComponent
    warrant: ArgumentComponent  # From Obligation
    backing: ArgumentComponent  # From Provision
    data: List[ArgumentComponent] = field(default_factory=list)  # From Actions/Events
    qualifier: Optional[ArgumentComponent] = None  # From Constraint/Capability
    rebuttal: Optional[ArgumentComponent] = None  # From conflicting Obligation

    # Role ethics analysis
    role_uri: str = ""
    role_label: str = ""
    founding_good_analysis: str = ""
    professional_virtues: List[str] = field(default_factory=list)

    # Metadata
    confidence_score: float = 0.0
    source_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'argument_id': self.argument_id,
            'argument_type': self.argument_type,
            'decision_point_id': self.decision_point_id,
            'option_id': self.option_id,
            'option_description': self.option_description,
            'claim': self.claim.to_dict(),
            'warrant': self.warrant.to_dict(),
            'backing': self.backing.to_dict(),
            'data': [d.to_dict() for d in self.data],
            'qualifier': self.qualifier.to_dict() if self.qualifier else None,
            'rebuttal': self.rebuttal.to_dict() if self.rebuttal else None,
            'role_uri': self.role_uri,
            'role_label': self.role_label,
            'founding_good_analysis': self.founding_good_analysis,
            'professional_virtues': self.professional_virtues,
            'confidence_score': self.confidence_score,
            'source_entities': self.source_entities
        }


@dataclass
class GeneratedArguments:
    """Collection of generated arguments for a case."""
    case_id: int
    arguments: List[EntityGroundedArgument] = field(default_factory=list)
    decision_points_covered: int = 0
    options_with_arguments: int = 0
    pro_argument_count: int = 0
    con_argument_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'arguments': [a.to_dict() for a in self.arguments],
            'decision_points_covered': self.decision_points_covered,
            'options_with_arguments': self.options_with_arguments,
            'pro_argument_count': self.pro_argument_count,
            'con_argument_count': self.con_argument_count
        }


class ArgumentGenerator:
    """
    Generates entity-grounded Toulmin-structured arguments.

    Step F2 in the entity-grounded argument pipeline.
    """

    def __init__(self, domain_config: Optional[DomainConfig] = None):
        """
        Initialize with optional domain configuration.

        Args:
            domain_config: Domain-specific config. Defaults to engineering.
        """
        self.domain = domain_config or get_domain_config('engineering')
        self.founding_good = self.domain.founding_good
        self.founding_good_description = self.domain.founding_good_description
        self.professional_virtues = self.domain.professional_virtues

    def generate_arguments(
        self,
        case_id: int,
        decision_points: Optional[ComposedDecisionPoints] = None,
        alignment_map: Optional[AlignmentMap] = None
    ) -> GeneratedArguments:
        """
        Generate pro/con arguments for all decision points.

        Args:
            case_id: The case to analyze
            decision_points: Output from E3 (optional, will compute if not provided)
            alignment_map: Output from F1 (optional, will compute if not provided)

        Returns:
            GeneratedArguments with entity-grounded arguments
        """
        logger.info(f"Generating arguments for case {case_id}")

        # Get E3 and F1 outputs if not provided
        if decision_points is None:
            decision_points = compose_decision_points(case_id, self.domain.name)
        if alignment_map is None:
            alignment_map = get_principle_provision_alignment(case_id, self.domain.name)

        # Load additional entities for argument construction
        obligations = self._load_entities(case_id, 'Obligations')
        constraints = self._load_entities(case_id, 'Constraints')
        capabilities = self._load_entities(case_id, 'Capabilities')
        actions = self._load_entities(case_id, 'Actions')
        events = self._load_entities(case_id, 'Events')
        principles = self._load_entities(case_id, 'Principles')

        # Build entity lookups
        entity_lookup = self._build_entity_lookup(
            obligations + constraints + capabilities + actions + events + principles
        )

        arguments = []
        argument_counter = 1
        options_with_args = set()

        for dp in decision_points.decision_points:
            for option in dp.options:
                # Generate PRO argument
                pro_arg = self._generate_pro_argument(
                    dp, option, alignment_map, entity_lookup,
                    argument_counter, case_id
                )
                if pro_arg:
                    arguments.append(pro_arg)
                    options_with_args.add(f"{dp.focus_id}:{option.option_id}")
                    argument_counter += 1

                # Generate CON argument
                con_arg = self._generate_con_argument(
                    dp, option, alignment_map, entity_lookup,
                    argument_counter, case_id
                )
                if con_arg:
                    arguments.append(con_arg)
                    argument_counter += 1

        # Count types
        pro_count = sum(1 for a in arguments if a.argument_type == 'pro')
        con_count = sum(1 for a in arguments if a.argument_type == 'con')

        result = GeneratedArguments(
            case_id=case_id,
            arguments=arguments,
            decision_points_covered=len(decision_points.decision_points),
            options_with_arguments=len(options_with_args),
            pro_argument_count=pro_count,
            con_argument_count=con_count
        )

        logger.info(
            f"Generated {len(arguments)} arguments: {pro_count} pro, {con_count} con "
            f"covering {len(options_with_args)} options"
        )

        return result

    def _load_entities(self, case_id: int, entity_type: str) -> List[TemporaryRDFStorage]:
        """Load entities of a specific type."""
        return TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=entity_type
        ).all()

    def _build_entity_lookup(
        self,
        entities: List[TemporaryRDFStorage]
    ) -> Dict[str, Dict[str, Any]]:
        """Build lookup dictionary from entity URI to details."""
        lookup = {}
        for e in entities:
            uri = e.entity_uri or f"case-{e.case_id}#{e.entity_label.replace(' ', '_')}"
            lookup[uri] = {
                'uri': uri,
                'label': e.entity_label,
                'definition': e.entity_definition or "",
                'type': e.entity_type,
                'json_ld': e.rdf_json_ld or {}
            }
            # Also add by label for fuzzy matching
            lookup[e.entity_label] = lookup[uri]
        return lookup

    def _generate_pro_argument(
        self,
        dp: EntityGroundedDecisionPoint,
        option: DecisionPointOption,
        alignment_map: AlignmentMap,
        entity_lookup: Dict[str, Dict],
        arg_number: int,
        case_id: int
    ) -> Optional[EntityGroundedArgument]:
        """Generate a PRO argument for this option."""
        # Get warrant from obligation/constraint in grounding
        warrant_uri = dp.grounding.obligation_uri or dp.grounding.constraint_uri
        warrant_label = dp.grounding.obligation_label or dp.grounding.constraint_label

        if not warrant_uri:
            logger.warning(f"No warrant found for {dp.focus_id}")
            return None

        warrant_info = entity_lookup.get(warrant_uri, {})

        # Find backing from provisions
        backing = self._find_backing_provision(dp, alignment_map, entity_lookup)

        # Build data from action and events
        data_components = self._build_data_components(option, entity_lookup)

        # Find qualifier from constraints/capabilities
        qualifier = self._find_qualifier(dp, entity_lookup, case_id)

        # Build claim text
        claim_text = self._generate_pro_claim(dp, option)

        # Analyze founding good alignment
        founding_analysis = self._analyze_founding_good(
            claim_text, warrant_label, "pro"
        )

        # Identify relevant virtues
        virtues = self._identify_relevant_virtues(warrant_label, option.action_label)

        # Calculate confidence
        confidence = self._calculate_argument_confidence(
            warrant_uri, backing, data_components
        )

        # Collect all source entity URIs
        source_entities = [warrant_uri]
        if backing and backing.entity_uri:
            source_entities.append(backing.entity_uri)
        source_entities.extend(d.entity_uri for d in data_components if d.entity_uri)

        return EntityGroundedArgument(
            argument_id=f"A{arg_number}",
            argument_type="pro",
            decision_point_id=dp.focus_id,
            option_id=option.option_id,
            option_description=option.description,
            claim=ArgumentComponent(
                text=claim_text,
                entity_uri=option.action_uri,
                entity_label=option.action_label,
                entity_type="action"
            ),
            warrant=ArgumentComponent(
                text=f"Because {warrant_label} requires this action",
                entity_uri=warrant_uri,
                entity_label=warrant_label,
                entity_type="obligation"
            ),
            backing=backing,
            data=data_components,
            qualifier=qualifier,
            rebuttal=None,  # Will be added if conflicts exist
            role_uri=dp.grounding.role_uri,
            role_label=dp.grounding.role_label,
            founding_good_analysis=founding_analysis,
            professional_virtues=virtues,
            confidence_score=confidence,
            source_entities=source_entities
        )

    def _generate_con_argument(
        self,
        dp: EntityGroundedDecisionPoint,
        option: DecisionPointOption,
        alignment_map: AlignmentMap,
        entity_lookup: Dict[str, Dict],
        arg_number: int,
        case_id: int
    ) -> Optional[EntityGroundedArgument]:
        """Generate a CON argument against this option."""
        # For CON, we need a conflicting obligation or constraint
        conflicting_warrant = self._find_conflicting_warrant(dp, entity_lookup, case_id)

        if not conflicting_warrant:
            # No explicit conflict - generate based on potential harm
            return self._generate_harm_based_con(
                dp, option, alignment_map, entity_lookup, arg_number, case_id
            )

        # Find backing for conflicting warrant
        backing = self._find_backing_for_principle(
            conflicting_warrant.get('label', ''), alignment_map
        )

        # Build claim
        claim_text = self._generate_con_claim(dp, option)

        # Analyze founding good violation potential
        founding_analysis = self._analyze_founding_good(
            claim_text, conflicting_warrant.get('label', ''), "con"
        )

        virtues = self._identify_relevant_virtues(
            conflicting_warrant.get('label', ''), option.action_label
        )

        confidence = self._calculate_argument_confidence(
            conflicting_warrant.get('uri', ''), backing, []
        )

        return EntityGroundedArgument(
            argument_id=f"A{arg_number}",
            argument_type="con",
            decision_point_id=dp.focus_id,
            option_id=option.option_id,
            option_description=option.description,
            claim=ArgumentComponent(
                text=claim_text,
                entity_uri=option.action_uri,
                entity_label=option.action_label,
                entity_type="action"
            ),
            warrant=ArgumentComponent(
                text=f"Because {conflicting_warrant.get('label', 'this')} would be violated",
                entity_uri=conflicting_warrant.get('uri', ''),
                entity_label=conflicting_warrant.get('label', ''),
                entity_type="obligation"
            ),
            backing=backing,
            data=[],
            qualifier=None,
            rebuttal=ArgumentComponent(
                text=f"Unless {dp.grounding.obligation_label or 'the primary obligation'} takes precedence",
                entity_uri=dp.grounding.obligation_uri,
                entity_label=dp.grounding.obligation_label,
                entity_type="obligation"
            ) if dp.grounding.obligation_uri else None,
            role_uri=dp.grounding.role_uri,
            role_label=dp.grounding.role_label,
            founding_good_analysis=founding_analysis,
            professional_virtues=virtues,
            confidence_score=confidence,
            source_entities=[conflicting_warrant.get('uri', '')] if conflicting_warrant.get('uri') else []
        )

    def _generate_harm_based_con(
        self,
        dp: EntityGroundedDecisionPoint,
        option: DecisionPointOption,
        alignment_map: AlignmentMap,
        entity_lookup: Dict[str, Dict],
        arg_number: int,
        case_id: int
    ) -> Optional[EntityGroundedArgument]:
        """Generate a CON argument based on potential harm/consequences."""
        # Check for negative consequences in downstream events
        if not option.downstream_event_uris:
            return None

        # Build claim
        claim_text = f"{dp.grounding.role_label} should NOT {option.description} due to potential consequences"

        # Build data from downstream events
        data_components = []
        for event_uri in option.downstream_event_uris[:2]:
            event_info = entity_lookup.get(event_uri, {})
            if event_info:
                data_components.append(ArgumentComponent(
                    text=f"May lead to: {event_info.get('label', event_uri)}",
                    entity_uri=event_uri,
                    entity_label=event_info.get('label', ''),
                    entity_type="event"
                ))

        if not data_components:
            return None

        return EntityGroundedArgument(
            argument_id=f"A{arg_number}",
            argument_type="con",
            decision_point_id=dp.focus_id,
            option_id=option.option_id,
            option_description=option.description,
            claim=ArgumentComponent(
                text=claim_text,
                entity_uri=option.action_uri,
                entity_label=option.action_label,
                entity_type="action"
            ),
            warrant=ArgumentComponent(
                text=f"Because professional {self.founding_good.replace('_', ' ')} could be compromised",
                entity_uri=None,
                entity_label=self.founding_good,
                entity_type="founding_good"
            ),
            backing=ArgumentComponent(
                text=self.founding_good_description,
                entity_uri=None,
                entity_label="Founding Good",
                entity_type="principle"
            ),
            data=data_components,
            qualifier=None,
            rebuttal=None,
            role_uri=dp.grounding.role_uri,
            role_label=dp.grounding.role_label,
            founding_good_analysis=f"This option may compromise {self.founding_good.replace('_', ' ')}",
            professional_virtues=[],
            confidence_score=0.5,  # Lower confidence for harm-based argument
            source_entities=option.downstream_event_uris[:2]
        )

    def _find_backing_provision(
        self,
        dp: EntityGroundedDecisionPoint,
        alignment_map: AlignmentMap,
        entity_lookup: Dict[str, Dict]
    ) -> ArgumentComponent:
        """Find a code provision to back the warrant."""
        # First try from decision point's provisions
        if dp.provision_uris:
            provision_uri = dp.provision_uris[0]
            provision_label = dp.provision_labels[0] if dp.provision_labels else provision_uri
            return ArgumentComponent(
                text=f"As stated in {provision_label}",
                entity_uri=provision_uri,
                entity_label=provision_label,
                entity_type="provision"
            )

        # Try from alignment map
        obligation_label = dp.grounding.obligation_label or ""
        for alignment in alignment_map.alignments:
            # Check if any principle relates to this obligation
            if self._texts_overlap(alignment.principle_label, obligation_label):
                if alignment.provision_uris:
                    return ArgumentComponent(
                        text=f"As stated in {alignment.provision_labels[0]}",
                        entity_uri=alignment.provision_uris[0],
                        entity_label=alignment.provision_labels[0],
                        entity_type="provision"
                    )

        # Fallback - generic backing
        code_name = self.domain.provision_structure.code_name or 'Code of Ethics'
        return ArgumentComponent(
            text=f"As required by the {code_name}",
            entity_uri=None,
            entity_label=code_name,
            entity_type="code"
        )

    def _find_backing_for_principle(
        self,
        principle_label: str,
        alignment_map: AlignmentMap
    ) -> ArgumentComponent:
        """Find backing provision for a principle."""
        for alignment in alignment_map.alignments:
            if self._texts_overlap(alignment.principle_label, principle_label):
                if alignment.provision_uris:
                    return ArgumentComponent(
                        text=f"As stated in {alignment.provision_labels[0]}",
                        entity_uri=alignment.provision_uris[0],
                        entity_label=alignment.provision_labels[0],
                        entity_type="provision"
                    )

        return ArgumentComponent(
            text="According to professional standards",
            entity_uri=None,
            entity_label="Professional Standards",
            entity_type="code"
        )

    def _build_data_components(
        self,
        option: DecisionPointOption,
        entity_lookup: Dict[str, Dict]
    ) -> List[ArgumentComponent]:
        """Build data/grounds components from action and events."""
        data = []

        # Add the action itself
        action_info = entity_lookup.get(option.action_uri, {})
        data.append(ArgumentComponent(
            text=f"The action: {option.action_label}",
            entity_uri=option.action_uri,
            entity_label=option.action_label,
            entity_type="action"
        ))

        # Add downstream events
        for event_uri in option.downstream_event_uris[:2]:  # Limit to 2
            event_info = entity_lookup.get(event_uri, {})
            if event_info:
                data.append(ArgumentComponent(
                    text=f"Leads to: {event_info.get('label', event_uri)}",
                    entity_uri=event_uri,
                    entity_label=event_info.get('label', ''),
                    entity_type="event"
                ))

        return data

    def _find_qualifier(
        self,
        dp: EntityGroundedDecisionPoint,
        entity_lookup: Dict[str, Dict],
        case_id: int
    ) -> Optional[ArgumentComponent]:
        """Find a qualifier from constraints or capabilities."""
        # Check if decision point has a constraint
        if dp.grounding.constraint_uri:
            return ArgumentComponent(
                text=f"Provided that {dp.grounding.constraint_label}",
                entity_uri=dp.grounding.constraint_uri,
                entity_label=dp.grounding.constraint_label,
                entity_type="constraint"
            )

        # Look for capabilities that might qualify the argument
        capabilities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type='Capabilities'
        ).limit(3).all()

        for cap in capabilities:
            cap_label = cap.entity_label.lower()
            role_label = dp.grounding.role_label.lower()
            # Check if capability relates to this role
            if role_label.replace(' ', '') in cap_label.replace(' ', '').replace('_', ''):
                return ArgumentComponent(
                    text=f"Given the capability: {cap.entity_label}",
                    entity_uri=cap.entity_uri,
                    entity_label=cap.entity_label,
                    entity_type="capability"
                )

        return None

    def _find_conflicting_warrant(
        self,
        dp: EntityGroundedDecisionPoint,
        entity_lookup: Dict[str, Dict],
        case_id: int
    ) -> Optional[Dict[str, str]]:
        """Find an obligation that conflicts with the decision point's primary obligation."""
        if not dp.grounding.obligation_uri:
            return None

        # Load obligations to find conflicts
        obligations = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type='Obligations'
        ).all()

        primary_label = dp.grounding.obligation_label.lower() if dp.grounding.obligation_label else ""

        for obl in obligations:
            obl_label = obl.entity_label.lower()
            obl_uri = obl.entity_uri or f"case-{case_id}#{obl.entity_label.replace(' ', '_')}"

            # Skip the primary obligation
            if obl_uri == dp.grounding.obligation_uri:
                continue

            # Check for potential conflict based on keywords
            if self._are_potentially_conflicting(primary_label, obl_label):
                return {
                    'uri': obl_uri,
                    'label': obl.entity_label,
                    'definition': obl.entity_definition or ""
                }

        return None

    def _are_potentially_conflicting(self, label1: str, label2: str) -> bool:
        """Check if two obligations might conflict."""
        conflict_pairs = [
            ({'disclosure', 'transparency'}, {'confidential', 'privacy'}),
            ({'safety'}, {'efficiency', 'cost'}),
            ({'verify', 'review'}, {'delegate', 'trust'}),
        ]

        for set1, set2 in conflict_pairs:
            if (any(w in label1 for w in set1) and any(w in label2 for w in set2)) or \
               (any(w in label2 for w in set1) and any(w in label1 for w in set2)):
                return True

        return False

    def _generate_pro_claim(
        self,
        dp: EntityGroundedDecisionPoint,
        option: DecisionPointOption
    ) -> str:
        """Generate PRO argument claim text."""
        return f"{dp.grounding.role_label} should {option.description}"

    def _generate_con_claim(
        self,
        dp: EntityGroundedDecisionPoint,
        option: DecisionPointOption
    ) -> str:
        """Generate CON argument claim text."""
        return f"{dp.grounding.role_label} should NOT {option.description}"

    def _analyze_founding_good(
        self,
        claim: str,
        warrant_label: str,
        arg_type: str
    ) -> str:
        """Analyze how the argument relates to the profession's founding good."""
        founding = self.founding_good.replace('_', ' ')

        if arg_type == "pro":
            return f"This action supports {founding} by fulfilling the {warrant_label}"
        else:
            return f"This action may compromise {founding} by violating the {warrant_label}"

    def _identify_relevant_virtues(
        self,
        warrant_label: str,
        action_label: str
    ) -> List[str]:
        """Identify which professional virtues are relevant."""
        text = f"{warrant_label} {action_label}".lower()
        virtues = []

        virtue_keywords = {
            'competence': ['competence', 'skill', 'qualified', 'expertise'],
            'trustworthiness': ['trust', 'reliable', 'faithful', 'commitment'],
            'honesty': ['honest', 'truth', 'disclosure', 'transparency'],
            'humility': ['humble', 'limitation', 'acknowledge', 'admit'],
            'diligence': ['diligent', 'careful', 'thorough', 'review'],
        }

        for virtue in self.professional_virtues:
            keywords = virtue_keywords.get(virtue, [virtue])
            if any(kw in text for kw in keywords):
                virtues.append(virtue)

        return virtues

    def _calculate_argument_confidence(
        self,
        warrant_uri: str,
        backing: ArgumentComponent,
        data: List[ArgumentComponent]
    ) -> float:
        """Calculate confidence score for the argument."""
        confidence = 0.3  # Base confidence

        # Has valid warrant
        if warrant_uri:
            confidence += 0.2

        # Has backing with entity URI
        if backing and backing.entity_uri:
            confidence += 0.2

        # Has data with entity URIs
        grounded_data = sum(1 for d in data if d.entity_uri)
        confidence += min(grounded_data * 0.1, 0.3)

        return min(confidence, 1.0)

    def _texts_overlap(self, text1: str, text2: str) -> bool:
        """Check if two texts have significant word overlap."""
        words1 = set(text1.lower().replace('_', ' ').split())
        words2 = set(text2.lower().replace('_', ' ').split())

        # Remove common words
        common = {'the', 'a', 'an', 'to', 'for', 'of', 'and', 'or', 'in', 'on'}
        words1 -= common
        words2 -= common

        overlap = len(words1 & words2)
        return overlap >= 2


def generate_arguments(
    case_id: int,
    domain: str = 'engineering'
) -> GeneratedArguments:
    """
    Convenience function to generate arguments.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)

    Returns:
        GeneratedArguments with entity-grounded arguments
    """
    domain_config = get_domain_config(domain)
    generator = ArgumentGenerator(domain_config)
    return generator.generate_arguments(case_id)
