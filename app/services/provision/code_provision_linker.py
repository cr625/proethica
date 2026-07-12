"""
Code Provision Entity Linking Service

Links NSPE code provisions to extracted case entities (Roles, States, Resources)
using LLM-based semantic matching.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

from model_config import ModelConfig

logger = logging.getLogger(__name__)


class CodeProvisionLinker:
    """Links code provisions to case entities using LLM analysis."""

    def __init__(self, llm_client=None):
        """
        Initialize the linker.

        Args:
            llm_client: Claude API client for LLM analysis
        """
        self.llm_client = llm_client
        self.last_linking_prompt = None
        self.last_linking_response = None

    def link_provisions_to_entities(
        self,
        provisions: List[Dict],
        roles: List[Dict] = None,
        states: List[Dict] = None,
        resources: List[Dict] = None,
        principles: List[Dict] = None,
        obligations: List[Dict] = None,
        constraints: List[Dict] = None,
        capabilities: List[Dict] = None,
        actions: List[Dict] = None,
        events: List[Dict] = None,
        case_text_summary: str = ""
    ) -> List[Dict]:
        """
        Link code provisions to applicable case entities (all 9 types).

        Args:
            provisions: List of parsed code provisions
            roles: List of role entities
            states: List of state entities
            resources: List of resource entities
            principles: List of principle entities
            obligations: List of obligation entities
            constraints: List of constraint entities
            capabilities: List of capability entities
            actions: List of action entities
            events: List of event entities
            case_text_summary: Brief summary of the case

        Returns:
            List of provisions with 'applies_to' relationships added
        """
        if not self.llm_client:
            logger.warning("No LLM client provided, skipping entity linking")
            return provisions

        if not provisions:
            logger.info("No provisions to link")
            return []

        # Build entity groups for batched processing
        entity_groups = [
            ('role', 'Roles', roles or []),
            ('state', 'States', states or []),
            ('resource', 'Resources', resources or []),
            ('principle', 'Principles', principles or []),
            ('obligation', 'Obligations', obligations or []),
            ('constraint', 'Constraints', constraints or []),
            ('capability', 'Capabilities', capabilities or []),
            ('action', 'Actions', actions or []),
            ('event', 'Events', events or []),
        ]

        total_entities = sum(len(g[2]) for g in entity_groups)
        entity_counts = {g[1].lower(): len(g[2]) for g in entity_groups}
        logger.info(f"Linking {len(provisions)} provisions to {total_entities} total entities across 9 types")
        logger.info(f"Entity breakdown: {entity_counts}")

        # Initialize applies_to for each provision
        for provision in provisions:
            provision['applies_to'] = []

        # Process entity types in parallel (independent LLM calls)
        all_prompts = []
        all_responses = []

        def _link_one_type(entity_type, type_label, prompt):
            """Call LLM for one entity type and return parsed links.

            Receives the ALREADY-RENDERED prompt: prompt building runs on the
            main thread because get_step4_template reads the DB templates and
            needs the Flask app context, which executor worker threads do not
            have. Since the 2026-07-11 Step-4 template migration every worker
            raised 'Working outside of application context' and the swallow
            below reduced the whole stage to zero links (caught by the
            shadow gate: case-121 shadow lost all 68 appliesTo edges)."""
            from app.utils.llm_utils import streaming_completion
            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4096,
                prompt=prompt,
                temperature=0.1,
            )
            batch_links = self._parse_batch_response(response_text, entity_type)
            link_count = sum(len(v) for v in batch_links.values())
            logger.info(f"Linked {type_label}: {link_count} links")
            return entity_type, type_label, prompt, response_text, batch_links

        # Render all prompts on the main thread (app context available here).
        active_groups = [
            (et, tl, self._create_batch_linking_prompt(
                provisions, et, tl, ents, case_text_summary))
            for et, tl, ents in entity_groups if ents
        ]

        failed_groups = 0
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_link_one_type, et, tl, prompt): (et, tl)
                for et, tl, prompt in active_groups
            }
            for future in as_completed(futures):
                et, tl = futures[future]
                try:
                    entity_type, type_label, prompt, response_text, batch_links = future.result()
                    all_prompts.append(prompt)
                    all_responses.append(response_text)
                    for provision in provisions:
                        code = provision['code_provision'].rstrip('.')
                        if code in batch_links:
                            provision['applies_to'].extend(batch_links[code])
                except Exception as e:
                    failed_groups += 1
                    logger.error(f"Error linking {tl}: {e}")
        if active_groups and failed_groups == len(active_groups):
            # Every group failing is an infrastructure fault, not a judgment;
            # swallowing it stored empty applies_to arrays that read as data.
            raise RuntimeError(
                f"provision linking failed for ALL {failed_groups} entity groups; "
                f"see 'Error linking' log lines")

        self.last_linking_prompt = "\n\n---BATCH---\n\n".join(all_prompts)
        self.last_linking_response = "\n\n---BATCH---\n\n".join(all_responses)

        total_links = sum(len(p.get('applies_to', [])) for p in provisions)
        logger.info(f"Provision linking complete: {total_links} total links across {len(provisions)} provisions")
        return provisions

    def _create_batch_linking_prompt(
        self,
        provisions: List[Dict],
        entity_type: str,
        type_label: str,
        entities: List[Dict],
        case_summary: str
    ) -> str:
        """Create prompt for linking provisions to a single entity type."""

        provisions_text = ""
        for i, prov in enumerate(provisions, 1):
            provisions_text += f"{i}. **{prov['code_provision']}**: {prov['provision_text']}\n"

        entities_text = self._format_entities_for_prompt(entities, type_label)

        type_descriptions = {
            'role': 'The provision governs the professional conduct of that role',
            'state': 'The provision addresses or relates to that ethical situation',
            'resource': 'The provision references or requires that resource/document',
            'principle': 'The provision embodies or relates to that principle',
            'obligation': 'The provision specifies or relates to that obligation',
            'constraint': 'The provision creates or relates to that constraint',
            'capability': 'The provision requires or relates to that capability',
            'action': 'The provision governs or prohibits that action',
            'event': 'The provision addresses that event or occurrence',
        }
        applicability = type_descriptions.get(entity_type, '')

        from app.services.step4_synthesis.template_loader import get_step4_template
        return get_step4_template('step4_provision_link').render(
            provisions_text=provisions_text,
            type_label=type_label,
            entities_text=entities_text,
            entity_type=entity_type,
            applicability=applicability,
            case_summary=case_summary,
        )

    def _parse_batch_response(self, response_text: str, entity_type: str) -> Dict[str, List[Dict]]:
        """Parse batch linking response, returning {provision_code: [links]}."""
        from app.utils.llm_json_utils import parse_json_response

        linkings = parse_json_response(response_text, context=f"{entity_type}_linking")
        if linkings is None:
            logger.warning(f"No JSON in {entity_type} linking response")
            return {}

        return self._extract_links_from_parsed(linkings, entity_type)

    def _extract_links_from_parsed(self, linkings: list, entity_type: str) -> Dict[str, List[Dict]]:
        """Convert parsed JSON linkings list to result dict."""
        result = {}
        for link in linkings:
            code = link.get('code_provision', '').rstrip('.')
            applies_to = []
            for item in link.get('applies_to', []):
                applies_to.append({
                    'entity_type': entity_type,
                    'entity_label': item.get('entity_label', ''),
                    'reasoning': item.get('reasoning', ''),
                })
            if applies_to:
                result[code] = applies_to
        return result

    def _format_entities_for_prompt(self, entities: List[Dict], entity_type: str) -> str:
        """Format entity list for inclusion in prompt."""
        if not entities:
            return f"**{entity_type}:** (none extracted)"

        formatted = f"**{entity_type}:**\n"
        for entity in entities:
            label = entity.get('label', entity.get('entity_label', 'Unknown'))
            definition = entity.get('definition', entity.get('entity_definition', ''))

            formatted += f"- {label}"
            if definition:
                # Truncate long definitions
                if len(definition) > 150:
                    definition = definition[:150] + "..."
                formatted += f": {definition}"
            formatted += "\n"

        return formatted

    def get_last_prompt_and_response(self) -> Dict:
        """Return the last linking prompt and response for UI display."""
        return {
            'prompt': self.last_linking_prompt,
            'response': self.last_linking_response
        }
