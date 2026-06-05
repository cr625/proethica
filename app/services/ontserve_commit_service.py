"""
OntServe Commit Service for ProEthica

Handles committing extracted entities from temporary storage to permanent OntServe storage.
- Classes are saved to proethica-intermediate-extended.ttl (supplemental file)
- Individuals are saved to case-specific ontologies (proethica-case-N.ttl)
- Synchronizes with OntServe database via refresh scripts

Versioning Strategy (January 2026):
- Case TTL files are OVERWRITTEN on re-extraction (single file, no accumulation)
- OntServe DB preserves historical versions via concepts.is_current and concept_versions
- Classes are versioned individually (same class from different cases = new version)

Note: Current architecture stores new classes in proethica-intermediate-extended.ttl
for testing purposes. Alternative approach would be to store both classes and
individuals in case-specific ontologies (proethica-case-N.ttl) and have
proethica-intermediate import from all cases, but this could become unwieldy.
The current approach allows easy clearing of test classes via clear_extracted_classes().
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import subprocess
from pathlib import Path
import requests
import psycopg2
from psycopg2.extras import Json

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, DCTERMS

from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.models.case_ontology_commit import CaseOntologyCommit
from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI
from app.services.ontserve_config import (
    get_ontserve_db_config, get_ontserve_base_path, get_ontserve_mcp_url,
)

logger = logging.getLogger(__name__)

# Namespaces
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
TIME = Namespace("http://www.w3.org/2006/time#")
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
PROV = Namespace("http://www.w3.org/ns/prov#")
PROETHICA_PROV = Namespace("http://proethica.org/provenance#")


class OntServeCommitService:
    """Service for committing extracted entities to OntServe permanent storage."""

    def __init__(self):
        """Initialize the commit service."""
        self.ontserve_path = get_ontserve_base_path()
        self.ontologies_dir = self.ontserve_path / "ontologies"
        self.mcp_url = get_ontserve_mcp_url()
        # Use OntServe's venv Python for subprocess calls (has pgvector, etc.)
        self.ontserve_python = str(self.ontserve_path / "venv-ontserve" / "bin" / "python")

        # Ensure directories exist
        self.ontologies_dir.mkdir(parents=True, exist_ok=True)

        # Lazily-built resolver: intermediate class local-name -> its established
        # core category (resolved via subClassOf* in
        # proethica-core+intermediate[-extended]). Shared implementation with the
        # matcher cross-category gate (app.services.extraction.category_resolver).
        self._category_resolver = None

    def _case_title(self, case_id: int) -> Optional[str]:
        """Return the human case title for a case id, or None if the document is
        absent. Emitted as dcterms:title in the case TTL header so the title
        travels with the artifact (OntServe reads it into display_name on sync,
        rather than coupling to the ProEthica database)."""
        from app.models.document import Document
        from app.models import db
        doc = db.session.get(Document, case_id)
        title = (doc.title or '').strip() if doc else ''
        return title or None

    def _established_core_category(self, class_local_name: str) -> Optional[str]:
        """Return the core category an EXISTING intermediate class already chains
        to (via rdfs:subClassOf*), or None if the class is unknown / has no core
        ancestor.

        Used to avoid re-declaring a conceptCategory-derived parent for a class
        the ontology already defines: e.g. proeth:ProfessionalCompetence is
        subClassOf proeth-core:Capability in proethica-intermediate, so a commit
        must NOT add proeth-core:Principle just because an instance's
        conceptCategory literal says "Principle" -- that second disjoint parent
        makes the case OWL-DL inconsistent. The ontology definition wins over the
        (lie-prone) literal. Mirrors pellet_validate's skip-if-parent-exists rule
        at commit time rather than as an after-the-fact in-memory patch.

        Delegates to the shared CategoryResolver (one implementation, shared with
        the matcher cross-category gate), pinned to this service's ontologies_dir.
        """
        if self._category_resolver is None:
            from app.services.extraction.category_resolver import CategoryResolver
            self._category_resolver = CategoryResolver(self.ontologies_dir)
        return self._category_resolver.resolve(class_local_name)

    def _base_core_category(self, class_local_name: str) -> Optional[str]:
        """Core category an IRI is reserved for in the IMMUTABLE base (core +
        intermediate ONLY, NOT the extended store).

        `_established_core_category` includes proethica-intermediate-extended, which
        a re-extraction is actively writing -- so once a colliding class is written
        there it masks the conflict (it would report the just-written category).
        The base is fixed during a run, so it is the authority for deciding whether
        a label collides with a reserved category. Cached per instance. e.g.
        ProfessionalCompetence -> Capability (reserved by proethica-intermediate),
        regardless of what a principle pass tries to write to the same IRI.
        """
        cache = getattr(self, '_base_cat_cache', None)
        if cache is None:
            cache = {}
            from rdflib import Graph as _G
            base = _G()
            for fn in ('proethica-core.ttl', 'proethica-intermediate.ttl'):
                p = self.ontologies_dir / fn
                if p.exists():
                    try:
                        base.parse(str(p), format='turtle')
                    except Exception as e:
                        logger.warning("base-category map: could not parse %s: %s", fn, e)
            core_ns = str(PROETHICA_CORE)
            nine = {'Role', 'Principle', 'Obligation', 'State', 'Resource',
                    'Action', 'Event', 'Capability', 'Constraint'}

            def reach(cls, seen):
                if cls in seen:
                    return None
                seen.add(cls)
                s = str(cls)
                if s.startswith(core_ns) and s.split('#')[-1] in nine:
                    return s.split('#')[-1]
                for sup in base.objects(cls, RDFS.subClassOf):
                    r = reach(sup, seen)
                    if r:
                        return r
                return None

            for cls in set(base.subjects(RDF.type, OWL.Class)):
                local = str(cls).split('#')[-1].split('/')[-1]
                cat = reach(cls, set())
                if cat:
                    cache[local] = cat
            self._base_cat_cache = cache
        return cache.get(class_local_name)

    def _category_safe_class_local(self, class_local_name: str, concept_category: Optional[str]) -> str:
        """Disambiguate a class local name when it collides, in the immutable base,
        with a DIFFERENT (disjoint) core category than the entity's own.

        The nine core categories are mutually disjoint, so a Principle minted onto
        proeth:ProfessionalCompetence (reserved by the base for Capability) makes the
        case OWL-DL inconsistent. Rather than dual-class one IRI, give the new
        concept its own IRI by appending its category (ProfessionalCompetencePrinciple).
        No-op when there is no collision (the common case) or no category."""
        if not concept_category:
            return class_local_name
        base_cat = self._base_core_category(class_local_name)
        if base_cat and base_cat != concept_category:
            disambiguated = f"{class_local_name}{concept_category}"
            logger.info(
                "Cross-category IRI collision: %s is reserved for %s in the base but "
                "carries conceptCategory %s; minting %s instead.",
                class_local_name, base_cat, concept_category, disambiguated)
            return disambiguated
        return class_local_name

    def _record_edge_provenance(self, case_id, edge_result):
        """Record the commit-time edge materialization (per family) + the unified guard as
        provenance PASSES, so the record shows the post-extraction graph construction, not only
        the LLM stages. Best-effort: provenance must never fail a commit."""
        try:
            if not isinstance(edge_result, dict):
                return
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()

            def _count(r):
                for k in ('total', 'edges', 'edges_emitted', 'edges_added', 'triples_added'):
                    if isinstance(r.get(k), int):
                        return r[k]
                return None

            by_family, total = {}, 0
            for fam, r in edge_result.items():
                if fam == 'unified_guard' or not isinstance(r, dict):
                    continue
                n = _count(r)
                by_family[fam] = {'edges': n, 'unresolved': r.get('unresolved')}
                if isinstance(n, int):
                    total += n
            prov.track_pass(
                activity_type='materialization', activity_name='edge_materialization',
                case_id=case_id, agent_type='extraction_service', agent_name='edge_materialization',
                execution_plan={'families': list(by_family.keys()),
                                'resolver': 'embedding shortlist + LLM select'},
                result={'total_edges': total, 'by_family': by_family},
            )
            guard = edge_result.get('unified_guard')
            if isinstance(guard, dict):
                prov.track_pass(
                    activity_type='guard', activity_name='unified_guard',
                    case_id=case_id, agent_type='extraction_service', agent_name='unified_guard',
                    execution_plan={'rule': 'drop any edge whose endpoint reaches a disjoint core '
                                            'category other than the one the property requires'},
                    result={'triples_dropped': guard.get('triples_dropped', 0)},
                )
        except Exception:
            logger.warning("edge provenance recording failed for case %s (best-effort)",
                           case_id, exc_info=True)

    def _record_conformance_provenance(self, case_id, conf):
        """Record the C3 conformance gate (SHACL+OWL-RL check) + any deterministic Tier-0 repairs
        as provenance passes. Best-effort."""
        try:
            if not isinstance(conf, dict):
                return
            from app.services.provenance_service import get_provenance_service
            prov = get_provenance_service()
            prov.track_pass(
                activity_type='validation', activity_name='conformance_check',
                case_id=case_id, agent_type='shacl_engine', agent_name='pyshacl+owl-rl',
                execution_plan={'shapes': 'validation/shapes/core-shapes.ttl',
                                'engine': 'SHACL + OWL-RL', 'via': 'OntServe repair_conformance_ttl MCP'},
                result={'conforms': conf.get('conforms'), 'remaining': conf.get('remaining'),
                        'reason': conf.get('reason'), 'status': conf.get('status')},
            )
            repairs = conf.get('repairs_applied')
            if repairs:
                prov.track_pass(
                    activity_type='repair', activity_name='tier0_conformance_repair',
                    case_id=case_id, agent_type='extraction_service', agent_name='tier0_repair',
                    execution_plan={'tier': 0, 'strategy': 'deterministic re-typing to the '
                                    'property-required category (no LLM)'},
                    result={'repairs_applied': repairs},
                )
        except Exception:
            logger.warning("conformance provenance recording failed for case %s (best-effort)",
                           case_id, exc_info=True)

    def commit_selected_entities(self, case_id: int, entity_ids: List[int]) -> Dict[str, Any]:
        """
        Commit selected entities from temporary storage to permanent OntServe storage.

        Args:
            case_id: The case ID
            entity_ids: List of TemporaryRDFStorage IDs to commit

        Returns:
            Dictionary with commit results
        """
        try:
            # Fetch selected entities
            entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.id.in_(entity_ids),
                TemporaryRDFStorage.case_id == case_id
            ).all()

            if not entities:
                return {
                    'success': False,
                    'error': 'No entities found for the provided IDs'
                }

            # Separate classes and individuals
            classes_to_commit = []
            individuals_to_commit = []

            for entity in entities:
                # Use rdf_json_ld column instead of rdf_data
                rdf_data = entity.rdf_json_ld if entity.rdf_json_ld else {}

                # Check storage_type directly from entity
                if entity.storage_type == 'class':
                    classes_to_commit.append((entity, rdf_data))
                elif entity.storage_type == 'individual':
                    individuals_to_commit.append((entity, rdf_data))

            results = {
                'success': True,
                'classes_committed': 0,
                'individuals_committed': 0,
                'errors': []
            }

            # Commit classes to proethica-intermediate-extended.ttl
            if classes_to_commit:
                class_result = self._commit_classes_to_intermediate(classes_to_commit)
                results['classes_committed'] = class_result['count']
                if class_result.get('error'):
                    results['errors'].append(class_result['error'])

            # Commit individuals to case-specific ontology
            if individuals_to_commit:
                individual_result = self._commit_individuals_to_case_ontology(case_id, individuals_to_commit)
                results['individuals_committed'] = individual_result['count']
                if individual_result.get('error'):
                    results['errors'].append(individual_result['error'])

                # C3 pre-commit conformance gate: SHACL + OWL-RL check + deterministic Tier-0
                # repair (via the OntServe repair_conformance_ttl MCP tool) over the just-
                # materialised case TTL, BEFORE the disk->DB sync so the persisted version is the
                # conforming one. Best-effort (never raises); the LLM repair tiers are deferred to
                # the Section-C pilot, so a Tier-0-unfixable residual is flagged, not refused.
                try:
                    from app.services.extraction.conformance_gate import gate_case_ttl
                    case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
                    results['conformance'] = gate_case_ttl(case_id, case_file)
                except Exception as e:  # noqa: BLE001
                    logger.warning("conformance gate skipped for case %s: %s", case_id, e)
                    results['conformance'] = {"status": "gate_error", "error": str(e)}
                self._record_conformance_provenance(case_id, results.get('conformance'))

            # Mark entities as published and record content hashes
            now = datetime.now(timezone.utc)
            for entity in entities:
                entity.is_published = True
                entity.committed_at = now
                entity.content_hash = TemporaryRDFStorage.compute_content_hash(
                    entity.entity_uri or '',
                    entity.entity_label,
                    entity.entity_definition
                )

            from app import db

            # Record ontology version binding
            self._record_ontology_commit(db, case_id, entities)

            db.session.commit()

            # Sync the edge-bearing disk TTL -> OntServe DB. One call creates the
            # ontology record if new, writes a new current ontology_versions row,
            # and re-extracts entities (register + refresh are now one operation).
            if individuals_to_commit:
                sync_result = self._sync_ontology_to_db(f"proethica-case-{case_id}")
                if sync_result.get('success'):
                    results['ontserve_synced'] = True
                else:
                    results['errors'].append(f"OntServe sync warning: {sync_result.get('error', 'Unknown')}")

            if classes_to_commit:
                sync_result = self._synchronize_with_ontserve()
                if not sync_result['success']:
                    results['errors'].append(f"OntServe sync warning: {sync_result.get('error', 'Unknown')}")
                else:
                    results['ontserve_synced'] = True

            return results

        except Exception as e:
            logger.error(f"Error committing entities: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _record_ontology_commit(self, db, case_id: int, entities: list):
        """Record which OntServe ontology versions were current at commit time.

        Queries OntServe DB for current version info for each ontology target
        and creates CaseOntologyCommit records.
        """
        # Group entities by ontology target
        targets = {}
        for entity in entities:
            target = entity.ontology_target or 'unknown'
            targets.setdefault(target, 0)
            targets[target] += 1

        try:
            conn = psycopg2.connect(**get_ontserve_db_config())
            cur = conn.cursor()

            for ontology_name, count in targets.items():
                # Get current version info from OntServe
                cur.execute("""
                    SELECT v.id, v.version_tag
                    FROM ontology_versions v
                    JOIN ontologies o ON v.ontology_id = o.id
                    WHERE o.name = %s AND v.is_current = TRUE
                    LIMIT 1
                """, (ontology_name,))
                row = cur.fetchone()

                version_id = row[0] if row else None
                version_tag = row[1] if row else None

                commit_record = CaseOntologyCommit(
                    case_id=case_id,
                    ontology_name=ontology_name,
                    ontserve_version_id=version_id,
                    version_tag=version_tag,
                    entity_count=count
                )
                db.session.add(commit_record)

            cur.close()
            conn.close()
            logger.info(f"Recorded ontology commits for case {case_id}: {targets}")

        except Exception as e:
            logger.warning(f"Failed to record ontology version binding for case {case_id}: {e}")
            # Non-fatal -- the commit itself still succeeds

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
            for entity, rdf_data in classes:
                # Use entity attributes directly
                label = entity.entity_label or 'UnknownClass'
                # Sanitize label for valid URI: remove quotes, parens, and other special chars
                safe_label = label.replace(" ", "").replace("(", "").replace(")", "")
                safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")
                # Category-aware disambiguation: never mint a class IRI that the
                # immutable base reserves for a disjoint category (e.g. a Principle
                # onto proeth:ProfessionalCompetence, a base Capability).
                safe_label = self._category_safe_class_local(safe_label, self._get_concept_category(entity))
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

                # Check if class already exists
                if (class_uri, RDF.type, OWL.Class) in g:
                    # Accumulate: add new case's discoveredInCase and context
                    self._accumulate_class_context(g, class_uri, entity, rdf_data, PROETHICA_PROV)
                    # Reconcile subClassOf parents a prior commit may be missing --
                    # notably the occupational archetype on role classes minted
                    # before the resolver was wired. Additive only (archetype parents
                    # all chain to the same core class, so no disjointness risk).
                    for sc_uri in self._resolve_subclass_uris(entity, rdf_data):
                        if (class_uri, RDFS.subClassOf, URIRef(sc_uri)) not in g:
                            g.add((class_uri, RDFS.subClassOf, URIRef(sc_uri)))
                    continue

                # Add class triple
                g.add((class_uri, RDF.type, OWL.Class))
                g.add((class_uri, RDFS.label, Literal(label)))

                # Definitions: rdfs:comment + skos:definition (primary) and
                # skos:scopeNote (alternates), via the shared serializer that the
                # individual path also calls (single source of truth).
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

                    # Domain properties: everything the class card displays beyond the
                    # provenance keys handled above (e.g. valueBasis, obligationType,
                    # capabilityCategory, textReferences, confidence). The class
                    # serializer previously emitted only definitions + provenance, so
                    # the entire "Properties" column was dropped at commit. Emit each
                    # remaining key as a literal, mirroring the individual generic path
                    # (same _camelCase predicate convention) so the class round-trips.
                    for prop_name, prop_values in props.items():
                        if prop_name in self._PROV_PROP_KEYS:
                            continue
                        values = prop_values if isinstance(prop_values, list) else [prop_values]
                        prop_uri = PROETHICA[self._camelCase(prop_name)]
                        for value in values:
                            if value not in (None, '', [], {}):
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
            g.serialize(destination=extracted_file, format='turtle')
            logger.info(f"Committed {count} classes to {extracted_file}")

            # Update proethica-intermediate.ttl to import this file if not already
            self._ensure_import_statement()

            return {'count': count, 'file': str(extracted_file)}

        except Exception as e:
            logger.error(f"Error committing classes: {e}")
            return {'count': 0, 'error': str(e)}

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

    def _commit_individuals_to_case_ontology(self, case_id: int, individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit individuals to a case-specific ontology file.

        Creates proethica-case-N.ttl files that import from proethica-cases.
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Tracks the core category each invented class was first declared
            # subClassOf in this commit, so a class shared (incorrectly) across
            # disjoint categories does not accumulate two subClassOf-core edges
            # (which would make the case ontology OWL-DL inconsistent).
            class_core_category: Dict[str, str] = {}

            # Load existing graph or create new one
            g = Graph()
            if case_file.exists():
                g.parse(case_file, format='turtle')
            else:
                # Add ontology declaration for new case file
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                _title = self._case_title(case_id)
                if _title:
                    g.add((case_ontology_uri, DCTERMS.title, Literal(_title)))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/cases")))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            g.bind(f"case{case_id}", Namespace(f"http://proethica.org/ontology/case/{case_id}#"))
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("proeth-cases", PROETHICA_CASES)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)
            PROETHICA_PROV = Namespace("http://proethica.org/provenance#")
            g.bind("proeth-prov", PROETHICA_PROV)
            g.bind("dcterms", DCTERMS)

            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")

            # First pass: label -> individual URI index, so role relationship
            # targets (short actor names like "Engineer A") resolve to real edges
            # in _add_individual_properties. Mirrors _write_case_ttl_fresh.
            self._rel_label_index = {}
            for _ent, _rdf in individuals:
                _lbl = getattr(_ent, 'entity_label', None)
                if _lbl:
                    self._rel_label_index[self._norm_label(_lbl)] = case_ns[self._safe_label(_lbl)]
            # Append path only: also seed from individuals already on disk (the
            # loaded graph), so a later-section commit can still resolve targets
            # against actors an earlier-section commit wrote. The current batch
            # (authoritative fresh URIs) wins via setdefault. The versioned path
            # overwrites and has no prior graph, so it does not need this.
            for _s in g.subjects(RDF.type, OWL.NamedIndividual):
                for _lbl_lit in g.objects(_s, RDFS.label):
                    self._rel_label_index.setdefault(self._norm_label(str(_lbl_lit)), _s)

            # Agent layer (Option C): map each role facet to one proeth-core:Agent
            # per distinct actor (must precede the loop so the relationships branch
            # can attach actor relations at the Agent level).
            self._build_agent_indices(individuals, case_ns)

            count = 0
            for entity, rdf_data in individuals:
                extraction_type = entity.extraction_type or ''

                # Determine label - use short IDs for certain entity types
                # For types with dedicated property fields (focus, questionText, etc.), skip rdfs:comment
                if extraction_type == 'canonical_decision_point' and rdf_data and rdf_data.get('focus_id'):
                    # Use focus_id (e.g., "DP1") - full text goes in proeth:focus
                    label = rdf_data['focus_id']
                    full_description = None
                elif extraction_type in ('ethical_question', 'question_generated') and rdf_data and rdf_data.get('questionNumber'):
                    # Use Question_N - full text goes in proeth:questionText
                    label = f"Question_{rdf_data['questionNumber']}"
                    full_description = None
                elif extraction_type == 'ethical_conclusion' and rdf_data and rdf_data.get('conclusionNumber'):
                    # Use Conclusion_N - full text goes in proeth:conclusionText
                    label = f"Conclusion_{rdf_data['conclusionNumber']}"
                    full_description = None
                else:
                    label = entity.entity_label or 'UnknownIndividual'
                    full_description = None

                # Sanitize label for valid URI: remove quotes, parens, and other special
                # chars. Reified TemporalRelation / CausalChain individuals instead take
                # the opaque case#TemporalRelation_<n> / CausalChain_<n> URI from their @id
                # (rdfs:label stays readable).
                safe_label = self._opaque_reified_uri_local(rdf_data) or self._safe_label(label)
                individual_uri = case_ns[safe_label]

                # Check if individual already exists
                if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
                    # A same-label individual is already committed. If it is the SAME
                    # concept category (the same entity re-seen in another section),
                    # merge by skipping. If it is a DIFFERENT category (a genuine label
                    # collision -- e.g. an obligation and a capability that happen to
                    # share an entity_label), disambiguate the URI by category so the
                    # second individual is not silently dropped (display-to-RDF fidelity).
                    new_cat = self._get_concept_category(entity)
                    existing_cats = {str(o) for o in g.objects(individual_uri, PROETHICA['conceptCategory'])}
                    if new_cat and existing_cats and new_cat not in existing_cats:
                        disambiguated = case_ns[f"{safe_label}_{new_cat}"]
                        if (disambiguated, RDF.type, OWL.NamedIndividual) in g:
                            logger.info(f"Individual {label} ({new_cat}) already exists, skipping")
                            continue
                        logger.info(
                            f"Label collision for {label!r}: existing={sorted(existing_cats)} "
                            f"new={new_cat}; minting category-disambiguated URI "
                            f"{str(disambiguated).split('#')[-1]}")
                        individual_uri = disambiguated
                    else:
                        logger.info(f"Individual {label} already exists, skipping")
                        continue

                # Add individual as NamedIndividual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

                # Add full description if we used a short label
                if full_description:
                    g.add((individual_uri, RDFS.comment, Literal(full_description)))

                # Base concept category for this entity (from its extraction pass).
                concept_cat = self._get_concept_category(entity)
                # Authoritative category = the reasoner-visible type chain. Starts as
                # the extraction-pass category and is overridden below to an
                # established class's core category when the individual is typed to
                # one, so the conceptCategory literal we write cannot disagree with
                # the chain (the case-8 re-extraction inconsistency).
                resolved_cat = concept_cat

                # Add type based on the class from rdf_json_ld
                if rdf_data and rdf_data.get('types'):
                    for type_uri in rdf_data['types']:
                        # Extract class name from URI
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = class_name.replace(" ", "").replace("(", "").replace(")", "")
                        # Category-aware disambiguation (mirrors the class-commit
                        # path): a Principle individual must not be typed to an IRI
                        # the base reserves for a disjoint category. Disambiguating
                        # here and in _commit_classes_to_intermediate with the same
                        # rule keeps the individual's type IRI == the minted class IRI.
                        safe_class = self._category_safe_class_local(safe_class, concept_cat)
                        class_uri = PROETHICA[safe_class]
                        g.add((individual_uri, RDF.type, class_uri))
                        # Normalized D15 form: declare the type class IN THE CASE TTL only
                        # when it is genuinely new (not already in core/intermediate/extended).
                        # A class in the shared store is referenced by the rdf:type above and
                        # resolves through the case import plus the per-case validation patch;
                        # re-declaring it here is the ~4,800 redundant copies D15 removes
                        # (they were bare stubs anyway -- no subClassOf -- so dropping them
                        # loses no self-containment the case did not already lack).
                        # established != None => the class lives in the shared store.
                        established = self._established_core_category(safe_class)
                        if concept_cat:
                            if established is not None:
                                # Shared class. R1 self-contained-TTL (2026-06-04): declare its
                                # subClassOf-core IN THE CASE using the chain-authoritative
                                # `established` category (NOT the instance conceptCategory
                                # literal), so the persisted case validates standalone under
                                # Pellet/SHACL without the in-memory pellet_validate patch.
                                # Using `established` (the ontology's own parent) makes the
                                # triple identical to the one in the shared store: no second
                                # disjoint parent, and no self-loop (parent is a core class,
                                # never the class itself). This is what D15 deferred; emitting
                                # from `established` rather than the lie-prone literal is what
                                # makes it safe.
                                if established != concept_cat:
                                    logger.warning(
                                        "Class %s is established as %s in the ontology but an "
                                        "instance carries conceptCategory %s; keeping the "
                                        "ontology parent. Flagged for canonicalization.",
                                        safe_class, established, concept_cat,
                                    )
                                class_core_category[safe_class] = established
                                resolved_cat = established
                                g.add((class_uri, RDF.type, OWL.Class))
                                g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE[established]))
                            else:
                                # Genuinely-new (case-only) class: declare it locally with its
                                # subClassOf-core so the case stays self-validating.
                                g.add((class_uri, RDF.type, OWL.Class))
                                prior = class_core_category.get(safe_class)
                                if prior is None:
                                    class_core_category[safe_class] = concept_cat
                                    g.add((class_uri, RDFS.subClassOf, PROETHICA_CORE[concept_cat]))
                                elif prior != concept_cat:
                                    # Same fresh class IRI proposed under a second, disjoint
                                    # category in this commit (LLM naming collision the matcher
                                    # guard cannot catch). Keep the first; flag.
                                    logger.warning(
                                        "Class %s proposed under categories %s and %s in one "
                                        "commit; keeping %s, skipping conflicting subClassOf.",
                                        safe_class, prior, concept_cat, prior,
                                    )

                        # Layer-1 convergence: attach both archetype axes (occupational +
                        # relational) to a GENUINELY-NEW role class the individual is typed
                        # under. For an established role class the archetypes already live in
                        # intermediate, so skip (the normalized case does not re-declare shared
                        # classes). The axes are orthogonal (relational archetypes sit under
                        # RelationalRole), so the additive subClassOf carries no disjointness risk.
                        if established is None and self._is_role_individual(entity):
                            for arch_uri in self._role_individual_archetype_parents(rdf_data, class_name):
                                g.add((class_uri, RDF.type, OWL.Class))
                                if (class_uri, RDFS.subClassOf, URIRef(arch_uri)) not in g:
                                    g.add((class_uri, RDFS.subClassOf, URIRef(arch_uri)))

                # Tag with the resolved (chain-authoritative) concept category for
                # display grouping. Derived from the type chain so it cannot drift
                # from what the reasoner sees.
                if resolved_cat:
                    g.add((individual_uri, PROETHICA['conceptCategory'], Literal(resolved_cat)))

                # Per-individual property serialization. SINGLE shared serializer for
                # both commit paths (see _add_individual_properties): typed provenance,
                # the matcher XAI decision (D16), the definition (rdfs:comment +
                # skos:definition), the rich Step-4 synthesis handlers, the Step-3
                # temporal fields, and the Step-1/2 generic handler that turns
                # `attributes` into per-key triples and `relationships` into real
                # proeth-core actor edges (resolved via the _rel_label_index).
                self._add_individual_properties(g, individual_uri, entity, rdf_data, case_ns)

                # Commit-time generation marker. The extraction-time generatedAtTime
                # (from the extracted props) is emitted as prov:generatedAtTime by
                # _emit_provenance, so only wasGeneratedBy is added here to avoid a
                # second, conflicting prov:generatedAtTime value.
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Extraction")))

                # IAO document references
                if entity.iao_document_uri:
                    g.add((individual_uri, DCTERMS.references, URIRef(entity.iao_document_uri)))
                    if entity.iao_document_label:
                        g.add((individual_uri, PROETHICA_PROV.documentReference, Literal(entity.iao_document_label)))
                if entity.cited_by_role:
                    g.add((individual_uri, PROETHICA_PROV.citedByRole, Literal(entity.cited_by_role)))
                if entity.available_to_role:
                    g.add((individual_uri, PROETHICA_PROV.availableToRole, Literal(entity.available_to_role)))

                # Specific extraction model attribution
                if entity.extraction_model:
                    g.add((individual_uri, PROV.wasAttributedTo, Literal(entity.extraction_model)))

                count += 1

            # Emit the Agent layer (one proeth-core:Agent per actor + hasRole to
            # each role facet) once all facets have been written.
            self._emit_agent_layer(g)

            # Save the graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Committed {count} individuals to {case_file}")

            # Materialize the relational edge layer (defeasibility + R->P->O +
            # cites-provision) on the just-written TTL. The pipeline commit
            # previously emitted no edges (only the entity-review path did), so
            # re-extraction stripped them; routing through the shared helper
            # keeps both paths in lockstep. Best-effort: never fails the commit.
            try:
                from app.services.extraction.edge_materialization import materialize_edges_on_ttl
                edge_result = materialize_edges_on_ttl(case_id, case_file)
                logger.info(f"Edge materialization for case {case_id}: {edge_result}")
                self._record_edge_provenance(case_id, edge_result)
            except Exception as e:
                logger.exception(f"Edge materialization failed for case {case_id}: {e}")

            # The disk TTL -> OntServe DB sync is driven by the orchestrator
            # (commit_selected_entities), which runs after this returns so the
            # edge-bearing TTL is on disk before the version import.

            return {'count': count, 'file': str(case_file)}

        except Exception as e:
            logger.error(f"Error committing individuals: {e}")
            return {'count': 0, 'error': str(e)}

    def _ensure_import_statement(self):
        """
        Ensure proethica-intermediate.ttl imports the extracted file.

        This adds an owl:imports statement if not already present.
        """
        try:
            intermediate_file = self.ontologies_dir / "proethica-intermediate.ttl"
            if not intermediate_file.exists():
                logger.warning("proethica-intermediate.ttl not found")
                return

            # Check if import already exists
            with open(intermediate_file, 'r') as f:
                content = f.read()

            import_statement = "owl:imports <http://proethica.org/ontology/intermediate-extended> ;"

            if "intermediate-extended" not in content:
                # Add import statement after other imports
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'owl:imports' in line and 'proethica-core' in line:
                        # Insert after this line
                        lines.insert(i + 1, f"    {import_statement}")
                        break

                # Write back
                with open(intermediate_file, 'w') as f:
                    f.write('\n'.join(lines))

                logger.info("Added import statement for intermediate-extended to proethica-intermediate.ttl")

        except Exception as e:
            logger.error(f"Error ensuring import statement: {e}")

    def _sync_ontology_to_db(self, ontology_name: str) -> Dict[str, Any]:
        """Sync one disk TTL into the OntServe DB via tools/sync_ontology_to_db.py.

        That CLI wraps OntologySyncService._sync_single_ontology (the importer
        the web app runs on startup): it creates the Ontology record if missing,
        writes a new current ontology_versions row from the edge-bearing disk
        TTL, and re-extracts ontology_entities. --force is used so a committed
        TTL is imported even in the rare case its hash matched a prior version.

        Replaces the former subprocess refs to scripts/register_case_ontologies.py
        (never existed) and scripts/refresh_entity_extraction.py (relocated to
        tools/, and refreshed only the entity table, never the version content).
        """
        try:
            sync_script = self.ontserve_path / "tools" / "sync_ontology_to_db.py"
            if not sync_script.exists():
                return {'success': False, 'error': f'Sync script not found: {sync_script}'}

            result = subprocess.run(
                [self.ontserve_python, str(sync_script), ontology_name, "--force"],
                capture_output=True,
                text=True,
                cwd=str(self.ontserve_path),
                timeout=120,
            )
            if result.returncode != 0:
                logger.error(f"Sync of {ontology_name} failed: {result.stderr}")
                return {'success': False, 'error': result.stderr}

            logger.info(f"Synced {ontology_name} to OntServe DB: {result.stdout.strip()}")
            # Notify the MCP server to refresh its cache (optional).
            try:
                response = requests.post(f"{self.mcp_url}/refresh_cache")
                if response.status_code == 200:
                    logger.info("MCP server cache refreshed")
            except Exception:
                logger.debug("MCP server cache refresh failed (optional)", exc_info=True)
            return {'success': True, 'output': result.stdout}

        except subprocess.TimeoutExpired:
            logger.error(f"Sync of {ontology_name} timed out")
            return {'success': False, 'error': 'Sync timed out'}
        except Exception as e:
            logger.error(f"Error syncing {ontology_name} to OntServe DB: {e}")
            return {'success': False, 'error': str(e)}

    def _synchronize_with_ontserve(self) -> Dict[str, Any]:
        """Sync proethica-intermediate-extended.ttl (new classes) into the DB."""
        return self._sync_ontology_to_db("proethica-intermediate-extended")

    def _register_case_ontology(self, case_id: int) -> Dict[str, Any]:
        """Register + import a case ontology into the OntServe DB. The sync CLI
        auto-creates the ontology record, so registration and refresh are one
        operation."""
        return self._sync_ontology_to_db(f"proethica-case-{case_id}")

    def _refresh_case_ontology(self, case_id: int) -> Dict[str, Any]:
        """Re-import a case ontology's disk TTL into the OntServe DB."""
        return self._sync_ontology_to_db(f"proethica-case-{case_id}")

    # Maps extraction_type (or entity_type for temporal_dynamics) to:
    #   (category_field_name, CATEGORY_TO_ONTOLOGY_IRI key, fallback core class URI)
    # Multi-axis concepts (obligations, constraints) have a second entry for the
    # orthogonal axis (enforcement_level, flexibility).
    # Maps extraction_type (+ entity_type for temporal_dynamics) to the base
    # concept name used for display categorization in OntServe case views.
    _EXTRACTION_TO_CONCEPT = {
        'roles': 'Role',
        'principles': 'Principle',
        'obligations': 'Obligation',
        'states': 'State',
        'resources': 'Resource',
        'actions': 'Action',
        'events': 'Event',
        'capabilities': 'Capability',
        'constraints': 'Constraint',
    }

    def _get_concept_category(self, entity) -> str | None:
        """Derive base concept category from extraction_type/entity_type.

        Returns one of the 9 concept names (Role, Principle, ...) or None
        for non-concept entities (arguments, decision points, etc.).
        """
        ext_type = (entity.extraction_type or '').lower()

        # Direct match (steps 1-2)
        concept = self._EXTRACTION_TO_CONCEPT.get(ext_type)
        if concept:
            return concept

        # Step 3 temporal_dynamics: entity_type carries the concept
        if 'temporal_dynamics' in ext_type:
            etype = (entity.entity_type or '').lower().rstrip('s')
            for key, val in self._EXTRACTION_TO_CONCEPT.items():
                if key.startswith(etype):
                    return val

        return None

    _CONCEPT_CATEGORY_CONFIG = {
        'roles':        [('role_category',       'roles',                  f'{PROETHICA_CORE}Role')],
        'principles':   [('principle_category',  'principles',             f'{PROETHICA_CORE}Principle')],
        'obligations':  [('obligation_type',     'obligations',            f'{PROETHICA_CORE}Obligation'),
                         ('enforcement_level',   'obligation_enforcement', None)],
        'states':       [('state_category',      'states',                 f'{PROETHICA_CORE}State')],
        'resources':    [('resource_category',   'resources',              f'{PROETHICA_CORE}Resource')],
        'actions':      [('action_category',     'actions',                f'{PROETHICA_CORE}Action')],
        'events':       [('event_category',      'events',                 f'{PROETHICA_CORE}Event')],
        'capabilities': [('capability_category', 'capabilities',           f'{PROETHICA_CORE}Capability')],
        'constraints':  [('constraint_type',     'constraints',            f'{PROETHICA_CORE}Constraint'),
                         ('flexibility',         'constraint_flexibility', None)],
    }

    def _resolve_subclass_uris(self, entity, rdf_data: Dict) -> list[str]:
        """
        Resolve the rdfs:subClassOf target(s) for a class entity.

        Checks rdf_json_ld for category fields from the unified Pydantic schemas
        and looks them up in CATEGORY_TO_ONTOLOGY_IRI.  Falls back to the core
        concept class (e.g. proethica-core#Role) for legacy data without category.

        Multi-axis concepts (obligations, constraints) can produce two subclass
        URIs -- one per axis.
        """
        concept_type = (entity.extraction_type or '').lower()
        entity_type_lower = (entity.entity_type or '').lower()

        # For temporal_dynamics_enhanced, the entity_type carries the actual
        # concept (e.g. 'actions' or 'events') rather than extraction_type.
        if 'temporal_dynamics' in concept_type:
            key = entity_type_lower.rstrip('s') if entity_type_lower else concept_type
            # Normalize to plural form used in config
            for config_key in self._CONCEPT_CATEGORY_CONFIG:
                if config_key.startswith(key):
                    concept_type = config_key
                    break

        axes = self._CONCEPT_CATEGORY_CONFIG.get(concept_type)
        if not axes:
            # Unrecognized concept type -- try substring match for robustness
            for config_key, config_axes in self._CONCEPT_CATEGORY_CONFIG.items():
                if config_key in concept_type or config_key in entity_type_lower:
                    axes = config_axes
                    concept_type = config_key
                    break

        if not axes:
            logger.warning(f"No category config for extraction_type={entity.extraction_type}, "
                          f"entity_type={entity.entity_type}")
            return []

        result = []
        props = (rdf_data or {}).get('properties', {})

        for category_field, iri_map_key, fallback_uri in axes:
            # Check for category value in rdf_json_ld properties
            category_value = None
            if props:
                vals = props.get(category_field)
                if vals:
                    category_value = vals[0] if isinstance(vals, list) else vals
            # Also check top-level rdf_json_ld (unified extractor stores flat)
            if not category_value and rdf_data:
                category_value = rdf_data.get(category_field)

            if category_value:
                # Normalize enum value (Pydantic may store as 'provider_client' or 'ProviderClient')
                normalized = category_value.lower().replace(' ', '_').replace('-', '_')
                iri_map = CATEGORY_TO_ONTOLOGY_IRI.get(iri_map_key, {})
                iri = iri_map.get(normalized)
                if iri:
                    result.append(iri)
                elif fallback_uri:
                    result.append(fallback_uri)
            elif fallback_uri:
                # No category info (legacy data) -- use core class
                result.append(fallback_uri)

        # Occupational archetype axis for roles. The relational axis is handled above via
        # role_category; a role class chains through BOTH an occupational and a relational
        # archetype (multi-inheritance). The label carries the occupational signal. The
        # occupational archetype subClassOf*-chains to core:Role, so a bare core:Role
        # fallback becomes redundant and is dropped.
        if concept_type == 'roles':
            from app.services.extraction.role_archetype_resolver import resolve_occupational_archetype
            occ = resolve_occupational_archetype(entity.entity_label)
            if occ:
                core_role = f'{PROETHICA_CORE}Role'
                result = [r for r in result if r != core_role]
                if occ not in result:
                    result.append(occ)

        return result

    def _role_individual_archetype_parents(self, rdf_data: Dict, type_class_name: str) -> list[str]:
        """Occupational + relational archetype URIs for the class a role INDIVIDUAL
        is typed under.

        The matcher sometimes types a role individual under a compound class that
        diverges from its own role_class entity (the entity gets the archetype via
        _resolve_subclass_uris, but the individual's type is a different, often
        matched-existing, class). This attaches both archetype axes to the class the
        individual really bears: the occupational axis resolved from the
        (de-camelCased) type-class name, the relational axis from the individual's
        roleCategory. The two axes are orthogonal -- the relational archetypes sit
        under RelationalRole, decoupled from the ProfessionalRole/ParticipantRole
        disjointness -- so the additive subClassOf carries no disjointness risk."""
        import re
        parents: list[str] = []
        props = (rdf_data or {}).get('properties', {}) or {}
        rc = (props.get('roleCategory') or props.get('role_category')
              or (rdf_data or {}).get('role_category'))
        if isinstance(rc, list):
            rc = rc[0] if rc else None
        if rc:
            norm = str(rc).lower().replace(' ', '_').replace('-', '_')
            iri = CATEGORY_TO_ONTOLOGY_IRI.get('roles', {}).get(norm)
            if iri:
                parents.append(iri)
        from app.services.extraction.role_archetype_resolver import resolve_occupational_archetype
        label = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', type_class_name or '')
        occ = resolve_occupational_archetype(label)
        if occ and occ not in parents:
            parents.append(occ)
        return parents

    def _camelCase(self, text: str) -> str:
        """Convert a snake_case / spaced key to camelCase for a property local name.

        Delegates to the single shared converter (R3, app/utils/predicate_naming)
        so commit and storage cannot drift apart from the edge readers that hardcode
        these predicate names. Idempotent on an already-camelCase single token (the
        generic `properties` keys arrive already camelCase and must be preserved, not
        lowercased -- that was the `activePeriod` -> `activeperiod` mangling bug).
        """
        from app.utils.predicate_naming import to_camel_case
        return to_camel_case(text)

    # Synthesis / temporal individuals carry their text in dedicated predicates
    # (proeth:focus / questionText / conclusionText / description), so they are
    # skipped by the generic definition emitter to avoid a redundant comment.
    _DEF_SKIP_TYPES = frozenset({
        'argument_generated', 'argument_validation', 'canonical_decision_point',
        'ethical_conclusion', 'ethical_question',
    })

    # Matcher-provenance annotation properties (declared in proethica-provenance.ttl).
    _MATCH_ANNOTATION_PROPS = (
        'matchedOntologyClass', 'matchedOntologyLabel', 'matchConfidence',
        'matchesExisting', 'matchReasoning',
    )

    def _emit_definitions(self, g: Graph, subject_uri: URIRef, entity, rdf_data: Dict) -> None:
        """Emit rdfs:comment + skos:definition (primary) and skos:scopeNote
        (alternates) for a class OR an individual.

        Single source of truth for definition serialization, shared by the class
        path and the individual path so the two cannot drift. Individuals
        previously received no definition triple at all: their definition survived
        only when it happened to be duplicated into a `properties` key
        (caseInvolvement / usedInContext / subject), under a non-canonical
        predicate. This restores symmetry with the class path.
        """
        definitions = (rdf_data or {}).get('definitions', [])
        if definitions:
            primary = next((d for d in definitions if d.get('is_primary')), definitions[0])
            if primary.get('text'):
                g.add((subject_uri, RDFS.comment, Literal(primary['text'])))
                g.add((subject_uri, SKOS.definition, Literal(primary['text'])))
            for defn in definitions:
                if defn is primary:
                    continue
                text = defn.get('text', '')
                if not text:
                    continue
                # Tag the scope note with its source so the review UI and OntServe
                # both read "Inherited from <X>". Prefer the source CLASS (e.g.
                # EngineerRole, the matched parent whose definition this is) so the
                # specific class survives the commit, not just the source ontology.
                # Fall back to the section (a second extraction definition), then the
                # source ontology, then the type.
                src_uri = defn.get('source_uri')
                src_class = src_uri.rsplit('#', 1)[-1].rsplit('/', 1)[-1] if src_uri else None
                source_tag = src_class or defn.get('source_section') or defn.get('source_ontology') or defn.get('source_type', '')
                tagged_text = f"[{source_tag}] {text}" if source_tag else text
                g.add((subject_uri, SKOS.scopeNote, Literal(tagged_text)))
        elif getattr(entity, 'entity_definition', None):
            g.add((subject_uri, RDFS.comment, Literal(entity.entity_definition)))
            g.add((subject_uri, SKOS.definition, Literal(entity.entity_definition)))

    def _ensure_match_annotation_decls(self, g: Graph, prov_ns: Namespace) -> None:
        """Emit the owl:AnnotationProperty declarations for the matcher-provenance
        predicates inline into the graph. The Pellet harness loads only
        core+intermediate+case (not provenance), so the IRI-valued
        matchedOntologyClass must be declared an annotation property in the graph
        it reads, or it would be auto-typed an ObjectProperty (punning the target
        class as an individual). Idempotent."""
        for local in self._MATCH_ANNOTATION_PROPS:
            decl = (prov_ns[local], RDF.type, OWL.AnnotationProperty)
            if decl not in g:
                g.add(decl)

    def _emit_match_decision(self, g: Graph, subject_uri: URIRef, rdf_data: Dict,
                             prov_ns: Namespace) -> None:
        """Persist the extraction matcher's decision as XAI annotation provenance
        on the subject (individual or class): which canonical class it matched, the
        confidence, whether it reused an existing class, and the rationale. All
        owl:AnnotationProperty, so this records WHY the rdf:type was chosen without
        affecting OWL-DL reasoning."""
        md = (rdf_data or {}).get('match_decision')
        if not isinstance(md, dict):
            return
        self._ensure_match_annotation_decls(g, prov_ns)
        if 'matches_existing' in md:
            g.add((subject_uri, prov_ns['matchesExisting'],
                   Literal(bool(md['matches_existing']), datatype=XSD.boolean)))
        matched_uri = md.get('matched_uri')
        # Record only a canonical (shared-layer) class IRI; a per-case copy would
        # re-introduce the injection pollution the curated-vocabulary filter removed.
        if matched_uri and '/ontology/case/' not in str(matched_uri):
            g.add((subject_uri, prov_ns['matchedOntologyClass'], URIRef(matched_uri)))
        if md.get('matched_label'):
            g.add((subject_uri, prov_ns['matchedOntologyLabel'], Literal(md['matched_label'])))
        conf = md.get('confidence')
        if conf is not None:
            try:
                g.add((subject_uri, prov_ns['matchConfidence'],
                       Literal(float(conf), datatype=XSD.decimal)))
            except (TypeError, ValueError):
                pass
        if md.get('reasoning'):
            g.add((subject_uri, prov_ns['matchReasoning'], Literal(md['reasoning'])))

    # Provenance keys handled by _emit_provenance as typed prov:/proeth-prov:
    # triples. The generic property loops (class and individual) skip these so
    # they are not also emitted as untyped (and, pre-fix, lowercased) proeth:
    # literals -- the double-emission the individual path produced.
    _PROV_PROP_KEYS = frozenset({
        'generatedAtTime', 'wasAttributedTo', 'wasGeneratedBy',
        'firstDiscoveredInCase', 'firstDiscoveredAt', 'discoveredInCase',
        'discoveredInSection', 'discoveredInPass', 'sourceText',
    })

    def _emit_provenance(self, g: Graph, subject_uri: URIRef, rdf_data: Dict) -> None:
        """Typed PROV-O / proeth-prov provenance from the extracted properties,
        shared by the class and individual paths (single source of truth). The
        individual path previously emitted these via the generic loop as untyped,
        lowercased proeth: literals (e.g. proeth:generatedattime), duplicating and
        mismatching the typed triples the class path emits. Routing both paths
        through this helper de-duplicates and types them consistently. Also emits
        per-section sourceText so the facts and discussion snippets both survive
        (the top-level source_texts dict that previously collapsed to one literal).
        """
        PP = PROETHICA_PROV
        props = (rdf_data or {}).get('properties', {}) or {}

        for ts in (props.get('generatedAtTime') or []):
            try:
                clean = ts.replace('Z', '+00:00') if ts.endswith('Z') else ts
                g.add((subject_uri, PROV.generatedAtTime, Literal(datetime.fromisoformat(clean), datatype=XSD.dateTime)))
            except Exception as e:
                logger.warning(f"Could not parse generatedAtTime {ts}: {e}")
        for attribution in (props.get('wasAttributedTo') or []):
            g.add((subject_uri, PROV.wasAttributedTo, Literal(attribution)))
        if props.get('firstDiscoveredInCase'):
            g.add((subject_uri, PP.firstDiscoveredInCase, Literal(int(props['firstDiscoveredInCase'][0]), datatype=XSD.integer)))
        if props.get('firstDiscoveredAt'):
            ts = props['firstDiscoveredAt'][0]
            try:
                clean = ts.replace('Z', '+00:00') if ts.endswith('Z') else ts
                g.add((subject_uri, PP.firstDiscoveredAt, Literal(datetime.fromisoformat(clean), datatype=XSD.dateTime)))
            except Exception as e:
                logger.warning(f"Could not parse firstDiscoveredAt {ts}: {e}")
        for case_id_val in (props.get('discoveredInCase') or []):
            g.add((subject_uri, PP.discoveredInCase, Literal(int(case_id_val), datatype=XSD.integer)))
        if props.get('discoveredInSection'):
            g.add((subject_uri, PP.discoveredInSection, Literal(props['discoveredInSection'][0])))
        if props.get('discoveredInPass'):
            g.add((subject_uri, PP.discoveredInPass, Literal(int(props['discoveredInPass'][0]), datatype=XSD.integer)))

        # sourceText: the props value plus every distinct per-section snippet from
        # the top-level source_texts dict (section attribution is on discoveredInSection).
        emitted_src = set()
        st = props.get('sourceText')
        if st:
            val = st[0] if isinstance(st, list) else st
            if val:
                g.add((subject_uri, PP.sourceText, Literal(val)))
                emitted_src.add(str(val).strip())
        for _section, text in ((rdf_data or {}).get('source_texts', {}) or {}).items():
            if text and str(text).strip() not in emitted_src:
                g.add((subject_uri, PP.sourceText, Literal(text)))
                emitted_src.add(str(text).strip())

    def _emit_synthesis_literal_marker(self, g: Graph, subject_uri: URIRef,
                                       rdf_data: Dict, prov_ns: Namespace) -> None:
        """Mark which of an individual's literal fields are kept synthesis inputs
        (CONTENT / ASSESSMENT in field_classification) as opposed to structural relations,
        derived literals, or provenance. Emitted as an owl:AnnotationProperty
        (proeth-prov:synthesisLiteral, one value per kept-literal local name), so the
        triple-vs-literal distinction is captured in the committed provenance and the
        synthesis layer can collect the kept literals by query rather than re-deriving the
        classification. Pellet-neutral (annotation property, like the matcher decision)."""
        from app.services.extraction.field_classification import synthesis_literals, _normalize
        # Predicate names this individual carries, across the two storage shapes:
        # pass-1/2 keep them under 'properties'; temporal keeps proeth: keys at top level.
        preds = list(((rdf_data or {}).get('properties', {}) or {}).keys())
        preds += [k for k in (rdf_data or {}).keys() if isinstance(k, str) and k.startswith('proeth:')]
        kept = synthesis_literals(preds)
        if not kept:
            return
        decl = (prov_ns['synthesisLiteral'], RDF.type, OWL.AnnotationProperty)
        if decl not in g:
            g.add(decl)
        emitted = set()
        for p in kept:
            local = _normalize(p)
            if local and local not in emitted:
                g.add((subject_uri, prov_ns['synthesisLiteral'], Literal(local)))
                emitted.add(local)

    def get_commit_status(self, case_id: int) -> Dict[str, Any]:
        """
        Get the commit status for a case.

        Returns information about what has been committed and what's pending.
        """
        try:
            # Count draft (unpublished) entities
            pending = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=False
            ).count()

            # Count published entities
            committed = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_published=True
            ).count()

            # Check if case ontology exists
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            case_ontology_exists = case_file.exists()

            return {
                'pending_count': pending,
                'committed_count': committed,
                'case_ontology_exists': case_ontology_exists,
                'case_ontology_file': str(case_file) if case_ontology_exists else None
            }

        except Exception as e:
            logger.error(f"Error getting commit status: {e}")
            return {
                'error': str(e)
            }

    # ========== VERSIONED COMMIT METHODS ==========

    def commit_case_versioned(self, case_id: int, entity_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Commit entities with versioning support.

        This method:
        1. Marks existing OntServe concepts for this case as superseded (is_current=false)
        2. Creates new concept records with incremented extraction_run_version
        3. OVERWRITES the case TTL file (no merging)
        4. For classes, creates individual class versions

        Args:
            case_id: The case ID
            entity_ids: Optional list of specific entity IDs to commit. If None, commits all.

        Returns:
            Dictionary with commit results including version info
        """
        try:
            # Fetch entities to commit
            if entity_ids:
                entities = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.id.in_(entity_ids),
                    TemporaryRDFStorage.case_id == case_id
                ).all()
            else:
                # Commit all entities for this case
                entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

            if not entities:
                return {
                    'success': False,
                    'error': 'No entities found to commit'
                }

            # Separate classes and individuals
            classes_to_commit = []
            individuals_to_commit = []

            for entity in entities:
                rdf_data = entity.rdf_json_ld if entity.rdf_json_ld else {}
                if entity.storage_type == 'class':
                    classes_to_commit.append((entity, rdf_data))
                elif entity.storage_type == 'individual':
                    individuals_to_commit.append((entity, rdf_data))

            results = {
                'success': True,
                'case_id': case_id,
                'classes_committed': 0,
                'individuals_committed': 0,
                'versions_superseded': 0,
                'new_version': None,
                'errors': []
            }

            # Connect to OntServe database
            conn = psycopg2.connect(**get_ontserve_db_config())
            try:
                # Get the next extraction run version for this case
                new_version = self._get_next_extraction_version(conn, case_id)
                results['new_version'] = new_version

                # Supersede existing current versions for this case
                superseded = self._supersede_case_versions(conn, case_id)
                results['versions_superseded'] = superseded

                # Commit individuals to OntServe concepts table
                if individuals_to_commit:
                    ind_result = self._commit_individuals_versioned(
                        conn, case_id, new_version, individuals_to_commit
                    )
                    results['individuals_committed'] = ind_result['count']
                    if ind_result.get('error'):
                        results['errors'].append(ind_result['error'])

                # Commit classes with individual versioning
                if classes_to_commit:
                    class_result = self._commit_classes_versioned(
                        conn, case_id, new_version, classes_to_commit
                    )
                    results['classes_committed'] = class_result['count']
                    results['class_versions_created'] = class_result.get('versions_created', 0)
                    if class_result.get('error'):
                        results['errors'].append(class_result['error'])

                conn.commit()

            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()

            # Write TTL files (overwrites existing)
            if individuals_to_commit:
                ttl_result = self._write_case_ttl_fresh(case_id, individuals_to_commit)
                if ttl_result.get('error'):
                    results['errors'].append(ttl_result['error'])
                results['ttl_file'] = ttl_result.get('file')

                # Materialize the relational edge layer on the FINAL TTL (this is
                # the persisted writer for the versioned path). Shared helper, so
                # it stays in lockstep with the pipeline commit. Best-effort.
                if ttl_result.get('file'):
                    try:
                        from app.services.extraction.edge_materialization import materialize_edges_on_ttl
                        edge_result = materialize_edges_on_ttl(case_id, ttl_result['file'])
                        logger.info(f"Edge materialization for case {case_id}: {edge_result}")
                        self._record_edge_provenance(case_id, edge_result)
                    except Exception as e:
                        logger.exception(f"Edge materialization failed for case {case_id}: {e}")

            if classes_to_commit:
                # For classes, we still append to intermediate-extended.ttl
                # but with version metadata
                class_ttl_result = self._commit_classes_to_intermediate(classes_to_commit)
                if class_ttl_result.get('error'):
                    results['errors'].append(class_ttl_result['error'])

            # Mark entities as published in ProEthica
            for entity in entities:
                entity.is_published = True

            from app import db
            db.session.commit()

            # Sync the edge-bearing disk TTL -> OntServe DB (single call:
            # create-if-new + new version + entity re-extract).
            if individuals_to_commit:
                sync_result = self._sync_ontology_to_db(f"proethica-case-{case_id}")
                if sync_result.get('success'):
                    results['ontserve_synced'] = True
                else:
                    results['errors'].append(f"OntServe sync warning: {sync_result.get('error')}")

            logger.info(f"Versioned commit for case {case_id}: v{new_version}, "
                       f"{results['individuals_committed']} individuals, "
                       f"{results['classes_committed']} classes")

            return results

        except Exception as e:
            logger.error(f"Error in versioned commit: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _get_next_extraction_version(self, conn, case_id: int) -> int:
        """Get the next extraction run version for a case."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(extraction_run_version), 0) + 1
                FROM concepts
                WHERE case_id = %s
            """, (case_id,))
            result = cur.fetchone()
            return result[0] if result else 1

    def _supersede_case_versions(self, conn, case_id: int) -> int:
        """Mark all current versions for a case as superseded."""
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE concepts
                SET is_current = false,
                    superseded_at = %s
                WHERE case_id = %s AND is_current = true
            """, (datetime.now(timezone.utc), case_id))
            return cur.rowcount

    def _commit_individuals_versioned(self, conn, case_id: int, version: int,
                                      individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """Commit individuals to OntServe concepts table with versioning."""
        try:
            count = 0
            with conn.cursor() as cur:
                # Get domain ID for engineering-ethics
                cur.execute("SELECT id FROM domains WHERE name = 'engineering-ethics'")
                domain_row = cur.fetchone()
                domain_id = domain_row[0] if domain_row else None

                for entity, rdf_data in individuals:
                    label = entity.entity_label or 'UnknownIndividual'
                    safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
                    safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                    safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")

                    uri = f"http://proethica.org/ontology/case/{case_id}#{safe_label}"

                    cur.execute("""
                        INSERT INTO concepts (
                            uuid, domain_id, uri, label, primary_type, description,
                            status, case_id, extraction_run_version, is_current,
                            entity_class, extraction_method, source_document,
                            confidence_score, created_by, metadata
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, %s, %s, %s,
                            'candidate', %s, %s, true,
                            'individual', 'llm_extraction', %s,
                            %s, 'proethica-pipeline', %s
                        )
                    """, (
                        domain_id,
                        uri,
                        label,
                        entity.extraction_type or 'Unknown',
                        entity.entity_definition,
                        case_id,
                        version,
                        f'case:{case_id}',
                        0.7,  # Default confidence
                        Json(rdf_data or {})
                    ))
                    count += 1

            return {'count': count}

        except Exception as e:
            logger.error(f"Error committing individuals versioned: {e}")
            return {'count': 0, 'error': str(e)}

    def _commit_classes_versioned(self, conn, case_id: int, version: int,
                                  classes: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit classes with individual versioning.

        If a class already exists (by URI), creates a new version entry.
        If new, creates the class as current version.
        """
        try:
            count = 0
            versions_created = 0

            with conn.cursor() as cur:
                # Get domain ID
                cur.execute("SELECT id FROM domains WHERE name = 'engineering-ethics'")
                domain_row = cur.fetchone()
                domain_id = domain_row[0] if domain_row else None

                for entity, rdf_data in classes:
                    label = entity.entity_label or 'UnknownClass'
                    safe_label = label.replace(" ", "").replace("(", "").replace(")", "")
                    safe_label = safe_label.replace('"', '').replace("'", "").replace(",", "")
                    safe_label = safe_label.replace("<", "").replace(">", "").replace("&", "")
                    # Category-aware disambiguation (same rule as the TTL commit paths).
                    safe_label = self._category_safe_class_local(safe_label, self._get_concept_category(entity))

                    uri = f"http://proethica.org/ontology/intermediate#{safe_label}"

                    # Check if class already exists
                    cur.execute("""
                        SELECT id, version_number FROM concepts
                        WHERE uri = %s AND entity_class = 'class' AND is_current = true
                    """, (uri,))
                    existing = cur.fetchone()

                    if existing:
                        # Class exists - create version history and update
                        concept_id, old_version = existing

                        # Create version entry for the old version
                        cur.execute("""
                            INSERT INTO concept_versions (
                                concept_id, version_number, uri, label, semantic_label,
                                primary_type, description, status, metadata,
                                changed_fields, change_reason, changed_by
                            )
                            SELECT id, version_number, uri, label, semantic_label,
                                   primary_type, description, status, metadata,
                                   %s, %s, %s
                            FROM concepts WHERE id = %s
                        """, (
                            Json(['description', 'case_id']),
                            f'Re-extracted from case {case_id}',
                            'proethica-pipeline',
                            concept_id
                        ))

                        # Update existing concept with new version
                        cur.execute("""
                            UPDATE concepts
                            SET description = %s,
                                version_number = version_number + 1,
                                case_id = %s,
                                extraction_run_version = %s,
                                updated_at = %s,
                                updated_by = 'proethica-pipeline',
                                metadata = %s
                            WHERE id = %s
                        """, (
                            entity.entity_definition,
                            case_id,
                            version,
                            datetime.now(timezone.utc),
                            Json(rdf_data or {}),
                            concept_id
                        ))
                        versions_created += 1
                    else:
                        # New class - create fresh
                        cur.execute("""
                            INSERT INTO concepts (
                                uuid, domain_id, uri, label, primary_type, description,
                                status, case_id, extraction_run_version, is_current,
                                entity_class, extraction_method, source_document,
                                created_by, metadata
                            )
                            VALUES (
                                gen_random_uuid(), %s, %s, %s, %s, %s,
                                'candidate', %s, %s, true,
                                'class', 'llm_extraction', %s,
                                'proethica-pipeline', %s
                            )
                        """, (
                            domain_id,
                            uri,
                            label,
                            entity.extraction_type or 'Unknown',
                            entity.entity_definition,
                            case_id,
                            version,
                            f'case:{case_id}',
                            Json(rdf_data or {})
                        ))

                    count += 1

            return {'count': count, 'versions_created': versions_created}

        except Exception as e:
            logger.error(f"Error committing classes versioned: {e}")
            return {'count': 0, 'error': str(e)}

    def _write_case_ttl_fresh(self, case_id: int, individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Write a fresh case TTL file (overwrites any existing file).

        This is the versioned approach - each extraction completely replaces the previous TTL.
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Create new graph (don't load existing)
            g = Graph()

            # Add ontology declaration
            case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
            g.add((case_ontology_uri, RDF.type, OWL.Ontology))
            g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
            _title = self._case_title(case_id)
            if _title:
                g.add((case_ontology_uri, DCTERMS.title, Literal(_title)))
            g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/cases")))
            g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
            g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.now(timezone.utc))))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("proeth-cases", PROETHICA_CASES)
            g.bind("bfo", BFO)
            g.bind("iao", IAO)
            g.bind("prov", PROV)

            # Label -> individual URI index (first pass) so role relationship targets,
            # which are short actor names like "Engineer A", resolve to real edges.
            self._rel_label_index = {}
            for _ent, _rdf in individuals:
                _lbl = getattr(_ent, 'entity_label', None)
                if _lbl:
                    self._rel_label_index[self._norm_label(_lbl)] = case_ns[self._safe_label(_lbl)]

            # Agent layer (Option C): one proeth-core:Agent per distinct actor.
            self._build_agent_indices(individuals, case_ns)

            count = 0
            for entity, rdf_data in individuals:
                # Use the existing individual serialization logic
                extraction_type = entity.extraction_type or ''

                # Determine label
                if extraction_type == 'canonical_decision_point' and rdf_data and rdf_data.get('focus_id'):
                    label = rdf_data['focus_id']
                elif extraction_type in ('ethical_question', 'question_generated') and rdf_data and rdf_data.get('questionNumber'):
                    label = f"Question_{rdf_data['questionNumber']}"
                elif extraction_type == 'ethical_conclusion' and rdf_data and rdf_data.get('conclusionNumber'):
                    label = f"Conclusion_{rdf_data['conclusionNumber']}"
                else:
                    label = entity.entity_label or 'UnknownIndividual'

                # Reified TemporalRelation / CausalChain individuals get the opaque
                # case#TemporalRelation_<n> / CausalChain_<n> URI (rdfs:label keeps the
                # readable text); every other individual mints from its label.
                safe_label = self._opaque_reified_uri_local(rdf_data) or self._safe_label(label)
                individual_uri = case_ns[safe_label]

                # Add individual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

                # Add type based on rdf_json_ld types
                if rdf_data and rdf_data.get('types'):
                    for type_uri in rdf_data['types']:
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = class_name.replace(" ", "").replace("(", "").replace(")", "")
                        # Category-aware disambiguation (same rule as the append +
                        # class-commit paths): never type to an IRI the base reserves
                        # for a disjoint category.
                        safe_class = self._category_safe_class_local(safe_class, self._get_concept_category(entity))
                        class_uri = PROETHICA[safe_class]
                        g.add((individual_uri, RDF.type, class_uri))
                        # Layer-1 convergence: both archetype axes on the
                        # individual's own type-class (see
                        # _commit_individuals_to_case_ontology).
                        if self._is_role_individual(entity):
                            for arch_uri in self._role_individual_archetype_parents(rdf_data, class_name):
                                g.add((class_uri, RDF.type, OWL.Class))
                                if (class_uri, RDFS.subClassOf, URIRef(arch_uri)) not in g:
                                    g.add((class_uri, RDFS.subClassOf, URIRef(arch_uri)))

                # Tag with base concept category for display grouping
                concept_cat = self._get_concept_category(entity)
                if concept_cat:
                    g.add((individual_uri, PROETHICA['conceptCategory'], Literal(concept_cat)))

                # Add type-specific properties (reuse existing logic)
                self._add_individual_properties(g, individual_uri, entity, rdf_data, case_ns)

                # Commit-time marker only; extraction-time prov:generatedAtTime is
                # emitted by _emit_provenance (inside _add_individual_properties).
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Extraction")))

                count += 1

            # Emit the Agent layer (one proeth-core:Agent per actor + hasRole).
            self._emit_agent_layer(g)

            # Write file (overwrites existing)
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Wrote fresh TTL file with {count} individuals to {case_file}")

            return {'count': count, 'file': str(case_file)}

        except Exception as e:
            logger.error(f"Error writing fresh case TTL: {e}")
            return {'count': 0, 'error': str(e)}

    def _safe_label(self, label: str) -> str:
        """URI-safe local name from a label (single source of truth for minting
        individual URIs and for the relationship target index)."""
        s = (label or '').replace(" ", "_").replace("(", "").replace(")", "")
        s = s.replace('"', '').replace("'", "").replace(",", "")
        s = s.replace("<", "").replace(">", "").replace("&", "")
        return s

    # Reified nodes whose identity should be OPAQUE (the W3C n-ary-relations
    # convention -- "Purchase_1", not the participant prose), keyed to the local-name
    # prefix their extraction-time @id carries. A TemporalRelation reifies an Allen
    # interval relation; a CausalChain reifies a cause/effect link. Both formerly took
    # their committed URI from a concatenated entity_label
    # (AllenRelation_<from>_<rel>_<to>, or "cause -> effect" with a raw arrow), which
    # produced 90-140 char IRIs; the opaque @id was minted by rdf_converter but ignored
    # at commit.
    _OPAQUE_REIFIED_PREFIXES = {
        'proeth:TemporalRelation': 'TemporalRelation_',
        'proeth:CausalChain': 'CausalChain_',
    }

    # Controlled professional-attribute vocabulary (Part B). The LLM places free-form
    # keys in a role's `attributes` dict; map the recurring ones (lowercased) to the
    # declared proeth: datatype properties so cross-case queries (e.g. all licensed PEs)
    # work. Unmapped keys are kept verbatim (camelCased) and logged, so the uncontrolled
    # tail is visible and the vocabulary can grow deliberately rather than silently.
    _ATTRIBUTE_VOCAB = {
        'license': 'hasLicense', 'licensure': 'hasLicense', 'licensestatus': 'hasLicense',
        'licensed': 'hasLicense', 'professionallicense': 'hasLicense', 'licensing': 'hasLicense',
        'specialty': 'hasSpecialty', 'specialization': 'hasSpecialty',
        'specialisation': 'hasSpecialty', 'specialties': 'hasSpecialty',
        'experience': 'experienceLevel', 'yearsofexperience': 'experienceLevel',
        'experiencelevel': 'experienceLevel', 'yearsexperience': 'experienceLevel',
        'employer': 'hasEmployer', 'employedby': 'hasEmployer', 'employment': 'hasEmployer',
        'jurisdiction': 'hasJurisdiction',
        'registration': 'registrationStatus', 'registrationstatus': 'registrationStatus',
        'position': 'roleInOrganization', 'roleinorganization': 'roleInOrganization',
        'technicalbackground': 'technicalBackground',
        # role-nature descriptors (the kind of actor: "Affected public", "Manufacturing
        # corporation", "Private development entity")
        'type': 'roleNature', 'entitytype': 'roleNature', 'roletype': 'roleNature',
        'rolenature': 'roleNature', 'nature': 'roleNature',
    }

    @classmethod
    def _opaque_reified_uri_local(cls, rdf_data) -> str | None:
        """Opaque local name (e.g. TemporalRelation_<n> / CausalChain_<n>) for a
        reified relation/causal node, read from its extraction-time @id (minted by
        rdf_converter in extraction order). Returns None for any other individual, so
        the caller mints the URI from the label as usual; also None for legacy rows
        whose @id still carries the old concatenated-prose form, which then fall back
        to _safe_label. rdfs:label is unaffected -- it keeps the readable text (the
        "X relation Y" / "cause -> effect" phrasing). The reified node's participants
        live as properties resolved post-commit (temporal_relation_edges / causal_edges),
        not in the IRI."""
        if not rdf_data:
            return None
        prefix = cls._OPAQUE_REIFIED_PREFIXES.get(rdf_data.get('@type'))
        if not prefix:
            return None
        frag = str(rdf_data.get('@id', '')).split('#')[-1]
        return frag if frag.startswith(prefix) else None

    @staticmethod
    def _norm_label(label: str) -> str:
        return ' '.join((label or '').lower().split())

    # LLM relationship type -> proeth-core actor relation; relatedTo is the fallback.
    # Ordered: the passive/subject review forms (the role-bearer whose work is
    # reviewed) must precede the generic 'review' needle, otherwise substring
    # matching would route them to reviewsWorkOf and assert the edge backwards.
    # (substring needle, proeth-core property, swap). The proeth-core actor
    # properties hasClient/employedBy/workReviewedBy are DIRECTIONAL, but the LLM
    # emits a relationship from each role-bearer's own perspective, so the same
    # edge is seen from both endpoints. `swap` records which perspective a needle
    # encodes: swap=False means the role-bearer is the subject of the property
    # (provider / employee / reviewed party); swap=True means it is the object
    # (client naming its provider, employer naming its employee), so the edge is
    # asserted target->subject. Ordered most-specific-first: directional and
    # passive forms precede their generic stems so substring matching neither
    # mis-routes nor mis-orients them.
    _REL_TYPE_TO_PROP = (
        ('has_provider', 'hasClient', True),
        ('has provider', 'hasClient', True),
        ('is_client_of', 'hasClient', True),
        ('client_of', 'hasClient', True),
        ('has_client', 'hasClient', False),
        ('has client', 'hasClient', False),
        ('provider_of', 'hasClient', False),
        ('retained_by', 'hasClient', False),
        ('retained by', 'hasClient', False),
        ('employer_of', 'employedBy', True),
        ('employs', 'employedBy', True),
        ('employed_by', 'employedBy', False),
        ('employed by', 'employedBy', False),
        ('employ', 'employedBy', False),
        ('subject_of_review', 'workReviewedBy', False),
        ('subject of review', 'workReviewedBy', False),
        ('reviewed_by', 'workReviewedBy', False),
        ('reviewed by', 'workReviewedBy', False),
        ('being_reviewed', 'workReviewedBy', False),
        ('being reviewed', 'workReviewedBy', False),
        ('reviewee', 'workReviewedBy', False),
        ('reviewer_of', 'reviewsWorkOf', False),
        ('reviews', 'reviewsWorkOf', False),
        ('review', 'reviewsWorkOf', False),
        ('peer', 'professionalPeerOf', False),
        ('client', 'hasClient', False),
    )

    def _rel_property_for(self, rel_type: str):
        """(proeth-core property, swap) for an LLM relationship type. swap=True
        means the edge is asserted target->subject (the role-bearer is on the
        receiving side of a directional relation). professionalPeerOf is symmetric,
        so swap is immaterial there. relatedTo is the controlled fallback."""
        t = (rel_type or '').lower()
        for needle, prop, swap in self._REL_TYPE_TO_PROP:
            if needle in t:
                return prop, swap
        return 'relatedTo', False

    def _resolve_rel_target(self, target: str):
        """Resolve an actor-relationship target label to a case individual URI via
        the first-pass index. Actor relationships hold between role-bearers, so a
        role facet (a key of _facet_to_agent) is always preferred over a same-named
        non-role individual; otherwise a bare actor name like "Owner" can substring
        -match a non-role node (e.g. an action "Owner Covert Review Instruction").
        Match tiers: exact, then prefix/substring. Returns the URI or None."""
        index = getattr(self, '_rel_label_index', None)
        if not index or not target:
            return None
        nt = self._norm_label(target)
        role_facets = set(getattr(self, '_facet_to_agent', {}) or {})

        def _pick(cands):
            cands = sorted(set(cands), key=str)
            role_cands = [u for u in cands if u in role_facets]
            return role_cands[0] if role_cands else (cands[0] if cands else None)

        exact = _pick([uri for nl, uri in index.items() if nl == nt])
        if exact is not None:
            return exact
        return _pick([uri for nl, uri in index.items() if nl.startswith(nt) or nt in nl])

    def _target_agent(self, g: Graph, facet_to_agent: dict, tgt_uri):
        """Agent URI for a resolved relationship target, or None when the target is
        not a role-bearer. Actor relations hold between role-bearers, so a target
        that resolved to a non-role node (an Action/State/Event that happened to
        substring-match a bare actor name) must NOT receive an actor edge. Checks
        the current batch's facet->Agent map, then on-disk role facets (objects of
        core:hasRole) so the section-by-section append path still resolves an actor
        an earlier-section commit wrote."""
        agent = facet_to_agent.get(tgt_uri)
        if agent is not None:
            return agent
        for ag in g.subjects(PROETHICA_CORE.hasRole, tgt_uri):
            return ag
        return None

    # --- Agent layer (Option C: cross-section actor identity) -----------------
    # A role facet (e.g. "Engineer A Original Design Engineer" in facts,
    # "Cooperation-Refusing Design Engineer" in discussion) is a role the same
    # underlying actor bears. We mint ONE proeth-core:Agent per distinct actor
    # and link each facet to it via proeth-core:hasRole, so the actor is not
    # fragmented across sections. The actor identity is the LLM-declared `actor`
    # field (rules-as-data); when absent it falls back to the facet's own label
    # (so every role still gets an Agent, but only a shared `actor` merges
    # facets). The Agent URI is deterministic from the actor label, so separate
    # section commits on the append path converge on the same Agent node.

    @staticmethod
    def _is_role_individual(entity) -> bool:
        return (getattr(entity, 'extraction_type', '') or '').lower() == 'roles'

    def _actor_key_and_label(self, entity, rdf_data: Dict):
        """(normalized key, display label) of a role individual's underlying
        actor, or (None, None) if it cannot be determined."""
        props = (rdf_data or {}).get('properties', {}) or {}
        actor_vals = props.get('actor')
        actor = None
        if actor_vals:
            actor = actor_vals[0] if isinstance(actor_vals, list) else actor_vals
        if not actor:
            actor = getattr(entity, 'entity_label', None)
        if not actor:
            return None, None
        return self._norm_label(str(actor)), str(actor)

    def _build_agent_indices(self, individuals, case_ns: Namespace) -> None:
        """First-pass build of the Agent layer maps over the batch:
        - self._agent_index: actor_key -> Agent URI
        - self._facet_to_agent: role-facet URI -> Agent URI
        - self._agent_facets: Agent URI -> (actor_label, set(facet URIs))
        Used by _emit_agent_layer (mints the Agents + hasRole) and by the
        relationships branch (attaches actor relations at the Agent level)."""
        self._agent_index = {}
        self._facet_to_agent = {}
        self._agent_facets = {}
        for _ent, _rdf in individuals:
            if not self._is_role_individual(_ent):
                continue
            akey, alabel = self._actor_key_and_label(_ent, _rdf)
            if not akey:
                continue
            facet_uri = case_ns[self._safe_label(getattr(_ent, 'entity_label', '') or '')]
            agent_uri = self._agent_index.get(akey)
            if agent_uri is None:
                agent_uri = case_ns['Agent_' + self._safe_label(alabel)]
                self._agent_index[akey] = agent_uri
                self._agent_facets[agent_uri] = (alabel, set())
            self._facet_to_agent[facet_uri] = agent_uri
            self._agent_facets[agent_uri][1].add(facet_uri)

    def _emit_agent_layer(self, g: Graph) -> None:
        """Emit one proeth-core:Agent per distinct actor and a hasRole edge to
        each role facet it bears. Idempotent: re-emitting the same Agent URI on a
        later-section append commit just re-asserts the same triples."""
        for agent_uri, (alabel, facet_uris) in getattr(self, '_agent_facets', {}).items():
            g.add((agent_uri, RDF.type, OWL.NamedIndividual))
            g.add((agent_uri, RDF.type, PROETHICA_CORE.Agent))
            g.add((agent_uri, RDFS.label, Literal(alabel)))
            for f in sorted(facet_uris):
                g.add((agent_uri, PROETHICA_CORE.hasRole, f))

    @staticmethod
    def _safe_frag(iri) -> str:
        """Sanitized local name of an IRI, for building a derived provenance-node
        fragment (mirrors defeasibility_pipeline._safe_frag)."""
        frag = str(iri).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
        return ''.join(c if c.isalnum() or c in '_-' else '_' for c in frag)[:60]

    def _emit_relationship_provenance(self, g: Graph, case_ns: Namespace, subj,
                                      relprop: str, obj, rtype, quote) -> None:
        """PROV-O Derivation for an actor relationship edge, mirroring the
        defeasibility-edge provenance: a prov:Derivation node linking the two
        endpoints, carrying the triggering quote in prov:value when the roles
        prompt supplied one. Best-effort and additive; never blocks the edge."""
        try:
            frag = f"{self._safe_frag(subj)}_{relprop}_{self._safe_frag(obj)}"
            prov_iri = case_ns['relationship_edge_provenance_' + frag]
            # Idempotent: the prov-node IRI is deterministic from (subj, relprop,
            # obj), and the same actor edge is emitted once per facet the actor
            # bears (and again on a re-commit). Emit the node once; re-emission
            # would otherwise multi-value generatedAtTime / comment / value.
            if (prov_iri, RDF.type, PROV.Derivation) in g:
                return
            g.add((prov_iri, RDF.type, PROV.Derivation))
            g.add((prov_iri, PROV.wasDerivedFrom, subj))
            g.add((prov_iri, PROV.wasDerivedFrom, obj))
            g.add((prov_iri, RDFS.label, Literal(f"Actor relationship edge ({rtype or relprop})")))
            if quote:
                g.add((prov_iri, PROV.value, Literal(str(quote))))
            g.add((prov_iri, RDFS.comment, Literal(f"relation_type={rtype}; property={relprop}")))
            g.add((prov_iri, PROV.generatedAtTime, Literal(
                datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))
        except Exception as e:
            logger.info(f"relationship provenance skipped: {e}")

    def _add_individual_properties(self, g: Graph, uri: URIRef, entity: Any,
                                   rdf_data: Dict, case_ns: Namespace):
        """Add type-specific properties to an individual in the graph.

        SINGLE per-individual serializer shared by BOTH commit paths: the live
        append path (`_commit_individuals_to_case_ontology`, used by the pipeline
        / staged re-extraction / entity-review commit) and the versioned path
        (`_write_case_ttl_fresh`). It is the union of what the two paths had
        drifted into emitting separately: the rich Step-4 synthesis handlers
        (arguments, validations, decision points, conclusions, questions) AND the
        Step-1/2 generic handler that turns `attributes` into per-key triples and
        `relationships` into real proeth-core actor edges (resolved via
        `_rel_label_index`). Keeping one serializer is what stops the two paths
        re-drifting; do not reintroduce an inline copy in either caller.
        """
        extraction_type = entity.extraction_type or ''

        # Universal per-individual serialization. Lives here (not in a caller) so
        # BOTH commit paths -- the append path (_commit_individuals_to_case_ontology)
        # and the versioned path (_write_case_ttl_fresh) -- emit them identically:
        # typed provenance, the matcher XAI decision (D16), and the definition
        # (rdfs:comment + skos:definition, symmetric with the class path; gated for
        # the synthesis/temporal types that carry their text in dedicated predicates).
        self._emit_provenance(g, uri, rdf_data)
        self._emit_match_decision(g, uri, rdf_data, PROETHICA_PROV)
        self._emit_synthesis_literal_marker(g, uri, rdf_data, PROETHICA_PROV)
        if extraction_type not in self._DEF_SKIP_TYPES and 'temporal_dynamics' not in extraction_type:
            self._emit_definitions(g, uri, entity, rdf_data)

        if extraction_type == 'argument_generated' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.Argument))
            if rdf_data.get('argument_type'):
                g.add((uri, PROETHICA['argumentType'], Literal(rdf_data['argument_type'])))
            if rdf_data.get('decision_point_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['decision_point_id'])))
            if rdf_data.get('option_description'):
                g.add((uri, PROETHICA['optionDescription'], Literal(rdf_data['option_description'])))
            if rdf_data.get('confidence_score'):
                g.add((uri, PROETHICA['confidenceScore'], Literal(float(rdf_data['confidence_score']), datatype=XSD.decimal)))
            claim = rdf_data.get('claim', {})
            if isinstance(claim, dict) and claim.get('text'):
                g.add((uri, PROETHICA['claimText'], Literal(claim['text'])))
                if claim.get('entity_label'):
                    g.add((uri, PROETHICA['claimEntity'], Literal(claim['entity_label'])))
            warrant = rdf_data.get('warrant', {})
            if isinstance(warrant, dict) and warrant.get('entity_label'):
                g.add((uri, PROETHICA['warrantEntity'], Literal(warrant['entity_label'])))
                if warrant.get('entity_type'):
                    g.add((uri, PROETHICA['warrantType'], Literal(warrant['entity_type'])))
            backing = rdf_data.get('backing', {})
            if isinstance(backing, dict) and backing.get('entity_label'):
                g.add((uri, PROETHICA['backingProvision'], Literal(backing['entity_label'])))
            qualifier = rdf_data.get('qualifier', {})
            if isinstance(qualifier, dict) and qualifier.get('entity_label'):
                g.add((uri, PROETHICA['qualifierConstraint'], Literal(qualifier['entity_label'])))
            if rdf_data.get('role_label'):
                g.add((uri, PROETHICA['roleLabel'], Literal(rdf_data['role_label'])))
            if rdf_data.get('founding_good_analysis'):
                g.add((uri, PROETHICA['foundingGoodAnalysis'], Literal(rdf_data['founding_good_analysis'])))

        elif extraction_type == 'argument_validation' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.ArgumentValidation))
            if rdf_data.get('argument_id'):
                arg_id = rdf_data['argument_id']
                g.add((uri, PROETHICA['validatesArgument'], case_ns[arg_id]))
                g.add((uri, PROETHICA['argumentId'], Literal(arg_id)))
            if rdf_data.get('decision_point_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['decision_point_id'])))
            if rdf_data.get('argument_type'):
                g.add((uri, PROETHICA['argumentType'], Literal(rdf_data['argument_type'])))
            if 'is_valid' in rdf_data:
                g.add((uri, PROETHICA['isValid'], Literal(rdf_data['is_valid'], datatype=XSD.boolean)))
            if rdf_data.get('validation_score') is not None:
                g.add((uri, PROETHICA['validationScore'], Literal(float(rdf_data['validation_score']), datatype=XSD.decimal)))
            for i, note in enumerate(rdf_data.get('validation_notes', []) or []):
                g.add((uri, PROETHICA[f'validationNote{i+1}'], Literal(note)))
            entity_val = rdf_data.get('entity_validation', {}) or {}
            if entity_val:
                if 'is_valid' in entity_val:
                    g.add((uri, PROETHICA['entityValidationPassed'], Literal(entity_val['is_valid'], datatype=XSD.boolean)))
                for i, m in enumerate(entity_val.get('missing_entities', []) or []):
                    g.add((uri, PROETHICA[f'missingEntity{i+1}'], Literal(m)))
            founding_val = rdf_data.get('founding_value_validation', {}) or {}
            if founding_val:
                if 'is_compliant' in founding_val:
                    g.add((uri, PROETHICA['foundingValueCompliant'], Literal(founding_val['is_compliant'], datatype=XSD.boolean)))
                if founding_val.get('founding_good'):
                    g.add((uri, PROETHICA['foundingGood'], Literal(founding_val['founding_good'])))
                if founding_val.get('analysis'):
                    g.add((uri, PROETHICA['foundingValueAnalysis'], Literal(founding_val['analysis'])))
            virtue_val = rdf_data.get('virtue_validation', {}) or {}
            if virtue_val:
                if 'is_valid' in virtue_val:
                    g.add((uri, PROETHICA['virtueValidationPassed'], Literal(virtue_val['is_valid'], datatype=XSD.boolean)))
                for i, v in enumerate(virtue_val.get('missing_virtues', []) or []):
                    g.add((uri, PROETHICA[f'missingVirtue{i+1}'], Literal(v)))

        elif extraction_type == 'canonical_decision_point' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.DecisionPoint))
            if rdf_data.get('focus_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['focus_id'])))
            if rdf_data.get('description'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['description'])))
            elif rdf_data.get('focus'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['focus'])))
            if rdf_data.get('decision_question'):
                g.add((uri, PROETHICA['decisionQuestion'], Literal(rdf_data['decision_question'])))
            if rdf_data.get('context'):
                g.add((uri, PROETHICA['context'], Literal(rdf_data['context'])))
            if rdf_data.get('role_label'):
                g.add((uri, PROETHICA['roleLabel'], Literal(rdf_data['role_label'])))
            for i, opt in enumerate(rdf_data.get('options', []) or []):
                if isinstance(opt, dict) and opt.get('description'):
                    g.add((uri, PROETHICA[f'option{i+1}'], Literal(opt['description'])))

        elif extraction_type == 'ethical_conclusion' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalConclusion))
            if rdf_data.get('conclusionText'):
                g.add((uri, PROETHICA['conclusionText'], Literal(rdf_data['conclusionText'])))
            if rdf_data.get('conclusionType'):
                g.add((uri, PROETHICA['conclusionType'], Literal(rdf_data['conclusionType'])))
            if rdf_data.get('conclusionNumber'):
                g.add((uri, PROETHICA['conclusionNumber'], Literal(int(rdf_data['conclusionNumber']), datatype=XSD.integer)))
            if rdf_data.get('extractionReasoning'):
                g.add((uri, PROETHICA['extractionReasoning'], Literal(rdf_data['extractionReasoning'])))
            for i, prov in enumerate(rdf_data.get('citedProvisions', []) or []):
                g.add((uri, PROETHICA[f'citedProvision{i+1}'], Literal(prov)))
            for i, q in enumerate(rdf_data.get('answersQuestions', []) or []):
                g.add((uri, PROETHICA[f'answersQuestion{i+1}'], Literal(str(q))))

        elif extraction_type == 'ethical_question' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalQuestion))
            if rdf_data.get('questionText'):
                g.add((uri, PROETHICA['questionText'], Literal(rdf_data['questionText'])))
            if rdf_data.get('questionType'):
                g.add((uri, PROETHICA['questionType'], Literal(rdf_data['questionType'])))
            if rdf_data.get('questionNumber'):
                g.add((uri, PROETHICA['questionNumber'], Literal(int(rdf_data['questionNumber']), datatype=XSD.integer)))
            if rdf_data.get('emergence'):
                g.add((uri, PROETHICA['emergence'], Literal(rdf_data['emergence'])))

        # Step-3 temporal dynamics (Actions / Events). These arrive as a
        # JSON-LD record (@type + proeth:* predicates) from the LangGraph
        # converter, a different shape from the unified Pydantic rdf_data above,
        # which is why they previously fell through to a bare stub.
        elif 'temporal_dynamics' in extraction_type and rdf_data:
            self._add_temporal_fields(g, uri, rdf_data)

        # Generic properties fallback
        elif rdf_data and rdf_data.get('properties'):
            for prop_name, prop_values in rdf_data['properties'].items():
                # Provenance keys are emitted as typed prov:/proeth-prov: triples by
                # _emit_provenance above; skip them here so they are not also emitted
                # as untyped proeth: literals (the double-emission this fixes).
                if prop_name in self._PROV_PROP_KEYS:
                    continue
                # The attributes dict (qualifications/credentials/rights) is emitted
                # as one queryable triple per key, not one opaque stringified-dict
                # literal. Mirrors the per-key convention already in rdf_service /
                # entity_triple_service (PROETHICA[key]).
                if prop_name == 'attributes':
                    import ast
                    attr_dict = prop_values
                    # Stored shape is a single-element list holding the attributes
                    # dict, usually stringified (the storage layer str()s dict
                    # values). Unwrap the list, then literal_eval a stringified dict
                    # -- mirrors the relationships branch below. A non-dict result
                    # falls through to the generic literal so nothing is lost.
                    if isinstance(attr_dict, list) and len(attr_dict) == 1:
                        attr_dict = attr_dict[0]
                    if isinstance(attr_dict, str):
                        try:
                            attr_dict = ast.literal_eval(attr_dict)
                        except Exception:
                            attr_dict = None
                    if isinstance(attr_dict, dict):
                        for attr_key, attr_val in attr_dict.items():
                            if attr_val in (None, '', [], {}):
                                continue
                            # Map recurring professional attributes to the controlled
                            # vocabulary (proeth:hasLicense, ...) so cross-case queries
                            # work. A genuinely case-specific key goes to the single
                            # declared proeth:otherAttribute as "key: value", so the
                            # datatype-predicate space stays finite + fully declared
                            # (closed vocabulary) while the data is preserved; logged so
                            # the tail stays visible for deliberate vocabulary growth.
                            # Normalise the key (snake_case / spaced -> the vocab's
                            # no-separator lowercase form) so 'entity_type' / 'years of
                            # experience' match 'entitytype' / 'yearsofexperience'.
                            _akey = str(attr_key).strip().lower().replace('_', '').replace(' ', '')
                            controlled = self._ATTRIBUTE_VOCAB.get(_akey)
                            if not controlled:
                                logger.info("attributes: case-specific key %r on %s -> "
                                            "proeth:otherAttribute (not in the controlled vocabulary)",
                                            attr_key, str(uri).split('#')[-1])
                            for v in (attr_val if isinstance(attr_val, list) else [attr_val]):
                                if v in (None, ''):
                                    continue
                                lit = v if isinstance(v, (str, int, float, bool)) else str(v)
                                if controlled:
                                    g.add((uri, PROETHICA[controlled], Literal(lit)))
                                else:
                                    g.add((uri, PROETHICA['otherAttribute'], Literal(f"{attr_key}: {lit}")))
                        continue
                # Relationships (actor-to-actor) become real edges via a
                # proeth-core relation, instead of opaque stringified dicts.
                # Attached at the AGENT level when both endpoints have an Agent
                # (the relationship is between the persons, not the role facets);
                # falls back to the facet endpoints otherwise. Unresolvable
                # targets are logged and skipped so nothing becomes dead text.
                if prop_name == 'relationships':
                    import ast
                    facet_to_agent = getattr(self, '_facet_to_agent', {}) or {}
                    subj = facet_to_agent.get(uri, uri)
                    rels = prop_values if isinstance(prop_values, list) else [prop_values]
                    for rel in rels:
                        r = rel
                        if isinstance(r, str):
                            try:
                                r = ast.literal_eval(r)
                            except Exception as e:
                                logger.warning(f"relationship parse failed, dropped: {rel!r} ({e})")
                                continue
                        if not isinstance(r, dict):
                            logger.warning(f"relationship entry not a dict, dropped: {rel!r}")
                            continue
                        rtype = r.get('type') or r.get('relation') or ''
                        tgt = r.get('target') or r.get('to') or ''
                        if not tgt:
                            logger.warning(f"relationship missing target, dropped: {r!r}")
                            continue
                        if not rtype:
                            logger.warning(f"relationship missing type, dropped: target={tgt!r}")
                            continue
                        tgt_uri = self._resolve_rel_target(str(tgt))
                        if tgt_uri is None:
                            logger.info(f"relationship target unresolved, skipped: type={rtype!r} target={tgt!r}")
                            continue
                        # Actor relations hold between role-bearers: reject a target
                        # that resolved to a non-role node (no Agent) instead of
                        # emitting a domain/range-violating edge.
                        obj = self._target_agent(g, facet_to_agent, tgt_uri)
                        if obj is None:
                            logger.warning(
                                f"relationship target is not a role-bearer, skipped: "
                                f"type={rtype!r} target={tgt!r} resolved={str(tgt_uri).split('#')[-1]}")
                            continue
                        relprop, swap = self._rel_property_for(str(rtype))
                        if relprop == 'relatedTo':
                            logger.info(
                                f"relationship type {rtype!r} not in the actor-relation "
                                f"vocabulary; emitted as generic relatedTo")
                        # Orient the directional property: swap=True means the
                        # role-bearer is the object (e.g. a client naming its
                        # provider), so the edge runs target->subject.
                        edge_subj, edge_obj = (obj, subj) if swap else (subj, obj)
                        g.add((edge_subj, PROETHICA_CORE[relprop], edge_obj))
                        # PROV-O derivation for the edge (mirrors defeasibility edges);
                        # carries the per-relationship quote when the prompt supplied one.
                        self._emit_relationship_provenance(
                            g, case_ns, edge_subj, relprop, edge_obj, rtype, r.get('quote'))
                    continue
                if not isinstance(prop_values, list):
                    prop_values = [prop_values]
                safe_prop = self._camelCase(prop_name)
                prop_uri = PROETHICA[safe_prop]
                for value in prop_values:
                    if value:
                        g.add((uri, prop_uri, Literal(value)))

    def _object_property_locals(self) -> set:
        """Local names of every owl:ObjectProperty declared in core / intermediate.
        Cached per instance. Used so the temporal serializer never emits a literal
        on an object property (which would make the case OWL-DL inconsistent)."""
        if getattr(self, '_objprop_cache', None) is not None:
            return self._objprop_cache
        names = set()
        base = getattr(self, 'ontologies_dir', None)
        if not base:
            self._objprop_cache = names
            return names
        for fn in ('proethica-core.ttl', 'proethica-intermediate.ttl',
                   'proethica-intermediate-extended.ttl'):
            p = base / fn
            if not p.exists():
                continue
            try:
                gg = Graph()
                gg.parse(p, format='turtle')
            except Exception as e:
                logger.warning(f"Could not parse {fn} for object-property detection: {e}")
                continue
            for s in gg.subjects(RDF.type, OWL.ObjectProperty):
                names.add(str(s).split('#')[-1].split('/')[-1])
        self._objprop_cache = names
        return names

    def _add_temporal_fields(self, g: Graph, uri: URIRef, rdf_data: Dict):
        """Emit the descriptive triples for a temporal (Action/Event) individual
        from its JSON-LD record.

        Types the individual as the core Action/Event class (reasoner-visible,
        links to a real class), maps proeth:description to rdfs:comment, and
        copies the remaining proeth: scalar/list fields as literals. Deliberately
        skips: IRI-valued fields (e.g. proeth:causedByAction -- an ObjectProperty
        whose converter URI scheme differs from the committed individual URIs, so
        it would dangle), nested dicts, and the proeth-scenario:* teaching
        metadata.

        The temporal extractor sometimes carries a literal *description* of an
        obligation/capability under a predicate that is declared as an
        owl:ObjectProperty (e.g. proeth:fulfillsObligation, proeth:requiresCapability).
        Emitting a literal on an object property makes the case OWL-DL inconsistent,
        so such fields are redirected to a datatype sibling predicate (<local>Text)
        which preserves the text without the punning."""
        objprops = self._object_property_locals()
        jtype = rdf_data.get('@type', '')
        local_type = jtype.split(':')[-1] if jtype else ''
        # Type the individual against its 9-component class or its temporal-RDF
        # role class. Actions/Events get the core class (Pellet-visible 9-way
        # disjointness); Allen relations, causal chains, and timelines are
        # intermediate/OWL-Time classes that are not part of the 9-way axiom.
        if local_type in ('Action', 'Event'):
            g.add((uri, RDF.type, PROETHICA_CORE[local_type]))
        elif local_type in ('TemporalRelation', 'CausalChain'):
            g.add((uri, RDF.type, PROETHICA[local_type]))
        elif jtype == 'time:TemporalEntity':
            g.add((uri, RDF.type, TIME['TemporalEntity']))

        # The Allen converter emits OWL-Time triples whose object IRI uses the
        # legacy http://proethica.org/cases/{id}#Action_X scheme, but committed
        # individuals live at http://proethica.org/ontology/case/{id}#<safe_label>.
        # Without a remap the time:* triples would dangle. Derive the case-ns
        # base from the subject URI (Allen relations sit in the same case_ns).
        uri_str = str(uri)
        case_ns_base = uri_str.split('#')[0] + '#' if '#' in uri_str else None

        def _remap_legacy_iri(v):
            if not (isinstance(v, str) and v.startswith('http://proethica.org/cases/')):
                return v
            frag = v.split('#')[-1] if '#' in v else v
            # convert_action_to_rdf / convert_event_to_rdf prefix the fragment
            # with Action_ / Event_; strip that to recover the bare label-safe-id
            # which matches commit_case_versioned's safe_label for typical labels.
            if frag.startswith(('Action_', 'Event_')):
                frag = frag.split('_', 1)[1]
            return case_ns_base + frag if case_ns_base else v

        for key, value in rdf_data.items():
            if key.startswith('time:'):
                # OWL-Time predicate (proeth:owlTimeProperty named one of 15
                # intervalBefore/intervalAfter/.../intervalEquals/before/after).
                local = key.split(':', 1)[1]
                for v in (value if isinstance(value, list) else [value]):
                    if v is None or v == '' or isinstance(v, dict):
                        continue
                    if isinstance(v, str) and v.startswith(('http://', 'https://')):
                        g.add((uri, TIME[local], URIRef(_remap_legacy_iri(v))))
                    elif isinstance(v, bool):
                        g.add((uri, TIME[local], Literal(v)))
                    else:
                        g.add((uri, TIME[local], Literal(v if isinstance(v, (int, float)) else str(v))))
                continue
            if not key.startswith('proeth:'):
                continue  # skip @context/@id/@type/rdfs:label and proeth-scenario:*
            local = key.split(':', 1)[1]
            if local == 'causalSequence':
                # The causal sequence is a nested list of step dicts that the generic
                # dict-skip below would drop. Flatten it to numbered literals
                # (proeth:causalStep1..N = "element -- description") so the step-by-step
                # chain survives commit (the decision-point option1..N convention).
                seq = value if isinstance(value, list) else [value]
                step_no = 0
                for step in seq:
                    if not isinstance(step, dict):
                        continue
                    element = str(step.get('proeth:element') or step.get('element') or '').strip()
                    desc = str(step.get('proeth:description') or step.get('description') or '').strip()
                    text = ' -- '.join(p for p in (element, desc) if p)
                    if text:
                        step_no += 1
                        g.add((uri, PROETHICA[f'causalStep{step_no}'], Literal(text)))
                continue
            if local in ('discoveredInSection', 'sourceText', 'discoveredInPass'):
                # Temporal individuals carry provenance inline (no 'properties' wrapper for
                # _emit_provenance to read), so route these to the typed PROV-O predicates
                # here, giving the causal / temporal claims auditable source provenance.
                for v in (value if isinstance(value, list) else [value]):
                    if v in (None, ''):
                        continue
                    if local == 'discoveredInPass':
                        try:
                            g.add((uri, PROETHICA_PROV.discoveredInPass, Literal(int(v), datatype=XSD.integer)))
                        except (TypeError, ValueError):
                            pass
                    else:
                        g.add((uri, PROETHICA_PROV[local], Literal(str(v))))
                continue
            values = value if isinstance(value, list) else [value]
            for v in values:
                if v is None or v == '' or isinstance(v, dict):
                    continue
                if isinstance(v, str) and v.startswith(('http://', 'https://')):
                    continue  # IRI object refs use a different URI scheme; skip
                if local == 'description':
                    g.add((uri, RDFS.comment, Literal(v if isinstance(v, str) else str(v))))
                    continue
                # Redirect literal values on object properties to a datatype sibling
                # so a textual description never sits on an owl:ObjectProperty.
                pred_local = f"{local}Text" if local in objprops else local
                # Preserve native bool/int/float so declared datatype ranges are
                # satisfied (e.g. proeth:temporalSequence has range xsd:nonNegativeInteger;
                # a stringified "6" would violate it and make the case inconsistent).
                lit = Literal(v) if isinstance(v, (bool, int, float)) else Literal(str(v))
                g.add((uri, PROETHICA[pred_local], lit))

    def get_case_version_history(self, case_id: int) -> Dict[str, Any]:
        """
        Get version history for a case's extractions.

        Returns:
            Dictionary with version history and current state
        """
        try:
            conn = psycopg2.connect(**get_ontserve_db_config())
            try:
                with conn.cursor() as cur:
                    # Get all versions for this case
                    cur.execute("""
                        SELECT extraction_run_version, COUNT(*) as entity_count,
                               MIN(created_at) as extracted_at, is_current
                        FROM concepts
                        WHERE case_id = %s
                        GROUP BY extraction_run_version, is_current
                        ORDER BY extraction_run_version DESC
                    """, (case_id,))

                    versions = []
                    for row in cur.fetchall():
                        versions.append({
                            'version': row[0],
                            'entity_count': row[1],
                            'extracted_at': row[2].isoformat() if row[2] else None,
                            'is_current': row[3]
                        })

                    return {
                        'case_id': case_id,
                        'versions': versions,
                        'total_versions': len(set(v['version'] for v in versions))
                    }
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return {'error': str(e)}

    def uncommit_case(self, case_id: int) -> Dict[str, Any]:
        """Reverse a commit: remove entities from OntServe, reset is_published.

        Deletes the case TTL file, clears OntServe DB entries for the case
        ontology, and resets all committed entities to unpublished status.
        Does NOT attempt to remove classes from proethica-intermediate-extended.ttl
        (classes are shared and may be referenced by other cases).
        """
        from app.models import db

        result = {
            'case_id': case_id,
            'ttl_deleted': False,
            'ontserve_cleared': False,
            'entities_reset': 0,
            'errors': [],
        }

        # 1. Delete case TTL file
        case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
        if case_file.exists():
            case_file.unlink()
            result['ttl_deleted'] = True
            logger.info(f"Deleted case TTL file: {case_file}")

        # 2. Clear from OntServe database
        try:
            conn = psycopg2.connect(**get_ontserve_db_config())
            try:
                with conn.cursor() as cur:
                    ontology_name = f"proethica-case-{case_id}"

                    cur.execute(
                        "SELECT id FROM ontologies WHERE name = %s",
                        (ontology_name,)
                    )
                    row = cur.fetchone()

                    if row:
                        ontology_id = row[0]
                        cur.execute(
                            "DELETE FROM ontology_entities WHERE ontology_id = %s",
                            (ontology_id,)
                        )
                        deleted_entities = cur.rowcount

                        cur.execute(
                            "DELETE FROM ontology_versions WHERE ontology_id = %s",
                            (ontology_id,)
                        )
                        cur.execute(
                            "DELETE FROM ontologies WHERE id = %s",
                            (ontology_id,)
                        )
                        conn.commit()
                        result['ontserve_entities_deleted'] = deleted_entities
                        result['ontserve_cleared'] = True
                        logger.info(
                            f"Cleared {deleted_entities} entities from OntServe "
                            f"for {ontology_name}"
                        )
                    else:
                        result['ontserve_entities_deleted'] = 0
                        result['ontserve_cleared'] = True
            finally:
                conn.close()
        except Exception as e:
            error_msg = f"Failed to clear OntServe: {e}"
            logger.warning(error_msg)
            result['errors'].append(error_msg)

        # 3. Reset committed entities to unpublished
        reset_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=True
        ).update({'is_published': False})
        db.session.commit()
        result['entities_reset'] = reset_count
        logger.info(f"Reset {reset_count} committed entities to unpublished")

        result['success'] = len(result['errors']) == 0
        return result

