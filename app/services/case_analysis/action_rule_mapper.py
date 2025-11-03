"""
Step 4 Part E: Action-Rule Mapper

Maps the three-rule framework from action-based scenario analysis to ProEthica formalism.

Theoretical foundation:
- Marchais-Roubelat & Roubelat (2015): Three-rule framework for scenario analysis
  - Action Rule (What?): What was done, what alternatives existed
  - Institutional Rule (Why?): What justified/opposed actions
  - Operations Rule (How?): Situational context and constraints

Maps ProEthica concepts to rules:
- Action Rule: A (actions), Ca (capabilities), Rs (resources)
- Institutional Rule: P (principles), O (obligations), Cs (constraints)
- Operations Rule: S (states), R (roles), Rs (resources), E (events)
- Steering Rule: Transformation points and rule shifts

Output: Complete three-rule mapping showing what happened, why, and how.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from app.utils.llm_utils import get_llm_client
from app.models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class ActionRule:
    """
    Action Rule: What was done?
    Maps: A (Actions), Ca (Capabilities), Rs (Resources)
    """
    actions_taken: List[str]
    actions_not_taken: List[str]
    alternatives_available: List[str]
    capability_constraints: List[str]
    resource_constraints: List[str]
    action_rule_narrative: str


@dataclass
class InstitutionalRule:
    """
    Institutional Rule: Why was it done (or not done)?
    Maps: P (Principles), O (Obligations), Cs (Constraints)
    """
    justifications: List[str]  # Principles/obligations supporting action
    oppositions: List[str]  # Principles/obligations opposing action
    relevant_obligations: List[str]  # NSPE Code obligations invoked
    constraint_factors: List[str]  # Legal/professional/organizational constraints
    institutional_rule_narrative: str


@dataclass
class OperationsRule:
    """
    Operations Rule: How did context shape actions?
    Maps: S (States), R (Roles), Rs (Resources), E (Events)
    """
    situational_context: List[str]  # States that framed the problem
    organizational_constraints: List[str]  # Role structures that limited choices
    resource_availability: List[str]  # What resources were/weren't available
    key_events: List[str]  # Events that triggered or constrained actions
    operations_rule_narrative: str


@dataclass
class SteeringRule:
    """
    Steering Rule: How did the case transform?
    Maps: E (Events), A (Actions), cross-concept interactions
    """
    transformation_points: List[str]  # When case shifted (e.g., "Routine → Board review")
    rule_shifts: List[str]  # How ethical framing changed
    steering_rule_narrative: str


@dataclass
class ActionRuleMapping:
    """
    Complete three-rule framework mapping for a case.

    Answers:
    - What? (Action Rule: A, Ca, Rs)
    - Why? (Institutional Rule: P, O, Cs)
    - How? (Operations Rule: S, R, Rs, E)
    - Transformation? (Steering Rule: E, A, interactions)
    """
    action_rule: ActionRule
    institutional_rule: InstitutionalRule
    operations_rule: OperationsRule
    steering_rule: SteeringRule

    overall_analysis: str  # Summary of how the three rules interact

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'action_rule': {
                'actions_taken': self.action_rule.actions_taken,
                'actions_not_taken': self.action_rule.actions_not_taken,
                'alternatives_available': self.action_rule.alternatives_available,
                'capability_constraints': self.action_rule.capability_constraints,
                'resource_constraints': self.action_rule.resource_constraints,
                'action_rule_narrative': self.action_rule.action_rule_narrative
            },
            'institutional_rule': {
                'justifications': self.institutional_rule.justifications,
                'oppositions': self.institutional_rule.oppositions,
                'relevant_obligations': self.institutional_rule.relevant_obligations,
                'constraint_factors': self.institutional_rule.constraint_factors,
                'institutional_rule_narrative': self.institutional_rule.institutional_rule_narrative
            },
            'operations_rule': {
                'situational_context': self.operations_rule.situational_context,
                'organizational_constraints': self.operations_rule.organizational_constraints,
                'resource_availability': self.operations_rule.resource_availability,
                'key_events': self.operations_rule.key_events,
                'operations_rule_narrative': self.operations_rule.operations_rule_narrative
            },
            'steering_rule': {
                'transformation_points': self.steering_rule.transformation_points,
                'rule_shifts': self.steering_rule.rule_shifts,
                'steering_rule_narrative': self.steering_rule.steering_rule_narrative
            },
            'overall_analysis': self.overall_analysis
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ActionRuleMapping':
        """
        Reconstruct ActionRuleMapping from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            ActionRuleMapping instance
        """
        action_rule_data = data.get('action_rule', {})
        institutional_rule_data = data.get('institutional_rule', {})
        operations_rule_data = data.get('operations_rule', {})
        steering_rule_data = data.get('steering_rule', {})

        action_rule = ActionRule(
            actions_taken=action_rule_data.get('actions_taken', []),
            actions_not_taken=action_rule_data.get('actions_not_taken', []),
            alternatives_available=action_rule_data.get('alternatives_available', []),
            capability_constraints=action_rule_data.get('capability_constraints', []),
            resource_constraints=action_rule_data.get('resource_constraints', []),
            action_rule_narrative=action_rule_data.get('action_rule_narrative', '')
        )

        institutional_rule = InstitutionalRule(
            justifications=institutional_rule_data.get('justifications', []),
            oppositions=institutional_rule_data.get('oppositions', []),
            relevant_obligations=institutional_rule_data.get('relevant_obligations', []),
            constraint_factors=institutional_rule_data.get('constraint_factors', []),
            institutional_rule_narrative=institutional_rule_data.get('institutional_rule_narrative', '')
        )

        operations_rule = OperationsRule(
            situational_context=operations_rule_data.get('situational_context', []),
            organizational_constraints=operations_rule_data.get('organizational_constraints', []),
            resource_availability=operations_rule_data.get('resource_availability', []),
            key_events=operations_rule_data.get('key_events', []),
            operations_rule_narrative=operations_rule_data.get('operations_rule_narrative', '')
        )

        steering_rule = SteeringRule(
            transformation_points=steering_rule_data.get('transformation_points', []),
            rule_shifts=steering_rule_data.get('rule_shifts', []),
            steering_rule_narrative=steering_rule_data.get('steering_rule_narrative', '')
        )

        return cls(
            action_rule=action_rule,
            institutional_rule=institutional_rule,
            operations_rule=operations_rule,
            steering_rule=steering_rule,
            overall_analysis=data.get('overall_analysis', '')
        )


class ActionRuleMapper:
    """
    Maps three-rule framework (action-based scenario analysis) to ProEthica concepts.

    Analyzes what happened (A), why (P/O/Cs), how (S/R/Rs/E), and transformation patterns.
    """

    def __init__(self, llm_client=None):
        """
        Initialize mapper with LLM client.

        Args:
            llm_client: Optional pre-initialized LLM client. If None, will get one via get_llm_client().
                       Pass an existing client when calling from SSE generator to avoid Flask context issues.
        """
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = get_llm_client()
        logger.info("[Action Rule Mapper] Initialized")

    def analyze_case(
        self,
        case_id: int,
        actions: List[Any],
        events: List[Any],
        states: List[Any],
        roles: List[Any],
        resources: List[Any],
        capabilities: List[Any],
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any],
        case_context: Optional[Dict] = None
    ) -> ActionRuleMapping:
        """
        Map three-rule framework to ProEthica entities for entire case.

        Args:
            case_id: Case ID
            actions: List of Action entities (Pass 3)
            events: List of Event entities (Pass 3)
            states: List of State entities (Pass 1)
            roles: List of Role entities (Pass 1)
            resources: List of Resource entities (Pass 1)
            capabilities: List of Capability entities (Pass 2)
            principles: List of Principle entities (Pass 2)
            obligations: List of Obligation entities (Pass 2)
            constraints: List of Constraint entities (Pass 2)
            case_context: Optional context (questions, conclusions, provisions)

        Returns:
            ActionRuleMapping with three-rule framework analysis
        """
        logger.info(f"[Action Rule Mapper] Analyzing case {case_id}")
        logger.info(f"  Actions: {len(actions)}, Events: {len(events)}, States: {len(states)}")
        logger.info(f"  Roles: {len(roles)}, Resources: {len(resources)}, Capabilities: {len(capabilities)}")
        logger.info(f"  Principles: {len(principles)}, Obligations: {len(obligations)}, Constraints: {len(constraints)}")

        # Build prompt for LLM analysis
        prompt = self._build_analysis_prompt(
            actions, events, states, roles, resources, capabilities,
            principles, obligations, constraints, case_context
        )

        try:
            # Call LLM with Claude Sonnet 4
            # Using Sonnet 4 - Sonnet 4.5 has consistent timeout issues with complex reasoning tasks
            # See: chapter3_notes.md for detailed analysis of this model selection
            logger.info("[Action Rule Mapper] Calling LLM for three-rule framework mapping...")
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"[Action Rule Mapper] Response length: {len(response_text)} chars")

            # Store prompt and response for SSE streaming display
            self.last_prompt = prompt
            self.last_response = response_text

            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_text = self._extract_json_from_response(response_text)

            # Parse JSON response
            mapping_data = json.loads(json_text)

            # Build ActionRuleMapping object
            mapping = self._parse_mapping_response(mapping_data)

            logger.info(f"[Action Rule Mapper] Mapping complete:")
            logger.info(f"  - {len(mapping.action_rule.actions_taken)} actions taken")
            logger.info(f"  - {len(mapping.action_rule.actions_not_taken)} actions not taken")
            logger.info(f"  - {len(mapping.institutional_rule.relevant_obligations)} obligations invoked")
            logger.info(f"  - {len(mapping.steering_rule.transformation_points)} transformation points")

            return mapping

        except json.JSONDecodeError as e:
            logger.error(f"[Action Rule Mapper] Failed to parse LLM JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"[Action Rule Mapper] Analysis error: {e}")
            raise

    def save_to_database(
        self,
        case_id: int,
        mapping: ActionRuleMapping,
        llm_model: str = "claude-sonnet-4-20250514"
    ) -> bool:
        """
        Save action-rule mapping to database.

        Args:
            case_id: Case ID
            mapping: ActionRuleMapping result
            llm_model: LLM model used

        Returns:
            True if successful
        """
        try:
            # Delete existing mapping
            delete_query = text("""
                DELETE FROM case_action_mapping WHERE case_id = :case_id
            """)
            db.session.execute(delete_query, {'case_id': case_id})

            # Insert new mapping (matching actual schema with individual columns)
            insert_query = text("""
                INSERT INTO case_action_mapping (
                    case_id,
                    actions_taken, actions_not_taken, alternatives_available,
                    capability_constraints, resource_constraints,
                    justifications, oppositions, relevant_obligations, relevant_principles,
                    situational_context, organizational_constraints,
                    resource_availability, key_events,
                    transformation_points, rule_shifts,
                    llm_model, llm_prompt, llm_response
                ) VALUES (
                    :case_id,
                    :actions_taken, :actions_not_taken, :alternatives_available,
                    :capability_constraints, :resource_constraints,
                    :justifications, :oppositions, :relevant_obligations, :relevant_principles,
                    :situational_context, :organizational_constraints,
                    :resource_availability, :key_events,
                    :transformation_points, :rule_shifts,
                    :llm_model, :llm_prompt, :llm_response
                )
            """)

            # Extract data from mapping
            db.session.execute(insert_query, {
                'case_id': case_id,
                # Action Rule
                'actions_taken': json.dumps(mapping.action_rule.actions_taken),
                'actions_not_taken': json.dumps(mapping.action_rule.actions_not_taken),
                'alternatives_available': json.dumps(mapping.action_rule.alternatives_available),
                'capability_constraints': json.dumps(mapping.action_rule.capability_constraints),
                'resource_constraints': json.dumps(mapping.action_rule.resource_constraints),
                # Institutional Rule
                'justifications': json.dumps(mapping.institutional_rule.justifications),
                'oppositions': json.dumps(mapping.institutional_rule.oppositions),
                'relevant_obligations': json.dumps(mapping.institutional_rule.relevant_obligations),
                'relevant_principles': json.dumps([]),  # Will extract from justifications/oppositions if needed
                # Operations Rule
                'situational_context': json.dumps(mapping.operations_rule.situational_context),
                'organizational_constraints': json.dumps(mapping.operations_rule.organizational_constraints),
                'resource_availability': json.dumps(mapping.operations_rule.resource_availability),
                'key_events': json.dumps(mapping.operations_rule.key_events),
                # Steering Rule
                'transformation_points': json.dumps(mapping.steering_rule.transformation_points),
                'rule_shifts': json.dumps(mapping.steering_rule.rule_shifts),
                # LLM metadata
                'llm_model': llm_model,
                'llm_prompt': getattr(self, 'last_prompt', ''),
                'llm_response': getattr(self, 'last_response', '')
            })

            db.session.commit()

            logger.info(f"[Action Rule Mapper] Saved mapping to database for case {case_id}")
            return True

        except Exception as e:
            logger.error(f"[Action Rule Mapper] Database save error: {e}")
            db.session.rollback()
            raise

    def _build_analysis_prompt(
        self,
        actions: List[Any],
        events: List[Any],
        states: List[Any],
        roles: List[Any],
        resources: List[Any],
        capabilities: List[Any],
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any],
        case_context: Optional[Dict]
    ) -> str:
        """Build LLM prompt for three-rule framework mapping."""

        prompt = f"""Analyze this professional engineering ethics case using the three-rule framework from action-based scenario analysis.

**Context**: NSPE Board of Ethical Review case - analyze what happened, why, and how.

**Available Entities from ProEthica 9-Concept Extraction**:

**Actions (A)** - {len(actions)} total:
{self._format_actions(actions)}

**Events (E)** - {len(events)} total:
{self._format_events(events)}

**States (S)** - {len(states)} total:
{self._format_states(states)}

**Roles (R)** - {len(roles)} total:
{self._format_roles(roles)}

**Resources (Rs)** - {len(resources)} total:
{self._format_resources(resources)}

**Capabilities (Ca)** - {len(capabilities)} total:
{self._format_capabilities(capabilities)}

**Principles (P)** - {len(principles)} total:
{self._format_principles(principles)}

**Obligations (O)** - {len(obligations)} total:
{self._format_obligations(obligations)}

**Constraints (Cs)** - {len(constraints)} total:
{self._format_constraints(constraints)}

**Task**: Map these entities to the three-rule framework:

**1. ACTION RULE (What was done?)**
- Map A, Ca, Rs to answer:
  - What did stakeholders DO?
  - What did they NOT do?
  - What alternatives were available?
  - What capabilities enabled/prevented actions?
  - What resources constrained choices?

**2. INSTITUTIONAL RULE (Why was it done/not done?)**
- Map P, O, Cs to answer:
  - What principles justified the action?
  - What principles/obligations opposed it?
  - What professional duties (NSPE Code) were invoked?
  - What constraints shaped the ethical decision space?

**3. OPERATIONS RULE (How did context shape actions?)**
- Map S, R, Rs, E to answer:
  - What situational context (States) framed the problem?
  - What organizational structures (Roles) constrained choices?
  - What resource availability shaped options?
  - What external events triggered or reshaped the situation?

**4. STEERING RULE (How did the case transform?)**
- Map E, A, cross-concept interactions to answer:
  - What were the transformation points? (e.g., "Routine practice → Board review")
  - How did ethical framing shift during the case?
  - Did rules transform over time?

**Output Format** (JSON only, no markdown):
{{
  "action_rule": {{
    "actions_taken": ["Action 1", "Action 2"],
    "actions_not_taken": ["Alternative 1", "Alternative 2"],
    "alternatives_available": ["Could have done X", "Could have done Y"],
    "capability_constraints": ["Cannot verify AI internals", "Lacks expertise in X"],
    "resource_constraints": ["No validation infrastructure", "Limited budget"],
    "action_rule_narrative": "Clear narrative explaining what was done and why these specific actions"
  }},
  "institutional_rule": {{
    "justifications": ["Efficiency", "Modern practice", "Client expectations"],
    "oppositions": ["Unknown reliability", "Verification duty", "Public safety"],
    "relevant_obligations": ["III.2.a - Practice competently", "III.9 - Disclose conflicts"],
    "constraint_factors": ["Legal restrictions", "Organizational policy", "Professional standards"],
    "institutional_rule_narrative": "Clear narrative of why actions were justified or opposed"
  }},
  "operations_rule": {{
    "situational_context": ["Industry AI adoption", "Rapid technological change"],
    "organizational_constraints": ["Solo practitioner", "No oversight structure"],
    "resource_availability": ["AI software available", "No review team", "Limited validation tools"],
    "key_events": ["AI tool release", "Client deadline", "Industry standard shift"],
    "operations_rule_narrative": "Clear narrative of how context shaped the ethical problem"
  }},
  "steering_rule": {{
    "transformation_points": ["Routine engineering → Ethical dilemma", "Acceptable practice → Questionable ethics"],
    "rule_shifts": ["Efficiency frame → Competence frame", "Individual decision → Professional standards"],
    "steering_rule_narrative": "Clear narrative of how the case transformed and why"
  }},
  "overall_analysis": "2-3 sentence synthesis of how the three rules interact to explain this case"
}}

Focus on ACTUAL patterns from the extracted entities. The three rules should explain:
- WHAT happened (action rule)
- WHY it happened (institutional rule)
- HOW context shaped it (operations rule)
- HOW the case transformed (steering rule)

Respond with valid JSON only."""

        return prompt

    def _get_entity_attr(self, entity: Any, attr_name: str, default: Any = None) -> Any:
        """
        Get entity attribute, checking both TemporaryRDFStorage and OntServe naming conventions.

        Args:
            entity: Entity object
            attr_name: Base attribute name (e.g., 'label', 'definition', 'uri')
            default: Default value if attribute not found

        Returns:
            Attribute value or default
        """
        # Check TemporaryRDFStorage naming (entity_*)
        temp_name = f'entity_{attr_name}'
        temp_val = getattr(entity, temp_name, None)
        if temp_val is not None:
            return temp_val

        # Check standard/OntServe naming
        std_val = getattr(entity, attr_name, None)
        if std_val is not None:
            return std_val

        return default

    def _format_actions(self, actions: List[Any]) -> str:
        """Format actions for LLM."""
        if not actions:
            return "None available"

        lines = []
        for i, a in enumerate(actions[:30], 1):
            label = self._get_entity_attr(a, 'label', 'Unknown')
            definition = self._get_entity_attr(a, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(actions) > 30:
            lines.append(f"... and {len(actions) - 30} more")

        return "\n".join(lines)

    def _format_events(self, events: List[Any]) -> str:
        """Format events for LLM."""
        if not events:
            return "None available"

        lines = []
        for i, e in enumerate(events[:30], 1):
            label = self._get_entity_attr(e, 'label', 'Unknown')
            definition = self._get_entity_attr(e, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(events) > 30:
            lines.append(f"... and {len(events) - 30} more")

        return "\n".join(lines)

    def _format_states(self, states: List[Any]) -> str:
        """Format states for LLM."""
        if not states:
            return "None available"

        lines = []
        for i, s in enumerate(states[:20], 1):
            label = self._get_entity_attr(s, 'label', 'Unknown')
            definition = self._get_entity_attr(s, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(states) > 20:
            lines.append(f"... and {len(states) - 20} more")

        return "\n".join(lines)

    def _format_roles(self, roles: List[Any]) -> str:
        """Format roles for LLM."""
        if not roles:
            return "None available"

        lines = []
        for i, r in enumerate(roles[:20], 1):
            label = self._get_entity_attr(r, 'label', 'Unknown')
            definition = self._get_entity_attr(r, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(roles) > 20:
            lines.append(f"... and {len(roles) - 20} more")

        return "\n".join(lines)

    def _format_resources(self, resources: List[Any]) -> str:
        """Format resources for LLM."""
        if not resources:
            return "None available"

        lines = []
        for i, rs in enumerate(resources[:20], 1):
            label = self._get_entity_attr(rs, 'label', 'Unknown')
            definition = self._get_entity_attr(rs, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(resources) > 20:
            lines.append(f"... and {len(resources) - 20} more")

        return "\n".join(lines)

    def _format_capabilities(self, capabilities: List[Any]) -> str:
        """Format capabilities for LLM."""
        if not capabilities:
            return "None available"

        lines = []
        for i, ca in enumerate(capabilities[:20], 1):
            label = self._get_entity_attr(ca, 'label', 'Unknown')
            definition = self._get_entity_attr(ca, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(capabilities) > 20:
            lines.append(f"... and {len(capabilities) - 20} more")

        return "\n".join(lines)

    def _format_principles(self, principles: List[Any]) -> str:
        """Format principles for LLM."""
        if not principles:
            return "None available"

        lines = []
        for i, p in enumerate(principles[:20], 1):
            label = self._get_entity_attr(p, 'label', 'Unknown')
            definition = self._get_entity_attr(p, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(principles) > 20:
            lines.append(f"... and {len(principles) - 20} more")

        return "\n".join(lines)

    def _format_obligations(self, obligations: List[Any]) -> str:
        """Format obligations for LLM."""
        if not obligations:
            return "None available"

        lines = []
        for i, o in enumerate(obligations[:20], 1):
            label = self._get_entity_attr(o, 'label', 'Unknown')

            # Get obligation statement from RDF
            rdf_data = getattr(o, 'rdf_json_ld', {}) or {}
            props = rdf_data.get('properties', {})
            statement = props.get('obligationStatement', [''])[0] if 'obligationStatement' in props else ''
            code_section = props.get('derivedFrom', [''])[0] if 'derivedFrom' in props else ''

            lines.append(f"{i}. **{label}**: {statement}\n   Code: {code_section}")

        if len(obligations) > 20:
            lines.append(f"... and {len(obligations) - 20} more")

        return "\n".join(lines)

    def _format_constraints(self, constraints: List[Any]) -> str:
        """Format constraints for LLM."""
        if not constraints:
            return "None available"

        lines = []
        for i, c in enumerate(constraints[:20], 1):
            label = self._get_entity_attr(c, 'label', 'Unknown')
            definition = self._get_entity_attr(c, 'definition', '')
            lines.append(f"{i}. **{label}**: {definition}")

        if len(constraints) > 20:
            lines.append(f"... and {len(constraints) - 20} more")

        return "\n".join(lines)

    def _parse_mapping_response(self, data: Dict) -> ActionRuleMapping:
        """Parse LLM JSON response into ActionRuleMapping object."""

        # Parse action rule
        action_rule_data = data.get('action_rule', {})
        action_rule = ActionRule(
            actions_taken=action_rule_data.get('actions_taken', []),
            actions_not_taken=action_rule_data.get('actions_not_taken', []),
            alternatives_available=action_rule_data.get('alternatives_available', []),
            capability_constraints=action_rule_data.get('capability_constraints', []),
            resource_constraints=action_rule_data.get('resource_constraints', []),
            action_rule_narrative=action_rule_data.get('action_rule_narrative', '')
        )

        # Parse institutional rule
        institutional_rule_data = data.get('institutional_rule', {})
        institutional_rule = InstitutionalRule(
            justifications=institutional_rule_data.get('justifications', []),
            oppositions=institutional_rule_data.get('oppositions', []),
            relevant_obligations=institutional_rule_data.get('relevant_obligations', []),
            constraint_factors=institutional_rule_data.get('constraint_factors', []),
            institutional_rule_narrative=institutional_rule_data.get('institutional_rule_narrative', '')
        )

        # Parse operations rule
        operations_rule_data = data.get('operations_rule', {})
        operations_rule = OperationsRule(
            situational_context=operations_rule_data.get('situational_context', []),
            organizational_constraints=operations_rule_data.get('organizational_constraints', []),
            resource_availability=operations_rule_data.get('resource_availability', []),
            key_events=operations_rule_data.get('key_events', []),
            operations_rule_narrative=operations_rule_data.get('operations_rule_narrative', '')
        )

        # Parse steering rule
        steering_rule_data = data.get('steering_rule', {})
        steering_rule = SteeringRule(
            transformation_points=steering_rule_data.get('transformation_points', []),
            rule_shifts=steering_rule_data.get('rule_shifts', []),
            steering_rule_narrative=steering_rule_data.get('steering_rule_narrative', '')
        )

        return ActionRuleMapping(
            action_rule=action_rule,
            institutional_rule=institutional_rule,
            operations_rule=operations_rule,
            steering_rule=steering_rule,
            overall_analysis=data.get('overall_analysis', '')
        )

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.

        Args:
            response_text: Raw LLM response text

        Returns:
            Extracted JSON string
        """
        import re

        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r'```\s*\n(.*?)\n```', response_text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try to find JSON object directly (starts with { and ends with })
        json_obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(0).strip()

        # If all else fails, return the original text and let json.loads fail with a better error
        logger.warning("[Action Rule Mapper] Could not extract JSON from response, trying raw text")
        return response_text.strip()
