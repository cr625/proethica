"""
Argument Generator Service

Generates pro/con arguments for each decision point extracted in Step 4 Part E.
These arguments become the evaluative rationale in Step 5 scenarios.

Part of Step 4 Part F implementation.

Theoretical Foundation:
    IAAI Paper: "Pros and Cons in Ethical Decisions" - Evaluative AI approach
    with decision focus extraction and argument generation.
"""

import json
import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document, TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from models import ModelConfig

logger = logging.getLogger(__name__)

# Ontology URIs
PROETHICA_INT_NS = "http://proethica.org/ontology/intermediate#"
PROETHICA_CASE_NS = "http://proethica.org/ontology/case-{case_id}#"


@dataclass
class ArgumentPremise:
    """A premise supporting an argument."""
    premise_id: str
    text: str
    provision_reference: Optional[str] = None
    precedent_case: Optional[str] = None


@dataclass
class EthicalArgument:
    """An argument for or against a decision option."""
    argument_id: str
    option_id: str  # Links to DecisionOption
    decision_point_id: str  # Links to parent DecisionPoint
    argument_type: str  # 'pro' or 'con'
    claim: str  # Main argument claim
    premises: List[ArgumentPremise] = field(default_factory=list)
    provision_citations: List[str] = field(default_factory=list)  # e.g., ["II.1.c", "III.8.a"]
    precedent_references: List[str] = field(default_factory=list)  # e.g., ["Case 99-6", "Case 2010-1"]
    strength: str = "moderate"  # weak, moderate, strong
    confidence: float = 0.0


@dataclass
class DecisionPointArguments:
    """All arguments for a single decision point."""
    decision_point_id: str
    decision_description: str
    option_id: str
    option_description: str
    pro_arguments: List[EthicalArgument]
    con_arguments: List[EthicalArgument]
    evaluation_summary: str = ""


class ArgumentGenerator:
    """
    Generates pro/con arguments for decision points.

    For each decision option, generates balanced arguments citing:
    - NSPE Code provisions
    - Precedent cases
    - Principle tensions
    - Public welfare implications
    """

    def __init__(self, llm_client=None):
        """
        Initialize the generator.

        Args:
            llm_client: Optional Anthropic client. If not provided, will create one.
        """
        self._llm_client = llm_client
        self.last_prompt = None
        self.last_response = None

    @property
    def llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def generate_arguments(
        self,
        case_id: int,
        decision_points: List[Dict] = None
    ) -> List[DecisionPointArguments]:
        """
        Generate arguments for all decision points in a case.

        Args:
            case_id: The case ID
            decision_points: List of decision points (optional, loads from DB if not provided)

        Returns:
            List of DecisionPointArguments objects
        """
        logger.info(f"Generating arguments for case {case_id}")

        # Load decision points if not provided
        if decision_points is None:
            decision_points = self._load_decision_points(case_id)

        if not decision_points:
            logger.warning(f"No decision points found for case {case_id}")
            return []

        # Get case context
        case_title = self._get_case_title(case_id)
        provisions = self._load_provisions(case_id)

        # Generate arguments for each decision point
        all_arguments = []
        all_prompts = []
        all_responses = []

        for dp in decision_points:
            dp_args = self._generate_arguments_for_point(
                case_id, case_title, dp, provisions
            )
            if dp_args:
                all_arguments.extend(dp_args)
                all_prompts.append(self.last_prompt)
                all_responses.append(self.last_response)

        # Store combined prompts/responses for provenance
        self.last_prompt = "\n\n---\n\n".join(all_prompts)
        self.last_response = "\n\n---\n\n".join(all_responses)

        logger.info(f"Generated arguments for {len(all_arguments)} decision point options")
        return all_arguments

    def _generate_arguments_for_point(
        self,
        case_id: int,
        case_title: str,
        decision_point: Dict,
        provisions: List[Dict]
    ) -> List[DecisionPointArguments]:
        """Generate arguments for a single decision point."""

        dp_id = decision_point.get('focus_id', decision_point.get('point_id', ''))
        dp_description = decision_point.get('description', '')
        options = decision_point.get('options', [])
        applicable_provisions = decision_point.get('applicable_provisions', [])
        board_resolution = decision_point.get('board_resolution', '')
        board_reasoning = decision_point.get('board_reasoning', '')

        # Format provisions context
        provisions_text = self._format_provisions(provisions, applicable_provisions)

        # Create prompt for all options at once
        prompt = self._create_argument_prompt(
            case_title,
            dp_description,
            decision_point.get('decision_question', ''),
            options,
            applicable_provisions,
            provisions_text,
            board_resolution,
            board_reasoning
        )
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse response
            arguments_list = self._parse_response(response_text, dp_id, dp_description)
            return arguments_list

        except Exception as e:
            logger.error(f"Error generating arguments for decision point {dp_id}: {e}")
            return []

    def _create_argument_prompt(
        self,
        case_title: str,
        dp_description: str,
        decision_question: str,
        options: List[Dict],
        applicable_provisions: List[str],
        provisions_text: str,
        board_resolution: str,
        board_reasoning: str
    ) -> str:
        """Create LLM prompt for argument generation."""

        options_text = "\n".join([
            f"- Option {opt.get('option_id', 'O?')}: {opt.get('description', '')}"
            + (" [BOARD'S CHOICE]" if opt.get('is_board_choice') else "")
            for opt in options
        ])

        provisions_list = ", ".join(applicable_provisions) if applicable_provisions else "None specified"

        prompt = f"""Analyze this ethics case decision point and generate BALANCED pro/con arguments for each option.

CASE: {case_title}

DECISION POINT: {dp_description}

DECISION QUESTION: {decision_question}

AVAILABLE OPTIONS:
{options_text}

APPLICABLE NSPE CODE PROVISIONS: {provisions_list}

PROVISION DETAILS:
{provisions_text}

BOARD'S RESOLUTION: {board_resolution}

BOARD'S REASONING: {board_reasoning}

TASK:
For EACH option, generate:
1. PRO ARGUMENTS (reasons supporting this option)
2. CON ARGUMENTS (reasons against this option)

For each argument:
- State a clear claim
- Cite relevant NSPE Code provisions (e.g., "II.1.c", "III.8.a")
- Reference similar NSPE precedent cases if applicable (e.g., "Similar to Case 99-6")
- Assess argument strength (weak/moderate/strong)

IMPORTANT:
- Generate BALANCED arguments even for options the Board rejected
- Focus on professional ethics principles, not just outcomes
- Cite specific provision numbers
- Be concise but substantive

OUTPUT FORMAT (JSON):
```json
{{
  "option_arguments": [
    {{
      "option_id": "O1",
      "option_description": "Description of option",
      "pro_arguments": [
        {{
          "argument_id": "A1",
          "claim": "Clear statement of why this option is good",
          "premises": [
            {{"premise_id": "P1", "text": "Supporting reason", "provision_reference": "II.1.c"}}
          ],
          "provision_citations": ["II.1.c", "II.3.a"],
          "precedent_references": [],
          "strength": "moderate"
        }}
      ],
      "con_arguments": [
        {{
          "argument_id": "A2",
          "claim": "Clear statement of why this option is problematic",
          "premises": [
            {{"premise_id": "P1", "text": "Counterargument reason", "provision_reference": "I.1"}}
          ],
          "provision_citations": ["I.1"],
          "precedent_references": [],
          "strength": "strong"
        }}
      ],
      "evaluation_summary": "Brief summary of the ethical trade-offs for this option"
    }}
  ]
}}
```"""

        return prompt

    def _format_provisions(
        self,
        all_provisions: List[Dict],
        applicable_codes: List[str]
    ) -> str:
        """Format provisions for prompt context."""
        if not all_provisions:
            return "(No provisions extracted)"

        # Filter to applicable provisions if specified
        if applicable_codes:
            filtered = [
                p for p in all_provisions
                if any(code in p.get('code_provision', '') for code in applicable_codes)
            ]
            if filtered:
                all_provisions = filtered

        return "\n".join([
            f"- {p.get('code_provision', 'N/A')}: {p.get('provision_text', '')[:200]}..."
            for p in all_provisions[:10]
        ])

    def _parse_response(
        self,
        response_text: str,
        dp_id: str,
        dp_description: str
    ) -> List[DecisionPointArguments]:
        """Parse LLM response into DecisionPointArguments objects."""

        # Extract JSON from response
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*"option_arguments"[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("Could not find JSON in response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            data = json.loads(json_text)

            results = []
            for opt_data in data.get('option_arguments', []):
                # Parse pro arguments
                pro_args = []
                for arg in opt_data.get('pro_arguments', []):
                    premises = [
                        ArgumentPremise(
                            premise_id=p.get('premise_id', ''),
                            text=p.get('text', ''),
                            provision_reference=p.get('provision_reference')
                        )
                        for p in arg.get('premises', [])
                    ]
                    pro_args.append(EthicalArgument(
                        argument_id=arg.get('argument_id', ''),
                        option_id=opt_data.get('option_id', ''),
                        decision_point_id=dp_id,
                        argument_type='pro',
                        claim=arg.get('claim', ''),
                        premises=premises,
                        provision_citations=arg.get('provision_citations', []),
                        precedent_references=arg.get('precedent_references', []),
                        strength=arg.get('strength', 'moderate'),
                        confidence=0.8
                    ))

                # Parse con arguments
                con_args = []
                for arg in opt_data.get('con_arguments', []):
                    premises = [
                        ArgumentPremise(
                            premise_id=p.get('premise_id', ''),
                            text=p.get('text', ''),
                            provision_reference=p.get('provision_reference')
                        )
                        for p in arg.get('premises', [])
                    ]
                    con_args.append(EthicalArgument(
                        argument_id=arg.get('argument_id', ''),
                        option_id=opt_data.get('option_id', ''),
                        decision_point_id=dp_id,
                        argument_type='con',
                        claim=arg.get('claim', ''),
                        premises=premises,
                        provision_citations=arg.get('provision_citations', []),
                        precedent_references=arg.get('precedent_references', []),
                        strength=arg.get('strength', 'moderate'),
                        confidence=0.8
                    ))

                results.append(DecisionPointArguments(
                    decision_point_id=dp_id,
                    decision_description=dp_description,
                    option_id=opt_data.get('option_id', ''),
                    option_description=opt_data.get('option_description', ''),
                    pro_arguments=pro_args,
                    con_arguments=con_args,
                    evaluation_summary=opt_data.get('evaluation_summary', '')
                ))

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse arguments JSON: {e}")
            return []

    def save_provenance(self, case_id: int, llm_model: str = None) -> Optional[int]:
        """
        Save LLM prompt and response to extraction_prompts for provenance.

        Args:
            case_id: Case ID
            llm_model: Model used for extraction

        Returns:
            ExtractionPrompt ID if saved successfully
        """
        if not self.last_prompt or not self.last_response:
            logger.warning("No prompt/response to save for provenance")
            return None

        try:
            extraction_session_id = f"decision_argument_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            prompt = ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type='decision_argument',
                prompt_text=self.last_prompt,
                raw_response=self.last_response,
                step_number=4,  # Step 4 Part F
                llm_model=llm_model or ModelConfig.get_claude_model("default"),
                section_type='synthesis',
                extraction_session_id=extraction_session_id
            )

            logger.info(f"Saved argument generation provenance for case {case_id}")
            return prompt.id

        except Exception as e:
            logger.error(f"Failed to save argument provenance for case {case_id}: {e}")
            return None

    def save_to_rdf_storage(
        self,
        case_id: int,
        arguments: List[DecisionPointArguments],
        llm_model: str = None
    ) -> int:
        """
        Save arguments to temporary_rdf_storage as RDF entities.

        Args:
            case_id: Case ID
            arguments: List of DecisionPointArguments objects
            llm_model: Model used for extraction

        Returns:
            Number of entities stored
        """
        extraction_session_id = f"decision_argument_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_ns = PROETHICA_CASE_NS.format(case_id=case_id)
        stored_count = 0

        try:
            # Clear existing argument entities for this case
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_argument',
                is_published=False
            ).delete()

            for dp_args in arguments:
                # Store each argument as an entity
                all_args = dp_args.pro_arguments + dp_args.con_arguments

                for arg in all_args:
                    arg_uri = f"{case_ns}EthicalArgument_{dp_args.decision_point_id}_{arg.option_id}_{arg.argument_id}"

                    # Build JSON-LD representation
                    rdf_json_ld = {
                        "@id": arg_uri,
                        "@type": [f"{PROETHICA_INT_NS}EthicalArgument"],
                        "label": arg.claim[:100] + ("..." if len(arg.claim) > 100 else ""),
                        "argument_id": arg.argument_id,
                        "option_id": arg.option_id,
                        "decision_point_id": arg.decision_point_id,
                        "argument_type": arg.argument_type,
                        "claim": arg.claim,
                        "provision_citations": arg.provision_citations,
                        "precedent_references": arg.precedent_references,
                        "strength": arg.strength,
                        "evaluation_summary": dp_args.evaluation_summary,
                        "premises": [
                            {
                                "premise_id": p.premise_id,
                                "text": p.text,
                                "provision_reference": p.provision_reference
                            }
                            for p in arg.premises
                        ],
                        "properties": {
                            "rdfs:label": arg.claim[:100],
                            "proeth:argumentType": arg.argument_type,
                            "proeth:argumentStrength": arg.strength
                        },
                        "relationships": [
                            {
                                "type": "proeth:argumentFor" if arg.argument_type == 'pro' else "proeth:argumentAgainst",
                                "target_label": dp_args.option_description
                            }
                        ]
                    }

                    # Add provision relationships
                    for provision in arg.provision_citations:
                        rdf_json_ld["relationships"].append({
                            "type": "proeth:citesProvision",
                            "target_label": provision
                        })

                    arg_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=extraction_session_id,
                        extraction_type='decision_argument',
                        storage_type='individual',
                        ontology_target=f'proethica-case-{case_id}',
                        entity_label=arg.claim[:200],
                        entity_uri=arg_uri,
                        entity_type='EthicalArgument',
                        entity_definition=f"{arg.argument_type.upper()} argument for option: {dp_args.option_description}",
                        rdf_json_ld=rdf_json_ld,
                        extraction_model=llm_model or ModelConfig.get_claude_model("default"),
                        triple_count=len(rdf_json_ld["properties"]) + len(rdf_json_ld["relationships"]) + 2,
                        property_count=len(rdf_json_ld["properties"]),
                        relationship_count=len(rdf_json_ld["relationships"]),
                        provenance_metadata={
                            'extraction_step': 'step4_part_f',
                            'argument_type': arg.argument_type,
                            'strength': arg.strength,
                            'decision_point_id': arg.decision_point_id,
                            'option_id': arg.option_id
                        },
                        is_selected=True,
                        matched_ontology_uri=f"{PROETHICA_INT_NS}EthicalArgument",
                        matched_ontology_label="Ethical Argument",
                        match_confidence=1.0,
                        match_method='exact_class'
                    )
                    db.session.add(arg_entity)
                    stored_count += 1

            db.session.commit()
            logger.info(f"Stored {stored_count} argument entities for case {case_id}")
            return stored_count

        except Exception as e:
            logger.error(f"Failed to store argument entities for case {case_id}: {e}")
            db.session.rollback()
            return 0

    def save_to_database(
        self,
        case_id: int,
        arguments: List[DecisionPointArguments],
        llm_model: str = None
    ) -> bool:
        """
        Save arguments to database using RDF storage pattern.

        Stores:
        1. Provenance (prompt/response) in extraction_prompts
        2. Entities in temporary_rdf_storage for OntServe commit

        Args:
            case_id: Case ID
            arguments: List of DecisionPointArguments objects
            llm_model: Model used for extraction

        Returns:
            True if saved successfully
        """
        try:
            # Save provenance (LLM prompt/response)
            self.save_provenance(case_id, llm_model)

            # Save to RDF storage for OntServe commit
            stored_count = self.save_to_rdf_storage(case_id, arguments, llm_model)

            logger.info(f"Saved arguments ({stored_count} RDF entities) for case {case_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save arguments for case {case_id}: {e}")
            db.session.rollback()
            return False

    def load_from_rdf_storage(self, case_id: int) -> List[DecisionPointArguments]:
        """
        Load arguments from temporary_rdf_storage.

        Args:
            case_id: Case ID

        Returns:
            List of DecisionPointArguments objects
        """
        try:
            arg_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_argument'
            ).order_by(TemporaryRDFStorage.id).all()

            # Group arguments by decision point and option
            grouped = {}
            for entity in arg_entities:
                json_ld = entity.rdf_json_ld or {}
                dp_id = json_ld.get('decision_point_id', '')
                opt_id = json_ld.get('option_id', '')
                key = (dp_id, opt_id)

                if key not in grouped:
                    grouped[key] = {
                        'dp_id': dp_id,
                        'opt_id': opt_id,
                        'opt_description': '',
                        'evaluation_summary': json_ld.get('evaluation_summary', ''),
                        'pro': [],
                        'con': []
                    }

                # Parse premises
                premises = [
                    ArgumentPremise(
                        premise_id=p.get('premise_id', ''),
                        text=p.get('text', ''),
                        provision_reference=p.get('provision_reference')
                    )
                    for p in json_ld.get('premises', [])
                ]

                arg = EthicalArgument(
                    argument_id=json_ld.get('argument_id', ''),
                    option_id=opt_id,
                    decision_point_id=dp_id,
                    argument_type=json_ld.get('argument_type', 'pro'),
                    claim=json_ld.get('claim', entity.entity_label),
                    premises=premises,
                    provision_citations=json_ld.get('provision_citations', []),
                    precedent_references=json_ld.get('precedent_references', []),
                    strength=json_ld.get('strength', 'moderate'),
                    confidence=0.8
                )

                if arg.argument_type == 'pro':
                    grouped[key]['pro'].append(arg)
                else:
                    grouped[key]['con'].append(arg)

            # Convert to DecisionPointArguments
            results = []
            for key, data in grouped.items():
                results.append(DecisionPointArguments(
                    decision_point_id=data['dp_id'],
                    decision_description='',  # Would need to load from decision points
                    option_id=data['opt_id'],
                    option_description=data['opt_description'],
                    pro_arguments=data['pro'],
                    con_arguments=data['con'],
                    evaluation_summary=data['evaluation_summary']
                ))

            return results

        except Exception as e:
            logger.error(f"Failed to load arguments from RDF storage for case {case_id}: {e}")
            return []

    def load_from_database(self, case_id: int) -> List[DecisionPointArguments]:
        """
        Load arguments from database (uses RDF storage).

        Args:
            case_id: Case ID

        Returns:
            List of DecisionPointArguments objects
        """
        return self.load_from_rdf_storage(case_id)

    def _load_decision_points(self, case_id: int) -> List[Dict]:
        """Load decision points from database."""
        from app.services.decision_focus_extractor import DecisionFocusExtractor

        extractor = DecisionFocusExtractor()
        focuses = extractor.load_from_database(case_id)

        return [
            {
                'focus_id': f.focus_id,
                'focus_number': f.focus_number,
                'description': f.description,
                'decision_question': f.decision_question,
                'involved_roles': f.involved_roles,
                'applicable_provisions': f.applicable_provisions,
                'options': [
                    {
                        'option_id': opt.option_id,
                        'description': opt.description,
                        'is_board_choice': opt.is_board_choice
                    }
                    for opt in f.options
                ],
                'board_resolution': f.board_resolution,
                'board_reasoning': f.board_reasoning
            }
            for f in focuses
        ]

    def _load_provisions(self, case_id: int) -> List[Dict]:
        """Load code provisions from database."""
        provisions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()

        return [
            {
                'code_provision': p.entity_label,
                'provision_text': p.entity_definition
            }
            for p in provisions
        ]

    def _get_case_title(self, case_id: int) -> str:
        """Get case title from database."""
        case = Document.query.get(case_id)
        return case.title if case else f"Case {case_id}"

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging/provenance display."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response
        }
