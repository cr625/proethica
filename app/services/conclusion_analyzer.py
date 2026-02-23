"""
Conclusion Analyzer - Flexible Two-Stage Design with Entity URIs

Stage 1: Board Conclusions (Ground Truth)
- First attempts to parse from imported text (no LLM needed)
- Falls back to LLM extraction if parsing fails
- Marks source as 'imported' vs 'llm_extracted'

Stage 2: Analytical Conclusions (LLM-Generated)
- Generates conclusions that add scholarly/pedagogical value
- Based on ALL questions (Board + analytical)
- Uses entity URIs for grounding

Conclusion Types:
- board_explicit: The Board's actual conclusions (ground truth)
- analytical_extension: Extends Board's reasoning with additional analysis
- question_response: Responds to analytical questions not addressed by Board
- principle_synthesis: Synthesizes principle tensions into conclusions
"""

import json
import re
import time
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from models import ModelConfig
from app.utils.entity_prompt_utils import format_entities_compact, resolve_entity_labels_to_uris
from app.utils.llm_json_utils import parse_json_response, parse_json_object
import anthropic

logger = logging.getLogger(__name__)


class ConclusionType(Enum):
    """Types of ethical conclusions."""
    BOARD_EXPLICIT = "board_explicit"           # Board's actual conclusions
    ANALYTICAL_EXTENSION = "analytical_extension"  # Extends Board's reasoning
    QUESTION_RESPONSE = "question_response"     # Responds to analytical questions
    PRINCIPLE_SYNTHESIS = "principle_synthesis" # Synthesizes principle tensions


class ConclusionSource(Enum):
    """Source of conclusion extraction."""
    IMPORTED = "imported"           # Parsed from case text without LLM
    LLM_EXTRACTED = "llm_extracted" # Extracted via LLM
    LLM_GENERATED = "llm_generated" # Generated via LLM (analytical)


class BoardConclusionType(Enum):
    """Sub-types for Board's conclusions."""
    VIOLATION = "violation"         # Found a violation
    COMPLIANCE = "compliance"       # Found compliance
    NO_VIOLATION = "no_violation"   # Found no violation
    INTERPRETATION = "interpretation"  # Clarifies interpretation
    RECOMMENDATION = "recommendation"  # Recommends action


@dataclass
class EthicalConclusion:
    """Represents an extracted or generated ethical conclusion."""
    conclusion_number: int
    conclusion_text: str
    conclusion_type: str  # ConclusionType value
    board_conclusion_type: str = ""  # BoardConclusionType value (for board_explicit)
    mentioned_entities: Dict[str, List[str]] = field(default_factory=dict)
    mentioned_entity_uris: Dict[str, List[str]] = field(default_factory=dict)  # URIs for grounding
    cited_provisions: List[str] = field(default_factory=list)
    extraction_reasoning: str = ""
    source: str = "llm_extracted"  # ConclusionSource value
    # For linking
    answers_questions: List[int] = field(default_factory=list)  # Question numbers this conclusion addresses
    # For analytical conclusions
    source_conclusion: Optional[int] = None  # Links to board_explicit conclusion number
    related_analytical_questions: List[int] = field(default_factory=list)  # Analytical questions addressed


class ConclusionAnalyzer:
    """
    Analyzes Conclusions section with complete entity context.

    Flexible two-stage analysis:
    1. Load/Parse Board's explicit conclusions (try import first, then LLM)
    2. Generate analytical conclusions that add value (always LLM)
    """

    def __init__(self, llm_client=None):
        """Initialize analyzer."""
        self.llm_client = llm_client
        self.last_prompt = None
        self.last_response = None
        self.stage1_source = None  # Track how Stage 1 was performed
        self.analytical_failed = False  # Set True if analytical generation fails after retries

    def extract_conclusions(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None
    ) -> List[Dict]:
        """
        Extract Board's explicit conclusions with entity tagging.
        This is the basic extraction - returns dicts for compatibility.
        """
        conclusions, source = self._get_board_conclusions(conclusions_text, all_entities, code_provisions)
        return [self._conclusion_to_dict(c) for c in conclusions]

    def extract_conclusions_with_analysis(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None,
        board_questions: List[Dict] = None,
        analytical_questions: List[Dict] = None,
        case_facts: str = ""
    ) -> Dict[str, Any]:
        """
        Full analytical extraction: Board conclusions + generated analytical conclusions.

        Args:
            conclusions_text: Raw conclusions section text
            all_entities: Dict with all 9 entity types (with URIs)
            code_provisions: Extracted code provisions
            board_questions: Board's explicit questions
            analytical_questions: Generated analytical questions (implicit, theoretical, etc.)
            case_facts: Case facts for context

        Returns:
            Dict with conclusion types as keys plus metadata:
            {
                'board_explicit': [...],
                'analytical_extension': [...],
                'question_response': [...],
                'principle_synthesis': [...],
                'stage1_source': 'imported' or 'llm_extracted',
                'stage1_used_llm': bool
            }
        """
        result = {
            ConclusionType.BOARD_EXPLICIT.value: [],
            ConclusionType.ANALYTICAL_EXTENSION.value: [],
            ConclusionType.QUESTION_RESPONSE.value: [],
            ConclusionType.PRINCIPLE_SYNTHESIS.value: [],
            'stage1_source': None,
            'stage1_used_llm': False
        }

        # Stage 1: Get Board's explicit conclusions (flexible)
        board_conclusions, source = self._get_board_conclusions(
            conclusions_text, all_entities, code_provisions
        )
        result[ConclusionType.BOARD_EXPLICIT.value] = board_conclusions
        result['stage1_source'] = source.value
        result['stage1_used_llm'] = (source == ConclusionSource.LLM_EXTRACTED)

        if not board_conclusions:
            logger.warning("No board conclusions found, proceeding with analytical generation anyway")

        # Stage 2: Generate analytical conclusions (always LLM)
        if self.llm_client:
            analytical = self._generate_analytical_conclusions(
                board_conclusions,
                all_entities,
                code_provisions,
                board_questions or [],
                analytical_questions or [],
                case_facts
            )

            result[ConclusionType.ANALYTICAL_EXTENSION.value] = analytical.get('analytical_extension', [])
            result[ConclusionType.QUESTION_RESPONSE.value] = analytical.get('question_response', [])
            result[ConclusionType.PRINCIPLE_SYNTHESIS.value] = analytical.get('principle_synthesis', [])

        return result

    def _get_board_conclusions(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> Tuple[List[EthicalConclusion], ConclusionSource]:
        """
        Get Board's explicit conclusions - try parsing first, fall back to LLM.

        Returns:
            Tuple of (conclusions, source) where source indicates how they were obtained
        """
        if not conclusions_text or not conclusions_text.strip():
            logger.warning("No conclusions text provided")
            return [], ConclusionSource.IMPORTED

        # Stage 1A: Try to parse from imported text (no LLM needed)
        parsed_conclusions = self._parse_board_conclusions_from_text(conclusions_text, all_entities)

        if parsed_conclusions:
            logger.info(f"Parsed {len(parsed_conclusions)} Board conclusions from imported text (no LLM)")
            self.stage1_source = ConclusionSource.IMPORTED
            return parsed_conclusions, ConclusionSource.IMPORTED

        # Stage 1B: Fall back to LLM extraction
        if self.llm_client:
            logger.info("Parsing failed, falling back to LLM extraction for Board conclusions")
            llm_conclusions = self._extract_board_conclusions_llm(
                conclusions_text, all_entities, code_provisions
            )
            self.stage1_source = ConclusionSource.LLM_EXTRACTED
            return llm_conclusions, ConclusionSource.LLM_EXTRACTED

        logger.warning("No LLM client and parsing failed")
        return [], ConclusionSource.IMPORTED

    def _parse_board_conclusions_from_text(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List]
    ) -> List[EthicalConclusion]:
        """
        Parse Board's conclusions from imported text without LLM.

        Board conclusions typically have structured determinations like:
        - "Engineer A was ethical in..."
        - "Engineer A was not ethical in..."
        - "It was not unethical for..."
        """
        conclusions = []

        # Clean HTML tags
        clean_text = re.sub(r'<[^>]+>', ' ', conclusions_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # Pattern 1: Numbered conclusions (1., 2., etc.)
        numbered_pattern = r'(\d+)\.\s*([^.]+(?:ethical|unethical|violation|compliance|proper|improper)[^.]+\.)'
        numbered_matches = re.findall(numbered_pattern, clean_text, re.IGNORECASE)

        if numbered_matches:
            for num, c_text in numbered_matches:
                c_text = c_text.strip()
                if len(c_text) > 30:  # Minimum reasonable conclusion length
                    conclusion = self._create_parsed_conclusion(
                        conclusion_number=int(num),
                        conclusion_text=c_text,
                        all_entities=all_entities
                    )
                    conclusions.append(conclusion)

            if conclusions:
                return conclusions

        # Pattern 2: Look for ethical determination sentences
        determination_pattern = r'([A-Z][^.]*(?:was|were|is|are)\s+(?:ethical|unethical|not\s+(?:un)?ethical|a\s+violation|in\s+compliance|improper|proper)[^.]+\.)'
        determination_matches = re.findall(determination_pattern, clean_text, re.IGNORECASE)

        for idx, c_text in enumerate(determination_matches, 1):
            c_text = c_text.strip()
            if len(c_text) > 30:
                conclusion = self._create_parsed_conclusion(
                    conclusion_number=idx,
                    conclusion_text=c_text,
                    all_entities=all_entities
                )
                conclusions.append(conclusion)

        # Pattern 3: Simple sentence extraction if we found nothing structured
        if not conclusions:
            # Split on sentence boundaries and look for conclusion-like sentences
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            conclusion_keywords = ['conclude', 'conclusion', 'determination', 'finding',
                                   'ethical', 'unethical', 'violation', 'compliance']

            for idx, sentence in enumerate(sentences, 1):
                sentence = sentence.strip()
                if len(sentence) > 30:
                    sentence_lower = sentence.lower()
                    if any(kw in sentence_lower for kw in conclusion_keywords):
                        conclusion = self._create_parsed_conclusion(
                            conclusion_number=idx,
                            conclusion_text=sentence,
                            all_entities=all_entities
                        )
                        conclusions.append(conclusion)

        return conclusions

    def _create_parsed_conclusion(
        self,
        conclusion_number: int,
        conclusion_text: str,
        all_entities: Dict[str, List]
    ) -> EthicalConclusion:
        """Create an EthicalConclusion from parsed text, with entity matching."""
        # Find mentioned entities by looking for labels in the conclusion text
        mentioned = {}
        mentioned_uris = {}

        entity_types = ['roles', 'obligations', 'principles', 'constraints',
                       'actions', 'events', 'states', 'resources', 'capabilities']

        for entity_type in entity_types:
            entities = all_entities.get(entity_type, [])
            for entity in entities:
                # Get label and URI
                if isinstance(entity, dict):
                    label = entity.get('label', entity.get('entity_label', ''))
                    uri = entity.get('uri', entity.get('entity_uri', ''))
                else:
                    label = getattr(entity, 'entity_label', getattr(entity, 'label', ''))
                    uri = getattr(entity, 'entity_uri', getattr(entity, 'uri', ''))

                if label and label.lower() in conclusion_text.lower():
                    if entity_type not in mentioned:
                        mentioned[entity_type] = []
                        mentioned_uris[entity_type] = []
                    if label not in mentioned[entity_type]:
                        mentioned[entity_type].append(label)
                        if uri:
                            mentioned_uris[entity_type].append(uri)

        # Detect board conclusion type
        board_type = self._detect_board_conclusion_type(conclusion_text)

        # Detect cited provisions (look for patterns like II.1.c, III.2.a)
        provision_pattern = r'(?:Section\s+)?([IVX]+\.\d+(?:\.[a-z])?)'
        cited_provisions = re.findall(provision_pattern, conclusion_text, re.IGNORECASE)

        return EthicalConclusion(
            conclusion_number=conclusion_number,
            conclusion_text=conclusion_text,
            conclusion_type=ConclusionType.BOARD_EXPLICIT.value,
            board_conclusion_type=board_type,
            mentioned_entities=mentioned,
            mentioned_entity_uris=mentioned_uris,
            cited_provisions=cited_provisions,
            extraction_reasoning="Parsed from imported case text (no LLM)",
            source=ConclusionSource.IMPORTED.value
        )

    def _detect_board_conclusion_type(self, conclusion_text: str) -> str:
        """Detect the type of board conclusion from text."""
        text_lower = conclusion_text.lower()

        if 'violation' in text_lower or 'violated' in text_lower:
            return BoardConclusionType.VIOLATION.value
        elif 'not unethical' in text_lower or 'was ethical' in text_lower or 'were ethical' in text_lower:
            return BoardConclusionType.COMPLIANCE.value
        elif 'no violation' in text_lower or 'not a violation' in text_lower:
            return BoardConclusionType.NO_VIOLATION.value
        elif 'recommend' in text_lower or 'should' in text_lower:
            return BoardConclusionType.RECOMMENDATION.value
        elif 'interpret' in text_lower or 'means' in text_lower or 'clarif' in text_lower:
            return BoardConclusionType.INTERPRETATION.value
        elif 'unethical' in text_lower:
            return BoardConclusionType.VIOLATION.value
        else:
            return "unknown"

    def _extract_board_conclusions_llm(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> List[EthicalConclusion]:
        """Extract Board's conclusions using LLM (fallback when parsing fails)."""
        logger.info("Extracting Board's explicit conclusions via LLM")

        prompt = self._create_board_extraction_prompt(
            conclusions_text, all_entities, code_provisions
        )
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=6000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            conclusions = self._parse_board_conclusions_response(response_text, all_entities)
            logger.info(f"LLM extracted {len(conclusions)} Board conclusions")

            return conclusions

        except Exception as e:
            logger.error(f"Error extracting board conclusions via LLM: {e}")
            return []

    def _generate_analytical_conclusions(
        self,
        board_conclusions: List[EthicalConclusion],
        all_entities: Dict[str, List],
        code_provisions: List[Dict],
        board_questions: List[Dict],
        analytical_questions: List[Dict],
        case_facts: str
    ) -> Dict[str, List[EthicalConclusion]]:
        """Generate analytical conclusions in three focused LLM calls (one per category)."""
        if not self.llm_client:
            return {}

        logger.info("Generating analytical conclusions via LLM (3 batches)")

        result = {
            'analytical_extension': [],
            'question_response': [],
            'principle_synthesis': []
        }

        batch_specs = [
            (['analytical_extension'], "analytical extensions"),
            (['question_response'], "question responses"),
            (['principle_synthesis'], "principle synthesis"),
        ]

        for categories, desc in batch_specs:
            prompt = self._create_analytical_prompt(
                board_conclusions, all_entities, code_provisions,
                board_questions, analytical_questions, case_facts,
                categories=categories
            )

            label = f"ANALYTICAL ({'+'.join(categories)})"
            if self.last_prompt:
                self.last_prompt += f"\n\n--- {label} PROMPT ---\n" + prompt
            else:
                self.last_prompt = prompt

            batch_result = self._call_analytical_batch(prompt, all_entities, desc)
            for cat in categories:
                result[cat] = batch_result.get(cat, [])

        total = sum(len(v) for v in result.values())
        logger.info(f"Generated {total} analytical conclusions across 3 batches")
        return result

    def _call_analytical_batch(
        self,
        prompt: str,
        all_entities: Dict[str, List],
        desc: str
    ) -> Dict[str, List[EthicalConclusion]]:
        """Execute a single analytical conclusion batch with retries."""
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                from app.utils.llm_utils import streaming_completion
                response_text = streaming_completion(
                    self.llm_client,
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=10000,
                    prompt=prompt,
                    temperature=0.3,
                )
                logger.info(f"Batch '{desc}' response length: {len(response_text)} chars")
                if self.last_response:
                    self.last_response += f"\n\n--- ANALYTICAL RESPONSE ({desc}) ---\n" + response_text
                else:
                    self.last_response = response_text

                analytical = self._parse_analytical_conclusions_response(response_text, all_entities)

                total = sum(len(v) for v in analytical.values())
                logger.info(f"Batch '{desc}': {total} conclusions")
                return analytical

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError) as e:
                last_error = e
                wait = 2 ** (attempt + 1)
                logger.warning(f"Analytical batch '{desc}' attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"Analytical batch '{desc}' failed (non-retryable): {e}")
                self.analytical_failed = True
                return {}

        logger.error(f"Analytical batch '{desc}' failed after {max_retries} retries: {last_error}")
        self.analytical_failed = True
        return {}

    def _create_board_extraction_prompt(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> str:
        """Create prompt to extract Board's explicit conclusions via LLM."""
        entities_text = format_entities_compact(all_entities)
        provisions_text = self._format_provisions(code_provisions)

        return f"""You are analyzing the Conclusions section from an NSPE Board of Ethical Review case.

**CONCLUSIONS SECTION TEXT:**
{conclusions_text}

**EXTRACTED CASE ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Extract ONLY the Board's explicit conclusions (their formal determinations on each question).
These are the conclusions the Board reached on the ethical issues.

For each conclusion:
1. **Conclusion Text**: The verbatim conclusion text
2. **Mentioned Entities**: Which entities from the case are referenced? Use exact labels from the list above.
3. **Cited Provisions**: Which code provisions are cited in the reasoning?
4. **Board Conclusion Type**: What kind of conclusion?
   - 'violation': Found a violation of ethics code
   - 'compliance': Found compliance with ethics code
   - 'no_violation': Found no violation occurred
   - 'interpretation': Clarifies interpretation of provision
   - 'recommendation': Recommends action
5. **Reasoning**: Brief explanation of the conclusion

**OUTPUT FORMAT (JSON):**
```json
[
  {{
    "conclusion_number": 1,
    "conclusion_text": "Engineer A violated Section II.4.e by accepting the contract.",
    "conclusion_type": "board_explicit",
    "board_conclusion_type": "violation",
    "mentioned_entities": {{
      "roles": ["Engineer A"],
      "actions": ["accepting the contract"]
    }},
    "cited_provisions": ["II.4.e"],
    "extraction_reasoning": "The Board found a violation based on the conflict of interest."
  }}
]
```

Extract ALL conclusions the Board reached. Use EXACT entity labels from the lists above.
"""

    def _create_analytical_prompt(
        self,
        board_conclusions: List[EthicalConclusion],
        all_entities: Dict[str, List],
        code_provisions: List[Dict],
        board_questions: List[Dict],
        analytical_questions: List[Dict],
        case_facts: str,
        categories: Optional[List[str]] = None
    ) -> str:
        """Create prompt for analytical conclusion generation.

        Args:
            categories: Which conclusion categories to generate. Defaults to all three.
        """
        if categories is None:
            categories = ['analytical_extension', 'question_response', 'principle_synthesis']

        # Format board conclusions
        if board_conclusions:
            board_c_text = "\n".join([
                f"{c.conclusion_number}. [{c.board_conclusion_type}] {c.conclusion_text}"
                for c in board_conclusions
            ])
        else:
            board_c_text = "(No explicit Board conclusions identified)"

        # Format board questions
        if board_questions:
            board_q_text = "\n".join([
                f"Q{q.get('question_number', 0)}. {q.get('question_text', '')}"
                for q in board_questions
            ])
        else:
            board_q_text = "(No Board questions provided)"

        # Format analytical questions by type
        analytical_by_type = {}
        for q in analytical_questions:
            q_type = q.get('question_type', 'unknown')
            if q_type not in analytical_by_type:
                analytical_by_type[q_type] = []
            analytical_by_type[q_type].append(q)

        analytical_text = ""
        for q_type, qs in analytical_by_type.items():
            analytical_text += f"\n**{q_type.upper()} QUESTIONS:**\n"
            for q in qs:
                analytical_text += f"- Q{q.get('question_number', 0)}: {q.get('question_text', '')}\n"

        entities_text = format_entities_compact(all_entities)
        provisions_text = self._format_provisions(code_provisions)

        # Build category instructions and examples based on requested categories
        category_blocks = []
        example_blocks = []

        if 'analytical_extension' in categories:
            category_blocks.append("""**ANALYTICAL EXTENSIONS**: Extend the Board's reasoning with additional analysis.
   - What additional considerations apply to the Board's conclusions?
   - What nuances did the Board not address?""")
            example_blocks.append("""  "analytical_extension": [
    {
      "conclusion_text": "Beyond the Board's finding, Engineer A also demonstrated...",
      "mentioned_entities": {"roles": ["Engineer A"]},
      "cited_provisions": [],
      "source_conclusion": 1,
      "related_analytical_questions": []
    }
  ]""")

        if 'question_response' in categories:
            category_blocks.append("""**QUESTION RESPONSES**: Respond to analytical questions the Board didn't address.
   - Answer implicit, theoretical, or counterfactual questions
   - Reference the specific analytical question numbers""")
            example_blocks.append("""  "question_response": [
    {
      "conclusion_text": "In response to the implicit question about disclosure timing...",
      "mentioned_entities": {},
      "cited_provisions": [],
      "source_conclusion": null,
      "related_analytical_questions": [101]
    }
  ]""")

        if 'principle_synthesis' in categories:
            category_blocks.append("""**PRINCIPLE SYNTHESIS**: Synthesize how principles interact in this case.
   - How were principle tensions resolved (or not)?
   - What does this case teach about principle prioritization?""")
            example_blocks.append("""  "principle_synthesis": [
    {
      "conclusion_text": "The tension between client loyalty and public safety was resolved by...",
      "mentioned_entities": {"principles": ["Client Loyalty", "Public Safety"]},
      "cited_provisions": [],
      "source_conclusion": null,
      "related_analytical_questions": [201, 202]
    }
  ]""")

        numbered_categories = "\n\n".join(
            f"{i+1}. {block}" for i, block in enumerate(category_blocks)
        )
        json_example = "{{\n" + ",\n".join(example_blocks) + "\n}}"

        return f"""You are an ethics analyst examining an NSPE Board of Ethical Review case.

**BOARD'S EXPLICIT CONCLUSIONS:**
{board_c_text}

**BOARD'S QUESTIONS:**
{board_q_text}

**ANALYTICAL QUESTIONS (generated):**
{analytical_text if analytical_text else "(none provided)"}

**CASE FACTS:**
{case_facts if case_facts else "(not provided)"}

**ALL EXTRACTED ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Generate analytical conclusions that deepen understanding beyond the Board's explicit conclusions.

{numbered_categories}

**FORMATTING RULES:**
- Write conclusions in plain English. Do NOT embed URIs in conclusion_text.
- Reference entities by their exact label in the mentioned_entities field.
- Generate 1-3 conclusions per category.
- Link to source_conclusion (Board conclusion number) when extending Board's reasoning.
- Link to related_analytical_questions (question numbers) when responding to them.

**OUTPUT FORMAT (JSON):**
```json
{json_example}
```
"""

    def _format_provisions(self, code_provisions: List[Dict]) -> str:
        """Format code provisions for prompt."""
        if not code_provisions:
            return ""

        text = "\n**CODE PROVISIONS EXTRACTED:**\n"
        for prov in code_provisions[:10]:  # Limit for prompt size
            code = prov.get('code_provision', prov.get('codeProvision', 'Unknown'))
            provision_text = prov.get('provision_text', prov.get('provisionText', ''))
            text += f"- {code}: {provision_text[:100]}...\n"
        return text

    def _parse_board_conclusions_response(
        self,
        response_text: str,
        all_entities: Optional[Dict[str, List]] = None
    ) -> List[EthicalConclusion]:
        """Parse Board conclusions from LLM response."""
        json_data = parse_json_response(response_text, "board conclusions")
        if not json_data:
            return []

        conclusions = []
        for c_data in json_data:
            mentioned = c_data.get('mentioned_entities', {})
            resolved_uris = resolve_entity_labels_to_uris(mentioned, all_entities) if all_entities else {}
            conclusion = EthicalConclusion(
                conclusion_number=c_data.get('conclusion_number', 0),
                conclusion_text=c_data.get('conclusion_text', ''),
                conclusion_type=ConclusionType.BOARD_EXPLICIT.value,
                board_conclusion_type=c_data.get('board_conclusion_type', 'unknown'),
                mentioned_entities=mentioned,
                mentioned_entity_uris=resolved_uris,
                cited_provisions=c_data.get('cited_provisions', []),
                extraction_reasoning=c_data.get('extraction_reasoning', ''),
                source=ConclusionSource.LLM_EXTRACTED.value,
                answers_questions=c_data.get('answers_questions', [])
            )
            conclusions.append(conclusion)

        return conclusions

    def _parse_analytical_conclusions_response(
        self,
        response_text: str,
        all_entities: Optional[Dict[str, List]] = None
    ) -> Dict[str, List[EthicalConclusion]]:
        """Parse analytical conclusions from LLM response."""
        result = {
            'analytical_extension': [],
            'question_response': [],
            'principle_synthesis': []
        }

        json_data = parse_json_object(response_text, "analytical conclusions")
        if not json_data:
            return result

        # Number offsets: analytical_extension=101+, question_response=201+, principle_synthesis=301+
        number_bases = {'analytical_extension': 101, 'question_response': 201, 'principle_synthesis': 301}

        for category in result.keys():
            base = number_bases.get(category, 1)
            for idx, c_data in enumerate(json_data.get(category, [])):
                mentioned = c_data.get('mentioned_entities', {})
                resolved_uris = resolve_entity_labels_to_uris(mentioned, all_entities) if all_entities else {}
                conclusion = EthicalConclusion(
                    conclusion_number=base + idx,
                    conclusion_text=c_data.get('conclusion_text', ''),
                    conclusion_type=category,
                    mentioned_entities=mentioned,
                    mentioned_entity_uris=resolved_uris,
                    cited_provisions=c_data.get('cited_provisions', []),
                    extraction_reasoning='',
                    source=ConclusionSource.LLM_GENERATED.value,
                    source_conclusion=c_data.get('source_conclusion'),
                    related_analytical_questions=c_data.get('related_analytical_questions', [])
                )
                result[category].append(conclusion)

        return result

    def _conclusion_to_dict(self, c: EthicalConclusion) -> Dict:
        """Convert EthicalConclusion to dict for backward compatibility."""
        return {
            'conclusion_number': c.conclusion_number,
            'conclusion_text': c.conclusion_text,
            'conclusion_type': c.conclusion_type,
            'board_conclusion_type': c.board_conclusion_type,
            'mentioned_entities': c.mentioned_entities,
            'mentioned_entity_uris': c.mentioned_entity_uris,
            'cited_provisions': c.cited_provisions,
            'extraction_reasoning': c.extraction_reasoning,
            'source': c.source,
            'answers_questions': c.answers_questions,
            'source_conclusion': c.source_conclusion,
            'related_analytical_questions': c.related_analytical_questions,
            'label': f"Conclusion_{c.conclusion_number}"
        }

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response,
            'stage1_source': self.stage1_source.value if self.stage1_source else None
        }
