"""
Question Extraction Service

Implements McLaren's (2003) operationalization framework for Questions section.
Questions represent principle instantiation - linking abstract NSPE principles
to specific case facts.

Based on McLaren's nine operationalization techniques, particularly:
1. Principle Instantiation: Linking abstract principles to specific facts
2. Conflicting Principles Resolution: Resolving conflicts between principles
3. Fact Hypotheses: Identifying critical facts affecting principle application
4. Principle Grouping: Grouping related principles to strengthen arguments
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class PrincipleInstantiation:
    """
    Represents McLaren's principle instantiation technique.
    Links abstract NSPE principle to specific case facts.
    """
    principle_label: str
    principle_code: str  # e.g., "NSPE:CodeI.1"
    instantiated_facts: List[str]  # Critical facts that make this principle applicable
    rationale: str  # Why this principle applies to these facts


@dataclass
class PrincipleConflict:
    """
    Represents McLaren's conflicting principles resolution technique.
    Captures tension between competing ethical obligations.
    """
    principle1: str
    principle2: str
    conflict_description: str
    critical_facts: List[str]  # Facts that create the conflict


@dataclass
class EthicalQuestion:
    """
    Ethical question extracted from Questions section.
    Captures McLaren's operationalization in structured form.
    """
    question_number: int
    question_text: str

    # McLaren's Principle Instantiation
    invoked_principles: List[PrincipleInstantiation]

    # McLaren's Conflicting Principles Resolution
    principle_conflicts: List[PrincipleConflict]

    # Critical facts and entities
    critical_facts: List[str]
    referenced_entities: List[str]  # Entity labels from Facts/Discussion

    # Precedent value (for extensional definition)
    precedent_pattern: str  # What ethical pattern this exemplifies
    professional_context: str  # Engineering-specific context

    # Metadata
    confidence: float
    extraction_reasoning: str


class QuestionExtractionService:
    """
    Extract ethical questions from Questions section using McLaren framework.

    Implements extensional definition approach where questions show how
    abstract principles gain concrete meaning through specific applications.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the question extraction service.

        Args:
            llm_client: LLM client for intelligent extraction
        """
        self.llm_client = llm_client
        logger.info("QuestionExtractionService initialized with McLaren framework")

    def extract_questions(
        self,
        question_section_text: str,
        case_id: int,
        facts_entities: Dict[str, List[Dict]] = None,
        discussion_entities: Dict[str, List[Dict]] = None
    ) -> List[EthicalQuestion]:
        """
        Extract ethical questions with McLaren operationalization techniques.

        Args:
            question_section_text: Text of the Questions section
            case_id: Case identifier
            facts_entities: Entities extracted from Facts section
            discussion_entities: Entities extracted from Discussion section

        Returns:
            List of EthicalQuestion instances with principle instantiation
        """
        logger.info(f"Extracting questions for case {case_id} using McLaren framework")

        # Build context from previous sections
        entity_context = self._build_entity_context(facts_entities, discussion_entities)

        # Create LLM prompt with McLaren framework
        prompt = self._create_mclaren_extraction_prompt(
            question_section_text,
            entity_context,
            case_id
        )

        # Get LLM response
        if self.llm_client:
            response = self._call_llm(prompt)
            questions = self._parse_llm_response(response)
        else:
            # Fallback: basic parsing
            questions = self._fallback_extraction(question_section_text)

        logger.info(f"Extracted {len(questions)} ethical questions for case {case_id}")
        return questions

    def _build_entity_context(
        self,
        facts_entities: Dict[str, List[Dict]],
        discussion_entities: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """Build context from previously extracted entities."""
        context = {
            'roles': [],
            'states': [],
            'resources': [],
            'principles': [],
            'all_entity_labels': []
        }

        if facts_entities:
            for entity_type, entities in facts_entities.items():
                if entity_type in context:
                    context[entity_type].extend([e.get('label', e.get('name', '')) for e in entities])
                    context['all_entity_labels'].extend([e.get('label', e.get('name', '')) for e in entities])

        if discussion_entities:
            for entity_type, entities in discussion_entities.items():
                if entity_type in context:
                    labels = [e.get('label', e.get('name', '')) for e in entities]
                    # Add only if not already present (avoid duplicates)
                    context[entity_type].extend([l for l in labels if l not in context[entity_type]])
                    context['all_entity_labels'].extend([l for l in labels if l not in context['all_entity_labels']])

        return context

    def _create_mclaren_extraction_prompt(
        self,
        question_text: str,
        entity_context: Dict,
        case_id: int
    ) -> str:
        """
        Create LLM prompt implementing McLaren's operationalization framework.
        """
        prompt = f"""You are an expert in engineering ethics analyzing NSPE Board of Ethical Review cases.

# TASK: Extract Ethical Questions Using McLaren's Framework

Analyze the Questions section below and extract each ethical question with McLaren's (2003) operationalization techniques.

## McLaren's Operationalization Framework:

1. **Principle Instantiation**: Link abstract NSPE principles to specific case facts
2. **Conflicting Principles Resolution**: Identify conflicts between competing principles
3. **Fact Hypotheses**: Identify critical facts that affect principle application
4. **Precedent Value**: What ethical pattern this question exemplifies

## Previously Extracted Context:

**Roles from Facts/Discussion:**
{', '.join(entity_context['roles'][:10]) if entity_context['roles'] else 'None'}

**States from Facts/Discussion:**
{', '.join(entity_context['states'][:10]) if entity_context['states'] else 'None'}

**Resources from Facts/Discussion:**
{', '.join(entity_context['resources'][:10]) if entity_context['resources'] else 'None'}

## Questions Section Text:

{question_text}

## OUTPUT FORMAT (JSON):

Return a JSON array where each question has:

```json
[
  {{
    "question_number": 1,
    "question_text": "verbatim question text",

    "invoked_principles": [
      {{
        "principle_label": "Hold paramount public safety",
        "principle_code": "NSPE:CodeI.1",
        "instantiated_facts": ["fact that makes this principle apply"],
        "rationale": "why this principle applies here"
      }}
    ],

    "principle_conflicts": [
      {{
        "principle1": "Public Safety",
        "principle2": "Client Confidentiality",
        "conflict_description": "how these principles compete",
        "critical_facts": ["facts creating the conflict"]
      }}
    ],

    "critical_facts": ["key facts making this ethically significant"],
    "referenced_entities": ["Entity names from Facts/Discussion mentioned in question"],

    "precedent_pattern": "What ethical pattern this exemplifies (e.g., 'safety vs confidentiality in design review')",
    "professional_context": "Engineering-specific context",

    "confidence": 0.95,
    "extraction_reasoning": "Why these operationalizations were identified"
  }}
]
```

## Example (for reference):

If question is: "Was Engineer Smith ethically obligated to report the safety deficiency to authorities despite client confidentiality?"

```json
{{
  "question_number": 1,
  "question_text": "Was Engineer Smith ethically obligated to report the safety deficiency to authorities despite client confidentiality?",
  "invoked_principles": [
    {{
      "principle_label": "Hold paramount the safety, health, and welfare of the public",
      "principle_code": "NSPE:CodeI.1",
      "instantiated_facts": ["structural deficiency could cause bridge collapse", "public uses bridge daily"],
      "rationale": "Public safety paramount principle applies because identified deficiency poses imminent risk to public"
    }},
    {{
      "principle_label": "Act as faithful agents for clients",
      "principle_code": "NSPE:CodeII.1.a",
      "instantiated_facts": ["hired by client to review design", "client expects confidentiality"],
      "rationale": "Client loyalty principle applies due to contractual relationship and professional duties"
    }}
  ],
  "principle_conflicts": [
    {{
      "principle1": "Public Safety (CodeI.1)",
      "principle2": "Client Confidentiality (CodeII.1.a)",
      "conflict_description": "Engineer must choose between protecting public and maintaining client trust",
      "critical_facts": ["safety deficiency known to engineer", "reporting would violate client confidentiality", "public at risk"]
    }}
  ],
  "critical_facts": ["structural deficiency identified", "bridge serves public", "client expects confidentiality", "engineer has duty to both"],
  "referenced_entities": ["Engineer Smith", "Licensed Professional Engineer", "bridge structure"],
  "precedent_pattern": "Public safety paramount overrides client confidentiality when imminent risk exists",
  "professional_context": "Structural engineering - design review with safety implications",
  "confidence": 0.95,
  "extraction_reasoning": "Clear conflict between Code I.1 (public safety) and Code II.1.a (client loyalty) with safety deficiency as critical fact"
}}
```

Now extract all questions from the Questions section above. Return ONLY valid JSON array.
"""
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with the extraction prompt."""
        try:
            from models import ModelConfig

            model_name = ModelConfig.get_claude_model("powerful")

            # Use Anthropic messages API
            response = self.llm_client.messages.create(
                model=model_name,
                max_tokens=8000,
                temperature=0.3,  # Lower for structured extraction
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract content from Anthropic response
            content = response.content[0].text if response.content else ""
            return content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_llm_response(self, response: str) -> List[EthicalQuestion]:
        """Parse LLM JSON response into EthicalQuestion objects."""
        questions = []

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()

            data = json.loads(json_str)

            for q_data in data:
                # Parse principle instantiations
                invoked_principles = [
                    PrincipleInstantiation(
                        principle_label=p['principle_label'],
                        principle_code=p['principle_code'],
                        instantiated_facts=p['instantiated_facts'],
                        rationale=p['rationale']
                    )
                    for p in q_data.get('invoked_principles', [])
                ]

                # Parse principle conflicts
                principle_conflicts = [
                    PrincipleConflict(
                        principle1=c['principle1'],
                        principle2=c['principle2'],
                        conflict_description=c['conflict_description'],
                        critical_facts=c['critical_facts']
                    )
                    for c in q_data.get('principle_conflicts', [])
                ]

                question = EthicalQuestion(
                    question_number=q_data['question_number'],
                    question_text=q_data['question_text'],
                    invoked_principles=invoked_principles,
                    principle_conflicts=principle_conflicts,
                    critical_facts=q_data.get('critical_facts', []),
                    referenced_entities=q_data.get('referenced_entities', []),
                    precedent_pattern=q_data.get('precedent_pattern', ''),
                    professional_context=q_data.get('professional_context', ''),
                    confidence=q_data.get('confidence', 0.8),
                    extraction_reasoning=q_data.get('extraction_reasoning', '')
                )

                questions.append(question)

            logger.info(f"Successfully parsed {len(questions)} questions from LLM response")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response was: {response[:500]}")
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")

        return questions

    def _fallback_extraction(self, question_text: str) -> List[EthicalQuestion]:
        """
        Fallback extraction when LLM unavailable.
        Basic parsing of numbered questions.
        """
        questions = []

        # Split by question numbers (1., 2., etc.)
        import re
        q_pattern = r'(\d+)\.\s*(.+?)(?=\d+\.|$)'
        matches = re.findall(q_pattern, question_text, re.DOTALL)

        for num, text in matches:
            question = EthicalQuestion(
                question_number=int(num),
                question_text=text.strip(),
                invoked_principles=[],
                principle_conflicts=[],
                critical_facts=[],
                referenced_entities=[],
                precedent_pattern='',
                professional_context='',
                confidence=0.5,
                extraction_reasoning='Fallback extraction - LLM unavailable'
            )
            questions.append(question)

        return questions

    def to_rdf_storage(
        self,
        questions: List[EthicalQuestion],
        case_id: int,
        extraction_session_id: str
    ) -> List[Dict]:
        """
        Convert extracted questions to RDF storage format.

        Returns list of dictionaries ready for TemporaryRDFStorage.
        """
        storage_entries = []

        for question in questions:
            # Create RDF-like structure for question
            rdf_data = {
                '@type': 'proeth-case:EthicalQuestion',
                'questionNumber': question.question_number,
                'questionText': question.question_text,
                'invoked_principles': [
                    {
                        'principle_label': p.principle_label,
                        'principle_code': p.principle_code,
                        'instantiated_facts': p.instantiated_facts,
                        'rationale': p.rationale
                    }
                    for p in question.invoked_principles
                ],
                'principle_conflicts': [
                    {
                        'principle1': c.principle1,
                        'principle2': c.principle2,
                        'conflict_description': c.conflict_description,
                        'critical_facts': c.critical_facts
                    }
                    for c in question.principle_conflicts
                ],
                'critical_facts': question.critical_facts,
                'referenced_entities': question.referenced_entities,
                'precedent_pattern': question.precedent_pattern,
                'professional_context': question.professional_context,
                'mclaren_framework': True  # Mark as McLaren-enhanced
            }

            storage_entry = {
                'case_id': case_id,
                'extraction_session_id': extraction_session_id,
                'extraction_type': 'questions',
                'storage_type': 'individual',  # Questions are individual instances
                'ontology_target': f'proethica-case-{case_id}',
                'entity_label': f'Question {question.question_number}',
                'entity_type': 'EthicalQuestion',
                'entity_definition': question.question_text,
                'rdf_json_ld': rdf_data,
                'confidence': question.confidence
            }

            storage_entries.append(storage_entry)

        return storage_entries
