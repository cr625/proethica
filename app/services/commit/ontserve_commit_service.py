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
import re
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
from app.services.ontserve.ontserve_config import (
    get_ontserve_db_config, get_ontserve_base_path, get_ontserve_mcp_url,
)
from app.services.commit import naming
from app.services.commit.commit_context import build_commit_context

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

# The nine disjoint D-tuple core categories. The materialized direct
# rdf:type proeth-core:<Category> (CMT-1) ranges over exactly these, and the
# collision check reads them back to recover an individual's category after the
# proeth:conceptCategory literal was retired.
_NINE_CORE_CATEGORIES = frozenset({
    "Role", "Principle", "Obligation", "State", "Resource",
    "Action", "Event", "Capability", "Constraint",
})

# Naming/label/URI hygiene helpers (naming.py, god-file split Item 1 Step 1.1).
# _EVENT_ORIGIN_SUBCLASS is re-imported here because _commit_individuals_to_case_ontology
# (below, not moved) reads it directly; resolve_event_origin_category is re-exported so
# existing `from ontserve_commit_service import resolve_event_origin_category` keeps working.
from app.services.commit.naming import (  # noqa: E402
    resolve_event_origin_category,
    _EVENT_ORIGIN_SUBCLASS,
)

# Versioned-commit mixin (versioned_commit.py, god-file split Item 1 Step 1.3).
from app.services.commit.versioned_commit import VersionedCommitMixin  # noqa: E402
# Agent-layer mixin (agent_layer.py, god-file split Item 1 Step 1.4).
from app.services.commit.agent_layer import AgentLayerMixin  # noqa: E402
# Per-individual TTL emitter mixin (ttl_emitters.py, god-file split Item 1 Step 1.5).
from app.services.commit.ttl_emitters import EmitterMixin  # noqa: E402
# Category-resolution + role-axis guard mixin (category_resolution.py,
# god-file split CONTINUATION Item 4, Step 1.6).
from app.services.commit.category_resolution import CategoryResolutionMixin  # noqa: E402
# Class-commit mixin (class_commit.py, god-file split CONTINUATION Item 4, Step 1.7).
from app.services.commit.class_commit import ClassCommitMixin  # noqa: E402


class OntServeCommitService(VersionedCommitMixin, AgentLayerMixin, EmitterMixin,
                             CategoryResolutionMixin, ClassCommitMixin):
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

        # Cross-commit base-ontology caches (established-category resolver,
        # base category reservation map, object-property locals), owned by
        # one collaborator so the service's remaining state is exactly its
        # immutable configuration above. Built lazily on first use.
        self._base_index = None

    @property
    def _base_ontology_index(self):
        # getattr default: tests construct the service via __new__ (skipping
        # __init__) and plant caches directly on the index.
        idx = getattr(self, '_base_index', None)
        if idx is None:
            from app.services.commit.base_ontology_index import BaseOntologyIndex
            idx = BaseOntologyIndex(getattr(self, 'ontologies_dir', None))
            self._base_index = idx
        return idx

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
                # gate_case_ttl's contract: status always; conforms/repairs_applied/
                # residual when status == ok; error on gate_unavailable/gate_error.
                result={'conforms': conf.get('conforms'), 'residual': conf.get('residual'),
                        'error': conf.get('error'), 'status': conf.get('status')},
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
                # Role-axis contradiction guard count (like the terminates
                # veto: present in the stats only when it acted).
                if individual_result.get('role_axis_vetoes'):
                    results['role_axis_vetoes'] = individual_result['role_axis_vetoes']
                # Post-canonicalization re-sweep count (the ordering gap:
                # canonicalization retyped a compound facet axis-sided).
                if individual_result.get('role_axis_vetoes_post_canonicalization'):
                    results['role_axis_vetoes_post_canonicalization'] = \
                        individual_result['role_axis_vetoes_post_canonicalization']
                # Q&C endpoint guard count (present only when it acted): a
                # dropped answersQuestion/extendsQuestion edge means a
                # question number resolved to no committed individual --
                # recommit the conclusions after the questions to restore.
                if individual_result.get('qc_edges_dropped'):
                    results['qc_edges_dropped'] = individual_result['qc_edges_dropped']
                # Canonicalization counters (roles_decomposed, states/obligations
                # materialized, compound_classes_removed): always present so the
                # persisted run record shows the step ran, even when all-zero.
                if 'canonicalization' in individual_result:
                    results['canonicalization'] = individual_result['canonicalization']

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

            # A class- or individuals-commit error means a TTL write failed.
            # Abort BEFORE publishing: a row marked published while absent from
            # the committed TTL is silent data loss that every later
            # recommit-from-temp_rdf sweep inherits. Temp rows stay unpublished
            # for retry. The sync warnings appended after this point remain
            # non-fatal here because the TTL is already durable on disk then
            # (the orchestrating task decides whether they fail the run).
            if results['errors']:
                from app import db
                db.session.rollback()
                results['success'] = False
                results['error'] = '; '.join(str(e) for e in results['errors'])
                return results

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

            # Retrieval metadata: entity_classes for the case-overlap Jaccard.
            # Derived from the now-published rows, so it works for every commit
            # path (previously only AutoCommitService wrote it). Never raises.
            from app.services.commit.precedent_features import update_entity_classes_from_storage
            results['entity_class_types'] = update_entity_classes_from_storage(case_id)

            return results

        except Exception as e:
            logger.error(f"Error committing entities: {e}")
            # A DB-origin exception leaves the shared session poisoned; without
            # the rollback every later query in this request/task raises
            # InFailedSqlTransaction and masks this original error.
            try:
                from app import db
                db.session.rollback()
            except Exception:  # noqa: BLE001
                pass
            return {
                'success': False,
                'error': str(e)
            }

    def ensure_case_synced(self, case_id: int) -> Dict[str, Any]:
        """Verify the case's disk TTL matches the current OntServe DB version and
        re-run the sync when they diverge.

        The healing path for a commit whose post-publish sync failed: on retry
        there are no unpublished rows left, so the commit sub-task no-ops --
        without this check the disk TTL and the OntServe DB diverge silently
        for that case and nothing ever re-drives the sync."""
        case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
        if not case_file.exists():
            return {'success': True, 'skipped': 'no case TTL on disk'}
        try:
            conn = psycopg2.connect(**get_ontserve_db_config())
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT v.content FROM ontology_versions v
                    JOIN ontologies o ON v.ontology_id = o.id
                    WHERE o.name = %s AND v.is_current = TRUE LIMIT 1
                """, (f"proethica-case-{case_id}",))
                row = cur.fetchone()
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            return {'success': False, 'error': f'sync check failed: {e}'}
        if row and row[0] == case_file.read_text():
            return {'success': True, 'in_sync': True}
        logger.warning(f"case {case_id}: disk TTL and OntServe DB current version diverge; re-running sync")
        return self._sync_ontology_to_db(f"proethica-case-{case_id}")

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

    def _commit_individuals_to_case_ontology(self, case_id: int, individuals: List[Tuple[Any, Dict]]) -> Dict[str, Any]:
        """
        Commit individuals to a case-specific ontology file.

        Creates proethica-case-N.ttl files that import from proethica-cases.

        Result counters: 'count' is newly minted individuals (the same value
        the former skip guard produced -- a re-seen row never incremented it);
        'merged' is same-label rows whose facts were unioned additively onto
        an existing node. Downstream individuals_committed reads 'count'.
        """
        try:
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"

            # Tracks the core category each invented class was first declared
            # subClassOf in this commit, so a class shared (incorrectly) across
            # disjoint categories does not accumulate two subClassOf-core edges
            # (which would make the case ontology OWL-DL inconsistent).
            class_core_category: Dict[str, str] = {}

            # Role individual URI -> the extraction's own role_kind decision,
            # consumed by the finalized-graph role-axis contradiction guard.
            role_kind_by_uri: Dict[URIRef, Optional[str]] = {}

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

            # Per-commit context (Step 2.1): label->URI index (seeded from the
            # loaded graph on this append path so a later-section commit still
            # resolves actors an earlier-section commit wrote) plus the Agent
            # layer maps and the R1 edge-archetype tracker. Shared factory with
            # _write_case_ttl_fresh -- the two paths' index building no longer
            # duplicates.
            ctx = build_commit_context(case_id, case_ns, g, individuals,
                                       seed_rel_index_from_graph=True)

            count = 0
            merged = 0
            for entity, rdf_data in individuals:
                extraction_type = entity.extraction_type or ''
                is_merge = False

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
                safe_label = self._opaque_reified_uri_local(rdf_data) or naming.safe_label(label)
                individual_uri = case_ns[safe_label]

                # Check if individual already exists
                if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
                    # A same-label individual is already committed. If it is the SAME
                    # concept category (the same entity re-seen in another section, or
                    # a partial recommit), fall through and merge ADDITIVELY: the loop
                    # body below is g.add()-based, so an identical row is a no-op and a
                    # row carrying new facts unions them onto the existing node --
                    # matching _write_case_ttl_fresh and the class path. (The former
                    # skip dropped the second row's facts entirely: a
                    # PrecedentCaseReference stub could never regain its Resource
                    # typing on recommit, the case-8 lesson.) If it is a DIFFERENT
                    # category (a genuine label collision -- e.g. an obligation and a
                    # capability that happen to share an entity_label), disambiguate
                    # the URI by category so the second individual is not silently
                    # dropped (display-to-RDF fidelity).
                    new_cat = self._get_concept_category(entity)
                    # The materialized direct rdf:type proeth-core:<Category> (CMT-1)
                    # is the per-individual category signal now that the
                    # proeth:conceptCategory literal is retired; read it back (one hop)
                    # to detect a genuine cross-category label collision.
                    existing_cats = {
                        str(o).split('#')[-1]
                        for o in g.objects(individual_uri, RDF.type)
                        if str(o).startswith(str(PROETHICA_CORE))
                        and str(o).split('#')[-1] in _NINE_CORE_CATEGORIES
                    }
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
                        logger.info(f"Individual {label} already exists, merging additively")
                        is_merge = True

                # Add individual as NamedIndividual
                g.add((individual_uri, RDF.type, OWL.NamedIndividual))
                g.add((individual_uri, RDFS.label, Literal(label)))

                # Record the extraction's professional-vs-participant call for
                # the finalized-graph role-axis guard.
                if self._is_role_individual(entity):
                    role_kind_by_uri[individual_uri] = self._extract_role_kind(rdf_data)

                # Add full description if we used a short label
                if full_description:
                    g.add((individual_uri, RDFS.comment, Literal(full_description)))

                # Base concept category for this entity (from its extraction pass).
                concept_cat = self._get_concept_category(entity)
                # Authoritative category = the reasoner-visible type chain. Starts as
                # the extraction-pass category and is overridden below to an
                # established class's core category when the individual is typed to
                # one, so the materialized direct type we write cannot disagree with
                # the chain (the case-8 re-extraction inconsistency).
                resolved_cat = concept_cat

                # Add type based on the class from rdf_json_ld
                if rdf_data and rdf_data.get('types'):
                    type_uris = rdf_data['types']
                    # Matched-class honoring: when the matcher matched an EXISTING class
                    # (matchesExisting + matchedOntologyClass) whose curated chain resolves
                    # to this component's core category, type the individual to that class
                    # instead of the minted near-duplicate (chain-validated; falls back to
                    # the minted types on any failure -- see _matched_class_override).
                    _honored = self._matched_class_override(rdf_data, concept_cat, type_uris)
                    if _honored is not None:
                        type_uris = [str(PROETHICA[_honored])]
                    for type_uri in type_uris:
                        # Extract class name from URI
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = naming.safe_local_name(class_name)
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
                                # `established` category (NOT the instance routing
                                # category), so the persisted case validates standalone under
                                # Pellet/SHACL without the in-memory pellet_validate patch.
                                # Using `established` (the ontology's own parent) makes the
                                # triple identical to the one in the shared store: no second
                                # disjoint parent, and no self-loop (parent is a core class,
                                # never the class itself). This is what D15 deferred; emitting
                                # from `established` rather than the lie-prone routing category
                                # is what makes it safe.
                                if established != concept_cat:
                                    logger.warning(
                                        "Class %s is established as %s in the ontology but an "
                                        "instance carries routing category %s; keeping the "
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

                        # Layer-1 convergence: attach the OCCUPATIONAL archetype (or the role_kind
                        # backstop) to a GENUINELY-NEW role class the individual is typed under. For an
                        # established role class the archetype already lives in intermediate, so skip
                        # (the normalized case does not re-declare shared classes). The relational
                        # archetype is materialized edge-primary on the individual (rdf:type), not here
                        # (R1). The occupational axis carries no disjointness risk for the new class.
                        if established is None and self._is_role_individual(entity):
                            for arch_uri in self._role_individual_occupational_parents(rdf_data, class_name):
                                g.add((class_uri, RDF.type, OWL.Class))
                                if (class_uri, RDFS.subClassOf, URIRef(arch_uri)) not in g:
                                    g.add((class_uri, RDFS.subClassOf, URIRef(arch_uri)))

                # Materialized direct type (CMT-1): assert the resolved core category
                # as a direct rdf:type proeth-core:<Category> -- the type a reasoner
                # would infer from the subClassOf-core chain emitted above. A one-hop
                # type for plain-rdflib consumers, and a wrong type clashes with the
                # nine-way AllDisjointClasses rather than lying silently. resolved_cat
                # is the SAME category that drove the subClassOf-core edge; the retired
                # proeth:conceptCategory literal is no longer written.
                if resolved_cat:
                    g.add((individual_uri, RDF.type, PROETHICA_CORE[resolved_cat]))

                # ONT-4 (2026-07-01): additionally type a bare Event individual to its ORIGIN
                # subclass (AgentCausedEvent / ExogenousEvent / AutomaticEvent) from the emitted
                # proeth:eventType. Step 3 emits proeth:Event + proeth:eventType with no per-case
                # subclass, so an event otherwise commits as bare core:Event and the ratified origin
                # axis is never materialized. Asserted ALONGSIDE the bare core:Event (each origin is
                # subClassOf Event, so the pair is redundant-but-consistent): the origin gives
                # reasoners and origin-aware consumers the disjoint kind, while the bare core:Event
                # preserves the CMT-1 one-hop discoverability the nine-category readback relies on.
                # The three origins are pairwise disjoint, so one origin per event raises no clash.
                if resolved_cat == 'Event':
                    _origin = resolve_event_origin_category(rdf_data)
                    if _origin:
                        # Additive-merge hardening: the origins are pairwise disjoint,
                        # so a re-sighting whose eventType maps to a DIFFERENT origin
                        # must not stack a second one onto the node. First origin wins;
                        # a conflicting later sighting is logged, not asserted.
                        _prior_origins = {
                            o for o in _EVENT_ORIGIN_SUBCLASS.values()
                            if (individual_uri, RDF.type, PROETHICA_CORE[o]) in g
                        }
                        if not _prior_origins:
                            g.add((individual_uri, RDF.type, PROETHICA_CORE[_origin]))
                        elif _origin not in _prior_origins:
                            logger.warning(
                                "Event origin conflict on %s: already typed %s, incoming "
                                "eventType maps to %s; keeping the existing origin.",
                                str(individual_uri).split('#')[-1],
                                sorted(_prior_origins), _origin)

                # Per-individual property serialization. SINGLE shared serializer for
                # both commit paths (see _add_individual_properties): typed provenance,
                # the matcher XAI decision (D16), the definition (rdfs:comment +
                # skos:definition), the rich Step-4 synthesis handlers, the Step-3
                # temporal fields, and the Step-1/2 generic handler that turns
                # `attributes` into per-key triples and `relationships` into real
                # proeth-core actor edges (resolved via the _rel_label_index).
                self._add_individual_properties(g, individual_uri, entity, rdf_data, case_ns, ctx=ctx)

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

                if is_merge:
                    merged += 1
                else:
                    count += 1

            # Emit the Agent layer (one proeth-core:Agent per actor + hasRole to
            # each role facet) once all facets have been written.
            self._emit_agent_layer(g, ctx=ctx)

            # Role-axis contradiction guard (case-4 lesson): runs on the
            # finalized graph so it sees every rdf:type source, including the
            # role_category relational-archetype fallback. Acts only on
            # provable both-sides contradictions; logs every drop.
            role_axis_vetoes = self._apply_role_axis_guard(g, role_kind_by_uri)

            # Q&C endpoint guard (same finalized-graph pattern): edges minted
            # from LLM question numbers are kept only when the target
            # Question individual exists in the graph. The count travels with
            # the results (role_axis_vetoes pattern) so a commit that dropped
            # edges cannot read as unqualified success.
            qc_edges_dropped = self._prune_dangling_qc_edges(g)

            # Save the graph
            naming.sanitize_graph_literals(g)
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Committed {count} new individuals ({merged} merged onto existing) to {case_file}")

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
            # Canonicalization: role+facet decomposition. Not swallowed (dev: fail loud); idempotent.
            # Shared canonicalize + role-axis RE-SWEEP helper: canonicalization can retype a
            # compound facet the pre-sweep above ignored (axis-unresolvable) onto an axis-sided
            # canonical role, so the guard runs AGAIN on the post-canonicalization graph.
            canon_stats = self._canonicalize_with_role_axis_resweep(
                case_id, case_file, role_kind_by_uri)
            logger.info(f"Canonicalization for case {case_id}: {canon_stats}")

            # The disk TTL -> OntServe DB sync is driven by the orchestrator
            # (commit_selected_entities), which runs after this returns so the
            # edge-bearing TTL is on disk before the version import.

            return {'count': count, 'merged': merged, 'file': str(case_file),
                    'role_axis_vetoes': role_axis_vetoes,
                    'qc_edges_dropped': qc_edges_dropped,
                    'role_axis_vetoes_post_canonicalization':
                        canon_stats['role_axis_vetoes_post_canonicalization'],
                    # The full canonicalization counters (roles_decomposed etc.)
                    # were previously only logged; the run record persists them.
                    'canonicalization': {
                        k: v for k, v in canon_stats.items()
                        if k != 'role_axis_vetoes_post_canonicalization'}}

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
    # work. Unmapped keys go to proeth:otherAttribute as "key: value" (the overflow bag).
    #
    # TRANSITIONAL -- vocabulary growth is now owned by the promotion loop, not hand-edits here:
    # OntServe/tools/promotion_candidates.py mines the otherAttribute tail corpus-wide and ranks
    # recurring keys; a human + literature gate promotes a candidate by DECLARING a real proeth:
    # datatype property in the ontology. Once a property is declared, the right end-state is for this
    # map's EXACT-name matches to derive from the ontology (a key equal to a declared property name maps
    # to it automatically) and for the synonym rows below to migrate to skos:altLabel on the properties,
    # at which point this literal dict is deleted. Until promotion is live the synonym map stays.
    # Targets use the SHACL ProfessionalRolePropertyShape spellings (license,
    # specialty, employer) -- the same predicates the named-field path emits.
    # The former hasLicense/hasSpecialty/hasEmployer twins were consolidated
    # away 2026-07-05 (correspondence audit M4: the same datum reached a
    # different predicate depending on extraction placement; zero corpus
    # references to the has* forms existed).
    _ATTRIBUTE_VOCAB = {
        'license': 'license', 'licensure': 'license', 'licensestatus': 'license',
        'licensed': 'license', 'professionallicense': 'license', 'licensing': 'license',
        'specialty': 'specialty', 'specialization': 'specialty',
        'specialisation': 'specialty', 'specialties': 'specialty',
        'experience': 'experienceLevel', 'yearsofexperience': 'experienceLevel',
        'experiencelevel': 'experienceLevel', 'yearsexperience': 'experienceLevel',
        'employer': 'employer', 'employedby': 'employer', 'employment': 'employer',
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

    # R1 edge-primary relational archetype: the actor edge a role facet bears determines its Kong
    # relational archetype, which is materialized as the role facet's direct rdf:type at commit (the
    # type a reasoner would infer from the intermediate equivalentClass definitions: ProviderClientRole
    # equivalentClass Role and (hasClient some Role), etc.). The archetype attaches to the proeth-core
    # property's SUBJECT side (the provider for hasClient, the employee for employedBy). owesDutyToward /
    # PublicResponsibilityRole is intentionally absent: per the spec it is not materialized per instance
    # (the equivalentClass existential plus the reasoner supply it), so a public-responsibility role lands
    # via the role_category fallback only.
    _REL_PROP_TO_RELATIONAL_ARCHETYPE = {
        'hasClient': 'ProviderClientRole',
        'employedBy': 'EmployerRelationshipRole',
        'professionalPeerOf': 'ProfessionalPeerRole',
    }
    # Symmetric relations classify BOTH endpoints (professionalPeerOf is owl:SymmetricProperty).
    _SYMMETRIC_REL_PROPS = frozenset({'professionalPeerOf'})

    def _rel_property_for(self, rel_type: str):
        """(proeth-core property, swap) for an LLM relationship type. swap=True
        means the edge is asserted target->subject (the role-bearer is on the
        receiving side of a directional relation). professionalPeerOf is symmetric,
        so swap is immaterial there. relatedTo is the controlled fallback."""
        # Normalize separators so the snake_case needles match the camelCase types the prompt now derives
        # from the ontology property names (employedBy, retainedBy, ...): strip spaces/underscores both sides.
        import re as _re
        t = _re.sub(r'[ _]', '', (rel_type or '').lower())
        for needle, prop, swap in self._REL_TYPE_TO_PROP:
            if _re.sub(r'[ _]', '', needle) in t:
                return prop, swap
        return 'relatedTo', False

    def _resolve_rel_target(self, target: str, ctx=None):
        """Resolve an actor-relationship target label to a case individual URI via
        the first-pass index. Actor relationships hold between role-bearers, so a
        role facet (a key of facet_to_agent) is always preferred over a same-named
        non-role individual; otherwise a bare actor name like "Owner" can substring
        -match a non-role node (e.g. an action "Owner Covert Review Instruction").
        Match tiers: exact, then prefix/substring. Returns the URI or None.
        Reads the per-commit CommitContext when supplied; the instance-attribute
        fallback remains for direct test callers until Step 2.4."""
        if ctx is not None:
            index = ctx.rel_label_index
            role_facets = set(ctx.facet_to_agent)
        else:
            index = getattr(self, '_rel_label_index', None)
            role_facets = set(getattr(self, '_facet_to_agent', {}) or {})
        if not index or not target:
            return None
        nt = naming.norm_label(target)

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


# Decision-point / CPR / question / conclusion enrichment helpers (enrichment.py,
# god-file split Item 1 Step 1.2). Re-exported here so existing imports keep working.
from app.services.commit.enrichment import (  # noqa: E402
    emit_decision_point_enrichment,
    emit_cpr_enrichment,
    _readable_question_label,
    _readable_conclusion_label,
)
