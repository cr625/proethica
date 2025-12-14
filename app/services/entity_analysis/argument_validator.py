"""
Argument Validator (Step F3)

Validates entity-grounded arguments using three-tier role ethics tests
derived from Oakley & Cocking (2001).

Three-Tier Validation:
1. Entity Reference Validation: All entity URIs must exist in extracted data
2. Founding Value Test: Argument cannot violate the profession's founding good
3. Professional Virtue Test: Argument must align with professional virtues

This validator ensures arguments are both well-formed (structurally) and
ethically coherent (substantively).
"""

import logging
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage
from app.domains import DomainConfig, get_domain_config
from app.services.entity_analysis.argument_generator import (
    EntityGroundedArgument,
    ArgumentComponent,
    GeneratedArguments,
    generate_arguments
)

logger = logging.getLogger(__name__)


@dataclass
class EntityReferenceValidation:
    """Result of entity reference validation (Test 1)."""
    is_valid: bool = True
    missing_entities: List[str] = field(default_factory=list)
    invalid_uris: List[str] = field(default_factory=list)
    total_references: int = 0
    valid_references: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FoundingValueValidation:
    """Result of founding value test (Test 2)."""
    is_compliant: bool = True
    founding_good: str = ""
    violation_detected: bool = False
    violation_reason: str = ""
    analysis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProfessionalVirtueValidation:
    """Result of professional virtue test (Test 3)."""
    is_valid: bool = True
    required_virtues: List[str] = field(default_factory=list)
    present_virtues: List[str] = field(default_factory=list)
    missing_virtues: List[str] = field(default_factory=list)
    capability_support: List[str] = field(default_factory=list)  # URIs of supporting capabilities

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Complete validation result for a single argument."""
    argument_id: str
    decision_point_id: str
    option_id: str
    argument_type: str

    # Three-tier results
    entity_validation: EntityReferenceValidation
    founding_value_validation: FoundingValueValidation
    virtue_validation: ProfessionalVirtueValidation

    # Overall assessment
    is_valid: bool = True
    validation_score: float = 0.0  # 0.0 to 1.0
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'argument_id': self.argument_id,
            'decision_point_id': self.decision_point_id,
            'option_id': self.option_id,
            'argument_type': self.argument_type,
            'entity_validation': self.entity_validation.to_dict(),
            'founding_value_validation': self.founding_value_validation.to_dict(),
            'virtue_validation': self.virtue_validation.to_dict(),
            'is_valid': self.is_valid,
            'validation_score': self.validation_score,
            'validation_notes': self.validation_notes
        }


@dataclass
class ValidatedArguments:
    """Collection of validated arguments for a case."""
    case_id: int
    validations: List[ValidationResult] = field(default_factory=list)
    total_arguments: int = 0
    valid_arguments: int = 0
    invalid_arguments: int = 0
    average_score: float = 0.0

    # Summary by test
    entity_test_pass_rate: float = 0.0
    founding_test_pass_rate: float = 0.0
    virtue_test_pass_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'validations': [v.to_dict() for v in self.validations],
            'total_arguments': self.total_arguments,
            'valid_arguments': self.valid_arguments,
            'invalid_arguments': self.invalid_arguments,
            'average_score': self.average_score,
            'entity_test_pass_rate': self.entity_test_pass_rate,
            'founding_test_pass_rate': self.founding_test_pass_rate,
            'virtue_test_pass_rate': self.virtue_test_pass_rate
        }


# Founding value violation indicators
FOUNDING_VALUE_VIOLATIONS = {
    'public_safety': {
        'violation_keywords': ['endanger', 'harm', 'risk', 'unsafe', 'negligent', 'reckless'],
        'severity_keywords': ['death', 'injury', 'damage', 'catastroph'],
    },
    'student_welfare': {
        'violation_keywords': ['harm', 'discriminat', 'exploit', 'neglect'],
        'severity_keywords': ['abuse', 'danger', 'trauma'],
    },
    'patient_health': {
        'violation_keywords': ['harm', 'negligent', 'endanger', 'unsafe'],
        'severity_keywords': ['death', 'injury', 'malpractice'],
    },
}


class ArgumentValidator:
    """
    Validates entity-grounded arguments using role ethics tests.

    Step F3 in the entity-grounded argument pipeline.
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

    def validate_arguments(
        self,
        case_id: int,
        arguments: Optional[GeneratedArguments] = None
    ) -> ValidatedArguments:
        """
        Validate all arguments for a case.

        Args:
            case_id: The case to analyze
            arguments: Output from F2 (optional, will compute if not provided)

        Returns:
            ValidatedArguments with validation results
        """
        logger.info(f"Validating arguments for case {case_id}")

        # Get F2 output if not provided
        if arguments is None:
            arguments = generate_arguments(case_id, self.domain.name)

        # Load all entities for reference validation
        entity_uris = self._load_all_entity_uris(case_id)
        capabilities = self._load_capabilities(case_id)

        validations = []
        for arg in arguments.arguments:
            validation = self.validate_argument(arg, entity_uris, capabilities, case_id)
            validations.append(validation)

        # Calculate summary statistics
        valid_count = sum(1 for v in validations if v.is_valid)
        entity_pass = sum(1 for v in validations if v.entity_validation.is_valid)
        founding_pass = sum(1 for v in validations if v.founding_value_validation.is_compliant)
        virtue_pass = sum(1 for v in validations if v.virtue_validation.is_valid)

        total = len(validations) or 1  # Avoid division by zero
        avg_score = sum(v.validation_score for v in validations) / total if validations else 0.0

        result = ValidatedArguments(
            case_id=case_id,
            validations=validations,
            total_arguments=len(arguments.arguments),
            valid_arguments=valid_count,
            invalid_arguments=len(arguments.arguments) - valid_count,
            average_score=avg_score,
            entity_test_pass_rate=entity_pass / total,
            founding_test_pass_rate=founding_pass / total,
            virtue_test_pass_rate=virtue_pass / total
        )

        logger.info(
            f"Validation complete: {valid_count}/{len(arguments.arguments)} valid, "
            f"average score: {avg_score:.2f}"
        )

        return result

    def validate_argument(
        self,
        argument: EntityGroundedArgument,
        entity_uris: Set[str],
        capabilities: List[Dict],
        case_id: int
    ) -> ValidationResult:
        """
        Validate a single argument using three-tier tests.

        Args:
            argument: The argument to validate
            entity_uris: Set of valid entity URIs
            capabilities: List of capability entities
            case_id: The case ID

        Returns:
            ValidationResult with detailed validation results
        """
        # Test 1: Entity Reference Validation
        entity_validation = self._validate_entity_references(argument, entity_uris)

        # Test 2: Founding Value Test
        founding_validation = self._validate_founding_value(argument)

        # Test 3: Professional Virtue Test
        virtue_validation = self._validate_professional_virtues(argument, capabilities)

        # Calculate overall validity and score
        notes = []
        score = 0.0

        # Entity test (40% weight)
        if entity_validation.is_valid:
            score += 0.4
        else:
            notes.append(f"Entity validation failed: {len(entity_validation.missing_entities)} missing references")

        # Founding value test (40% weight)
        if founding_validation.is_compliant:
            score += 0.4
        else:
            notes.append(f"Founding value violation: {founding_validation.violation_reason}")

        # Virtue test (20% weight)
        if virtue_validation.is_valid:
            score += 0.2
        else:
            notes.append(f"Missing virtues: {', '.join(virtue_validation.missing_virtues)}")

        # Overall validity requires passing all three tests
        is_valid = (
            entity_validation.is_valid and
            founding_validation.is_compliant and
            virtue_validation.is_valid
        )

        return ValidationResult(
            argument_id=argument.argument_id,
            decision_point_id=argument.decision_point_id,
            option_id=argument.option_id,
            argument_type=argument.argument_type,
            entity_validation=entity_validation,
            founding_value_validation=founding_validation,
            virtue_validation=virtue_validation,
            is_valid=is_valid,
            validation_score=score,
            validation_notes=notes
        )

    def _load_all_entity_uris(self, case_id: int) -> Set[str]:
        """Load all entity URIs for the case."""
        entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

        uris = set()
        for e in entities:
            if e.entity_uri:
                uris.add(e.entity_uri)
            # Also add generated URI pattern
            generated_uri = f"case-{case_id}#{e.entity_label.replace(' ', '_')}"
            uris.add(generated_uri)

        return uris

    def _load_capabilities(self, case_id: int) -> List[Dict]:
        """Load capability entities for virtue test."""
        caps = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type='Capabilities'
        ).all()

        return [
            {
                'uri': c.entity_uri or f"case-{case_id}#{c.entity_label.replace(' ', '_')}",
                'label': c.entity_label,
                'definition': c.entity_definition or ""
            }
            for c in caps
        ]

    def _validate_entity_references(
        self,
        argument: EntityGroundedArgument,
        valid_uris: Set[str]
    ) -> EntityReferenceValidation:
        """
        Test 1: Validate all entity references exist.

        From Oakley & Cocking: Arguments must be grounded in actual entities.
        """
        missing = []
        invalid = []
        total_refs = 0
        valid_refs = 0

        # Check warrant
        if argument.warrant.entity_uri:
            total_refs += 1
            if argument.warrant.entity_uri in valid_uris:
                valid_refs += 1
            else:
                missing.append(f"Warrant: {argument.warrant.entity_uri}")

        # Check backing
        if argument.backing and argument.backing.entity_uri:
            total_refs += 1
            if argument.backing.entity_uri in valid_uris:
                valid_refs += 1
            else:
                missing.append(f"Backing: {argument.backing.entity_uri}")

        # Check data
        for data in argument.data:
            if data.entity_uri:
                total_refs += 1
                if data.entity_uri in valid_uris:
                    valid_refs += 1
                else:
                    missing.append(f"Data: {data.entity_uri}")

        # Check qualifier
        if argument.qualifier and argument.qualifier.entity_uri:
            total_refs += 1
            if argument.qualifier.entity_uri in valid_uris:
                valid_refs += 1
            else:
                missing.append(f"Qualifier: {argument.qualifier.entity_uri}")

        # Check rebuttal
        if argument.rebuttal and argument.rebuttal.entity_uri:
            total_refs += 1
            if argument.rebuttal.entity_uri in valid_uris:
                valid_refs += 1
            else:
                missing.append(f"Rebuttal: {argument.rebuttal.entity_uri}")

        # Argument is valid if has at least warrant and >70% of references are valid
        validity_rate = valid_refs / total_refs if total_refs > 0 else 0
        is_valid = argument.warrant.entity_uri is not None and validity_rate >= 0.7

        return EntityReferenceValidation(
            is_valid=is_valid,
            missing_entities=missing,
            invalid_uris=invalid,
            total_references=total_refs,
            valid_references=valid_refs
        )

    def _validate_founding_value(
        self,
        argument: EntityGroundedArgument
    ) -> FoundingValueValidation:
        """
        Test 2: Check if argument violates the founding good.

        From Oakley & Cocking: No professional argument can lead to gross
        violation of the profession's founding good.
        """
        # Get violation indicators for this founding good
        violations = FOUNDING_VALUE_VIOLATIONS.get(
            self.founding_good,
            {'violation_keywords': [], 'severity_keywords': []}
        )

        claim_text = argument.claim.text.lower()
        warrant_text = argument.warrant.text.lower() if argument.warrant else ""
        analysis_text = argument.founding_good_analysis.lower()

        # Check for violation keywords
        violation_found = False
        violation_reason = ""

        for kw in violations['violation_keywords']:
            if kw in claim_text or kw in warrant_text:
                violation_found = True
                violation_reason = f"Claim or warrant contains violation indicator: '{kw}'"
                break

        # Check for severity keywords (more serious violations)
        if not violation_found:
            for kw in violations['severity_keywords']:
                if kw in claim_text or kw in analysis_text:
                    violation_found = True
                    violation_reason = f"Potential severe violation detected: '{kw}'"
                    break

        # For CON arguments, we expect potential violation analysis
        if argument.argument_type == 'con' and not violation_found:
            # CON arguments should identify potential violations
            violation_found = False  # CON args discussing violations are valid

        # Generate analysis
        analysis = self._generate_founding_analysis(argument, violation_found)

        return FoundingValueValidation(
            is_compliant=not violation_found,
            founding_good=self.founding_good,
            violation_detected=violation_found,
            violation_reason=violation_reason,
            analysis=analysis
        )

    def _generate_founding_analysis(
        self,
        argument: EntityGroundedArgument,
        violation_found: bool
    ) -> str:
        """Generate analysis of founding value alignment."""
        founding = self.founding_good.replace('_', ' ')

        if violation_found:
            return f"This argument may compromise {founding}. Review recommended."

        if argument.argument_type == 'pro':
            return f"This argument supports {founding} by promoting professional responsibility."
        else:
            return f"This argument identifies potential risks to {founding} for evaluation."

    def _validate_professional_virtues(
        self,
        argument: EntityGroundedArgument,
        capabilities: List[Dict]
    ) -> ProfessionalVirtueValidation:
        """
        Test 3: Check if argument aligns with professional virtues.

        From Oakley & Cocking: Professional actions require professional virtues,
        and virtues require capabilities.
        """
        # Determine required virtues based on warrant type
        required_virtues = self._determine_required_virtues(argument)

        # Check which virtues are present in the argument
        present_virtues = argument.professional_virtues.copy()

        # Also check argument text for virtue indicators
        text_virtues = self._extract_virtues_from_text(argument)
        present_virtues = list(set(present_virtues + text_virtues))

        # Find missing virtues
        missing = [v for v in required_virtues if v not in present_virtues]

        # Check capability support
        capability_support = self._find_capability_support(
            argument.role_label, required_virtues, capabilities
        )

        # Argument is valid if:
        # - Has at least one required virtue present, OR
        # - Has capability support, OR
        # - Is a CON argument (CON args don't need to demonstrate virtues)
        is_valid = (
            len(present_virtues) > 0 or
            len(capability_support) > 0 or
            argument.argument_type == 'con'
        )

        return ProfessionalVirtueValidation(
            is_valid=is_valid,
            required_virtues=required_virtues,
            present_virtues=present_virtues,
            missing_virtues=missing,
            capability_support=capability_support
        )

    def _determine_required_virtues(
        self,
        argument: EntityGroundedArgument
    ) -> List[str]:
        """Determine which virtues are required for this argument."""
        warrant_text = argument.warrant.text.lower() if argument.warrant else ""
        claim_text = argument.claim.text.lower()

        required = []

        virtue_triggers = {
            'competence': ['competence', 'qualified', 'skill', 'expertise', 'technical'],
            'trustworthiness': ['trust', 'reliable', 'faithful', 'commitment', 'promise'],
            'honesty': ['honest', 'truth', 'disclosure', 'transparency', 'inform'],
            'humility': ['humble', 'limitation', 'acknowledge', 'admit', 'uncertain'],
            'diligence': ['diligent', 'careful', 'thorough', 'review', 'verify'],
        }

        text = f"{warrant_text} {claim_text}"

        for virtue, triggers in virtue_triggers.items():
            if any(t in text for t in triggers):
                required.append(virtue)

        # Always require at least competence
        if not required:
            required.append('competence')

        return required

    def _extract_virtues_from_text(
        self,
        argument: EntityGroundedArgument
    ) -> List[str]:
        """Extract virtue indicators from argument text."""
        virtues = []

        texts = [
            argument.claim.text,
            argument.warrant.text if argument.warrant else "",
            argument.founding_good_analysis
        ]
        combined_text = " ".join(texts).lower()

        virtue_indicators = {
            'competence': ['competent', 'skilled', 'qualified', 'capable', 'expert'],
            'trustworthiness': ['trustworthy', 'reliable', 'dependable', 'faithful'],
            'honesty': ['honest', 'truthful', 'transparent', 'forthcoming'],
            'humility': ['humble', 'modest', 'acknowledge limitation'],
            'diligence': ['diligent', 'careful', 'thorough', 'meticulous'],
        }

        for virtue in self.professional_virtues:
            indicators = virtue_indicators.get(virtue, [virtue])
            if any(ind in combined_text for ind in indicators):
                virtues.append(virtue)

        return virtues

    def _find_capability_support(
        self,
        role_label: str,
        required_virtues: List[str],
        capabilities: List[Dict]
    ) -> List[str]:
        """Find capabilities that support the required virtues."""
        supporting = []
        role_lower = role_label.lower().replace(' ', '')

        for cap in capabilities:
            cap_label = cap['label'].lower()

            # Check if capability relates to the role
            if role_lower not in cap_label.replace(' ', '').replace('_', ''):
                continue

            # Check if capability supports any required virtue
            for virtue in required_virtues:
                if virtue in cap_label or virtue in cap.get('definition', '').lower():
                    supporting.append(cap['uri'])
                    break

        return supporting


def validate_arguments(
    case_id: int,
    domain: str = 'engineering'
) -> ValidatedArguments:
    """
    Convenience function to validate arguments.

    Args:
        case_id: Case to analyze
        domain: Domain code (default: engineering)

    Returns:
        ValidatedArguments with validation results
    """
    domain_config = get_domain_config(domain)
    validator = ArgumentValidator(domain_config)
    return validator.validate_arguments(case_id)
