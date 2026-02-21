"""
Decision Focus Extractor Service

Extracts key decision points from NSPE ethics cases where ethical choices must be made.
These decision focuses become the decision points in Step 5 scenarios.

Part of Step 4 Part E implementation.

Theoretical Foundation:
    Hobbs & Moore (2005), "A Scenario-directed Computational Framework to Aid
    Decision-making and Systems Development" - Georgia Tech.
    Scenarios surface options and responsibilities BEFORE applying codes.
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
import uuid

logger = logging.getLogger(__name__)

# Ontology URIs for decision point entities
PROETHICA_INT_NS = "http://proethica.org/ontology/intermediate#"
PROETHICA_CASE_NS = "http://proethica.org/ontology/case-{case_id}#"


@dataclass
class DecisionOption:
    """An option available at a decision point."""
    option_id: str
    description: str
    is_board_choice: bool = False
    # Entity-grounded references (URIs from Pass 1-3 extraction)
    involved_action_uris: List[str] = field(default_factory=list)


@dataclass
class DecisionFocus:
    """A key decision point extracted from the case."""
    focus_id: str
    focus_number: int
    description: str
    decision_question: str
    involved_roles: List[str]
    applicable_provisions: List[str]
    options: List[DecisionOption]
    board_resolution: str
    board_reasoning: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Entity-grounded references (URIs from Pass 1-3 extraction)
    involved_role_uris: List[str] = field(default_factory=list)
    involved_obligation_uris: List[str] = field(default_factory=list)
    involved_constraint_uris: List[str] = field(default_factory=list)
    involved_action_uris: List[str] = field(default_factory=list)


class DecisionFocusExtractor:
    """
    Extracts decision focuses from ethics cases.

    Uses LLM to identify key decision points where ethical choices
    must be made, along with available options and how the Board resolved them.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the extractor.

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

    def extract_decision_focuses(
        self,
        case_id: int,
        case_text: str = None,
        entities: Dict[str, List] = None,
        questions: List[Dict] = None,
        conclusions: List[Dict] = None,
        provisions: List[Dict] = None
    ) -> List[DecisionFocus]:
        """
        Extract decision focuses from a case.

        Args:
            case_id: The case ID
            case_text: Full case text (Facts + Discussion). If not provided, loads from DB.
            entities: Dict of extracted entities by type. If not provided, loads from DB.
            questions: Extracted ethical questions. If not provided, loads from DB.
            conclusions: Board conclusions. If not provided, loads from DB.
            provisions: Code provisions cited. If not provided, loads from DB.

        Returns:
            List of DecisionFocus objects
        """
        logger.info(f"Extracting decision focuses for case {case_id}")

        # Load data if not provided
        if case_text is None:
            case_text = self._load_case_text(case_id)

        if entities is None:
            entities = self._load_entities(case_id)

        if questions is None or conclusions is None:
            questions, conclusions = self._load_qc(case_id)

        if provisions is None:
            provisions = self._load_provisions(case_id)

        # Get case title
        case_title = self._get_case_title(case_id)

        # Create extraction prompt
        prompt = self._create_extraction_prompt(
            case_title, case_text, entities, questions, conclusions, provisions
        )
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse response
            focuses = self._parse_response(response_text)

            logger.info(f"Extracted {len(focuses)} decision focuses for case {case_id}")

            return focuses

        except Exception as e:
            logger.error(f"Error extracting decision focuses: {e}")
            raise

    def _create_extraction_prompt(
        self,
        case_title: str,
        case_text: str,
        entities: Dict[str, List],
        questions: List[Dict],
        conclusions: List[Dict],
        provisions: List[Dict]
    ) -> str:
        """
        Create LLM prompt for entity-grounded decision focus extraction.

        The prompt includes extracted entities with their URIs so the LLM can
        reference specific entities when identifying decision points.
        """

        # Format entities with URIs for grounding
        roles_text = self._format_entity_list(entities.get('roles', []))
        actions_text = self._format_entity_list(entities.get('actions', []))
        obligations_text = self._format_entity_list(entities.get('obligations', []))
        constraints_text = self._format_entity_list(entities.get('constraints', []))

        # Format questions and conclusions
        questions_text = "\n".join([
            f"- Q{i+1}: {q.get('text', q.get('entity_definition', 'N/A'))}"
            for i, q in enumerate(questions)
        ]) if questions else "(none extracted)"

        conclusions_text = "\n".join([
            f"- C{i+1}: {c.get('text', c.get('entity_definition', 'N/A'))}"
            for i, c in enumerate(conclusions)
        ]) if conclusions else "(none extracted)"

        # Format provisions
        provisions_text = "\n".join([
            f"- {p.get('code_provision', p.get('provision_code', 'N/A'))}: {p.get('provision_text', '')[:100]}..."
            for p in provisions
        ]) if provisions else "(none extracted)"

        prompt = f"""Analyze this NSPE ethics case and identify the key DECISION FOCUSES -
points where an ethical choice must be made by one or more participants.

CASE: {case_title}

CASE TEXT:
{case_text[:6000]}{"..." if len(case_text) > 6000 else ""}

## EXTRACTED ENTITIES FROM PASSES 1-3

The entities below were extracted from the case in earlier analysis passes.
Each entity has a URI in brackets [URI] that you should reference in your output
to ground the decision points in the extracted entities.

### ROLES (Pass 1):
{roles_text}

### OBLIGATIONS (Pass 2):
{obligations_text}

### CONSTRAINTS (Pass 2):
{constraints_text}

### ACTIONS (Pass 3):
{actions_text}

### ETHICAL QUESTIONS POSED:
{questions_text}

### BOARD CONCLUSIONS:
{conclusions_text}

### CODE PROVISIONS CITED:
{provisions_text}

## TASK

Identify 1-4 key decision focuses. For each decision focus:
1. What choice/decision must be made?
2. Who makes the decision? Reference the specific role URIs from above.
3. What obligations/constraints apply? Reference their URIs.
4. What NSPE Code provisions apply?
5. What options are available? Link options to relevant action URIs.
6. Which option did the Board determine was correct?
7. Why did the Board choose this resolution?

## ENTITY GROUNDING REQUIREMENTS

CRITICAL: You MUST reference entity URIs to ground the decision points:
- involved_role_uris: Include URIs of roles involved in this decision
- involved_obligation_uris: Include URIs of obligations relevant to this decision
- involved_constraint_uris: Include URIs of constraints relevant to this decision
- For options: Include involved_action_uris linking to relevant actions

If an entity has no URI (empty brackets or missing), use an empty array for that field.
This grounding connects decision points to the formal case ontology.

## OUTPUT FORMAT (JSON)

```json
[
  {{
    "focus_id": "DF1",
    "focus_number": 1,
    "description": "Whether Engineer A should disclose the use of AI tools to the client",
    "decision_question": "Should Engineer A disclose to the client that AI tools were used?",
    "involved_roles": ["Engineer A", "Client W"],
    "involved_role_uris": ["http://proethica.org/ontology/case/7#Engineer_A", "http://proethica.org/ontology/case/7#Client_W"],
    "involved_obligation_uris": ["http://proethica.org/ontology/intermediate#AIDisclosureObligation"],
    "involved_constraint_uris": [],
    "applicable_provisions": ["II.1.c", "II.3.a"],
    "options": [
      {{
        "option_id": "O1",
        "description": "Disclose AI use to client",
        "is_board_choice": true,
        "involved_action_uris": []
      }},
      {{
        "option_id": "O2",
        "description": "Not disclose AI use",
        "is_board_choice": false,
        "involved_action_uris": []
      }}
    ],
    "board_resolution": "Engineer A should disclose the use of AI tools to the client",
    "board_reasoning": "Transparency with clients is required under II.1.c",
    "confidence": 0.9
  }}
]
```"""

        return prompt

    def _format_entity_list(self, entities: List, include_uris: bool = True) -> str:
        """
        Format a list of entities for the prompt.

        Args:
            entities: List of entity dicts with label, definition, uri
            include_uris: Whether to include URIs for entity grounding

        Returns:
            Formatted string with entities, URIs in brackets for LLM reference
        """
        if not entities:
            return "(none extracted)"

        formatted = []
        for entity in entities[:15]:  # Limit to 15
            if isinstance(entity, dict):
                label = entity.get('label', entity.get('entity_label', 'Unknown'))
                definition = entity.get('definition', entity.get('entity_definition', ''))
                uri = entity.get('uri', '') if include_uris else ''
            else:
                label = getattr(entity, 'entity_label', 'Unknown')
                definition = getattr(entity, 'entity_definition', '')
                uri = getattr(entity, 'entity_uri', '') if include_uris else ''

            if definition and len(definition) > 80:
                definition = definition[:80] + "..."

            # Format: "- Label [URI]: Definition" or "- Label: Definition" if no URI
            if uri:
                line = f"- {label} [{uri}]"
            else:
                line = f"- {label}"

            if definition:
                line += f": {definition}"

            formatted.append(line)

        return "\n".join(formatted)

    def _parse_response(self, response_text: str) -> List[DecisionFocus]:
        """Parse LLM response into DecisionFocus objects with entity URI references."""

        # Extract JSON from response
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            # Try to find raw JSON array
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            focuses_data = json.loads(json_text)

            focuses = []
            for f_data in focuses_data:
                # Parse options with entity grounding
                options = []
                for opt in f_data.get('options', []):
                    options.append(DecisionOption(
                        option_id=opt.get('option_id', ''),
                        description=opt.get('description', ''),
                        is_board_choice=opt.get('is_board_choice', False),
                        involved_action_uris=opt.get('involved_action_uris', [])
                    ))

                # Parse entity URI references for grounding
                involved_role_uris = f_data.get('involved_role_uris', [])
                involved_obligation_uris = f_data.get('involved_obligation_uris', [])
                involved_constraint_uris = f_data.get('involved_constraint_uris', [])
                involved_action_uris = f_data.get('involved_action_uris', [])

                focus = DecisionFocus(
                    focus_id=f_data.get('focus_id', f"DF{f_data.get('focus_number', 0)}"),
                    focus_number=f_data.get('focus_number', 0),
                    description=f_data.get('description', ''),
                    decision_question=f_data.get('decision_question', ''),
                    involved_roles=f_data.get('involved_roles', []),
                    applicable_provisions=f_data.get('applicable_provisions', []),
                    options=options,
                    board_resolution=f_data.get('board_resolution', ''),
                    board_reasoning=f_data.get('board_reasoning', ''),
                    confidence=float(f_data.get('confidence', 0.5)),
                    # Entity grounding
                    involved_role_uris=involved_role_uris,
                    involved_obligation_uris=involved_obligation_uris,
                    involved_constraint_uris=involved_constraint_uris,
                    involved_action_uris=involved_action_uris
                )
                focuses.append(focus)

                # Log with entity grounding info
                grounded_count = (
                    len(involved_role_uris) +
                    len(involved_obligation_uris) +
                    len(involved_constraint_uris) +
                    len(involved_action_uris)
                )
                logger.debug(
                    f"Decision Focus {focus.focus_id}: {focus.description[:50]}... "
                    f"({len(focus.options)} options, {len(focus.applicable_provisions)} provisions, "
                    f"{grounded_count} entity refs)"
                )

            return focuses

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse decision focuses JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
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
            extraction_session_id = f"decision_point_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            prompt = ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type='decision_point',
                prompt_text=self.last_prompt,
                raw_response=self.last_response,
                step_number=4,  # Step 4 Part E
                llm_model=llm_model or ModelConfig.get_claude_model("default"),
                section_type='synthesis',  # Use 'synthesis' as decision points are part of synthesis analysis
                extraction_session_id=extraction_session_id
            )

            logger.info(f"Saved decision point extraction provenance for case {case_id}")
            return prompt.id

        except Exception as e:
            logger.error(f"Failed to save decision point provenance for case {case_id}: {e}")
            return None

    def save_to_rdf_storage(self, case_id: int, focuses: List[DecisionFocus], llm_model: str = None) -> int:
        """
        Save decision focuses to temporary_rdf_storage as RDF entities.

        Args:
            case_id: Case ID
            focuses: List of DecisionFocus objects
            llm_model: Model used for extraction

        Returns:
            Number of entities stored
        """
        extraction_session_id = f"decision_point_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_ns = PROETHICA_CASE_NS.format(case_id=case_id)
        stored_count = 0

        try:
            # Clear existing decision point entities for this case
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_point',
                is_published=False
            ).delete()

            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_option',
                is_published=False
            ).delete()

            for focus in focuses:
                # Create Decision Point entity
                dp_uri = f"{case_ns}DecisionPoint_{focus.focus_id}"

                # Build JSON-LD representation with entity grounding
                rdf_json_ld = {
                    "@id": dp_uri,
                    "@type": [f"{PROETHICA_INT_NS}DecisionPoint"],
                    "label": focus.description,
                    "focus_id": focus.focus_id,
                    "focus_number": focus.focus_number,
                    "decision_question": focus.decision_question,
                    "involved_roles": focus.involved_roles,
                    "applicable_provisions": focus.applicable_provisions,
                    "board_resolution": focus.board_resolution,
                    "board_reasoning": focus.board_reasoning,
                    "confidence": focus.confidence,
                    # Entity grounding URIs from Pass 1-3 extraction
                    "involved_role_uris": focus.involved_role_uris,
                    "involved_obligation_uris": focus.involved_obligation_uris,
                    "involved_constraint_uris": focus.involved_constraint_uris,
                    "involved_action_uris": focus.involved_action_uris,
                    "properties": {
                        "rdfs:label": focus.description,
                        "proeth:decisionQuestion": focus.decision_question,
                        "proeth:boardResolution": focus.board_resolution,
                        "proeth:boardReasoning": focus.board_reasoning
                    },
                    "relationships": []
                }

                # Add role relationships (by label for backward compat)
                for role in focus.involved_roles:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:involvesRole",
                        "target_label": role
                    })

                # Add entity-grounded role relationships (by URI)
                for role_uri in focus.involved_role_uris:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:involvesRole",
                        "target_uri": role_uri
                    })

                # Add entity-grounded obligation relationships
                for obligation_uri in focus.involved_obligation_uris:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:involvesObligation",
                        "target_uri": obligation_uri
                    })

                # Add entity-grounded constraint relationships
                for constraint_uri in focus.involved_constraint_uris:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:involvesConstraint",
                        "target_uri": constraint_uri
                    })

                # Add entity-grounded action relationships
                for action_uri in focus.involved_action_uris:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:involvesAction",
                        "target_uri": action_uri
                    })

                # Add provision relationships
                for provision in focus.applicable_provisions:
                    rdf_json_ld["relationships"].append({
                        "type": "proeth:appliesProvision",
                        "target_label": provision
                    })

                # Store Decision Point entity
                dp_entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=extraction_session_id,
                    extraction_type='decision_point',
                    storage_type='individual',
                    ontology_target=f'proethica-case-{case_id}',
                    entity_label=focus.description,
                    entity_uri=dp_uri,
                    entity_type='DecisionPoint',
                    entity_definition=focus.decision_question,
                    rdf_json_ld=rdf_json_ld,
                    extraction_model=llm_model or ModelConfig.get_claude_model("default"),
                    triple_count=len(rdf_json_ld["properties"]) + len(rdf_json_ld["relationships"]) + 2,
                    property_count=len(rdf_json_ld["properties"]),
                    relationship_count=len(rdf_json_ld["relationships"]),
                    provenance_metadata={
                        'extraction_step': 'step4_part_e',
                        'focus_id': focus.focus_id,
                        'confidence': focus.confidence
                    },
                    is_selected=True,
                    # Pre-link to ontology class for AutoCommitService
                    matched_ontology_uri=f"{PROETHICA_INT_NS}DecisionPoint",
                    matched_ontology_label="Decision Point",
                    match_confidence=1.0,
                    match_method='exact_class'
                )
                db.session.add(dp_entity)
                stored_count += 1

                # Store Decision Options as separate entities
                for opt in focus.options:
                    opt_uri = f"{case_ns}DecisionOption_{focus.focus_id}_{opt.option_id}"

                    # Build relationships list starting with parent link
                    opt_relationships = [{
                        "type": "proeth:optionOf",
                        "target_uri": dp_uri,
                        "target_label": focus.description
                    }]

                    # Add entity-grounded action relationships for this option
                    for action_uri in opt.involved_action_uris:
                        opt_relationships.append({
                            "type": "proeth:involvesAction",
                            "target_uri": action_uri
                        })

                    opt_json_ld = {
                        "@id": opt_uri,
                        "@type": [f"{PROETHICA_INT_NS}DecisionOption"],
                        "label": opt.description,
                        "option_id": opt.option_id,
                        "is_board_choice": opt.is_board_choice,
                        "parent_decision_point": dp_uri,
                        # Entity grounding URIs
                        "involved_action_uris": opt.involved_action_uris,
                        "properties": {
                            "rdfs:label": opt.description,
                            "proeth:isBoardChoice": opt.is_board_choice
                        },
                        "relationships": opt_relationships
                    }

                    opt_entity = TemporaryRDFStorage(
                        case_id=case_id,
                        extraction_session_id=extraction_session_id,
                        extraction_type='decision_option',
                        storage_type='individual',
                        ontology_target=f'proethica-case-{case_id}',
                        entity_label=opt.description,
                        entity_uri=opt_uri,
                        entity_type='DecisionOption',
                        entity_definition=f"Option for: {focus.description}",
                        rdf_json_ld=opt_json_ld,
                        extraction_model=llm_model or ModelConfig.get_claude_model("default"),
                        triple_count=3 + len(opt.involved_action_uris),
                        property_count=2,
                        relationship_count=1 + len(opt.involved_action_uris),
                        provenance_metadata={
                            'extraction_step': 'step4_part_e',
                            'parent_focus_id': focus.focus_id,
                            'is_board_choice': opt.is_board_choice,
                            'action_uri_count': len(opt.involved_action_uris)
                        },
                        is_selected=True,
                        # Pre-link to ontology class for AutoCommitService
                        matched_ontology_uri=f"{PROETHICA_INT_NS}DecisionOption",
                        matched_ontology_label="Decision Option",
                        match_confidence=1.0,
                        match_method='exact_class'
                    )
                    db.session.add(opt_entity)
                    stored_count += 1

            db.session.commit()
            logger.info(f"Stored {stored_count} decision point entities for case {case_id}")
            return stored_count

        except Exception as e:
            logger.error(f"Failed to store decision point entities for case {case_id}: {e}")
            db.session.rollback()
            return 0

    def save_to_database(self, case_id: int, focuses: List[DecisionFocus], llm_model: str = None) -> bool:
        """
        Save decision focuses to database using RDF storage pattern.

        Stores:
        1. Provenance (prompt/response) in extraction_prompts
        2. Entities in temporary_rdf_storage for OntServe commit

        Args:
            case_id: Case ID
            focuses: List of DecisionFocus objects
            llm_model: Model used for extraction

        Returns:
            True if saved successfully
        """
        try:
            # Save provenance (LLM prompt/response)
            self.save_provenance(case_id, llm_model)

            # Save to RDF storage for OntServe commit
            stored_count = self.save_to_rdf_storage(case_id, focuses, llm_model)

            logger.info(f"Saved {len(focuses)} decision points ({stored_count} RDF entities) for case {case_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save decision focuses for case {case_id}: {e}")
            db.session.rollback()
            return False

    def load_from_rdf_storage(self, case_id: int) -> List[DecisionFocus]:
        """
        Load decision focuses from temporary_rdf_storage with entity grounding.

        Args:
            case_id: Case ID

        Returns:
            List of DecisionFocus objects with entity URI references
        """
        try:
            # Load decision points
            dp_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_point'
            ).order_by(TemporaryRDFStorage.id).all()

            # Load all options for this case
            opt_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='decision_option'
            ).all()

            # Group options by parent decision point, including entity grounding
            options_by_dp = {}
            for opt in opt_entities:
                json_ld = opt.rdf_json_ld or {}
                parent_uri = json_ld.get('parent_decision_point', '')
                if parent_uri not in options_by_dp:
                    options_by_dp[parent_uri] = []
                options_by_dp[parent_uri].append(DecisionOption(
                    option_id=json_ld.get('option_id', ''),
                    description=opt.entity_label,
                    is_board_choice=json_ld.get('is_board_choice', False),
                    # Entity grounding
                    involved_action_uris=json_ld.get('involved_action_uris', [])
                ))

            focuses = []
            for entity in dp_entities:
                json_ld = entity.rdf_json_ld or {}

                # Get options for this decision point
                dp_uri = entity.entity_uri or ''
                options = options_by_dp.get(dp_uri, [])

                focus = DecisionFocus(
                    focus_id=json_ld.get('focus_id', ''),
                    focus_number=json_ld.get('focus_number', 0),
                    description=entity.entity_label,
                    decision_question=json_ld.get('decision_question', entity.entity_definition or ''),
                    involved_roles=json_ld.get('involved_roles', []),
                    applicable_provisions=json_ld.get('applicable_provisions', []),
                    options=options,
                    board_resolution=json_ld.get('board_resolution', ''),
                    board_reasoning=json_ld.get('board_reasoning', ''),
                    confidence=json_ld.get('confidence', 0.0),
                    # Entity grounding
                    involved_role_uris=json_ld.get('involved_role_uris', []),
                    involved_obligation_uris=json_ld.get('involved_obligation_uris', []),
                    involved_constraint_uris=json_ld.get('involved_constraint_uris', []),
                    involved_action_uris=json_ld.get('involved_action_uris', [])
                )
                focuses.append(focus)

            return focuses

        except Exception as e:
            logger.error(f"Failed to load decision focuses from RDF storage for case {case_id}: {e}")
            return []

    def load_from_database(self, case_id: int) -> List[DecisionFocus]:
        """
        Load decision focuses from database (uses RDF storage).

        Args:
            case_id: Case ID

        Returns:
            List of DecisionFocus objects
        """
        return self.load_from_rdf_storage(case_id)

    def _load_case_text(self, case_id: int) -> str:
        """Load case text (Facts + Discussion) from database."""
        from app.models import DocumentSection

        sections = DocumentSection.query.filter_by(document_id=case_id).filter(
            DocumentSection.section_type.in_(['facts', 'discussion'])
        ).order_by(DocumentSection.position).all()

        text_parts = []
        for section in sections:
            if section.content:
                text_parts.append(f"[{section.section_type.upper()}]\n{section.content}")

        return "\n\n".join(text_parts)

    def _load_entities(self, case_id: int) -> Dict[str, List]:
        """
        Load all entity types from database with URIs for entity grounding.

        Returns dict with entity lists. Each entity has:
        - label: Human-readable name
        - definition: Description of the entity
        - uri: Ontology URI for entity grounding (may be None for some entities)
        """
        # Map from our key names to extraction_type values in the database
        # Note: extraction_type is capitalized in the database (e.g., 'roles', 'Roles')
        extraction_type_map = {
            'roles': 'roles',
            'states': 'states',
            'resources': 'resources',
            'principles': 'principles',
            'obligations': 'obligations',
            'constraints': 'constraints',
            'capabilities': 'capabilities',
            'actions': 'temporal_dynamics_enhanced',  # Actions are stored under temporal_dynamics_enhanced
            'events': 'temporal_dynamics_enhanced'    # Events too
        }

        # Entity type filters for temporal_dynamics_enhanced (which contains multiple types)
        entity_type_filter = {
            'actions': 'actions',
            'events': 'events'
        }

        entities = {}
        for key, extraction_type in extraction_type_map.items():
            query = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type
            )

            # Add entity_type filter for temporal_dynamics_enhanced
            if key in entity_type_filter:
                query = query.filter_by(entity_type=entity_type_filter[key])

            records = query.all()

            entities[key] = [
                {
                    'label': r.entity_label,
                    'definition': r.entity_definition or '',
                    'uri': r.entity_uri or ''
                }
                for r in records
            ]

        return entities

    def _load_qc(self, case_id: int) -> tuple:
        """Load questions and conclusions from database."""
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()

        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        return (
            [{'text': q.entity_definition} for q in questions],
            [{'text': c.entity_definition} for c in conclusions]
        )

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
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response
        }
