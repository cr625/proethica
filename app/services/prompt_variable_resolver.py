"""
Prompt Variable Resolver Service

Resolves template variables for the prompt editor's preview and test functionality.
Fetches case text, queries MCP for existing entities, and formats variables.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

from app.services.extraction.reference_sheet import reuse_block_for_concept

logger = logging.getLogger(__name__)


class PromptVariableResolver:
    """Resolves template variables from case context and MCP entities."""

    # Maps concept types to their MCP entity category
    CONCEPT_TO_MCP_CATEGORY = {
        'roles': 'Role',
        'states': 'State',
        'resources': 'Resource',
        'principles': 'Principle',
        'obligations': 'Obligation',
        'constraints': 'Constraint',
        'capabilities': 'Capability',
        'actions': 'Action',
        'events': 'Event'
    }

    def __init__(self):
        """Initialize the resolver with MCP client."""
        from app.services.ontserve.external_mcp_client import get_external_mcp_client
        self.mcp_client = get_external_mcp_client()

    def resolve_variables(self, case_id: int, section_type: str,
                          concept_type: str) -> Dict[str, Any]:
        """
        Resolve all template variables for a given case and concept.

        Args:
            case_id: ID of the case document
            section_type: 'facts' or 'discussion'
            concept_type: Concept type (roles, principles, etc.)

        Returns:
            Dictionary of variable names to values
        """
        variables = {}

        # Get case text
        case_text = self.get_case_section_text(case_id, section_type)
        variables['case_text'] = case_text
        variables['section_type'] = section_type

        # Get existing entities from MCP
        existing_entities = self.get_existing_entities(concept_type)
        existing_text = self.format_existing_entities(existing_entities, concept_type)

        # For non-facts sections, append classes extracted from prior sections
        if section_type != 'facts':
            prior_text = self._format_prior_section_classes(
                case_id, section_type, concept_type
            )
            if prior_text:
                existing_text += prior_text

        # Set concept-specific variable names
        var_name = f'existing_{concept_type}_text'
        variables[var_name] = existing_text
        variables['existing_entities_text'] = existing_text  # Generic fallback

        # Also provide the raw list
        variables[f'existing_{concept_type}'] = existing_entities
        variables['existing_entities'] = existing_entities

        # Ontology-derived slots (role definition anchor, SHACL field schema, compiled directives, category
        # vocabulary), resolved at injection from the curated ontology + SHACL shapes. SHARED with the live
        # extractor via concept_ontology_slots so the editor preview and real extraction inject identically.
        variables.update(concept_ontology_slots(concept_type, section_type))

        # Cross-concept context (e.g., roles for principles extraction)
        from app.services.extraction.unified_dual_extractor import (
            format_cross_concept_context,
        )
        variables['cross_concept_context'] = format_cross_concept_context(
            concept_type, case_id
        )

        logger.info(f"Resolved {len(variables)} variables for case {case_id}, "
                   f"section {section_type}, concept {concept_type}")

        return variables

    def _format_prior_section_classes(
        self, case_id: int, current_section: str, concept_type: str,
    ) -> str:
        """
        Format classes extracted from earlier sections for this case.

        Mirrors UnifiedDualExtractor._format_prior_section_classes() so the
        prompt editor preview matches what the actual extraction sends.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.extraction_prompt import ExtractionPrompt

            section_order = ['facts', 'discussion', 'questions', 'conclusions']
            current_idx = (
                section_order.index(current_section)
                if current_section in section_order else 0
            )
            prior_sections = section_order[:current_idx]
            if not prior_sections:
                return ''

            prior_sessions = [
                p.extraction_session_id
                for p in ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    concept_type=concept_type,
                    is_active=True,
                ).all()
                if p.extraction_session_id and p.section_type in prior_sections
            ]
            if not prior_sessions:
                return ''

            prior_classes = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == concept_type,
                TemporaryRDFStorage.storage_type == 'class',
                TemporaryRDFStorage.extraction_session_id.in_(prior_sessions),
            ).all()
            if not prior_classes:
                return ''

            lines = [
                f'\n\n--- {concept_type.upper()} CLASSES ALREADY EXTRACTED '
                f'FROM PRIOR SECTIONS ---',
                'These classes were found in earlier sections of this case.',
                'Reference them via match_decision if the same concept '
                'appears here.',
                'Do NOT re-create them as new classes.\n',
            ]
            for cls in prior_classes:
                defn = cls.entity_definition or ''
                lines.append(f'- {cls.entity_label}: {defn}')

            logger.info(
                f"Added {len(prior_classes)} prior-section {concept_type} "
                f"classes to prompt editor preview for case {case_id}"
            )
            return '\n'.join(lines)

        except Exception as e:
            logger.warning(f"Could not load prior-section classes: {e}")
            return ''

    def get_case_section_text(self, case_id: int, section_type: str) -> str:
        """
        Extract section text from case document.

        Args:
            case_id: Document ID
            section_type: 'facts' or 'discussion'

        Returns:
            Plain text content of the section
        """
        from app.models.document import Document

        document = Document.query.get(case_id)
        if not document:
            logger.warning(f"Document {case_id} not found")
            return f"[Document {case_id} not found]"

        content = document.get_content()
        if not content:
            logger.warning(f"Document {case_id} has no content")
            return "[No content available]"

        # Parse HTML to extract section
        return self._extract_section_from_html(content, section_type)

    def _extract_section_from_html(self, html_content: str, section_type: str) -> str:
        """
        Extract a specific section from HTML case content.

        The HTML structure is:
        <div class="card">
            <div class="card-header"><h5>Facts</h5></div>
            <div class="card-body"><p>...</p></div>
        </div>

        Args:
            html_content: Full HTML content
            section_type: 'facts' or 'discussion'

        Returns:
            Plain text of the section
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the section header
            section_title = section_type.title()  # 'facts' -> 'Facts'

            # Look for h5 tag with the section name
            for h5 in soup.find_all('h5'):
                if h5.get_text(strip=True).lower() == section_type.lower():
                    # Find the parent card
                    card = h5.find_parent('div', class_='card')
                    if card:
                        # Find the card-body
                        body = card.find('div', class_='card-body')
                        if body:
                            # Get text content, preserving paragraph breaks
                            text = body.get_text(separator='\n', strip=True)
                            return text

            # Fallback: try regex for simple patterns
            pattern = rf'{section_title}[:\s]*(.+?)(?=(?:Discussion|Conclusion|References|$))'
            match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if match:
                # Clean HTML tags from the match
                text = re.sub(r'<[^>]+>', ' ', match.group(1))
                text = re.sub(r'\s+', ' ', text).strip()
                return text

            logger.warning(f"Section '{section_type}' not found in document")
            return f"[Section '{section_type}' not found]"

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return f"[Error extracting section: {e}]"

    def get_existing_entities(self, concept_type: str) -> List[Dict[str, Any]]:
        """
        Get existing entities from MCP for the given concept type.

        Args:
            concept_type: Concept type (roles, principles, etc.)

        Returns:
            List of entity dictionaries
        """
        try:
            category = self.CONCEPT_TO_MCP_CATEGORY.get(concept_type)
            if not category:
                logger.warning(f"No MCP category for concept type: {concept_type}")
                return []

            # Use the appropriate MCP method based on concept type
            # These methods already handle extracting entities from MCP response
            if concept_type == 'roles':
                entities = self.mcp_client.get_all_role_entities()
            elif concept_type == 'principles':
                entities = self._get_entities_from_mcp('Principle')
            elif concept_type == 'obligations':
                entities = self._get_entities_from_mcp('Obligation')
            elif concept_type == 'states':
                entities = self._get_entities_from_mcp('State')
            elif concept_type == 'resources':
                entities = self._get_entities_from_mcp('Resource')
            elif concept_type == 'constraints':
                entities = self._get_entities_from_mcp('Constraint')
            elif concept_type == 'capabilities':
                entities = self._get_entities_from_mcp('Capability')
            elif concept_type == 'actions':
                entities = self._get_entities_from_mcp('Action')
            elif concept_type == 'events':
                entities = self._get_entities_from_mcp('Event')
            else:
                entities = self._get_entities_from_mcp(category)

            logger.info(f"Retrieved {len(entities)} existing {concept_type} from MCP")
            return entities

        except Exception as e:
            logger.error(f"Error getting existing entities for {concept_type}: {e}")
            return []

    def _get_entities_from_mcp(self, category: str) -> List[Dict[str, Any]]:
        """Extract entities list from MCP response."""
        result = self.mcp_client.get_entities_by_category(category)
        if result.get('success') and result.get('result'):
            return result['result'].get('entities', [])
        return []

    def format_existing_entities(self, entities: List[Dict[str, Any]],
                                  concept_type: str,
                                  label_only_tier2: bool = False) -> str:
        """Delegate to module-level function."""
        return format_existing_entities(entities, concept_type,
                                        label_only_tier2=label_only_tier2)


def _entity_source(entity: Dict[str, Any]) -> str:
    """Source ontology name for an MCP entity (ontology_name / source / metadata)."""
    return (
        entity.get('ontology_name')
        or entity.get('source')
        or (entity.get('metadata', {}) or {}).get('ontology', '')
    )


def _is_case_copy(entity: Dict[str, Any]) -> bool:
    """True when the entity's source is a per-case ontology (proethica-case-N)."""
    return str(_entity_source(entity) or '').startswith('proethica-case-')


def _curated_only(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the CURATED matching vocabulary; drop per-case self-containment copies.

    The injected existing-class list is the dictionary the extractor matches against,
    so it must be the curated layers (proethica-core + proethica-intermediate +
    intermediate-extended + external reference standards), NOT every case's standalone
    copy of a class. The case ontologies hold a copy of each class they use under the
    same canonical URI; corpus-wide those copies dominate the MCP result (case 15
    roles: 618 distinct from case copies vs 61 from intermediate-extended) and a class
    that exists only in case ontologies is one of the ~4.8k discovered classes that
    were never consolidated, which we deliberately do not offer for matching. Genuine
    reusable classes live in intermediate / intermediate-extended."""
    kept = [e for e in entities if not _is_case_copy(e)]
    if len(kept) < len(entities):
        logger.info(
            "format_existing_entities: excluded %d per-case class copies from the "
            "matching vocabulary (%d curated entries remain before dedup)",
            len(entities) - len(kept), len(kept))
    return kept


# Source priority for collapsing duplicate URIs: a class is canonically defined in
# core/intermediate, else in intermediate-extended (the consolidated discovered
# store), else an external standard; a per-case ontology is only ever a self-contained
# COPY (lowest priority). Lower rank wins.
_SOURCE_RANK = {
    'proethica-core': 0,
    'proethica-intermediate': 0,
    'proethica-intermediate-extended': 1,
    'engineering-ethics': 2,
}


def _dedup_entities_by_uri(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse the per-(ontology, entity) rows the MCP returns into one entry per URI.

    Every case ontology self-contains a COPY of each class it uses under the SAME
    canonical URI (e.g. 21 cases that use a role -> 21 rows for the one
    intermediate#<Role> URI). The MCP category query returns every such row, so without
    this the injected class list is dominated by redundant copies (case 15 roles: 810
    canonical lines, 498 distinct). The consolidation the intermediate-extended store is
    meant to provide already holds in the data (the copies share one URI); this surfaces
    it in the prompt.

    Deduplication is by URI and is LOSSLESS: a class is never dropped, only collapsed.
    When the same URI appears in several source ontologies, the highest-authority source
    is kept so the survivor classifies into the right tier (canonical > extracted >
    external > case-copy) and carries the canonical definition rather than a case copy.
    Entities without a URI are kept and de-duplicated by label as a fallback.
    """
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    no_uri: List[Dict[str, Any]] = []

    def _rank(e: Dict[str, Any]) -> int:
        return _SOURCE_RANK.get(_entity_source(e), 3)

    for e in entities:
        uri = e.get('uri') or e.get('iri') or e.get('id')
        if not uri:
            no_uri.append(e)
            continue
        cur = best.get(uri)
        if cur is None:
            best[uri] = e
            order.append(uri)
        elif _rank(e) < _rank(cur):
            best[uri] = e

    deduped = [best[u] for u in order]

    seen_lbl = set()
    for e in no_uri:
        lbl = (e.get('label') or e.get('name') or '').strip().lower()
        if lbl and lbl in seen_lbl:
            continue
        if lbl:
            seen_lbl.add(lbl)
        deduped.append(e)

    if len(deduped) < len(entities):
        logger.info(
            "format_existing_entities: collapsed %d entity rows -> %d distinct "
            "(removed %d per-case duplicate copies)",
            len(entities), len(deduped), len(entities) - len(deduped),
        )
    return deduped


def format_existing_entities(entities: List[Dict[str, Any]],
                             concept_type: str,
                             label_only_tier2: bool = False) -> str:
    """
    Format existing ontology entities (plus the canonical reuse-bias guidance) for a prompt.

    Shared by UnifiedDualExtractor and PromptVariableResolver to ensure
    the extraction pipeline and prompt editor produce identical prompts.

    The output is the per-domain reference-sheet reuse block (canonical classes to reuse, synonyms
    that fold into them, and compound anti-patterns to avoid) followed by the live class inventory.
    The reuse block rides the existing ``existing_<type>_text`` variable, so a second domain needs
    only its own reference-sheet directory -- no per-template edits. See reference_sheet.prompt_block.

    Entities are separated into tiers by source ontology:
      Tier 1 - Canonical (proethica-core, proethica-intermediate): hand-curated
      Tier 2 - Previously extracted (proethica-intermediate-extended): from prior cases
      Tier 4 - External standards (engineering-ethics): NSPE, ISO, ANSI references

    Args:
        entities: List of entity dictionaries from MCP
        concept_type: Concept type (roles, states, etc.)
        label_only_tier2: If True, Tier 2 entities emit labels only (no definitions).
            Used in Phase 2 extraction where definitions are retrieved on demand
            via the get_class_definition tool.

    Returns:
        Formatted string for prompt inclusion
    """
    guidance = reuse_block_for_concept(concept_type)
    inventory = _format_entity_inventory(entities, concept_type, label_only_tier2)
    return "\n\n".join(p for p in (guidance, inventory) if p)


def _role_schema_block() -> str:
    """Build the role definitional/bearer schema text from the SHACL role shapes (core-shapes.ttl) so the
    extraction prompt's controlled field list stays in lockstep with the ontology -- the same shapes the
    OntServe Role page renders. Single source: edit the shapes, both the page and the prompt update.
    Raises on an unreadable shapes file (a real misconfiguration; not silently swallowed)."""
    import os
    from pathlib import Path
    import rdflib
    from app.services.extraction.reference_sheet import _sheet_dir
    shapes = os.environ.get('ONTSERVE_SHAPES_PATH') or str(
        Path(_sheet_dir()).resolve().parents[1] / 'validation' / 'shapes' / 'core-shapes.ttl')
    SH = rdflib.Namespace('http://www.w3.org/ns/shacl#')
    PCSH = rdflib.Namespace('http://proethica.org/shapes/core#')
    g = rdflib.Graph()
    g.parse(shapes, format='turtle')

    def fields(shape: str):
        rows = []
        for pshape in g.objects(PCSH[shape], SH.property):
            name = next(g.objects(pshape, SH.name), None)
            if name is None:
                continue
            desc = next(g.objects(pshape, SH.description), None)
            order = next(g.objects(pshape, SH.order), None)
            rows.append((int(order) if order is not None else 999, str(name), str(desc) if desc else ''))
        return [f'- {n}: {d}' for _o, n, d in sorted(rows)]

    universal = fields('RoleDefinitionShape')                  # every role
    professional = fields('ProfessionalRoleDefinitionShape')   # obligation-bearing roles only
    bearer = fields('ProfessionalRolePropertyShape')           # per-individual
    out = ['=== ROLE SCHEMA (from the SHACL role shapes -- the controlled class/individual fields) ===']
    if universal:
        out.append('Universal class fields (every role, professional or participant):')
        out += universal
    if professional:
        out.append('Professional-role class fields (obligation-bearing roles only; omit for participant/stakeholder):')
        out += professional
    if bearer:
        out.append('Bearer fields (on the individual, where the case states them):')
        out += bearer
    return '\n'.join(out)


def _ontology_ttl(name: str) -> str:
    """Absolute path to a curated OntServe ontology TTL, mirroring the shapes-path derivation in
    _role_schema_block. Override the ontologies dir with ONTSERVE_ONTOLOGIES_PATH."""
    import os
    from pathlib import Path
    from app.services.extraction.reference_sheet import _sheet_dir
    base = os.environ.get('ONTSERVE_ONTOLOGIES_PATH')
    root = Path(base) if base else Path(_sheet_dir()).resolve().parents[1] / 'ontologies'
    return str(Path(root) / name)


def _role_definition_block() -> str:
    """The governing definitional anchor: core:Role's iao:0000115 textual definition, read VERBATIM from
    proethica-core.ttl so the prompt's framing IS the Ch2 operationalization, not a hand-written paraphrase.
    Raises on an unreadable ontology file (no silent fallback)."""
    import rdflib
    IAO_DEF = rdflib.URIRef('http://purl.obolibrary.org/obo/IAO_0000115')
    ROLE = rdflib.URIRef('http://proethica.org/ontology/core#Role')
    g = rdflib.Graph()
    g.parse(_ontology_ttl('proethica-core.ttl'), format='turtle')
    defn = next((str(o) for o in g.objects(ROLE, IAO_DEF)), None)
    if not defn:
        raise RuntimeError("core:Role iao:0000115 definition not found in proethica-core.ttl")
    return "=== WHAT A ROLE IS (ontology definition) ===\n" + defn


# Banned-example phrasing for the eight non-Role D-tuple components (D-EXCLUDE). The component LIST is read
# from the ontology (so a new component appears automatically); only the example phrasing is maintained here.
_ROLE_EXCLUDE_EXAMPLES = {
    'Obligation': "a duty or 'shall' statement", 'Principle': "a value or ideal such as public safety",
    'Capability': "a skill or competence", 'State': "a condition such as a conflict of interest",
    'Action': "an act such as reviewing a design", 'Event': "an external occurrence",
    'Resource': "a document or standard such as the NSPE Code", 'Constraint': "a hard boundary or prohibition",
}


def _role_directives_block() -> str:
    """Compile the role AXIOMS into terse extraction DIRECTIVES -- the prescriptive rules the descriptive
    SHACL schema does not carry. The exclusion list (D-EXCLUDE) is DERIVED from the nine mutually-disjoint
    D-tuple component classes (owl:AllDisjointClasses) in proethica-core.ttl; the remaining directive
    sentences are a maintained axiom->sentence map, each traced to its source axiom. Raises on unreadable TTL."""
    import rdflib
    CORE = rdflib.Namespace('http://proethica.org/ontology/core#')
    g = rdflib.Graph()
    g.parse(_ontology_ttl('proethica-core.ttl'), format='turtle')
    components = sorted(str(s).split('#')[-1] for s in g.subjects(CORE.dtupleComponent, None))
    excl = "; ".join(f"{_ROLE_EXCLUDE_EXAMPLES[c]} ({c})"
                     for c in components if c != 'Role' and c in _ROLE_EXCLUDE_EXAMPLES)
    D = ["=== ROLE EXTRACTION DIRECTIVES (rules the ontology enforces) ==="]
    # D-EXCLUDE  <- owl:AllDisjointClasses over the nine D-tuple components (proethica-core.ttl)
    D.append(f"- DO NOT emit as a role: {excl}. If the thing is something an agent DOES, an occurrence, or "
             "a condition that holds, it is not a role.")
    # D-AGENT  <- proeth-core:Agent owl:disjointWith proeth-core:Role
    D.append("- The ACTOR and the ROLE are disjoint: put the actor's stable identity in `actor` (e.g. "
             "Engineer A) and the role facet in `identifier`; a person is never a role class.")
    # D-TELEO  <- proeth-core:Role rdfs:subClassOf (hasObligation some Obligation) + scopeNote
    D.append("- Every PROFESSIONAL role generates at least one obligation: name at least one obligation it "
             "generates (each becomes a hasObligation edge to an Obligation). If you cannot name one, the "
             "role is participant/stakeholder, not professional.")
    # D-INDIVIDUATION  <- core:Role skos:scopeNote (TYPE vs occupant facts, Davis 1991)
    D.append("- Individuate a role CLASS by the obligations/principles it determines and its audience "
             "relationship, NOT by occupant attributes: role_category and associated virtues belong on the "
             "CLASS; license, specialty, and employer belong on the INDIVIDUAL. License is not role-defining, "
             "so never put it in the class label.")
    # D-FILTER  <- proeth:ProfessionalRole owl:disjointWith proeth:ParticipantRole + its restrictions
    D.append("- Classify each role as professional XOR participant (disjoint, never both). Professional only "
             "if (a) a professional code governs it AND (b) it generates obligations; then fill the "
             "professional-role fields. Otherwise participant/stakeholder: fill only the universal fields and "
             "invent no professional attributes.")
    # D-LABEL  <- canonical head-noun + archetype reuse (proethica-intermediate occupational archetypes)
    D.append("- Use a canonical head-noun role label (e.g. 'Structural Engineer Role') and REUSE an existing "
             "role class from the list above rather than minting a near-duplicate compound.")
    return "\n".join(D)


def _role_category_block() -> str:
    """The controlled role_category vocabulary: the FOUR Kong relational categories with their
    audience-relationship cues and the directed actor edge each implies. role_category is the nullable
    RELATIONAL fallback (a role may bear none); the relational archetype is resolved edge-primary from
    the actor edge at commit (decision R1), with role_category used only when no actor edge is emitted
    and the edge winning on conflict. The occupational professional/participant axis is carried by the
    separate role_kind field. participant and stakeholder were removed from this vocabulary (they are
    occupational, not relational; stakeholder collapses into participant)."""
    rows = [
        "=== ROLE CATEGORY (controlled relational vocabulary -- nullable; set role_category to match the directed actor edge you emit, or omit it when the role bears no relational category) ===",
        "- provider_client: the role serves a client (Kong provider-to-client). Edge: hasClient (the provider side bears the archetype).",
        "- professional_peer: a colleague relationship among professionals (symmetric). Edge: professionalPeerOf.",
        "- employer_relationship: an employment relationship. Edge: employedBy (the employee/professional side bears the archetype).",
        "- public_responsibility: a duty owed to the public. Edge: owesDutyToward (a PublicInterest).",
        "role_category is a routing input (not stored as a literal) and is the FALLBACK only: when the role bears an actor edge, the edge determines the relational archetype (ProviderClientRole, ProfessionalPeerRole, EmployerRelationshipRole, PublicResponsibilityRole) and wins on conflict.",
    ]
    return "\n".join(rows)


def _role_relationships_block() -> str:
    """The canonical role-to-role relationship `type` vocabulary for the relationships[] field, DERIVED from
    the ontology: the NON-DEPRECATED subproperties of proeth-core:relatedTo (hasClient, professionalPeerOf,
    employedBy, reviewsWorkOf, workReviewedBy) -- the actor-relationship family the pipeline emits, the commit
    path maps, and the defining edges of the relational archetype classes. The older domain-Role spellings
    (retainedBy, mentoredBy, reportsTo, supervisedBy, collaboratesWith, ...) are owl:deprecated as duplicates
    of this family and are EXCLUDED; relatedTo is the controlled fallback for an organizational link (e.g.
    supervision, reporting) with no dedicated archetype. Same single-source pattern as _role_schema_block.
    Raises on unreadable TTL."""
    import rdflib
    from rdflib.namespace import SKOS
    CORE = rdflib.Namespace('http://proethica.org/ontology/core#')
    g = rdflib.Graph()
    g.parse(_ontology_ttl('proethica-core.ttl'), format='turtle')
    g.parse(_ontology_ttl('proethica-intermediate.ttl'), format='turtle')
    names = sorted(str(p).split('#')[-1] for p in g.subjects(rdflib.RDFS.subPropertyOf, CORE.relatedTo)
                   if (p, rdflib.OWL.deprecated, rdflib.Literal(True)) not in g)
    out = ["=== ROLE RELATIONSHIPS (controlled `type` for the relationships[] field, from the ontology -- "
           "state each from THIS role-bearer's perspective) ==="]
    for n in names:
        # cue = the ontology's own skos:definition (single source; same text the entity page shows), with
        # rdfs:comment as a fallback. No authored cue map -- the description cannot drift from the ontology.
        cue = (next((str(d) for d in g.objects(CORE[n], SKOS.definition)), '')
               or next((str(c) for c in g.objects(CORE[n], rdflib.RDFS.comment)), ''))
        out.append(f"- {n}: {cue}")
    out.append("- relatedTo: any other professional relationship between two roles that none of the above "
               "fits (e.g. supervision, a reporting line).")
    out.append("Each relationship needs a verbatim `quote` from the case. If the case states a relationship "
               "that fits NONE of the types above, do NOT invent a listed type: record it under "
               "`additional_relationships` as {type: <short verb phrase>, target: <the other role or agent>, "
               "quote: <evidence>}. These overflow entries are collected for periodic review and possible "
               "promotion to a real ontology property.")
    return "\n".join(out)


# Per-pass directive: one body serves both pass rows, differing only by this runtime slot.
_PASS_DIRECTIVES = {
    ('roles', 'facts'): "THIS PASS (facts): extract the role classes and individuals introduced by the case FACTS.",
    ('roles', 'discussion'): ("THIS PASS (discussion): the facts-pass roles are already in EXISTING ROLES above. "
                              "REUSE or refine them via match_decision; extract only genuinely NEW roles the "
                              "discussion introduces. A near-duplicate of a facts-pass role is an error."),
    ('obligations', 'facts'): ("THIS PASS (facts): extract the obligation classes and individuals the case FACTS "
                               "establish (the duties in force as the situation unfolds)."),
    ('obligations', 'discussion'): ("THIS PASS (discussion): the facts-pass obligations are already in EXISTING "
                                    "OBLIGATIONS above. REUSE or refine them via match_decision; extract only "
                                    "genuinely NEW obligations the discussion introduces (e.g. duties the Board "
                                    "names in its analysis). A near-duplicate of a facts-pass obligation is an error."),
    ('principles', 'facts'): ("THIS PASS (facts): extract the principle classes and individuals the case FACTS "
                              "put in play (the values the parties act on as the situation unfolds)."),
    ('principles', 'discussion'): ("THIS PASS (discussion): the facts-pass principles are already in EXISTING "
                                   "PRINCIPLES above. REUSE or refine them via match_decision; extract only "
                                   "genuinely NEW principles the discussion introduces (e.g. values the Board "
                                   "invokes in its analysis). A near-duplicate of a facts-pass principle is an error."),
    ('states', 'facts'): ("THIS PASS (facts): extract the state classes and individuals the case FACTS "
                          "establish (the conditions that hold as the situation unfolds)."),
    ('states', 'discussion'): ("THIS PASS (discussion): the facts-pass states are already in EXISTING STATES "
                               "above. REUSE or refine them via match_decision; extract only genuinely NEW "
                               "states the discussion introduces. A near-duplicate of a facts-pass state is an error."),
    ('resources', 'facts'): ("THIS PASS (facts): extract the resource classes and individuals the case FACTS "
                             "name (the codes, standards, and precedents the parties relied on; set used_by)."),
    ('resources', 'discussion'): ("THIS PASS (discussion): the facts-pass resources are already in EXISTING "
                                  "RESOURCES above. REUSE or refine them via match_decision; extract only "
                                  "genuinely NEW resources the discussion cites as authority (set cited_by). A "
                                  "near-duplicate of a facts-pass resource is an error."),
    ('capabilities', 'facts'): ("THIS PASS (facts): extract the capability classes and individuals the case "
                                "FACTS evidence (competences a party possesses or exercises)."),
    ('capabilities', 'discussion'): ("THIS PASS (discussion): the facts-pass capabilities are already in EXISTING "
                                     "CAPABILITIES above. REUSE or refine them via match_decision; extract only "
                                     "genuinely NEW capabilities the discussion introduces. A near-duplicate of a "
                                     "facts-pass capability is an error."),
    ('constraints', 'facts'): ("THIS PASS (facts): extract the constraint classes and individuals the case FACTS "
                               "establish (the prohibitions and hard boundaries in force as the situation unfolds)."),
    ('constraints', 'discussion'): ("THIS PASS (discussion): the facts-pass constraints are already in EXISTING "
                                    "CONSTRAINTS above. REUSE or refine them via match_decision; extract only "
                                    "genuinely NEW constraints the discussion introduces. A near-duplicate of a "
                                    "facts-pass constraint is an error."),
}


# concept_type (plural, as the pipeline passes it) -> the core component class whose <Component>DefinitionShape
# carries the controlled field contract. Roles is handled separately (it unions multiple shapes along its class
# chain). Action has no shape (bare, per the spec). Modular: one builder reads ANY component's shape, so a new
# component needs no new code -- add its row here and author its DefinitionShape.
_COMPONENT_SHAPE = {
    'obligations': 'Obligation', 'principles': 'Principle', 'states': 'State',
    'resources': 'Resource', 'capabilities': 'Capability', 'constraints': 'Constraint',
    'events': 'Event',
}


def _component_schema_block(component_class: str) -> str:
    """Generic {{ <concept>_schema }} field contract, read from the component's SHACL <Component>DefinitionShape
    in core-shapes.ttl -- the same single-source pattern as _role_schema_block, so a component prompt's
    controlled field list stays in lockstep with the ontology and the OntServe entity page. Raises on an
    unreadable shapes file or a shape with no fields (a real misconfiguration, not silently swallowed)."""
    import os
    from pathlib import Path
    import rdflib
    from app.services.extraction.reference_sheet import _sheet_dir
    shapes = os.environ.get('ONTSERVE_SHAPES_PATH') or str(
        Path(_sheet_dir()).resolve().parents[1] / 'validation' / 'shapes' / 'core-shapes.ttl')
    SH = rdflib.Namespace('http://www.w3.org/ns/shacl#')
    PCSH = rdflib.Namespace('http://proethica.org/shapes/core#')
    g = rdflib.Graph()
    g.parse(shapes, format='turtle')
    rows = []
    for pshape in g.objects(PCSH[f'{component_class}DefinitionShape'], SH.property):
        name = next(g.objects(pshape, SH.name), None)
        if name is None:
            continue
        desc = next(g.objects(pshape, SH.description), None)
        order = next(g.objects(pshape, SH.order), None)
        rows.append((int(order) if order is not None else 999, str(name), str(desc) if desc else ''))
    if not rows:
        raise RuntimeError(f"{component_class}DefinitionShape has no fields in core-shapes.ttl (Phase-1 shape missing?)")
    lines = [f'=== {component_class.upper()} SCHEMA (the controlled fields, from the SHACL '
             f'{component_class}DefinitionShape; single source with the OntServe entity page) ===']
    lines += [f'- {n}: {d}' for _o, n, d in sorted(rows)]
    return '\n'.join(lines)


def concept_ontology_slots(concept_type: str, section_type: str = None) -> Dict[str, str]:
    """Ontology-derived prompt slots for a concept, resolved at INJECTION time from the curated ontology +
    SHACL shapes, plus the per-pass directive (section_type). SHARED by the live extractor (prompt_building)
    and the editor preview (resolve_variables) so the two inject identically -- preview == live by
    construction. Empty for concepts without slots yet."""
    if concept_type in ('roles', 'role'):
        key = ('roles', section_type)
        return {
            'role_definition': _role_definition_block(),
            'role_schema': _role_schema_block(),
            'role_directives': _role_directives_block(),
            'role_category_vocab': _role_category_block(),
            'role_relationships': _role_relationships_block(),
            'pass_directive': _PASS_DIRECTIVES.get(key, ''),
        }
    comp = _COMPONENT_SHAPE.get(concept_type)
    if comp:
        # Generic ontology-driven schema slot for the other eight components: {{ <concept>_schema }} read from
        # the component's DefinitionShape. The per-component prompt body wires this in (Phase-3 migration).
        return {
            f'{comp.lower()}_schema': _component_schema_block(comp),
            'pass_directive': _PASS_DIRECTIVES.get((concept_type, section_type), ''),
        }
    return {}


def _format_entity_inventory(entities: List[Dict[str, Any]],
                             concept_type: str,
                             label_only_tier2: bool = False) -> str:
    """The live existing-class inventory (tiered by source ontology), without the reuse guidance.
    Split out from format_existing_entities so the reuse block can be composed in front of it."""
    if not entities:
        return f"No existing {concept_type} classes found in ontology."

    # Restrict to the curated matching vocabulary (drop per-case self-containment
    # copies), then collapse any remaining duplicate URIs to one entry per class.
    entities = _curated_only(entities)
    if not entities:
        return f"No existing {concept_type} classes found in ontology."
    entities = _dedup_entities_by_uri(entities)

    # Classify entities by source ontology tier.
    # MCP entities use 'source' for ontology name, and nested
    # metadata.ontology as fallback.
    canonical = []     # proethica-core, proethica-intermediate
    extracted = []     # proethica-intermediate-extended
    external = []      # engineering-ethics
    for entity in entities:
        ont_name = _entity_source(entity)
        if ont_name in ('proethica-core', 'proethica-intermediate'):
            canonical.append(entity)
        elif ont_name == 'proethica-intermediate-extended':
            extracted.append(entity)
        elif ont_name == 'engineering-ethics':
            external.append(entity)
        else:
            canonical.append(entity)  # default to canonical

    def _format_entity_line(entity, label_only=False):
        label = entity.get('label', entity.get('name', 'Unknown'))
        if label_only:
            return f"- {label}"
        definition = (
            entity.get('definition')
            or entity.get('description')
            or entity.get('comment', '')
        )
        if definition:
            return f"- {label}: {definition}"
        return f"- {label}"

    lines = []

    # Specialization-axis grouping (sourced from the ontology via MCP): when existing
    # classes carry a specializationAxis annotation -- engineer role leaves tagged "discipline"
    # (Civil/Electrical/...) vs "function" (Quality/Safety/...; values are skos:notations of the
    # RoleSpecializationScheme) -- present them grouped up front so the model reuses the right
    # specialization instead of minting a compound. specializationAxis is now ROLE-only; the
    # principle-kind grouping it used to carry was retired (2026-06-27) -- a principle's kind is
    # the rdfs:subClassOf kind class (FundamentalEthical/ProfessionalVirtue/Relational/DomainSpecific
    # Principle), which already appears as a canonical class below.
    def _axis_label(v):
        # specializationAxis is now a SKOS concept URI (RoleSpecializationScheme); show a readable label
        # (the de-CamelCased fragment, e.g. "Discipline Specialization") rather than the raw URI.
        frag = str(v).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
        return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', frag) or frag
    axis_groups = {}
    for e in entities:
        axis = (e.get('properties') or {}).get('specializationAxis')
        if axis:
            axis_groups.setdefault(_axis_label(axis), []).append(
                e.get('label', e.get('name', 'Unknown')))
    if axis_groups:
        lines.append(f"=== {concept_type.upper()} SPECIALIZATIONS BY AXIS ===")
        lines.append(
            "Existing classes that specialize a parent along a named axis. Reuse the exact "
            "label; do not mint a compound variant. The axes are orthogonal (a class may "
            "specialize on more than one).")
        for axis in sorted(axis_groups):
            labels = "; ".join(sorted(set(axis_groups[axis])))
            lines.append(f"- {axis}: {labels}")
        lines.append('')

    if canonical:
        lines.append(f"=== CANONICAL ONTOLOGY CLASSES ({concept_type}) ===")
        lines.append("Hand-curated classes from the formal ontology. Match to these with high confidence.")
        for e in canonical:
            lines.append(_format_entity_line(e))

    if extracted:
        if lines:
            lines.append('')
        lines.append(f"=== PREVIOUSLY EXTRACTED CLASSES (from other cases) ===")
        if label_only_tier2:
            lines.append(
                "Auto-extracted from prior case analyses. Labels listed below. "
                "Use the get_class_definition tool to retrieve full definitions "
                "when you need to disambiguate between similar class names."
            )
        else:
            lines.append("Auto-extracted from prior case analyses and approved. Match if the same concept appears.")
        for e in extracted:
            lines.append(_format_entity_line(e, label_only=label_only_tier2))

    if external:
        if lines:
            lines.append('')
        lines.append(f"=== EXTERNAL REFERENCE STANDARDS ===")
        lines.append("NSPE, ISO, ANSI, and other professional standards. Reference context only.")
        for e in external:
            lines.append(_format_entity_line(e))

    return '\n'.join(lines)


def get_prompt_variable_resolver() -> PromptVariableResolver:
    """Get a PromptVariableResolver instance."""
    return PromptVariableResolver()
