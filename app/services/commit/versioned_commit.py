"""
Versioned-commit mixin for OntServeCommitService.

Extracted verbatim from ontserve_commit_service.py (god-file split, Item 1
Step 1.3): the "VERSIONED COMMIT METHODS" section plus the two version-
lifecycle methods that lived further down the file (get_case_version_history,
uncommit_case). OntServeCommitService gains VersionedCommitMixin as a base
class so every self._method(...) call site is unaffected.

Namespace/rdflib constants used by _write_case_ttl_fresh are redeclared
locally rather than imported back from ontserve_commit_service.py (which
imports this module for the mixin), to avoid a circular import; rdflib
Namespace equality is string-based, so this has no behavioral effect.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import Json
from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL
from rdflib.namespace import DCTERMS

from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.ontserve.ontserve_config import get_ontserve_db_config

logger = logging.getLogger(__name__)

# Namespaces (see ontserve_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
PROV = Namespace("http://www.w3.org/ns/prov#")


class VersionedCommitMixin:
    """Versioned commit path: commit_case_versioned and its helpers, plus
    get_case_version_history and uncommit_case."""

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
                # Role-axis contradiction guard count (like the terminates
                # veto: present in the stats only when it acted).
                if ttl_result.get('role_axis_vetoes'):
                    results['role_axis_vetoes'] = ttl_result['role_axis_vetoes']

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
                    # Canonicalization: role+facet decomposition. Not swallowed (dev: fail loud); idempotent.
                    # Shared canonicalize + role-axis RE-SWEEP helper (same ordering gap as the
                    # append path): the guard runs AGAIN on the post-canonicalization graph,
                    # keyed by the role_kind decisions _write_case_ttl_fresh recorded.
                    canon_stats = self._canonicalize_with_role_axis_resweep(
                        case_id, ttl_result['file'], ttl_result.get('role_kind_by_uri'))
                    logger.info(f"Canonicalization for case {case_id}: {canon_stats}")
                    if canon_stats['role_axis_vetoes_post_canonicalization']:
                        results['role_axis_vetoes_post_canonicalization'] = \
                            canon_stats['role_axis_vetoes_post_canonicalization']
                    results['canonicalization'] = {
                        k: v for k, v in canon_stats.items()
                        if k != 'role_axis_vetoes_post_canonicalization'}

            if classes_to_commit:
                # For classes, we still append to intermediate-extended.ttl
                # but with version metadata
                class_ttl_result = self._commit_classes_to_intermediate(classes_to_commit)
                if class_ttl_result.get('error'):
                    results['errors'].append(class_ttl_result['error'])

            # A failed TTL write must abort BEFORE publishing (the same guard
            # commit_selected_entities carries): a row marked published while
            # absent from the committed TTL is silent data loss. Rows stay
            # unpublished for retry; the OntServe-side version rows created
            # above are superseded by the retry's new version.
            if results['errors']:
                from app import db
                db.session.rollback()
                results['success'] = False
                results['error'] = '; '.join(str(e) for e in results['errors'])
                return results

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
                    safe_label = self._safe_local_name(label)
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

            # Per-commit context (Step 2.1): label->URI index, Agent layer maps,
            # R1 edge-archetype tracker. Shared factory with the append path;
            # this fresh-write path overwrites and has no prior graph, so it
            # does not seed the label index from the loaded graph.
            from app.services.commit.commit_context import build_commit_context
            ctx = build_commit_context(case_id, case_ns, g, individuals,
                                       seed_rel_index_from_graph=False)

            # Role individual URI -> role_kind decision, for the finalized-graph
            # role-axis contradiction guard (see the append path).
            role_kind_by_uri: Dict[URIRef, Optional[str]] = {}

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

                # Record the role_kind decision for the role-axis guard.
                if self._is_role_individual(entity):
                    role_kind_by_uri[individual_uri] = self._extract_role_kind(rdf_data)

                # Base concept category for this entity (from its extraction pass).
                concept_cat = self._get_concept_category(entity)
                # Authoritative category for the materialized direct type (CMT-1):
                # starts as the extraction-pass category and is overridden to an
                # established class's own core category when the individual is typed to
                # a class the shared ontology already defines, so the materialized type
                # cannot disagree with the subClassOf-core chain the reasoner sees.
                resolved_cat = concept_cat

                # Add type based on rdf_json_ld types
                if rdf_data and rdf_data.get('types'):
                    type_uris = rdf_data['types']
                    # Matched-class honoring (same rule as the append path): honor the
                    # matcher's chain-validated existing class over the minted near-duplicate.
                    _honored = self._matched_class_override(rdf_data, concept_cat, type_uris)
                    if _honored is not None:
                        type_uris = [str(PROETHICA[_honored])]
                    for type_uri in type_uris:
                        if '#' in type_uri:
                            class_name = type_uri.split('#')[-1]
                        else:
                            class_name = type_uri.split('/')[-1]
                        safe_class = self._safe_local_name(class_name)
                        # Category-aware disambiguation (same rule as the append +
                        # class-commit paths): never type to an IRI the base reserves
                        # for a disjoint category.
                        safe_class = self._category_safe_class_local(safe_class, concept_cat)
                        class_uri = PROETHICA[safe_class]
                        g.add((individual_uri, RDF.type, class_uri))
                        established = self._established_core_category(safe_class)
                        if established is not None:
                            resolved_cat = established
                        # Layer-1 convergence: the OCCUPATIONAL archetype (or role_kind backstop) on the
                        # individual's own type-class (see _commit_individuals_to_case_ontology). The
                        # relational archetype is materialized edge-primary on the individual (R1).
                        if self._is_role_individual(entity):
                            for arch_uri in self._role_individual_occupational_parents(rdf_data, class_name):
                                g.add((class_uri, RDF.type, OWL.Class))
                                if (class_uri, RDFS.subClassOf, URIRef(arch_uri)) not in g:
                                    g.add((class_uri, RDFS.subClassOf, URIRef(arch_uri)))

                # Materialized direct type (CMT-1): the resolved core category as a
                # direct rdf:type proeth-core:<Category>, replacing the retired
                # proeth:conceptCategory literal.
                if resolved_cat:
                    g.add((individual_uri, RDF.type, PROETHICA_CORE[resolved_cat]))

                # Add type-specific properties (reuse existing logic)
                self._add_individual_properties(g, individual_uri, entity, rdf_data, case_ns, ctx=ctx)

                # Commit-time marker only; extraction-time prov:generatedAtTime is
                # emitted by _emit_provenance (inside _add_individual_properties).
                g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Extraction")))

                count += 1

            # Emit the Agent layer (one proeth-core:Agent per actor + hasRole).
            self._emit_agent_layer(g, ctx=ctx)

            # Role-axis contradiction guard (case-4 lesson): finalized-graph
            # sweep, same as the append path. Provable both-sides
            # contradictions only; every drop is logged.
            role_axis_vetoes = self._apply_role_axis_guard(g, role_kind_by_uri)

            # Q&C endpoint guard (same finalized-graph pattern): edges minted
            # from LLM question numbers are kept only when the target
            # Question individual exists in the graph. The count travels with
            # the results (role_axis_vetoes pattern) so a commit that dropped
            # edges cannot read as unqualified success.
            qc_edges_dropped = self._prune_dangling_qc_edges(g)

            # Write file (overwrites existing)
            self._sanitize_graph_literals(g)
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Wrote fresh TTL file with {count} individuals to {case_file}")

            # role_kind_by_uri travels with the result so the caller's
            # post-canonicalization role-axis re-sweep keeps the extraction's
            # own professional/participant decision (never surfaced to users).
            return {'count': count, 'file': str(case_file),
                    'role_axis_vetoes': role_axis_vetoes,
                    'qc_edges_dropped': qc_edges_dropped,
                    'role_kind_by_uri': role_kind_by_uri}

        except Exception as e:
            logger.error(f"Error writing fresh case TTL: {e}")
            return {'count': 0, 'error': str(e)}

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
