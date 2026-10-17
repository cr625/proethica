"""
Class-commit mixin for OntServeCommitService.

Extracted verbatim from ontserve_commit_service.py (god-file split
CONTINUATION Item 4, Step 1.7): _commit_classes_to_intermediate and its two
helpers (_cite_discovering_cases, _accumulate_class_context), plus the three
class constants the class-commit path owns (_PROV_PROP_KEYS,
_CLASS_ROUTING_KEYS, _CORE_CLASS_FIELDS). OntServeCommitService gains
ClassCommitMixin as a base class so every self._method(...) call site is
unaffected.

_PROV_PROP_KEYS is also read by EmitterMixin's _add_individual_properties
(ttl_emitters.py) via self._PROV_PROP_KEYS; that resolves through the
instance's MRO regardless of which mixin declares the constant, so moving it
here changes no behavior.

rdflib namespace constants are redeclared locally rather than imported back
from ontserve_commit_service.py (which imports this module for the mixin),
to avoid a circular import; Namespace equality is string-based so this has
no behavioral effect.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, DCTERMS

from app.services.commit import naming
from app.services.commit.match_policy import linked_existing_class, matched_local_name
from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI

logger = logging.getLogger(__name__)

# Namespaces (see ontserve_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
PROV = Namespace("http://www.w3.org/ns/prov#")
PROETHICA_PROV = Namespace("http://proethica.org/provenance#")


class ClassCommitMixin:
    """Commit new/rediscovered classes to proethica-intermediate-extended.ttl."""

    def _commit_classes_to_intermediate(self, classes: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit new classes to proethica-intermediate-extended.ttl.

        This creates a supplemental file that can be imported by proethica-intermediate.ttl
        to avoid making the main file unwieldy.
        """
        try:
            extracted_file = self.ontologies_dir / "proethica-intermediate-extended.ttl"

            # Load existing graph or create new one
            g = Graph()
            if extracted_file.exists():
                g.parse(extracted_file, format='turtle')

            # Bind namespaces
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)
            g.bind("dcterms", DCTERMS)

            # Define provenance namespace
            PROETHICA_PROV = Namespace("http://proethica.org/provenance#")
            g.bind("proeth-prov", PROETHICA_PROV)

            count = 0
            linked_existing = 0
            declined_accumulations = 0
            for entity, rdf_data in classes:
                # Use entity attributes directly
                label = entity.entity_label or 'UnknownClass'
                # Sanitize label -> URI local-name via the shared allowlist (drops spaces, hyphens, and
                # all punctuation; see naming.safe_local_name for why a denylist was the wrong shape here).
                safe_label = naming.safe_local_name(label)
                # Category-aware disambiguation: never mint a class IRI that the
                # immutable base reserves for a disjoint category (e.g. a Principle
                # onto proeth:CompetenceSelfAssessmentCapability, a base Capability).
                category = self._get_concept_category(entity)
                safe_label = self._category_safe_class_local(safe_label, category)
                safe_label, label = naming.enforce_role_suffix(safe_label, label, category)
                class_uri = PROETHICA[safe_label]

                # Normalized D15 rule: do NOT copy a class that already lives in the curated
                # base (core / intermediate) into the extended store. A discovered class
                # matched to such a class (matchesExisting) belongs in the base, not here;
                # re-declaring it produced a subClassOf-self loop (the resolver pointed the
                # parent at the matched class, which is this IRI itself -- e.g.
                # SafetyObligation subClassOf SafetyObligation). The case references the
                # existing IRI through its import. Only genuinely-new classes reach extended.
                if self._base_core_category(safe_label) is not None:
                    logger.info(
                        "Class %s already in the curated base (core/intermediate); "
                        "not copying to the extended store.", safe_label)
                    continue

                # A row the matcher LINKED to an existing class (base or extended)
                # at or above the link threshold is reuse, not a mint (case-8
                # review, L3): PublicSafetyObligation was minted as a subclass of
                # SafetyObligation although its row had matched SafetyObligation
                # at 0.95 ("the same concept"), and UnbuildableDesignState
                # although it had matched ProjectFailureRiskState at 0.85. The
                # case individuals reach the matched class through honoring; the
                # class channel adds nothing. A row matched to ITS OWN IRI is a
                # re-discovery and takes the accumulate path below.
                linked = linked_existing_class(rdf_data, self._match_link_threshold())
                if linked is not None and naming.safe_local_name(linked).lower() != safe_label.lower():
                    logger.info(
                        "Class %s: row linked to existing class %s at or above the "
                        "link threshold %.2f; not minting.",
                        safe_label, linked, self._match_link_threshold())
                    linked_existing += 1
                    continue

                # Check if class already exists
                if (class_uri, RDF.type, OWL.Class) in g:
                    # A row whose match decision CONSIDERED this very class and
                    # declined it (matches_existing false, matched_uri = this IRI)
                    # must not accumulate case context onto it: the extraction
                    # said the concepts differ, and the IRI collision is a label
                    # collision (case 8 appended a scopeNote and discoveredInCase
                    # onto RegulatoryComplianceObligation, a procurement class
                    # the model had declined to match).
                    md = (rdf_data or {}).get('match_decision')
                    if (isinstance(md, dict) and md.get('matches_existing') is False
                            and naming.safe_local_name(
                                matched_local_name(md.get('matched_uri'))).lower() == safe_label.lower()):
                        logger.warning(
                            "Class %s: the extraction declined to match this existing "
                            "class; not accumulating case context onto it.", safe_label)
                        declined_accumulations += 1
                        continue
                    # Accumulate: add new case's discoveredInCase and context
                    self._accumulate_class_context(g, class_uri, entity, rdf_data, PROETHICA_PROV)
                    # Reconcile subClassOf parents a prior commit may be missing --
                    # notably the occupational archetype on role classes minted
                    # before the resolver was wired. GATED on core-category
                    # agreement (2026-07-11 shadow-gate review): the parents
                    # come from THIS extraction's category fields, so a
                    # re-discovery of the same label under a different concept
                    # category would otherwise add a second subClassOf into a
                    # disjoint core branch, making every case that loads the
                    # extended store Pellet-inconsistent. Same lesson as the
                    # KI2026 endpoint-chain repair: trust the chain, not the
                    # incoming category claim.
                    existing_cat = self._graph_core_category(g, class_uri)
                    existing_parents = set(g.objects(class_uri, RDFS.subClassOf))
                    for sc_uri in self._resolve_subclass_uris(entity, rdf_data):
                        parent_cat = self._core_category_of_iri(sc_uri)
                        if existing_cat and parent_cat and parent_cat != existing_cat:
                            logger.warning(
                                "cross-category subClassOf VETOED on %s: existing "
                                "chain -> %s, incoming parent %s -> %s "
                                "(re-discovery under a different category)",
                                class_uri, existing_cat, sc_uri, parent_cat)
                            continue
                        # Archetype-axis gate (case-8 review, L3): one archetype
                        # parent per class on a single-archetype axis. The core-
                        # category veto above cannot see this (every state
                        # archetype chains to core:State), so RegulatoryViolationState
                        # had accumulated four archetype parents.
                        blocking = self._archetype_axis_conflict(sc_uri, existing_parents)
                        if blocking is not None:
                            logger.warning(
                                "archetype-axis subClassOf VETOED on %s: already "
                                "parented under %s, incoming archetype %s "
                                "(one archetype parent per class on this axis)",
                                class_uri, blocking, sc_uri)
                            continue
                        if (class_uri, RDFS.subClassOf, URIRef(sc_uri)) not in g:
                            g.add((class_uri, RDFS.subClassOf, URIRef(sc_uri)))
                            existing_parents.add(URIRef(sc_uri))
                    continue

                # Add class triple. Normalize an extractor-vintage CamelCase label to
                # the spaced form the canonical intermediate uses ('DesignCapability' ->
                # 'Design Capability'), with the en language tag (extended-store labels
                # previously landed verbatim and rendered unsplit in the hierarchy).
                g.add((class_uri, RDF.type, OWL.Class))
                disp = label
                if disp and ' ' not in disp and any(c.isupper() for c in disp[1:]):
                    # NameError '_re' until 2026-07-11: this branch shipped in the
                    # 2026-07-07 sweep referencing an import that never existed and
                    # only executes for a genuinely NEW CamelCase class label --
                    # gold recommits take the accumulate path, so the shadow gate
                    # was the first run to reach it.
                    disp = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', disp)
                    disp = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', disp)
                g.add((class_uri, RDFS.label, Literal(disp, lang='en')))

                # Definitions: rdfs:comment + skos:definition (primary) and
                # skos:scopeNote (alternates), via the shared serializer that the
                # individual path also calls (single source of truth). A class
                # minted under a reference-sheet IRI takes the SHEET definition
                # (case-8 review, L3): the sheet text defines the reusable kind,
                # the row's text describes one case and becomes a case-tagged
                # scope note (UnbuildableDesignState carried the case-8
                # project-failure text as its definition).
                sheet_definition = self._reference_sheet_definition(safe_label, label)
                if sheet_definition:
                    g.add((class_uri, RDFS.comment, Literal(sheet_definition)))
                    g.add((class_uri, SKOS.definition, Literal(sheet_definition)))
                    row_definition = self._row_primary_definition(entity, rdf_data)
                    if row_definition and ' '.join(row_definition.split()) != sheet_definition:
                        case_tag = self._first_case_tag(rdf_data)
                        tagged = f"[Case {case_tag}] {row_definition}" if case_tag is not None else row_definition
                        g.add((class_uri, SKOS.scopeNote, Literal(tagged)))
                    logger.info("Class %s minted under a reference-sheet IRI; sheet definition used.",
                                safe_label)
                else:
                    self._emit_definitions(g, class_uri, entity, rdf_data)

                # XAI: persist the matcher's type/match decision as annotation
                # provenance (which canonical class, confidence, rationale).
                self._emit_match_decision(g, class_uri, rdf_data, PROETHICA_PROV)

                # Add subclass relationship using CATEGORY_TO_ONTOLOGY_IRI when
                # category info is available, otherwise fall back to core class.
                subclass_uris = self._resolve_subclass_uris(entity, rdf_data)
                for sc_uri in subclass_uris:
                    g.add((class_uri, RDFS.subClassOf, URIRef(sc_uri)))

                # Provenance from rdf_json_ld, via the shared serializer (single
                # source of truth with the individual path).
                if rdf_data and 'properties' in rdf_data:
                    self._emit_provenance(g, class_uri, rdf_data)
                    props = rdf_data['properties']

                    # Case citation: dcterms:source <case ontology IRI> per
                    # discovering case (class path only -- an individual inside
                    # its own case TTL would be self-citation).
                    self._cite_discovering_cases(g, class_uri, props)

                    # Domain properties: everything the class card displays beyond the
                    # provenance keys handled above (e.g. valueBasis, textReferences,
                    # confidence). The class serializer previously emitted only
                    # definitions + provenance, so the entire "Properties" column was
                    # dropped at commit. Emit each remaining key as a literal,
                    # mirroring the individual generic path (same naming.camelCase predicate
                    # convention) so the class round-trips.
                    for prop_name, prop_values in props.items():
                        if prop_name in self._PROV_PROP_KEYS:
                            continue
                        values = prop_values if isinstance(prop_values, list) else [prop_values]
                        safe_prop = naming.camelCase(prop_name)
                        # Routing inputs are consumed by the subClassOf/type routing
                        # and must not leak as class literals -- the individual loop
                        # has carried this skip since CMT-3, the class loop had not
                        # (correspondence audit T5/B3: principleCategory,
                        # obligationType, stateCategory, ... appeared as literals on
                        # every minted class, contra the shapes' not-stored-as-a-
                        # literal contract).
                        if safe_prop in self._CLASS_ROUTING_KEYS:
                            continue
                        # The four role definitional fields are DECLARED as core#
                        # annotation properties (and the SHACL shapes point at core:
                        # paths); the generic intermediate# emission left the declared
                        # properties dataless and the emitted predicates undeclared
                        # (correspondence-audit namespace-drift defect).
                        if safe_prop in self._CORE_CLASS_FIELDS:
                            prop_uri = PROETHICA_CORE[safe_prop]
                        else:
                            prop_uri = PROETHICA[safe_prop]
                        for value in values:
                            if value not in (None, '', [], {}):
                                if safe_prop == 'confidence':
                                    g.add((class_uri, prop_uri, naming.confidence_literal(value)))
                                    continue
                                lit = value if isinstance(value, (str, int, float, bool)) else str(value)
                                g.add((class_uri, prop_uri, Literal(lit)))
                else:
                    # Fallback to basic provenance if rdf_data not available
                    g.add((class_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
                    g.add((class_uri, PROV.wasGeneratedBy, Literal("ProEthica Extraction")))

                # IAO document references
                if entity.iao_document_uri:
                    g.add((class_uri, DCTERMS.references, URIRef(entity.iao_document_uri)))
                    if entity.iao_document_label:
                        g.add((class_uri, PROETHICA_PROV.documentReference, Literal(entity.iao_document_label)))
                if entity.cited_by_role:
                    g.add((class_uri, PROETHICA_PROV.citedByRole, Literal(entity.cited_by_role)))
                if entity.available_to_role:
                    g.add((class_uri, PROETHICA_PROV.availableToRole, Literal(entity.available_to_role)))

                # Specific extraction model attribution
                if entity.extraction_model:
                    g.add((class_uri, PROV.wasAttributedTo, Literal(entity.extraction_model)))

                count += 1

            # Save the graph
            naming.sanitize_graph_literals(g)
            g.serialize(destination=extracted_file, format='turtle')
            logger.info(f"Committed {count} classes to {extracted_file}")

            # Update proethica-intermediate.ttl to import this file if not already
            self._ensure_import_statement()

            return {'count': count, 'file': str(extracted_file),
                    'linked_existing': linked_existing,
                    'declined_accumulations': declined_accumulations}

        except Exception as e:
            logger.error(f"Error committing classes: {e}")
            return {'count': 0, 'error': str(e)}

    # Archetype axes on which an extended-store class carries ONE parent (case-8
    # review, L3). Keyed by the CATEGORY_TO_ONTOLOGY_IRI map whose values form
    # the axis; the state archetypes are the nine content kinds (RiskState,
    # EpistemicState, ...), all subClassOf core:State, so only this gate keeps a
    # re-discovery under a different kind from stacking a second parent.
    _SINGLE_ARCHETYPE_AXES = ('states',)

    def _archetype_axis_conflict(self, incoming_parent, existing_parents) -> "str | None":
        """The existing parent that blocks ``incoming_parent`` on a single-
        archetype axis, or None when the incoming parent is admissible (not on
        a gated axis, already present, or the first archetype on its axis)."""
        incoming = str(incoming_parent)
        existing = {str(p) for p in existing_parents}
        if incoming in existing:
            return None
        for axis in self._SINGLE_ARCHETYPE_AXES:
            members = set(CATEGORY_TO_ONTOLOGY_IRI.get(axis, {}).values())
            if incoming in members:
                prior = sorted(existing & members)
                if prior:
                    return prior[0]
        return None

    # Per-instance override of the reference-sheet directory (tests); None uses
    # the active domain's sheet (REFERENCE_SHEET_DIR or the domain config).
    reference_sheet_dir = None

    def _reference_sheet_definition(self, local_name: str, label: str) -> "str | None":
        """The reference sheet's definition for a class minted under one of its
        canonical IRIs (keyed by IRI local-name or label), or None when the sheet
        is unavailable or does not list the class."""
        try:
            from app.services.extraction.reference_sheet import get_sheet
            sheet = get_sheet(getattr(self, 'reference_sheet_dir', None))
        except Exception as e:  # noqa: BLE001 - no sheet configured on this host
            logger.info("Reference sheet unavailable (%s); minted classes keep the row definition.", e)
            return None
        return sheet.definition_for(local_name) or sheet.definition_for(label)

    @staticmethod
    def _row_primary_definition(entity, rdf_data: Dict) -> str:
        """The row's own primary definition text ('' when none), mirroring the
        precedence _emit_definitions applies."""
        definitions = (rdf_data or {}).get('definitions') or []
        if definitions:
            primary = next((d for d in definitions if d.get('is_primary')), definitions[0])
            text = (primary.get('text') or '').strip()
            if text:
                return text
        return (getattr(entity, 'entity_definition', None) or '').strip()

    @staticmethod
    def _first_case_tag(rdf_data: Dict):
        props = (rdf_data or {}).get('properties') or {}
        case_ids = props.get('discoveredInCase') or props.get('firstDiscoveredInCase') or []
        if not isinstance(case_ids, list):
            case_ids = [case_ids]
        return case_ids[0] if case_ids else None

    def _cite_discovering_cases(self, g: Graph, class_uri: URIRef, props: Dict) -> None:
        """Emit one dcterms:source case citation per discoveredInCase value
        (falling back to firstDiscoveredInCase), deduplicated against the graph."""
        case_ids = props.get('discoveredInCase') or props.get('firstDiscoveredInCase') or []
        if not isinstance(case_ids, list):
            case_ids = [case_ids]
        for case_id_val in case_ids:
            try:
                source = naming.case_ontology_iri(case_id_val)
            except (TypeError, ValueError):
                continue
            if (class_uri, DCTERMS.source, source) not in g:
                g.add((class_uri, DCTERMS.source, source))

    def _accumulate_class_context(self, g: Graph, class_uri: URIRef,
                                     entity, rdf_data: Dict,
                                     PROETHICA_PROV: Namespace) -> None:
        """
        When a class already exists in the extended TTL, accumulate new case context
        rather than skipping entirely.

        Adds:
        - proeth-prov:discoveredInCase (new case ID, if not already present)
        - skos:scopeNote with case-tagged definition (if definition differs)
        """
        props = (rdf_data or {}).get('properties', {})

        # Add discoveredInCase if not already present for this case
        case_ids_in_props = props.get('discoveredInCase', [])
        if not case_ids_in_props and props.get('firstDiscoveredInCase'):
            case_ids_in_props = props['firstDiscoveredInCase']

        for case_id_val in case_ids_in_props:
            case_literal = Literal(int(case_id_val), datatype=XSD.integer)
            if (class_uri, PROETHICA_PROV.discoveredInCase, case_literal) not in g:
                g.add((class_uri, PROETHICA_PROV.discoveredInCase, case_literal))
                logger.info(f"Class {entity.entity_label}: added discoveredInCase {case_id_val}")
        # Re-discovery extends the extensional grounding: cite the new case too.
        self._cite_discovering_cases(g, class_uri, props)

        # Add case-specific definition as skos:scopeNote if it differs from existing
        new_definition = ''
        definitions = (rdf_data or {}).get('definitions', [])
        if definitions:
            primary = next((d for d in definitions if d.get('is_primary')), definitions[0])
            new_definition = primary.get('text', '')
        if not new_definition:
            new_definition = entity.entity_definition or ''

        if new_definition:
            # Check if this exact text is already present as definition or scopeNote
            existing_notes = set()
            for _, _, obj in g.triples((class_uri, SKOS.definition, None)):
                existing_notes.add(str(obj).strip())
            for _, _, obj in g.triples((class_uri, SKOS.scopeNote, None)):
                existing_notes.add(str(obj).strip())
            for _, _, obj in g.triples((class_uri, RDFS.comment, None)):
                existing_notes.add(str(obj).strip())

            if new_definition.strip() not in existing_notes:
                case_tag = case_ids_in_props[0] if case_ids_in_props else '?'
                tagged = f"[Case {case_tag}] {new_definition}"
                g.add((class_uri, SKOS.scopeNote, Literal(tagged)))
                logger.info(f"Class {entity.entity_label}: added scopeNote from Case {case_tag}")

    # Provenance keys handled by _emit_provenance as typed prov:/proeth-prov:
    # triples. The generic property loops (class and individual) skip these so
    # they are not also emitted as untyped (and, pre-fix, lowercased) proeth:
    # literals -- the double-emission the individual path produced.
    _PROV_PROP_KEYS = frozenset({
        'generatedAtTime', 'wasAttributedTo', 'wasGeneratedBy',
        'firstDiscoveredInCase', 'firstDiscoveredAt', 'discoveredInCase',
        'discoveredInSection', 'discoveredInStep', 'sourceText',
    })

    # Routing inputs and commit-resolved carrier fields the CLASS path must not
    # store as literals. The shapes declare the routing inputs "a routing input,
    # not stored as a literal" (the typing they drive is the subClassOf/rdf:type
    # routing); the carrier fields (e.g. derivedFromPrinciple,
    # principleTransformation) resolve via the dedicated edge passes instead. The individual path applies
    # its own skip inline (roleCategory/roleKind + endswith('Class') + RELATION
    # classification); this is the class-path counterpart, covering every
    # class-minting component (correspondence audit T5/B3).
    _CLASS_ROUTING_KEYS = frozenset({
        'roleCategory', 'roleKind', 'principleCategory', 'obligationType',
        'derivedFromPrinciple', 'stateCategory', 'obligationActivation',
        'actionConstraints', 'activationConditions', 'terminationConditions',
        'principleTransformation', 'resourceCategory',
        'sourceKind',  # shape-path alias for resourceCategory (never emitted by the current schema)
        'capabilityKind', 'constraintType', 'boundaryType', 'eventType',
    })

    # Class-level definitional fields declared in the CORE namespace
    # (proethica-core annotation properties; the SHACL definition shapes point
    # at core: paths). Emitted under PROETHICA_CORE so declaration, shape, and
    # data agree.
    _CORE_CLASS_FIELDS = frozenset({
        'distinguishingFeatures', 'professionalScope',
        'typicalQualifications', 'associatedVirtues',
    })
