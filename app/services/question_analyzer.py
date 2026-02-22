"""
Question Analyzer - Flexible Two-Stage Design with Entity URIs

Stage 1: Board Questions (Ground Truth)
- First attempts to parse from imported text (no LLM needed)
- Falls back to LLM extraction if parsing fails
- Marks source as 'imported' vs 'llm_extracted'

Stage 2: Analytical Questions (LLM-Generated)
- Generates questions that add scholarly/pedagogical value
- Uses entity URIs for grounding
- Types: implicit, principle_tension, theoretical, counterfactual

Question Types:
- board_explicit: The Board's actual questions (ground truth)
- implicit: Questions the case raises but weren't explicitly asked
- principle_tension: Where ethical principles come into conflict
- theoretical: Questions framed in ethical theory terms
- counterfactual: What-if scenarios for deeper understanding
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


class QuestionType(Enum):
    """Types of ethical questions."""
    BOARD_EXPLICIT = "board_explicit"      # Board's actual questions
    IMPLICIT = "implicit"                   # Questions case raises but weren't asked
    PRINCIPLE_TENSION = "principle_tension" # Where principles conflict
    THEORETICAL = "theoretical"             # Ethical theory framings
    COUNTERFACTUAL = "counterfactual"       # What-if scenarios


class QuestionSource(Enum):
    """Source of question extraction."""
    IMPORTED = "imported"        # Parsed from case text without LLM
    LLM_EXTRACTED = "llm_extracted"  # Extracted via LLM
    LLM_GENERATED = "llm_generated"  # Generated via LLM (analytical)


@dataclass
class EthicalQuestion:
    """Represents an extracted or generated ethical question."""
    question_number: int
    question_text: str
    question_type: str  # QuestionType value
    mentioned_entities: Dict[str, List[str]] = field(default_factory=dict)
    mentioned_entity_uris: Dict[str, List[str]] = field(default_factory=dict)  # URIs for grounding
    related_provisions: List[str] = field(default_factory=list)
    extraction_reasoning: str = ""
    source: str = "llm_extracted"  # QuestionSource value
    # For analytical questions
    source_question: Optional[int] = None  # Links to board_explicit question number
    ethical_framework: Optional[str] = None  # deontological, consequentialist, virtue


class QuestionAnalyzer:
    """
    Analyzes Questions section with complete entity context.

    Flexible two-stage analysis:
    1. Load/Parse Board's explicit questions (try import first, then LLM)
    2. Generate analytical questions that add value (always LLM)
    """

    def __init__(self, llm_client=None):
        """Initialize analyzer."""
        self.llm_client = llm_client
        self.last_prompt = None
        self.last_response = None
        self.stage1_source = None  # Track how Stage 1 was performed
        self.analytical_failed = False  # Set True if analytical generation fails after retries

    def extract_questions(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None
    ) -> List[Dict]:
        """
        Extract Board's explicit questions with entity tagging.
        This is the basic extraction - returns dicts for compatibility.
        """
        questions, source = self._get_board_questions(questions_text, all_entities, code_provisions)
        return [self._question_to_dict(q) for q in questions]

    def extract_questions_with_analysis(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None,
        case_facts: str = "",
        case_conclusion: str = ""
    ) -> Dict[str, Any]:
        """
        Full analytical extraction: Board questions + generated analytical questions.

        Returns:
            Dict with question types as keys plus metadata:
            {
                'board_explicit': [...],
                'implicit': [...],
                'principle_tension': [...],
                'theoretical': [...],
                'counterfactual': [...],
                'stage1_source': 'imported' or 'llm_extracted',
                'stage1_used_llm': bool
            }
        """
        result = {
            QuestionType.BOARD_EXPLICIT.value: [],
            QuestionType.IMPLICIT.value: [],
            QuestionType.PRINCIPLE_TENSION.value: [],
            QuestionType.THEORETICAL.value: [],
            QuestionType.COUNTERFACTUAL.value: [],
            'stage1_source': None,
            'stage1_used_llm': False
        }

        # Stage 1: Get Board's explicit questions (flexible)
        board_questions, source = self._get_board_questions(
            questions_text, all_entities, code_provisions
        )
        result[QuestionType.BOARD_EXPLICIT.value] = board_questions
        result['stage1_source'] = source.value
        result['stage1_used_llm'] = (source == QuestionSource.LLM_EXTRACTED)

        if not board_questions:
            logger.warning("No board questions found, proceeding with analytical generation anyway")

        # Stage 2: Generate analytical questions (always LLM)
        if self.llm_client:
            logger.info(f"Stage 2: Generating analytical questions (LLM client present)")
            analytical = self._generate_analytical_questions(
                board_questions,
                all_entities,
                code_provisions,
                case_facts,
                case_conclusion
            )

            result[QuestionType.IMPLICIT.value] = analytical.get('implicit', [])
            result[QuestionType.PRINCIPLE_TENSION.value] = analytical.get('principle_tension', [])
            result[QuestionType.THEORETICAL.value] = analytical.get('theoretical', [])
            result[QuestionType.COUNTERFACTUAL.value] = analytical.get('counterfactual', [])

            logger.info(f"Stage 2 complete: implicit={len(result[QuestionType.IMPLICIT.value])}, "
                       f"principle_tension={len(result[QuestionType.PRINCIPLE_TENSION.value])}, "
                       f"theoretical={len(result[QuestionType.THEORETICAL.value])}, "
                       f"counterfactual={len(result[QuestionType.COUNTERFACTUAL.value])}")
        else:
            logger.warning("Stage 2 skipped: No LLM client available for analytical generation")

        return result

    def _get_board_questions(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> Tuple[List[EthicalQuestion], QuestionSource]:
        """
        Get Board's explicit questions - try parsing first, fall back to LLM.

        Returns:
            Tuple of (questions, source) where source indicates how they were obtained
        """
        if not questions_text or not questions_text.strip():
            logger.warning("No questions text provided")
            return [], QuestionSource.IMPORTED

        # Stage 1A: Try to parse from imported text (no LLM needed)
        parsed_questions = self._parse_board_questions_from_text(questions_text, all_entities)

        if parsed_questions:
            logger.info(f"Parsed {len(parsed_questions)} Board questions from imported text (no LLM)")
            self.stage1_source = QuestionSource.IMPORTED
            return parsed_questions, QuestionSource.IMPORTED

        # Stage 1B: Fall back to LLM extraction
        if self.llm_client:
            logger.info("Parsing failed, falling back to LLM extraction for Board questions")
            llm_questions = self._extract_board_questions_llm(
                questions_text, all_entities, code_provisions
            )
            self.stage1_source = QuestionSource.LLM_EXTRACTED
            return llm_questions, QuestionSource.LLM_EXTRACTED

        logger.warning("No LLM client and parsing failed")
        return [], QuestionSource.IMPORTED

    def _parse_board_questions_from_text(
        self,
        questions_text: str,
        all_entities: Dict[str, List]
    ) -> List[EthicalQuestion]:
        """
        Parse Board's questions from imported text without LLM.

        Handles various formats:
        - Numbered questions: "1. Was it ethical..."
        - Lettered questions: "a) Was it ethical..."
        - Single question (no numbering)
        - Questions ending with "?"
        """
        questions = []

        # Clean HTML tags
        clean_text = re.sub(r'<[^>]+>', ' ', questions_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # Pattern 1: Numbered questions (1., 2., etc.)
        numbered_pattern = r'(\d+)\.\s*([^?]+\?)'
        numbered_matches = re.findall(numbered_pattern, clean_text)

        if numbered_matches:
            for num, q_text in numbered_matches:
                q_text = q_text.strip()
                if len(q_text) > 20:  # Minimum reasonable question length
                    question = self._create_parsed_question(
                        question_number=int(num),
                        question_text=q_text,
                        all_entities=all_entities
                    )
                    questions.append(question)

            if questions:
                return questions

        # Pattern 2: Lettered questions (a), b), etc. or a., b., etc.)
        lettered_pattern = r'([a-z])[.)\]]\s*([^?]+\?)'
        lettered_matches = re.findall(lettered_pattern, clean_text, re.IGNORECASE)

        if lettered_matches:
            for idx, (letter, q_text) in enumerate(lettered_matches, 1):
                q_text = q_text.strip()
                if len(q_text) > 20:
                    question = self._create_parsed_question(
                        question_number=idx,
                        question_text=q_text,
                        all_entities=all_entities
                    )
                    questions.append(question)

            if questions:
                return questions

        # Pattern 3: Single question (no numbering) - find sentences ending with ?
        single_pattern = r'([A-Z][^?]*\?)'
        single_matches = re.findall(single_pattern, clean_text)

        for idx, q_text in enumerate(single_matches, 1):
            q_text = q_text.strip()
            if len(q_text) > 20:
                question = self._create_parsed_question(
                    question_number=idx,
                    question_text=q_text,
                    all_entities=all_entities
                )
                questions.append(question)

        return questions

    def _create_parsed_question(
        self,
        question_number: int,
        question_text: str,
        all_entities: Dict[str, List]
    ) -> EthicalQuestion:
        """Create an EthicalQuestion from parsed text, with entity matching."""
        # Find mentioned entities by looking for labels in the question text
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

                if label and label.lower() in question_text.lower():
                    if entity_type not in mentioned:
                        mentioned[entity_type] = []
                        mentioned_uris[entity_type] = []
                    if label not in mentioned[entity_type]:
                        mentioned[entity_type].append(label)
                        if uri:
                            mentioned_uris[entity_type].append(uri)

        return EthicalQuestion(
            question_number=question_number,
            question_text=question_text,
            question_type=QuestionType.BOARD_EXPLICIT.value,
            mentioned_entities=mentioned,
            mentioned_entity_uris=mentioned_uris,
            extraction_reasoning="Parsed from imported case text (no LLM)",
            source=QuestionSource.IMPORTED.value
        )

    def _extract_board_questions_llm(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> List[EthicalQuestion]:
        """Extract Board's questions using LLM (fallback when parsing fails)."""
        logger.info("Extracting Board's explicit questions via LLM")

        prompt = self._create_board_extraction_prompt(
            questions_text, all_entities, code_provisions
        )
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            questions = self._parse_board_questions_response(response_text, all_entities)
            logger.info(f"LLM extracted {len(questions)} Board questions")

            return questions

        except Exception as e:
            logger.error(f"Error extracting board questions via LLM: {e}")
            return []

    def _generate_analytical_questions(
        self,
        board_questions: List[EthicalQuestion],
        all_entities: Dict[str, List],
        code_provisions: List[Dict],
        case_facts: str,
        case_conclusion: str
    ) -> Dict[str, List[EthicalQuestion]]:
        """Generate analytical questions in two focused LLM calls.

        Split into two batches to keep output size manageable:
          Batch 1: implicit + principle_tension
          Batch 2: theoretical + counterfactual
        """
        if not self.llm_client:
            return {}

        logger.info("Generating analytical questions via LLM (2 batches)")

        result = {
            'implicit': [],
            'principle_tension': [],
            'theoretical': [],
            'counterfactual': []
        }

        batch_specs = [
            (['implicit', 'principle_tension'], "implicit questions and principle tensions"),
            (['theoretical', 'counterfactual'], "theoretical framings and counterfactual questions"),
        ]

        for categories, desc in batch_specs:
            prompt = self._create_analytical_prompt(
                board_questions, all_entities, code_provisions,
                case_facts, case_conclusion, categories=categories
            )

            # Track prompts
            label = f"ANALYTICAL ({'+'.join(categories)})"
            if self.last_prompt:
                self.last_prompt += f"\n\n--- {label} PROMPT ---\n" + prompt
            else:
                self.last_prompt = prompt

            batch_result = self._call_analytical_batch(prompt, all_entities, desc)
            for cat in categories:
                result[cat] = batch_result.get(cat, [])

        total = sum(len(v) for v in result.values())
        logger.info(f"Generated {total} analytical questions across 2 batches")
        return result

    def _call_analytical_batch(
        self,
        prompt: str,
        all_entities: Dict[str, List],
        desc: str
    ) -> Dict[str, List[EthicalQuestion]]:
        """Execute a single analytical question batch with retries."""
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                from app.utils.llm_utils import streaming_completion
                response_text = streaming_completion(
                    self.llm_client,
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=6000,
                    prompt=prompt,
                    temperature=0.3,
                )
                if self.last_response:
                    self.last_response += f"\n\n--- ANALYTICAL RESPONSE ({desc}) ---\n" + response_text
                else:
                    self.last_response = response_text

                analytical = self._parse_analytical_questions_response(response_text, all_entities)

                total = sum(len(v) for v in analytical.values())
                logger.info(f"Batch '{desc}': {total} questions")
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
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> str:
        """Create prompt to extract Board's explicit questions via LLM."""
        entities_text = format_entities_compact(all_entities)
        provisions_text = self._format_provisions(code_provisions)

        return f"""You are analyzing the Questions section from an NSPE Board of Ethical Review case.

**QUESTIONS SECTION TEXT:**
{questions_text}

**EXTRACTED CASE ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Extract ONLY the Board's explicit questions (the actual questions posed to the Board).
These are the questions the case was asked to answer.

For each question:
1. **Question Text**: The verbatim question text
2. **Mentioned Entities**: Which entities from the case are referenced? Use exact labels from the list above.
3. **Related Provisions**: Which code provisions (if any) are mentioned?
4. **Reasoning**: What is this question really asking?

**OUTPUT FORMAT (JSON):**
```json
[
  {{
    "question_number": 1,
    "question_text": "Was it ethical for Engineer A to accept the contract?",
    "question_type": "board_explicit",
    "mentioned_entities": {{
      "roles": ["Engineer A"]
    }},
    "related_provisions": ["II.4.e"],
    "extraction_reasoning": "Asks whether accepting the contract violated ethical duties."
  }}
]
```

Extract ALL questions the Board was asked. Use EXACT entity labels from the lists above.
"""

    def _create_analytical_prompt(
        self,
        board_questions: List[EthicalQuestion],
        all_entities: Dict[str, List],
        code_provisions: List[Dict],
        case_facts: str,
        case_conclusion: str,
        categories: Optional[List[str]] = None
    ) -> str:
        """Create prompt for analytical question generation.

        Args:
            categories: Which question categories to generate. Defaults to all four.
        """
        if categories is None:
            categories = ['implicit', 'principle_tension', 'theoretical', 'counterfactual']

        # Format board questions
        if board_questions:
            board_q_text = "\n".join([
                f"{q.question_number}. {q.question_text}" for q in board_questions
            ])
        else:
            board_q_text = "(No explicit Board questions identified - generate based on case facts)"

        entities_text = format_entities_compact(all_entities)
        provisions_text = self._format_provisions(code_provisions)

        # Build category instructions and examples based on requested categories
        category_blocks = []
        example_blocks = []

        if 'implicit' in categories:
            category_blocks.append("""**IMPLICIT QUESTIONS**: Questions the case raises but the Board didn't explicitly ask.
   - What ethical issues lurk beneath the surface?
   - What questions should have been asked?""")
            example_blocks.append("""  "implicit": [
    {
      "question_text": "Should Engineer A have disclosed the conflict earlier?",
      "mentioned_entities": {"roles": ["Engineer A"]},
      "related_provisions": [],
      "source_question": 1
    }
  ]""")

        if 'principle_tension' in categories:
            from app.utils.entity_prompt_utils import _get_entity_field
            principles = all_entities.get('principles', [])
            principles_list = ""
            if principles:
                for p in principles:
                    label = _get_entity_field(p, 'label', 'entity_label', default='Unknown')
                    principles_list += f"  - {label}\n"

            category_blocks.append(f"""**PRINCIPLE TENSIONS**: Where do extracted principles come into conflict?
   - "Does [Principle X] conflict with [Principle Y]?"
   Extracted principles:
{principles_list}""")
            example_blocks.append("""  "principle_tension": [
    {
      "question_text": "How should Engineer A balance client loyalty against public safety obligations?",
      "mentioned_entities": {"principles": ["Client Loyalty", "Public Safety"]},
      "related_provisions": ["III.1.a"],
      "source_question": null
    }
  ]""")

        if 'theoretical' in categories:
            category_blocks.append("""**THEORETICAL FRAMINGS**: Frame the case in ethical theory terms.
   - Deontological: "Did the engineer fulfill their duty of...?"
   - Consequentialist: "Did the outcome justify...?"
   - Virtue Ethics: "Did the engineer act with professional integrity when...?"
   Include an "ethical_framework" field (deontological, consequentialist, virtue_ethics).""")
            example_blocks.append("""  "theoretical": [
    {
      "question_text": "From a deontological perspective, did Engineer A fulfill their duty of transparency?",
      "mentioned_entities": {"roles": ["Engineer A"], "obligations": ["Transparency"]},
      "related_provisions": [],
      "ethical_framework": "deontological",
      "source_question": 1
    }
  ]""")

        if 'counterfactual' in categories:
            category_blocks.append("""**COUNTERFACTUAL QUESTIONS**: What-if scenarios.
   - "Would earlier disclosure have changed the outcome?"
   - "What if the engineer had refused the contract?"
""")
            example_blocks.append("""  "counterfactual": [
    {
      "question_text": "Would the outcome have differed if Engineer A had refused the contract?",
      "mentioned_entities": {"roles": ["Engineer A"], "actions": ["refuse contract"]},
      "related_provisions": [],
      "source_question": 1
    }
  ]""")

        numbered_categories = "\n\n".join(
            f"{i+1}. {block}" for i, block in enumerate(category_blocks)
        )
        json_example = "{{\n" + ",\n".join(example_blocks) + "\n}}"

        return f"""You are an ethics analyst examining an NSPE Board of Ethical Review case.

**BOARD'S EXPLICIT QUESTIONS:**
{board_q_text}

**CASE FACTS (summary):**
{case_facts[:2000] if case_facts else "(not provided)"}

**BOARD'S CONCLUSION (summary):**
{case_conclusion[:1000] if case_conclusion else "(not provided)"}

**ALL EXTRACTED ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Generate analytical questions that deepen understanding beyond the Board's explicit questions.

{numbered_categories}

**FORMATTING RULES:**
- Write questions in plain English. Do NOT embed URIs in question_text.
- Reference entities by their exact label in the mentioned_entities field.
- Generate 2-4 questions per category.
- Link to source Board questions when applicable (source_question field).

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

    def _parse_board_questions_response(
        self,
        response_text: str,
        all_entities: Dict[str, List]
    ) -> List[EthicalQuestion]:
        """Parse Board questions from LLM response."""
        json_data = parse_json_response(response_text, "board questions")
        if not json_data:
            return []

        questions = []
        for q_data in json_data:
            mentioned = q_data.get('mentioned_entities', {})
            question = EthicalQuestion(
                question_number=q_data.get('question_number', 0),
                question_text=q_data.get('question_text', ''),
                question_type=QuestionType.BOARD_EXPLICIT.value,
                mentioned_entities=mentioned,
                mentioned_entity_uris=resolve_entity_labels_to_uris(mentioned, all_entities),
                related_provisions=q_data.get('related_provisions', []),
                extraction_reasoning=q_data.get('extraction_reasoning', ''),
                source=QuestionSource.LLM_EXTRACTED.value
            )
            questions.append(question)

        return questions

    def _parse_analytical_questions_response(
        self,
        response_text: str,
        all_entities: Dict[str, List]
    ) -> Dict[str, List[EthicalQuestion]]:
        """Parse analytical questions from LLM response."""
        result = {
            'implicit': [],
            'principle_tension': [],
            'theoretical': [],
            'counterfactual': []
        }

        json_data = parse_json_object(response_text, "analytical questions")
        if not json_data:
            return result

        # Number offsets: implicit=101+, principle_tension=201+, theoretical=301+, counterfactual=401+
        number_bases = {'implicit': 101, 'principle_tension': 201, 'theoretical': 301, 'counterfactual': 401}

        for category in result.keys():
            base = number_bases.get(category, 1)
            for idx, q_data in enumerate(json_data.get(category, [])):
                mentioned = q_data.get('mentioned_entities', {})
                question = EthicalQuestion(
                    question_number=base + idx,
                    question_text=q_data.get('question_text', ''),
                    question_type=category,
                    mentioned_entities=mentioned,
                    mentioned_entity_uris=resolve_entity_labels_to_uris(mentioned, all_entities),
                    related_provisions=q_data.get('related_provisions', []),
                    extraction_reasoning='',
                    source=QuestionSource.LLM_GENERATED.value,
                    source_question=q_data.get('source_question'),
                    ethical_framework=q_data.get('ethical_framework')
                )
                result[category].append(question)

        return result

    def _question_to_dict(self, q: EthicalQuestion) -> Dict:
        """Convert EthicalQuestion to dict for backward compatibility."""
        return {
            'question_number': q.question_number,
            'question_text': q.question_text,
            'question_type': q.question_type,
            'mentioned_entities': q.mentioned_entities,
            'mentioned_entity_uris': q.mentioned_entity_uris,
            'related_provisions': q.related_provisions,
            'extraction_reasoning': q.extraction_reasoning,
            'source': q.source,
            'source_question': q.source_question,
            'ethical_framework': q.ethical_framework,
            'label': f"Question_{q.question_number}"
        }

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response,
            'stage1_source': self.stage1_source.value if self.stage1_source else None
        }
