"""
Entity Matching Service

Matches entities mentioned in one section (e.g., Questions) to entities
already extracted from previous sections (Facts, Discussion).

This implements cross-section entity linking for McLaren's framework,
showing how entities from the contextual framework (Pass 1) connect to
ethical questions and conclusions.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EntityMatch:
    """
    Represents a match between mentioned text and an extracted entity.
    """
    entity_id: int  # TemporaryRDFStorage ID
    entity_label: str
    entity_type: str  # 'Role', 'State', 'Resource'
    source_section: str  # 'facts' or 'discussion'
    mention_text: str  # How it was mentioned in the new section
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this match was made
    is_committed: bool  # Whether already in OntServe


class EntityMatchingService:
    """
    Service for matching entity mentions across case sections.

    Uses LLM to identify when entities from Facts/Discussion are
    referenced in Questions/Conclusions sections.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the entity matching service.

        Args:
            llm_client: LLM client for intelligent matching
        """
        self.llm_client = llm_client
        self.last_matching_prompt = None  # Store matching prompt for UI display
        self.last_matching_response = None  # Store matching response for UI display
        self.last_extraction_prompt = None  # Store new entity extraction prompt
        self.last_extraction_response = None  # Store new entity extraction response
        logger.info("EntityMatchingService initialized")

    def match_entities_in_text(
        self,
        section_text: str,
        entity_type: str,
        case_id: int,
        previous_sections: List[str] = None,
        extract_new: bool = True
    ) -> Tuple[List[EntityMatch], List[Dict]]:
        """
        Find entities of given type mentioned in section text, and optionally extract new ones.

        Args:
            section_text: Text to search for entity mentions
            entity_type: Type to match ('roles', 'states', 'resources')
            case_id: Case identifier
            previous_sections: Which sections to search (default: ['facts', 'discussion'])
            extract_new: If True, also extract entities not found in previous sections

        Returns:
            Tuple of (matched_entities, new_entities)
            - matched_entities: List of EntityMatch objects for entities found in previous sections
            - new_entities: List of new entity dicts extracted from this section
        """
        if previous_sections is None:
            previous_sections = ['facts', 'discussion']

        logger.info(f"Matching {entity_type} entities in section for case {case_id}")
        logger.info(f"Section text length: {len(section_text)} chars")
        logger.info(f"Previous sections to search: {previous_sections}")
        logger.info(f"Extract new entities: {extract_new}")

        # Get entities from previous sections
        available_entities = self._get_available_entities(
            case_id,
            entity_type,
            previous_sections
        )

        logger.info(f"Retrieved {len(available_entities)} available entities")
        if available_entities:
            logger.info(f"Sample entities: {[e['label'] for e in available_entities[:5]]}")

        # Use LLM to match entities
        matches = []
        if available_entities:
            if self.llm_client:
                logger.info(f"Using LLM-based entity matching")
                try:
                    matches = self._llm_match_entities(
                        section_text,
                        available_entities,
                        entity_type
                    )
                    logger.info(f"LLM matching returned {len(matches)} matches")
                except Exception as e:
                    logger.error(f"LLM matching failed, falling back to string matching: {e}")
                    import traceback
                    traceback.print_exc()
                    matches = self._fallback_match_entities(
                        section_text,
                        available_entities,
                        entity_type
                    )
            else:
                # Fallback: simple string matching
                logger.info(f"No LLM client, using fallback string matching")
                matches = self._fallback_match_entities(
                    section_text,
                    available_entities,
                    entity_type
                )
        else:
            logger.warning(f"No {entity_type} entities found in previous sections")

        logger.info(f"Found {len(matches)} {entity_type} entity matches")

        # Extract new entities if requested
        new_entities = []
        if extract_new and self.llm_client:
            logger.info(f"Extracting NEW {entity_type} entities from section text")
            new_entities = self._extract_new_entities(
                section_text,
                entity_type,
                case_id,
                matched_labels=[m.entity_label for m in matches]
            )
            logger.info(f"Found {len(new_entities)} NEW {entity_type} entities")

        return matches, new_entities

    def _get_available_entities(
        self,
        case_id: int,
        entity_type: str,
        sections: List[str]
    ) -> List[Dict]:
        """
        Get entities from specified sections (temporary + committed).
        """
        from app.models import TemporaryRDFStorage, ExtractionPrompt

        logger.info(f"_get_available_entities: case_id={case_id}, entity_type={entity_type}, sections={sections}")
        entities = []

        # Get temporary entities from specified sections
        for section in sections:
            logger.info(f"Processing section: {section}")

            # For Questions and Conclusions sections, we need to match multiple concept_type patterns:
            # - entity_type (e.g., 'roles') for Facts/Discussion
            # - {entity_type}_matching (e.g., 'roles_matching') for Questions/Conclusions
            # - {entity_type}_new_extraction (e.g., 'roles_new_extraction') for Questions/Conclusions
            from sqlalchemy import or_

            if section in ['questions', 'conclusions']:
                # Use OR to match all relevant patterns
                section_prompts = ExtractionPrompt.query.filter(
                    ExtractionPrompt.case_id == case_id,
                    ExtractionPrompt.section_type == section,
                    or_(
                        ExtractionPrompt.concept_type == entity_type,
                        ExtractionPrompt.concept_type == f'{entity_type}_matching',
                        ExtractionPrompt.concept_type == f'{entity_type}_new_extraction'
                    )
                ).all()
            else:
                # For Facts/Discussion, use simple match
                section_prompts = ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    section_type=section,
                    concept_type=entity_type
                ).all()

            logger.info(f"  Found {len(section_prompts)} prompts for {section}/{entity_type}")

            session_ids = {p.extraction_session_id for p in section_prompts if p.extraction_session_id}

            logger.info(f"  Session IDs: {len(session_ids)} unique sessions")

            if session_ids:
                # For Questions/Conclusions, also need to check for different extraction_type patterns
                if section in ['questions', 'conclusions']:
                    # Build the section-specific extraction_type patterns
                    section_entity_refs = f'{section}_entity_refs'
                    section_new_entities = f'{entity_type}_new_from_{section}'

                    rdf_entities = TemporaryRDFStorage.query.filter(
                        TemporaryRDFStorage.case_id == case_id,
                        TemporaryRDFStorage.extraction_session_id.in_(session_ids),
                        or_(
                            TemporaryRDFStorage.extraction_type == entity_type,
                            TemporaryRDFStorage.extraction_type == section_new_entities,
                            TemporaryRDFStorage.extraction_type == section_entity_refs
                        )
                    ).all()

                    # For entity_refs, we need to filter by the JSON entityType field
                    # because all entity types are stored with extraction_type = 'questions_entity_refs'
                    filtered_entities = []
                    for entity in rdf_entities:
                        if entity.extraction_type == section_entity_refs:
                            # Check the entityType in JSON
                            json_entity_type = entity.rdf_json_ld.get('entityType', '').lower() if entity.rdf_json_ld else ''
                            # Match if the entityType contains the requested entity_type
                            if entity_type.rstrip('s') in json_entity_type:  # 'role' in 'roles'
                                filtered_entities.append(entity)
                        else:
                            # Not an entity_ref, so include it
                            filtered_entities.append(entity)

                    rdf_entities = filtered_entities
                else:
                    # For Facts/Discussion, use simple extraction_type match
                    rdf_entities = TemporaryRDFStorage.query.filter(
                        TemporaryRDFStorage.case_id == case_id,
                        TemporaryRDFStorage.extraction_type == entity_type,
                        TemporaryRDFStorage.extraction_session_id.in_(session_ids)
                    ).all()

                logger.info(f"  Found {len(rdf_entities)} RDF entities in {section}")

                for entity in rdf_entities:
                    entities.append({
                        'id': entity.id,
                        'label': entity.entity_label,
                        'type': entity.entity_type,
                        'definition': entity.entity_definition,
                        'storage_type': entity.storage_type,
                        'source_section': section,
                        'is_committed': entity.is_committed,
                        'rdf_data': entity.rdf_json_ld
                    })

        # Also get committed entities from OntServe via MCP
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            external_client = get_external_mcp_client()

            # Query OntServe for committed entities of this type
            if entity_type == 'roles':
                committed_entities = external_client.get_all_role_entities()
            elif entity_type == 'states':
                committed_entities = external_client.get_all_state_entities()
            elif entity_type == 'resources':
                committed_entities = external_client.get_all_resource_entities()
            else:
                committed_entities = []

            # Add committed entities to available list
            for entity in committed_entities:
                entities.append({
                    'id': None,  # No TemporaryRDFStorage ID
                    'label': entity.get('label', ''),
                    'type': entity.get('type', entity_type),
                    'definition': entity.get('definition', ''),
                    'storage_type': 'committed',
                    'source_section': 'ontserve',  # From OntServe
                    'is_committed': True,
                    'rdf_data': entity
                })

            logger.info(f"Added {len(committed_entities)} committed entities from OntServe")

        except Exception as e:
            logger.warning(f"Could not fetch committed entities from OntServe: {e}")

        logger.info(f"Retrieved {len(entities)} total available {entity_type} entities (temporary + committed)")
        return entities

    def _llm_match_entities(
        self,
        section_text: str,
        available_entities: List[Dict],
        entity_type: str
    ) -> List[EntityMatch]:
        """
        Use LLM to match entity mentions to available entities.
        """
        logger.info(f"_llm_match_entities: Creating prompt with {len(available_entities)} available entities")

        # Create prompt for LLM
        prompt = self._create_matching_prompt(
            section_text,
            available_entities,
            entity_type
        )

        # Store matching prompt for UI display
        self.last_matching_prompt = prompt

        logger.info(f"Prompt created, length: {len(prompt)} chars")

        try:
            from models import ModelConfig

            model_name = ModelConfig.get_claude_model("powerful")
            logger.info(f"Calling LLM with model: {model_name}")

            # Use Anthropic messages API
            response = self.llm_client.messages.create(
                model=model_name,
                max_tokens=4000,
                temperature=0.2,  # Lower for matching task
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract content from Anthropic response
            content = response.content[0].text if response.content else ""

            # Store matching response for UI display
            self.last_matching_response = content

            logger.info(f"LLM response received, length: {len(content)} chars")
            logger.info(f"Response content: {content[:200]}...")

            matches = self._parse_matching_response(
                content,
                available_entities
            )

            logger.info(f"Parsed {len(matches)} matches from LLM response")
            return matches

        except Exception as e:
            logger.error(f"LLM matching failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _create_matching_prompt(
        self,
        section_text: str,
        available_entities: List[Dict],
        entity_type: str
    ) -> str:
        """
        Create LLM prompt for entity matching.
        """
        entity_list = []
        for i, entity in enumerate(available_entities):
            storage_info = f" [{entity['storage_type']}]" if entity.get('storage_type') else ""
            section_info = f" (from {entity['source_section']})"
            entity_list.append(
                f"{i}. {entity['label']}{storage_info}{section_info}: {entity.get('definition', '')[:100]}"
            )

        prompt = f"""You are analyzing an NSPE engineering ethics case to identify entity references across sections.

# TASK: Entity Matching

You have these {entity_type.upper()} entities extracted from Facts and Discussion sections:

{chr(10).join(entity_list[:20])}  # Limit to 20 for prompt size

Now analyze this text from the Questions section:

{section_text}

# TASK:
Identify which of the available {entity_type} are REFERENCED or MENTIONED in the Questions text above.

Look for:
- Direct mentions: "Engineer Smith" matches entity "Engineer Smith"
- Pronouns/references: "the engineer" or "he" might refer to "Engineer Smith"
- Synonyms: "the client" might match "Client Representative"
- Implicit references: "the safety issue" might match state "Safety Risk Identified"

# OUTPUT FORMAT (JSON):

Return a JSON array of matches:

```json
[
  {{
    "entity_index": 0,
    "mention_text": "how it was mentioned in the text",
    "confidence": 0.95,
    "reasoning": "why this is a match"
  }}
]
```

Return ONLY matches with confidence >= 0.6. Return empty array [] if no clear matches.

Return ONLY valid JSON array.
"""
        return prompt

    def _parse_matching_response(
        self,
        response: str,
        available_entities: List[Dict]
    ) -> List[EntityMatch]:
        """
        Parse LLM response into EntityMatch objects.
        """
        matches = []

        try:
            import json

            # Extract JSON from response
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()

            data = json.loads(json_str)

            for match_data in data:
                idx = match_data['entity_index']
                if 0 <= idx < len(available_entities):
                    entity = available_entities[idx]

                    match = EntityMatch(
                        entity_id=entity['id'],
                        entity_label=entity['label'],
                        entity_type=entity['type'],
                        source_section=entity['source_section'],
                        mention_text=match_data['mention_text'],
                        confidence=match_data['confidence'],
                        reasoning=match_data['reasoning'],
                        is_committed=entity.get('is_committed', False)
                    )
                    matches.append(match)

            logger.info(f"Parsed {len(matches)} entity matches from LLM response")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response was: {response[:500]}")
        except Exception as e:
            logger.error(f"Error parsing matching response: {e}")

        return matches

    def _fallback_match_entities(
        self,
        section_text: str,
        available_entities: List[Dict],
        entity_type: str
    ) -> List[EntityMatch]:
        """
        Fallback: simple string matching when LLM unavailable.
        """
        matches = []
        section_lower = section_text.lower()

        for entity in available_entities:
            label = entity['label']
            if label.lower() in section_lower:
                match = EntityMatch(
                    entity_id=entity['id'],
                    entity_label=label,
                    entity_type=entity['type'],
                    source_section=entity['source_section'],
                    mention_text=label,
                    confidence=0.7,  # Lower confidence for string matching
                    reasoning=f"Direct string match found in text",
                    is_committed=entity.get('is_committed', False)
                )
                matches.append(match)

        return matches

    def _get_entity_full_data(
        self,
        entity_id: int,
        case_id: int
    ) -> Dict:
        """
        Get full RDF data for an entity, combining individual + class information.

        For role individuals, this includes:
        - The individual's properties
        - The role class they instantiate
        - Related individuals/relationships
        """
        if not entity_id:
            return {}

        try:
            from app.models import TemporaryRDFStorage

            entity = TemporaryRDFStorage.query.get(entity_id)
            if not entity:
                return {}

            # Get the base RDF data
            full_data = entity.rdf_json_ld.copy() if entity.rdf_json_ld else {}

            # If this is an individual, also include its class information
            if entity.storage_type == 'individual' and full_data.get('types'):
                # Get the role class this individual instantiates
                role_class_uri = full_data.get('types', [])[0] if full_data.get('types') else None

                if role_class_uri:
                    # Find the class entity
                    class_label = role_class_uri.split('#')[-1].replace('_', ' ')
                    class_entity = TemporaryRDFStorage.query.filter_by(
                        case_id=case_id,
                        entity_label=class_label,
                        storage_type='class'
                    ).first()

                    if class_entity:
                        full_data['roleClassData'] = class_entity.rdf_json_ld

            return full_data

        except Exception as e:
            logger.error(f"Error getting full entity data: {e}")
            return {}

    def store_entity_matches(
        self,
        matches: List[EntityMatch],
        case_id: int,
        target_section: str,
        extraction_session_id: str
    ) -> List[Dict]:
        """
        Store entity matches as relationship records.

        Returns list of storage entries for TemporaryRDFStorage.
        """
        storage_entries = []

        for match in matches:
            # Get full entity data for richer structure
            entity_rdf_data = self._get_entity_full_data(match.entity_id, case_id)

            # Create relationship record with rich entity information
            rdf_data = {
                '@type': 'proeth-case:EntityReference',
                'referencesEntity': match.entity_id,
                'entityLabel': match.entity_label,
                'entityType': match.entity_type,
                'sourceSection': match.source_section,
                'targetSection': target_section,
                'mentionText': match.mention_text,
                'confidence': match.confidence,
                'reasoning': match.reasoning,
                'isCommitted': match.is_committed,
                # Include full entity data (individual + class info)
                'entityData': entity_rdf_data
            }

            storage_entry = {
                'case_id': case_id,
                'extraction_session_id': extraction_session_id,
                'extraction_type': f'{target_section}_entity_refs',
                'storage_type': 'relationship',
                'ontology_target': f'proethica-case-{case_id}',
                'entity_label': f'{match.entity_label} (referenced)',
                'entity_type': 'EntityReference',
                'entity_definition': f'Reference to {match.entity_label} from {match.source_section}',
                'rdf_json_ld': rdf_data,
                'confidence': match.confidence
            }

            storage_entries.append(storage_entry)

        return storage_entries

    def _extract_new_entities(
        self,
        section_text: str,
        entity_type: str,
        case_id: int,
        matched_labels: List[str]
    ) -> List[Dict]:
        """
        Extract NEW entities from section text that weren't matched to existing ones.

        Args:
            section_text: Text to extract from
            entity_type: Type of entities ('roles', 'states', 'resources')
            case_id: Case identifier
            matched_labels: Labels of entities already matched (to exclude)

        Returns:
            List of new entity dicts with label, definition, confidence
        """
        logger.info(f"Extracting new {entity_type} not in matched list: {matched_labels}")

        # Create extraction prompt
        prompt = self._create_new_entity_extraction_prompt(
            section_text,
            entity_type,
            matched_labels
        )

        # Store extraction prompt for UI display
        self.last_extraction_prompt = prompt

        try:
            from models import ModelConfig

            model_name = ModelConfig.get_claude_model("powerful")

            # Call LLM
            response = self.llm_client.messages.create(
                model=model_name,
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text if response.content else ""
            logger.info(f"New entity extraction response length: {len(content)} chars")

            # Store extraction response for UI display
            self.last_extraction_response = content

            # Parse response
            new_entities = self._parse_new_entity_response(content, entity_type)
            logger.info(f"Parsed {len(new_entities)} new entities")

            return new_entities

        except Exception as e:
            logger.error(f"New entity extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _create_new_entity_extraction_prompt(
        self,
        section_text: str,
        entity_type: str,
        matched_labels: List[str]
    ) -> str:
        """Create prompt for extracting NEW entities not already matched."""

        already_matched = "\n".join([f"- {label}" for label in matched_labels]) if matched_labels else "(none)"

        if entity_type == 'roles':
            entity_desc = "professional roles (e.g., 'Engineer', 'Client', 'Project Manager')"
            example = {
                "label": "Environmental Consultant",
                "definition": "Professional who assesses environmental impact",
                "confidence": 0.9,
                "is_class": True,
                "reasoning": "Mentioned as a distinct professional role"
            }
        elif entity_type == 'states':
            entity_desc = "ethical or situational states (e.g., 'Conflict of Interest', 'Safety Risk Identified')"
            example = {
                "label": "Refusal to Address Risk",
                "definition": "State where identified safety risk is knowingly not addressed",
                "confidence": 0.85,
                "is_class": True,
                "reasoning": "Describes a problematic ethical state"
            }
        else:  # resources
            entity_desc = "knowledge resources (e.g., 'Code of Ethics', 'Safety Regulations')"
            example = {
                "label": "Engineering Standards",
                "definition": "Professional standards governing engineering practice",
                "confidence": 0.8,
                "is_class": True,
                "reasoning": "Referenced as authoritative resource"
            }

        prompt = f"""You are analyzing an NSPE engineering ethics case Questions section.

# TASK: Extract NEW {entity_type.upper()}

We have already identified these {entity_type} from Facts/Discussion sections:

{already_matched}

Now analyze this Questions section text:

{section_text}

# TASK:
Extract ANY ADDITIONAL {entity_type} mentioned in the Questions that are NOT in the already-identified list above.

Look for {entity_desc} that represent concepts, situations, or entities that should have been captured but weren't.

For each NEW {entity_type.rstrip('s')} you find:
1. Check it's NOT in the already-matched list
2. Determine if it's a CLASS (general concept) or INDIVIDUAL (specific instance)
3. Provide clear definition and reasoning

# OUTPUT FORMAT (JSON):

```json
[
  {example}
]
```

Return ONLY new {entity_type} with confidence >= 0.7.
Return empty array [] if no new {entity_type} found.
Return ONLY valid JSON array.
"""
        return prompt

    def _parse_new_entity_response(
        self,
        response: str,
        entity_type: str
    ) -> List[Dict]:
        """Parse LLM response for new entity extraction."""
        entities = []

        try:
            import json

            # Extract JSON from response
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()

            data = json.loads(json_str)

            for item in data:
                entity = {
                    'label': item.get('label', ''),
                    'definition': item.get('definition', ''),
                    'confidence': item.get('confidence', 0.7),
                    'is_class': item.get('is_class', True),
                    'reasoning': item.get('reasoning', ''),
                    'entity_type': entity_type,
                    'storage_type': 'class' if item.get('is_class', True) else 'individual'
                }
                entities.append(entity)

            logger.info(f"Parsed {len(entities)} new entities from response")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response was: {response[:500]}")
        except Exception as e:
            logger.error(f"Error parsing new entity response: {e}")

        return entities
