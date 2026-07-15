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
from model_config import ModelConfig
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
    MIXED = "mixed"                 # Multi-situation verdict, differing polarities


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
        case_facts: str = "",
        conclusion_items: List[str] = None
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
            conclusions_text, all_entities, code_provisions,
            conclusion_items=conclusion_items
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
        code_provisions: List[Dict],
        conclusion_items: List[str] = None
    ) -> Tuple[List[EthicalConclusion], ConclusionSource]:
        """
        Get Board's explicit conclusions - structured items first, then parsing,
        then LLM fallback.

        Returns:
            Tuple of (conclusions, source) where source indicates how they were obtained
        """
        # Stage 1A0: the import already parsed the numbered conclusion items into
        # doc_metadata (the ground truth the review compares against). Use them
        # verbatim when present: the regex re-parse below has a single-sentence
        # match window and keyword gates, which dropped whole conclusions in 6
        # of 15 gold cases and truncated 16 to their first sentence
        # (2026-07-08 Q/C analysis, step4-qc-analysis.md finding 1/2).
        if conclusion_items:
            items = [t.strip() for t in conclusion_items if t and len(t.strip()) > 10]
            if items:
                conclusions = [
                    self._create_parsed_conclusion(
                        conclusion_number=i,
                        conclusion_text=text,
                        all_entities=all_entities,
                    )
                    for i, text in enumerate(items, 1)
                ]
                logger.info(f"Using {len(conclusions)} imported conclusion_items (no parse, no LLM)")
                self.stage1_source = ConclusionSource.IMPORTED
                return conclusions, ConclusionSource.IMPORTED

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
        """Detect the type of board conclusion from text.

        Ordering is load-bearing: negated forms match FIRST. Until 2026-07-12
        the bare 'violation' check ran first, so 'no violation' / 'not a
        violation' holdings returned VIOLATION and the NO_VIOLATION branch was
        dead code (polarity inversion). The semantic audit (S4) also found the
        era phrasings 'acted ethically' and 'has an ethical obligation to'
        falling through to 'unknown'; both are covered below. Round 3 (batch-5
        audit): 'Situation N.' multi-verdict bundles segment before detection
        and aggregate (uniform -> that type, differing polarities -> MIXED);
        '(not) consistent with the ... Code' maps per polarity; a past-tense
        duty affirmation ('had an (ethical) obligation to') is a breach
        finding, not a recommendation; and a prescriptive-opening conclusion
        whose only 'violation' tokens describe a third party's LEGAL violation
        inside advisory speech stays a recommendation. Deterministic by
        design -- the corpus backfill recomputes stored values with the same
        rules, so committed literals never drift from this function."""
        text_lower = conclusion_text.lower()

        # Multi-situation bundles ('Situation 1. ... Situation 2. ...') carry
        # one verdict per situation; detect per segment and aggregate.
        segments = re.split(r'(?i)(?=situation\s+\d+\s*[.:)])', conclusion_text)
        segments = [s for s in segments if re.match(r'(?i)situation\s+\d+', s.strip())]
        if len(segments) >= 2:
            seg_types = {self._detect_single_verdict(s.lower()) for s in segments}
            seg_types.discard("unknown")
            if len(seg_types) == 1:
                return seg_types.pop()
            if len(seg_types) > 1:
                return BoardConclusionType.MIXED.value
        return self._detect_single_verdict(text_lower)

    def _detect_single_verdict(self, text_lower: str) -> str:
        """The single-verdict pattern chain (see _detect_board_conclusion_type)."""
        # Split verdict in one holding (gold case 7 c2: 'was not unethical
        # per se. However, ... was unethical') -> MIXED; must precede the
        # 'not unethical' NO_VIOLATION token below.
        if (re.search(r'\bnot unethical\b', text_lower)
                and re.search(r'\b(?:was|is|were)\s+unethical\b', text_lower)):
            return BoardConclusionType.MIXED.value
        # Negated / exonerating forms before anything containing 'violation'
        # or 'unethical' as a substring. Convention (batch-3 semantic audit):
        # negated-violation wordings ('not unethical', 'no violation') ->
        # NO_VIOLATION; affirmative-ethical wordings ('acted ethically') ->
        # COMPLIANCE.
        if ('no violation' in text_lower or 'not a violation' in text_lower
                or 'did not violate' in text_lower or 'does not violate' in text_lower
                or 'not unethical' in text_lower):
            return BoardConclusionType.NO_VIOLATION.value
        # Modern exoneration forms (batch-7 audit): a negated-deception or
        # no-conflict clearance is a no-violation finding, not a
        # recommendation, even when 'should' appears in the sentence
        # (case 129: 'should not present any clear or apparent conflict of
        # interest'; case 146: 'does not compel disclosure nor does a failure
        # to disclose somehow constitute a deception').
        if (re.search(r'\b(?:does not|nor does|do not|did not)\b[^.]*\bconstitutes? a\b',
                      text_lower)
                or re.search(r'should not present any\b[^.]*\bconflict of interest',
                             text_lower)):
            return BoardConclusionType.NO_VIOLATION.value
        # Round 5 (batch-8 + gold audit). Split verdicts in one sentence
        # ('partly ethical, and partly unethical', gold case 7) -> MIXED;
        # must precede the bare 'unethical' violation token.
        if (re.search(r'\bpartly\s+ethical\b', text_lower)
                and re.search(r'\bpartly\s+unethical\b', text_lower)):
            return BoardConclusionType.MIXED.value
        # Misconduct finding bundled with an
        # affirmative report duty in one holding (case 19: 'would constitute
        # professional misconduct ... and Engineer A has a clear obligation
        # to report') -> MIXED.
        if (re.search(r'(?<!not )\bconstitutes?\b[^.]*\bmisconduct\b', text_lower)
                and re.search(r'\bha(?:s|ve) a (?:clear )?obligation to\b', text_lower)):
            return BoardConclusionType.MIXED.value
        # Duty-scope holdings are interpretations (case 18): 'X satisfies the
        # obligation' (discharge-condition statement) and 'not an obligation
        # ... but rather a personal choice' (negative scope ruling); both must
        # outrank the generic 'should'/'obligation to' recommendation match.
        if (re.search(r'\bsatisf(?:ies|y|ied)\b[^.]*\bobligations?\b', text_lower)
                and not re.search(r'\b(?:not|fails? to)\s+satisf', text_lower)):
            return BoardConclusionType.INTERPRETATION.value
        if 'not an obligation' in text_lower and 'personal choice' in text_lower:
            return BoardConclusionType.INTERPRETATION.value
        # Negated-duty clearances (batch-8/gold audit): 'does not have an
        # obligation to' / 'has no (professional or ethical) obligation to'.
        # Alone -> NO_VIOLATION (the conduct without the duty is cleared);
        # with a prescriptive 'should' rider -> MIXED (clearance + guidance,
        # gold case 7 c3). Must precede the 'obligation to' recommendation
        # token, which these phrases contain.
        neg_duty = re.search(
            r'\b(?:does not|do not)\s+have\s+an?\s+obligation to\b'
            r'|\bha(?:s|ve) no (?:professional or ethical |professional |ethical )?obligation to\b',
            text_lower)
        if neg_duty and 'should' in text_lower:
            return BoardConclusionType.MIXED.value
        if neg_duty:
            return BoardConclusionType.NO_VIOLATION.value
        if ('was ethical' in text_lower or 'were ethical' in text_lower
                or 'acted ethically' in text_lower or 'acted properly' in text_lower
                or 'it was ethical' in text_lower or 'would be ethical' in text_lower):
            return BoardConclusionType.COMPLIANCE.value
        # Fulfilled/discharged duty is a compliance verdict (batch-6 case 133:
        # 'has fulfilled his ethical obligation by taking prudent action');
        # negated fulfillment ('did not fulfill', 'had not fulfilled') stays
        # with the violation block below.
        if (re.search(r'\bfulfilled\s+(?:(?:his|her|their|its)\s+)?(?:ethical\s+)?obligations?\b',
                      text_lower)
                and 'not fulfill' not in text_lower):
            return BoardConclusionType.COMPLIANCE.value
        # 2000s-era per-situation verdict form (batch-5 case 128): negated
        # polarity first ('not consistent' contains 'consistent').
        if 'not consistent with' in text_lower and 'code' in text_lower:
            return BoardConclusionType.VIOLATION.value
        if 'consistent with' in text_lower and 'code' in text_lower:
            return BoardConclusionType.NO_VIOLATION.value
        # Past-tense duty affirmation is a breach finding (batch-5 case 148:
        # 'had an ethical obligation to report' where the facts show the duty
        # unmet); must precede the 'obligation to' -> recommendation rule.
        if ('had an ethical obligation to' in text_lower
                or 'had an obligation to' in text_lower
                or 'was obligated to' in text_lower):
            return BoardConclusionType.VIOLATION.value
        # Prescriptive-opening advisory conclusions (batch-5 case 86:
        # 'Engineer A should contact the client ... point out the action is a
        # violation of the law'): the 'violation' tokens describe a third
        # party's LEGAL violation inside recommended speech, not a Code
        # verdict. Suppress the bare-violation rule when the first sentence
        # prescribes ('should') and no Code-verdict wording appears anywhere.
        first_sentence = text_lower.split('.', 1)[0]
        # 'not ethical' is word-boundary-guarded (round 5): the adverb form
        # 'not ethically <verb>' appears in permissibility interpretations
        # ('Engineer A may not ethically object', case 15) and must not read
        # as a conduct verdict.
        code_verdict = ('unethical' in text_lower or 'violated' in text_lower
                        or 'violation of the code' in text_lower
                        or 'violation of the nspe code' in text_lower
                        or re.search(r'\bnot ethical\b', text_lower) is not None
                        or 'did not act ethically' in text_lower
                        or 'not be ethical' in text_lower)
        if 'should' in first_sentence and not code_verdict:
            return BoardConclusionType.RECOMMENDATION.value
        # Violation-by-omission and negated-ethical wordings (batch-3 audit:
        # 'did not fulfill her ethical obligations', 'would not be ethical').
        # 'not unethical' is already routed above and cannot reach these.
        if ('violation' in text_lower or 'violated' in text_lower
                or 'unethical' in text_lower or 'did not fulfill' in text_lower
                or 'failed to fulfill' in text_lower or 'not fulfilled' in text_lower
                or 'not be ethical' in text_lower
                or 'did not act ethically' in text_lower
                or re.search(r'\bnot ethical\b', text_lower)):
            return BoardConclusionType.VIOLATION.value
        if ('recommend' in text_lower or 'should' in text_lower
                or 'obligation to' in text_lower or 'duty to' in text_lower
                or 'is free to' in text_lower or 'required to' in text_lower
                or re.search(r'\b(?:is|are)\s+obligated\s+to\b', text_lower)):
            return BoardConclusionType.RECOMMENDATION.value
        if 'interpret' in text_lower or 'means' in text_lower or 'clarif' in text_lower:
            return BoardConclusionType.INTERPRETATION.value
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
            from app.utils.llm_utils import text_from_message, direct_call_params
            response = self.llm_client.messages.create(
                **direct_call_params(ModelConfig.get_claude_model("default"),
                                     max_tokens=6000, temperature=0.1),
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = text_from_message(response)
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

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError, ValueError) as e:  # ValueError = strict-parse failure on a malformed response: retryable nondeterminism (2026-07-10)
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
        from app.services.step4_synthesis.template_loader import get_step4_template
        return get_step4_template('step4_c_board').render(
            **self._board_extraction_variables(conclusions_text, all_entities, code_provisions)
        )

    def _board_extraction_variables(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> Dict[str, str]:
        """Variables for the step4_c_board template."""
        return {
            'conclusions_text': conclusions_text,
            'entities_text': format_entities_compact(all_entities),
            'provisions_text': self._format_provisions(code_provisions),
        }

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
        from app.services.step4_synthesis.template_loader import get_step4_template
        return get_step4_template('step4_c_analytical').render(
            **self._analytical_prompt_variables(
                board_conclusions, all_entities, code_provisions,
                board_questions, analytical_questions, case_facts, categories
            )
        )

    def _analytical_prompt_variables(
        self,
        board_conclusions: List[EthicalConclusion],
        all_entities: Dict[str, List],
        code_provisions: List[Dict],
        board_questions: List[Dict],
        analytical_questions: List[Dict],
        case_facts: str,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Variables for the step4_c_analytical template.

        The per-category instruction blocks and output-JSON example fragments
        are built here (category selection; the blocks are static strings,
        unlike the question side) and passed to the template as the
        `categories` list of {block, example} dicts; the template holds the
        frame.
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

        return {
            'board_c_text': board_c_text,
            'board_q_text': board_q_text,
            'analytical_text': analytical_text,
            'case_facts': case_facts,
            'entities_text': entities_text,
            'provisions_text': provisions_text,
            'categories': [
                {'block': block, 'example': example}
                for block, example in zip(category_blocks, example_blocks)
            ],
        }

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
