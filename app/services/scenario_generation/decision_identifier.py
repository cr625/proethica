"""
Stage 4: Decision Point Identification

Identifies critical decision moments in the scenario from:
1. Actions with isDecisionPoint=true (from Step 3 enhanced temporal extraction)
2. Ethical questions from Step 4 synthesis

For each decision point, generates:
- Decision question
- Context and stakes
- Decision options (actual choice + alternatives from action metadata)
- Arguments for/against each option
- Links to code provisions and principles
- Ethical tensions and competing values

Documentation: docs/SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md (Stage 4)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class DecisionOption:
    """A single decision option (choice the agent could make)."""
    id: str
    label: str  # Short description
    description: str  # Full description of this option
    is_actual_choice: bool  # Whether this was the actual choice made

    # Arguments
    arguments_for: List[str]  # Reasons to choose this option
    arguments_against: List[str]  # Reasons to reject this option

    # Ethical analysis
    principles_supported: List[str]  # Principles this option upholds
    principles_violated: List[str]  # Principles this option violates
    obligations_fulfilled: List[str]  # Obligations this satisfies
    obligations_neglected: List[str]  # Obligations this ignores

    # Consequences
    likely_consequences: List[str]  # What would happen if chosen

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'label': self.label,
            'description': self.description,
            'is_actual_choice': self.is_actual_choice,
            'arguments_for': self.arguments_for,
            'arguments_against': self.arguments_against,
            'principles_supported': self.principles_supported,
            'principles_violated': self.principles_violated,
            'obligations_fulfilled': self.obligations_fulfilled,
            'obligations_neglected': self.obligations_neglected,
            'likely_consequences': self.likely_consequences
        }


@dataclass
class InstitutionalRuleAnalysis:
    """
    Institutional Rule Analysis: What triggers/opposes the action?

    Maps decisions to ProEthica's normative concepts (P, O, Cs) to understand
    why this decision matters ethically.
    """
    # Principle conflicts (P1 vs P2)
    principles_in_tension: List[Dict[str, str]]  # [{'principle': label, 'uri': uri, 'supports': option_id}]
    principle_conflict_description: str  # LLM-generated description of tension

    # Obligation tensions (O1 vs O3)
    obligations_in_tension: List[Dict[str, str]]  # [{'obligation': label, 'uri': uri, 'supports': option_id}]
    obligation_conflict_description: str  # LLM-generated description of tension

    # Constraint influences (Cs)
    constraining_factors: List[Dict[str, str]]  # [{'constraint': label, 'uri': uri, 'impact': description}]
    constraint_influence_description: str  # How constraints shaped options

    # Symbolic significance
    why_this_matters: str  # What strategic ethical issue does this represent?

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'principles_in_tension': self.principles_in_tension,
            'principle_conflict_description': self.principle_conflict_description,
            'obligations_in_tension': self.obligations_in_tension,
            'obligation_conflict_description': self.obligation_conflict_description,
            'constraining_factors': self.constraining_factors,
            'constraint_influence_description': self.constraint_influence_description,
            'why_this_matters': self.why_this_matters
        }


@dataclass
class TransformationAnalysis:
    """
    Transformation Detection: What type of ethical challenge is this?

    Classifies the decision according to action-based scenario framework
    (Marchais-Roubelat & Roubelat, 2015) mapped to ProEthica formalism.
    """
    # Transformation type
    transformation_type: str  # 'transfer', 'stalemate', 'oscillation', 'phase_lag'
    confidence: float  # 0.0-1.0

    # Rationale
    type_rationale: str  # Why this classification?

    # Indicators
    indicators: List[str]  # Evidence for this classification

    # Comparison to other cases
    similar_transformation_cases: List[str]  # Case IDs with same pattern

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'transformation_type': self.transformation_type,
            'confidence': self.confidence,
            'type_rationale': self.type_rationale,
            'indicators': self.indicators,
            'similar_transformation_cases': self.similar_transformation_cases
        }


@dataclass
class DecisionPoint:
    """
    A critical decision moment in the scenario.

    Built from actions with isDecisionPoint=true and ethical questions.
    Enhanced with institutional rule analysis and transformation detection.
    """
    # Identity
    id: str  # Unique identifier
    decision_question: str  # The central ethical question

    # Context
    timepoint: str  # When this decision occurs (from timeline)
    decision_maker: str  # Who must decide (participant)
    situation_context: str  # What's happening

    # Stakes and tensions
    ethical_tension: str  # Core ethical conflict
    stakes: str  # What's at risk
    competing_values: List[str]  # Which values/duties conflict

    # Options
    options: List[DecisionOption]  # Available choices
    actual_choice_id: str  # Which option was actually chosen

    # Links
    related_action_uri: Optional[str]  # Source action entity
    related_question_uris: List[str]  # Related ethical questions from Step 4
    code_provisions: List[str]  # Relevant NSPE code sections

    # Metadata
    source_type: str  # 'action' or 'question'
    narrative_significance: str  # Why this matters for learning

    # NEW - Institutional Rule Analysis (Stage 4 enhancement)
    institutional_rule_analysis: Optional[InstitutionalRuleAnalysis] = None

    # NEW - Transformation Analysis (Stage 4 enhancement)
    transformation_analysis: Optional[TransformationAnalysis] = None

    # Source data
    extracted_data: Dict[str, Any] = field(default_factory=dict)  # Original RDF data

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        result = {
            'id': self.id,
            'decision_question': self.decision_question,
            'timepoint': self.timepoint,
            'decision_maker': self.decision_maker,
            'situation_context': self.situation_context,
            'ethical_tension': self.ethical_tension,
            'stakes': self.stakes,
            'competing_values': self.competing_values,
            'options': [opt.to_dict() for opt in self.options],
            'actual_choice_id': self.actual_choice_id,
            'related_action_uri': self.related_action_uri,
            'related_question_uris': self.related_question_uris,
            'code_provisions': self.code_provisions,
            'source_type': self.source_type,
            'narrative_significance': self.narrative_significance
        }

        # Add institutional rule analysis if available
        if self.institutional_rule_analysis:
            result['institutional_rule_analysis'] = self.institutional_rule_analysis.to_dict()

        # Add transformation analysis if available
        if self.transformation_analysis:
            result['transformation_analysis'] = self.transformation_analysis.to_dict()

        return result


@dataclass
class DecisionIdentificationResult:
    """Result of Stage 4 decision identification."""
    decision_points: List[DecisionPoint]
    total_decisions: int
    decisions_from_actions: int
    decisions_from_questions: int
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'total_decisions': self.total_decisions,
            'decisions_from_actions': self.decisions_from_actions,
            'decisions_from_questions': self.decisions_from_questions,
            'decision_points': [dp.to_dict() for dp in self.decision_points]
        }


class DecisionIdentifier:
    """
    Stage 4: Identify decision points from actions and questions.

    Extracts critical decision moments and enriches them with:
    - Decision options
    - Arguments for/against
    - Ethical analysis
    - Code provision links
    """

    def __init__(self):
        """Initialize decision identifier with LLM client."""
        self.llm_client = get_llm_client()
        logger.info("[Decision Identifier] Initialized")

    def identify_decisions(
        self,
        actions: List[Any],  # RDFEntity objects
        questions: List[Any],  # RDFEntity objects
        timeline_data: Optional[Dict] = None,
        participants: Optional[List] = None,
        synthesis_data: Optional[Any] = None
    ) -> DecisionIdentificationResult:
        """
        Identify decision points from actions and ethical questions.

        Args:
            actions: List of action entities from temporal extraction
            questions: List of ethical question entities from Step 4
            timeline_data: Optional timeline for temporal context
            participants: Optional participant profiles for decision makers
            synthesis_data: Optional synthesis data for code provisions

        Returns:
            DecisionIdentificationResult with decision points
        """
        logger.info(f"[Decision Identifier] Processing {len(actions)} actions, {len(questions)} questions")

        decision_points = []

        # Extract decisions from actions with isDecisionPoint=true
        action_decisions = self._identify_from_actions(
            actions,
            timeline_data,
            participants,
            synthesis_data
        )
        decision_points.extend(action_decisions)

        # Extract decisions from ethical questions
        question_decisions = self._identify_from_questions(
            questions,
            actions,
            participants,
            synthesis_data
        )
        decision_points.extend(question_decisions)

        result = DecisionIdentificationResult(
            decision_points=decision_points,
            total_decisions=len(decision_points),
            decisions_from_actions=len(action_decisions),
            decisions_from_questions=len(question_decisions)
        )

        logger.info(
            f"[Decision Identifier] Identified {len(decision_points)} decision points "
            f"({len(action_decisions)} from actions, {len(question_decisions)} from questions)"
        )

        return result

    def _identify_from_actions(
        self,
        actions: List[Any],
        timeline_data: Optional[Dict],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> List[DecisionPoint]:
        """Identify decision points from actions with isDecisionPoint=true."""
        decision_points = []

        for action in actions:
            try:
                rdf_data = action.rdf_json_ld if hasattr(action, 'rdf_json_ld') else {}

                # Debug: Log what we're seeing
                logger.debug(f"[Decision Identifier] Checking action: {action.label}")
                logger.debug(f"[Decision Identifier] RDF data keys: {list(rdf_data.keys()) if rdf_data else 'None'}")
                if rdf_data and 'proeth-scenario:isDecisionPoint' in rdf_data:
                    logger.debug(f"[Decision Identifier] isDecisionPoint value: {rdf_data['proeth-scenario:isDecisionPoint']}")

                # Check if this is a decision point
                is_decision = rdf_data.get('proeth-scenario:isDecisionPoint', False)
                if not is_decision:
                    logger.debug(f"[Decision Identifier] Action {action.label} is not a decision point (value: {is_decision})")
                    continue

                logger.info(f"[Decision Identifier] Found decision point: {action.label}")

                # Extract decision point data
                decision = self._create_decision_from_action(
                    action,
                    rdf_data,
                    timeline_data,
                    participants,
                    synthesis_data
                )

                if decision:
                    decision_points.append(decision)
                    logger.debug(f"[Decision Identifier] Created decision from action: {action.label}")

            except Exception as e:
                logger.error(f"[Decision Identifier] Error processing action {action.label}: {e}", exc_info=True)
                continue

        return decision_points

    def _create_decision_from_action(
        self,
        action: Any,
        rdf_data: Dict,
        timeline_data: Optional[Dict],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> Optional[DecisionPoint]:
        """Create a DecisionPoint from an action entity."""

        # Extract scenario metadata
        ethical_tension = rdf_data.get('proeth-scenario:ethicalTension', 'Ethical tension not specified')
        stakes = rdf_data.get('proeth-scenario:stakes', 'Stakes not specified')
        decision_significance = rdf_data.get('proeth-scenario:decisionSignificance', '')
        alternative_actions = rdf_data.get('proeth-scenario:alternativeActions', [])
        consequences_if_alternative = rdf_data.get('proeth-scenario:consequencesIfAlternative', [])
        character_motivation = rdf_data.get('proeth-scenario:characterMotivation', '')

        # Extract action data
        description = rdf_data.get('proeth:description', action.label)
        agent = rdf_data.get('proeth:hasAgent', 'Unknown')
        timepoint = rdf_data.get('proeth:temporalMarker', 'Time unknown')

        # Generate decision question
        decision_question = f"Should {agent} {action.label.lower()}?"

        # Create decision options
        options = []

        # Generate safe base ID for options
        if action.uri:
            base_id = action.uri
        else:
            base_id = action.label.replace(' ', '_')

        # Option 1: Actual choice made
        actual_option = DecisionOption(
            id=f"{base_id}_actual",
            label=action.label,
            description=description,
            is_actual_choice=True,
            arguments_for=[character_motivation] if character_motivation else [],
            arguments_against=[],  # Will be filled by LLM
            principles_supported=self._extract_principles(rdf_data, 'proeth:guidedByPrinciple'),
            principles_violated=[],
            obligations_fulfilled=self._extract_obligations(rdf_data, 'proeth:fulfillsObligation'),
            obligations_neglected=[],
            likely_consequences=self._extract_consequences(rdf_data)
        )
        options.append(actual_option)

        # Options 2+: Alternatives
        for i, alt_action in enumerate(alternative_actions):
            alt_consequences = consequences_if_alternative[i] if i < len(consequences_if_alternative) else ''

            alt_option = DecisionOption(
                id=f"{base_id}_alt_{i}",
                label=f"Alternative {i+1}",
                description=alt_action,
                is_actual_choice=False,
                arguments_for=[],  # Will be filled by LLM
                arguments_against=[],
                principles_supported=[],
                principles_violated=[],
                obligations_fulfilled=[],
                obligations_neglected=[],
                likely_consequences=[alt_consequences] if alt_consequences else []
            )
            options.append(alt_option)

        # Extract code provisions
        code_provisions = self._extract_code_provisions(rdf_data, synthesis_data)

        # Create decision point
        # Generate safe ID from URI or label
        if action.uri and '#' in action.uri:
            decision_id = f"decision_{action.uri.split('#')[-1]}"
        else:
            # Fallback: use label with underscores
            decision_id = f"decision_{action.label.replace(' ', '_')}"

        decision = DecisionPoint(
            id=decision_id,
            decision_question=decision_question,
            timepoint=timepoint,
            decision_maker=agent,
            situation_context=description,
            ethical_tension=ethical_tension,
            stakes=stakes,
            competing_values=self._extract_competing_values(ethical_tension),
            options=options,
            actual_choice_id=actual_option.id,
            related_action_uri=action.uri if action.uri else '',
            related_question_uris=[],
            code_provisions=code_provisions,
            source_type='action',
            narrative_significance=decision_significance,
            extracted_data=rdf_data
        )

        return decision

    def _identify_from_questions(
        self,
        questions: List[Any],
        actions: List[Any],
        participants: Optional[List],
        synthesis_data: Optional[Any]
    ) -> List[DecisionPoint]:
        """Identify decision points from ethical questions."""
        decision_points = []

        # For now, skip question-based decisions (focus on action-based)
        # Can enhance later to convert questions into decision points

        return decision_points

    def _extract_principles(self, rdf_data: Dict, key: str) -> List[str]:
        """Extract principle URIs and convert to labels."""
        principles = rdf_data.get(key, [])
        if not principles:
            return []
        if isinstance(principles, str):
            principles = [principles]

        # Extract labels from URIs (handle None values)
        result = []
        for p in principles:
            if p and isinstance(p, str):
                result.append(p.split('#')[-1].replace('_', ' '))
        return result

    def _extract_obligations(self, rdf_data: Dict, key: str) -> List[str]:
        """Extract obligation URIs and convert to labels."""
        obligations = rdf_data.get(key, [])
        if not obligations:
            return []
        if isinstance(obligations, str):
            obligations = [obligations]

        # Extract labels from URIs (handle None values)
        result = []
        for o in obligations:
            if o and isinstance(o, str):
                result.append(o.split('#')[-1].replace('_', ' '))
        return result

    def _extract_consequences(self, rdf_data: Dict) -> List[str]:
        """Extract consequence descriptions."""
        intended = rdf_data.get('proeth:intendedOutcome', '')
        foreseen = rdf_data.get('proeth:foreseenUnintendedEffects', [])

        consequences = []
        if intended:
            consequences.append(f"Intended: {intended}")
        if foreseen:
            if isinstance(foreseen, list):
                consequences.extend([f"Foreseen: {f}" for f in foreseen])
            else:
                consequences.append(f"Foreseen: {foreseen}")

        return consequences

    def _extract_competing_values(self, ethical_tension: str) -> List[str]:
        """Extract competing values from ethical tension description."""
        # Simple heuristic: split on "vs.", "versus", "vs", or "conflict between"
        tension_lower = ethical_tension.lower()

        if ' vs. ' in tension_lower:
            parts = ethical_tension.split(' vs. ')
            return [p.strip() for p in parts]
        elif ' vs ' in tension_lower:
            parts = ethical_tension.split(' vs ')
            return [p.strip() for p in parts]
        elif 'versus' in tension_lower:
            parts = ethical_tension.split('versus')
            return [p.strip() for p in parts]
        elif 'conflict between' in tension_lower:
            # Extract text after "conflict between"
            idx = tension_lower.index('conflict between')
            text = ethical_tension[idx + len('conflict between'):].strip()
            if ' and ' in text:
                parts = text.split(' and ')
                return [p.strip() for p in parts]

        # Fallback: return the whole tension as single value
        return [ethical_tension]

    def _extract_code_provisions(
        self,
        rdf_data: Dict,
        synthesis_data: Optional[Any]
    ) -> List[str]:
        """Extract relevant code provisions."""
        # TODO: Link to code provisions from Step 4 synthesis
        # For now, return empty list
        return []

    def analyze_institutional_rules(
        self,
        decision: DecisionPoint,
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any]
    ) -> InstitutionalRuleAnalysis:
        """
        Analyze institutional rules for a decision point.
        
        Maps the decision to Principles (P), Obligations (O), and Constraints (Cs)
        to understand what triggers/opposes the action.
        
        Args:
            decision: DecisionPoint to analyze
            principles: List of Principle entities from Pass 2
            obligations: List of Obligation entities from Pass 2
            constraints: List of Constraint entities from Pass 2
            
        Returns:
            InstitutionalRuleAnalysis with principle conflicts, obligation tensions, constraints
        """
        logger.info(f"[Decision Identifier] Analyzing institutional rules for decision: {decision.id}")
        
        # Build context for LLM
        context = self._build_institutional_context(decision, principles, obligations, constraints)
        
        # Create LLM prompt
        prompt = f"""Analyze this ethical decision through the lens of institutional rules (principles, obligations, constraints).

**Decision**: {decision.decision_question}
**Context**: {decision.situation_context}
**Ethical Tension**: {decision.ethical_tension}
**Stakes**: {decision.stakes}

**Available Principles**:
{self._format_principles(principles)}

**Available Obligations**:
{self._format_obligations(obligations)}

**Available Constraints**:
{self._format_constraints(constraints)}

**Decision Options**:
{self._format_options(decision.options)}

**Task**: Identify which principles, obligations, and constraints are in tension for this decision.

**Output Format** (JSON only):
{{
  "principles_in_tension": [
    {{"principle": "Principle Name", "uri": "http://...", "supports": "option_1", "rationale": "why"}},
    {{"principle": "Principle Name 2", "uri": "http://...", "supports": "option_2", "rationale": "why"}}
  ],
  "principle_conflict_description": "Clear description of how these principles create ethical tension",
  "obligations_in_tension": [
    {{"obligation": "Obligation Name", "uri": "http://...", "supports": "option_1", "rationale": "why"}},
    {{"obligation": "Obligation Name 2", "uri": "http://...", "supports": "option_2", "rationale": "why"}}
  ],
  "obligation_conflict_description": "Clear description of how these obligations conflict",
  "constraining_factors": [
    {{"constraint": "Constraint Name", "uri": "http://...", "impact": "how this limits options"}}
  ],
  "constraint_influence_description": "How constraints shaped the decision space",
  "why_this_matters": "What strategic ethical issue does this decision represent? Why would NSPE publish this case?"
}}

Respond with valid JSON only."""

        try:
            # Call LLM
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text
            
            # Parse JSON
            import json
            analysis_data = json.loads(response_text)
            
            # Create InstitutionalRuleAnalysis
            analysis = InstitutionalRuleAnalysis(
                principles_in_tension=analysis_data.get('principles_in_tension', []),
                principle_conflict_description=analysis_data.get('principle_conflict_description', ''),
                obligations_in_tension=analysis_data.get('obligations_in_tension', []),
                obligation_conflict_description=analysis_data.get('obligation_conflict_description', ''),
                constraining_factors=analysis_data.get('constraining_factors', []),
                constraint_influence_description=analysis_data.get('constraint_influence_description', ''),
                why_this_matters=analysis_data.get('why_this_matters', '')
            )
            
            logger.info(f"[Decision Identifier] Institutional rule analysis complete")
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"[Decision Identifier] Failed to parse LLM JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            # Return empty analysis
            return InstitutionalRuleAnalysis(
                principles_in_tension=[],
                principle_conflict_description="Analysis failed",
                obligations_in_tension=[],
                obligation_conflict_description="Analysis failed",
                constraining_factors=[],
                constraint_influence_description="Analysis failed",
                why_this_matters="Analysis failed"
            )
        except Exception as e:
            logger.error(f"[Decision Identifier] Institutional rule analysis error: {e}")
            return InstitutionalRuleAnalysis(
                principles_in_tension=[],
                principle_conflict_description="Analysis failed",
                obligations_in_tension=[],
                obligation_conflict_description="Analysis failed",
                constraining_factors=[],
                constraint_influence_description="Analysis failed",
                why_this_matters="Analysis failed"
            )
    
    def _build_institutional_context(self, decision, principles, obligations, constraints):
        """Build context dict for institutional analysis."""
        return {
            'decision': decision.to_dict(),
            'principles': [self._entity_to_dict(p) for p in principles[:20]],
            'obligations': [self._entity_to_dict(o) for o in obligations[:20]],
            'constraints': [self._entity_to_dict(c) for c in constraints[:20]]
        }
    
    def _entity_to_dict(self, entity):
        """Convert RDFEntity to dict."""
        return {
            'uri': entity.uri if hasattr(entity, 'uri') else '',
            'label': entity.label if hasattr(entity, 'label') else '',
            'definition': entity.definition if hasattr(entity, 'definition') else ''
        }
    
    def _format_principles(self, principles):
        """Format principles for LLM."""
        if not principles:
            return "None available"
        lines = []
        for i, p in enumerate(principles[:15], 1):
            label = p.label if hasattr(p, 'label') else 'Unknown'
            definition = p.definition if hasattr(p, 'definition') else ''
            uri = p.uri if hasattr(p, 'uri') else ''
            lines.append(f"{i}. **{label}**: {definition} [URI: {uri}]")
        return "\n".join(lines)
    
    def _format_obligations(self, obligations):
        """Format obligations for LLM."""
        if not obligations:
            return "None available"
        lines = []
        for i, o in enumerate(obligations[:15], 1):
            label = o.label if hasattr(o, 'label') else 'Unknown'
            # Get obligation statement from RDF
            rdf_data = o.rdf_json_ld if hasattr(o, 'rdf_json_ld') else {}
            props = rdf_data.get('properties', {})
            statement = props.get('obligationStatement', [''])[0] if 'obligationStatement' in props else ''
            uri = o.uri if hasattr(o, 'uri') else ''
            lines.append(f"{i}. **{label}**: {statement} [URI: {uri}]")
        return "\n".join(lines)
    
    def _format_constraints(self, constraints):
        """Format constraints for LLM."""
        if not constraints:
            return "None available"
        lines = []
        for i, c in enumerate(constraints[:15], 1):
            label = c.label if hasattr(c, 'label') else 'Unknown'
            definition = c.definition if hasattr(c, 'definition') else ''
            uri = c.uri if hasattr(c, 'uri') else ''
            lines.append(f"{i}. **{label}**: {definition} [URI: {uri}]")
        return "\n".join(lines)
    
    def _format_options(self, options):
        """Format decision options for LLM."""
        lines = []
        for opt in options:
            lines.append(f"**{opt.id}**: {opt.label} - {opt.description}")
        return "\n".join(lines)


    def detect_transformation_type(
        self,
        decision: DecisionPoint,
        institutional_analysis: InstitutionalRuleAnalysis,
        all_decisions: List[DecisionPoint]
    ) -> TransformationAnalysis:
        """
        Detect transformation type for this decision.
        
        Classifies according to action-based scenario framework:
        - Transfer: Clear shift from one rule set to another
        - Stalemate: Trapped, no clear ethical path
        - Oscillation: Cycling between competing obligations
        - Phase Lag: Different stakeholders operating under different frames
        
        Args:
            decision: DecisionPoint to classify
            institutional_analysis: Institutional rule analysis for context
            all_decisions: All decisions in case (for oscillation detection)
            
        Returns:
            TransformationAnalysis with classification and rationale
        """
        logger.info(f"[Decision Identifier] Detecting transformation type for decision: {decision.id}")
        
        # Create LLM prompt
        prompt = f"""Classify this ethical decision according to transformation type.

**Decision**: {decision.decision_question}
**Context**: {decision.situation_context}
**Institutional Analysis**: {institutional_analysis.why_this_matters}

**Principle Conflicts**: {institutional_analysis.principle_conflict_description}
**Obligation Conflicts**: {institutional_analysis.obligation_conflict_description}
**Constraints**: {institutional_analysis.constraint_influence_description}

**Transformation Types**:

1. **Transfer**: Case escalates from routine to board review, new rules apply
   - Indicators: External event triggers rule change, new authorities involved, scope expands
   
2. **Stalemate**: Engineer trapped with no clear ethical path forward
   - Indicators: All options violate something, competing obligations unresolvable, paralysis
   
3. **Oscillation**: Cycling between competing obligations repeatedly
   - Indicators: Multiple decisions with same tension, back-and-forth pattern, no resolution
   
4. **Phase Lag**: Different stakeholders operating under different ethical frames
   - Indicators: Client values efficiency, engineer values competence; misaligned priorities

**Task**: Classify this decision's transformation type.

**Output Format** (JSON only):
{{
  "transformation_type": "transfer|stalemate|oscillation|phase_lag",
  "confidence": 0.85,
  "type_rationale": "Clear explanation of why this classification fits",
  "indicators": [
    "Specific evidence from the decision",
    "Another indicator",
    "Another indicator"
  ],
  "similar_transformation_cases": []
}}

Respond with valid JSON only."""

        try:
            # Call LLM
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text
            
            # Parse JSON
            import json
            analysis_data = json.loads(response_text)
            
            # Create TransformationAnalysis
            analysis = TransformationAnalysis(
                transformation_type=analysis_data.get('transformation_type', 'unknown'),
                confidence=float(analysis_data.get('confidence', 0.0)),
                type_rationale=analysis_data.get('type_rationale', ''),
                indicators=analysis_data.get('indicators', []),
                similar_transformation_cases=analysis_data.get('similar_transformation_cases', [])
            )
            
            logger.info(f"[Decision Identifier] Transformation type: {analysis.transformation_type} (confidence: {analysis.confidence})")
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"[Decision Identifier] Failed to parse transformation JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            return TransformationAnalysis(
                transformation_type="unknown",
                confidence=0.0,
                type_rationale="Analysis failed",
                indicators=[],
                similar_transformation_cases=[]
            )
        except Exception as e:
            logger.error(f"[Decision Identifier] Transformation detection error: {e}")
            return TransformationAnalysis(
                transformation_type="unknown",
                confidence=0.0,
                type_rationale="Analysis failed",
                indicators=[],
                similar_transformation_cases=[]
            )

    def identify_decisions_with_institutional_analysis(
        self,
        actions: List[Any],
        questions: List[Any],
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any],
        timeline_data: Optional[Dict] = None,
        participants: Optional[List] = None,
        synthesis_data: Optional[Any] = None
    ) -> DecisionIdentificationResult:
        """
        Identify decision points AND perform institutional rule + transformation analysis.
        
        This is the enhanced Stage 4 method that adds analytical capabilities.
        
        Args:
            actions: List of action entities
            questions: List of ethical question entities
            principles: List of Principle entities (Pass 2)
            obligations: List of Obligation entities (Pass 2)
            constraints: List of Constraint entities (Pass 2)
            timeline_data: Optional timeline context
            participants: Optional participant profiles
            synthesis_data: Optional synthesis data
            
        Returns:
            DecisionIdentificationResult with institutional + transformation analysis
        """
        logger.info("[Decision Identifier] Enhanced Stage 4: Identifying decisions with institutional analysis")
        
        # Step 1: Identify base decisions (existing logic)
        result = self.identify_decisions(
            actions=actions,
            questions=questions,
            timeline_data=timeline_data,
            participants=participants,
            synthesis_data=synthesis_data
        )
        
        # Step 2: Enhance each decision with institutional rule analysis
        for decision in result.decision_points:
            logger.info(f"[Decision Identifier] Analyzing decision: {decision.id}")
            
            # Institutional rule analysis
            institutional_analysis = self.analyze_institutional_rules(
                decision=decision,
                principles=principles,
                obligations=obligations,
                constraints=constraints
            )
            decision.institutional_rule_analysis = institutional_analysis
            
            # Transformation detection
            transformation_analysis = self.detect_transformation_type(
                decision=decision,
                institutional_analysis=institutional_analysis,
                all_decisions=result.decision_points
            )
            decision.transformation_analysis = transformation_analysis
            
            logger.info(f"[Decision Identifier] Decision {decision.id} analysis complete: {transformation_analysis.transformation_type}")
        
        logger.info(f"[Decision Identifier] Enhanced Stage 4 complete: {result.total_decisions} decisions analyzed")
        return result

    def identify_decisions_from_step4_analysis(
        self,
        case_id: int,
        actions: List[Any],
        questions: List[Any],
        timeline_data: Optional[Dict] = None,
        participants: Optional[List] = None,
        synthesis_data: Optional[Any] = None
    ) -> DecisionIdentificationResult:
        """
        Identify decision points and enrich with Step 4 analysis FROM DATABASE.
        
        This is the refactored Stage 4 method that REFERENCES pre-computed analysis
        from Step 4 Parts D, E, F instead of re-analyzing.
        
        Architectural principle: Step 4 = Analysis Engine, Step 5 = Presentation Layer
        
        Args:
            case_id: Case ID to load analysis for
            actions: List of action entities
            questions: List of ethical question entities
            timeline_data: Optional timeline context
            participants: Optional participant profiles
            synthesis_data: Optional synthesis data
            
        Returns:
            DecisionIdentificationResult with referenced Step 4 analysis
        """
        from app.models import db
        from sqlalchemy import text
        import json
        
        logger.info(f"[Decision Identifier] Stage 4 Refactored: Referencing Step 4 analysis from database for case {case_id}")
        
        # Step 1: Identify base decision points (no analysis yet)
        base_result = self.identify_decisions(
            actions=actions,
            questions=questions,
            timeline_data=timeline_data,
            participants=participants,
            synthesis_data=synthesis_data
        )
        
        logger.info(f"[Decision Identifier] Identified {base_result.total_decisions} decision points")
        
        # Step 2: Load Part D (Institutional Analysis) from database
        institutional_query = text("""
            SELECT 
                principle_tensions,
                principle_conflict_description,
                obligation_conflicts,
                obligation_conflict_description,
                constraining_factors,
                constraint_influence_description,
                case_significance
            FROM case_institutional_analysis 
            WHERE case_id = :case_id
        """)
        
        inst_result = db.session.execute(institutional_query, {'case_id': case_id}).fetchone()
        
        if inst_result:
            logger.info(f"[Decision Identifier] Loaded Part D analysis from database")
            
            # Enrich each decision point with institutional analysis
            for decision in base_result.decision_points:
                # Create InstitutionalRuleAnalysis from Part D data
                institutional_analysis = InstitutionalRuleAnalysis(
                    principles_in_tension=inst_result.principle_tensions or [],
                    principle_conflict_description=inst_result.principle_conflict_description or '',
                    obligations_in_tension=inst_result.obligation_conflicts or [],
                    obligation_conflict_description=inst_result.obligation_conflict_description or '',
                    constraining_factors=inst_result.constraining_factors or [],
                    constraint_influence_description=inst_result.constraint_influence_description or '',
                    why_this_matters=inst_result.case_significance or ''
                )
                decision.institutional_rule_analysis = institutional_analysis
                
            logger.info(f"[Decision Identifier] Enriched {base_result.total_decisions} decisions with Part D analysis")
        else:
            logger.warning(f"[Decision Identifier] No Part D analysis found for case {case_id}")
        
        # Step 3: Load Part F (Transformation Classification) from database
        transformation_query = text("""
            SELECT 
                transformation_type,
                confidence,
                type_rationale,
                indicators
            FROM case_transformation 
            WHERE case_id = :case_id
        """)
        
        trans_result = db.session.execute(transformation_query, {'case_id': case_id}).fetchone()
        
        if trans_result:
            logger.info(f"[Decision Identifier] Loaded Part F analysis from database")
            
            # Enrich each decision point with transformation analysis
            for decision in base_result.decision_points:
                # Create TransformationAnalysis from Part F data
                transformation_analysis = TransformationAnalysis(
                    transformation_type=trans_result.transformation_type or 'transfer',
                    confidence=trans_result.confidence or 0.0,
                    type_rationale=trans_result.type_rationale or '',
                    indicators=trans_result.indicators or [],
                    similar_transformation_cases=[]  # TODO: Could query database for similar patterns
                )
                decision.transformation_analysis = transformation_analysis
                
            logger.info(f"[Decision Identifier] Enriched {base_result.total_decisions} decisions with Part F analysis")
        else:
            logger.warning(f"[Decision Identifier] No Part F analysis found for case {case_id}")
        
        logger.info(f"[Decision Identifier] Stage 4 Refactored complete: {base_result.total_decisions} decisions with referenced analysis")
        return base_result
