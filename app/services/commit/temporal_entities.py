"""
Temporal-entities mixin for AutoCommitService.

Extracted verbatim from auto_commit_service.py (god-file split PHASE 2 Step
2.5): committing temporal entities (actions, events, causal chains, Allen
relations, timeline) to the case TTL, plus the two module-level convenience
wrapper functions that lived at the file tail. AutoCommitService gains
TemporalEntitiesMixin as a base class so every self._method(...) call site
is unaffected; the two module-level functions are re-exported from
auto_commit_service.py so existing imports keep working.

Depends at runtime (via self, once mixed into AutoCommitService) on
CaseTtlBuilderMixin's ``_make_safe_uri`` / ``_get_core_type`` and on
AutoCommitService's own ``_sync_to_ontserve`` / ``_case_title``
(``_case_title`` moved to CaseTtlBuilderMixin) -- no import needed for
those, since the final class mixes in all of them.

Namespace constants (PROETHICA, PROETHICA_CORE, PROV) are redeclared locally
rather than imported back from auto_commit_service.py (which imports this
module for the mixin), to avoid a circular import; rdflib Namespace equality
is string-based, so this has no behavioral effect.

DEVIATION (recorded): the two module-level wrapper functions
(``commit_temporal_entities``, ``clear_case_ontology``) instantiate
``AutoCommitService()``. Importing that class at module level here would
be circular (auto_commit_service.py imports this module, for the mixin,
before the AutoCommitService class is defined), so the import is placed
inside each function body instead, deferred to call time. This matches the
existing lazy-import style already used elsewhere in this file (for example
``_sync_to_ontserve``'s local import of ``OntServeCommitService``).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL
from rdflib.namespace import SKOS, DCTERMS

from app import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)

# Namespaces (see auto_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")


class TemporalEntitiesMixin:
    """Commit temporal entities (actions, events, causal chains, Allen
    relations, timeline) to the case TTL, linking them to existing
    Pass 1-3 individuals."""

    def commit_temporal_entities(self, case_id: int) -> Dict[str, Any]:
        """
        Commit temporal entities (actions, events, causal_chains) to the case TTL file.

        Called after enhanced temporal extraction completes to add temporal entities
        to the case ontology with relationships to Pass 1-3 entities.

        Args:
            case_id: The case ID to process

        Returns:
            Dict with summary of committed temporal entities
        """
        logger.info(f"Committing temporal entities for case {case_id}")

        try:
            # Define temporal entity types
            temporal_types = ['actions', 'events', 'causal_chains', 'allen_relations', 'timeline']

            # Gather temporal entities
            temporal_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.entity_type.in_(temporal_types)
            ).all()

            if not temporal_entities:
                logger.info(f"No temporal entities found for case {case_id}")
                return {'status': 'no_entities', 'counts': {}}

            logger.info(f"Found {len(temporal_entities)} temporal entities for case {case_id}")

            # Load or create case TTL graph
            case_file = self.ontologies_dir / f"proethica-case-{case_id}.ttl"
            g = Graph()

            if case_file.exists():
                g.parse(case_file, format='turtle')
                logger.info(f"Loaded existing case TTL: {case_file}")
            else:
                # Create new graph with ontology declaration
                case_ontology_uri = URIRef(f"http://proethica.org/ontology/case/{case_id}")
                g.add((case_ontology_uri, RDF.type, OWL.Ontology))
                g.add((case_ontology_uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
                _title = self._case_title(case_id)
                if _title:
                    g.add((case_ontology_uri, DCTERMS.title, Literal(_title)))
                g.add((case_ontology_uri, OWL.imports, URIRef("http://proethica.org/ontology/intermediate")))
                g.add((case_ontology_uri, DCTERMS.created, Literal(datetime.utcnow())))

            # Bind namespaces
            case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
            g.bind(f"case{case_id}", case_ns)
            g.bind("proeth", PROETHICA)
            g.bind("proeth-core", PROETHICA_CORE)
            g.bind("prov", PROV)
            g.bind("skos", SKOS)

            # Track counts by type
            counts = {t: 0 for t in temporal_types}

            # Build a map of existing Pass 1-3 individuals for linking
            existing_individuals = self._get_existing_individuals(g, case_ns)

            # Process each temporal entity
            for entity in temporal_entities:
                try:
                    self._add_temporal_entity_to_graph(
                        g, entity, case_ns, existing_individuals, case_id
                    )
                    counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
                except Exception as e:
                    logger.warning(f"Error adding temporal entity {entity.id}: {e}")

            # Save the updated graph
            g.serialize(destination=case_file, format='turtle')
            logger.info(f"Saved case TTL with temporal entities: {case_file}")

            # Mark temporal entities as committed
            for entity in temporal_entities:
                entity.is_published = True
                entity.updated_at = datetime.utcnow()
            db.session.commit()

            # Sync to OntServe
            self._sync_to_ontserve(case_id)

            total_added = sum(counts.values())
            logger.info(f"Committed {total_added} temporal entities for case {case_id}: {counts}")

            return {
                'status': 'success',
                'counts': counts,
                'total': total_added,
                'ttl_file': str(case_file)
            }

        except Exception as e:
            logger.error(f"Error committing temporal entities for case {case_id}: {e}")
            db.session.rollback()
            return {'status': 'error', 'error': str(e)}

    def _get_existing_individuals(self, g: Graph, case_ns: Namespace) -> Dict[str, URIRef]:
        """
        Get map of existing Pass 1-3 individuals for linking.

        Maps normalized labels to URIs for quick lookup when creating relationships.
        """
        individuals = {}

        for s, p, o in g.triples((None, RDF.type, OWL.NamedIndividual)):
            # Get label
            for label in g.objects(s, RDFS.label):
                normalized = str(label).lower().strip()
                individuals[normalized] = s

        logger.debug(f"Found {len(individuals)} existing individuals for linking")
        return individuals

    def _add_temporal_entity_to_graph(
        self,
        g: Graph,
        entity: TemporaryRDFStorage,
        case_ns: Namespace,
        existing_individuals: Dict[str, URIRef],
        case_id: int
    ):
        """
        Add a temporal entity to the case graph with relationships.

        Args:
            g: The RDF graph
            entity: The temporal entity to add
            case_ns: The case namespace
            existing_individuals: Map of existing individuals for linking
            case_id: The case ID
        """
        # Create individual URI from label
        safe_label = self._make_safe_uri(entity.entity_label)

        # Use appropriate prefix based on entity type
        type_prefix = {
            'actions': 'Action',
            'events': 'Event',
            'causal_chains': 'CausalChain',
            'allen_relations': 'AllenRelation',
            'timeline': 'Timeline'
        }
        prefix = type_prefix.get(entity.entity_type, entity.entity_type.title())
        individual_uri = case_ns[f"{prefix}_{safe_label}"]

        # Skip if already exists
        if (individual_uri, RDF.type, OWL.NamedIndividual) in g:
            return

        # Add as NamedIndividual
        g.add((individual_uri, RDF.type, OWL.NamedIndividual))
        g.add((individual_uri, RDFS.label, Literal(entity.entity_label)))

        # Add core type
        core_type = self._get_core_type(entity.entity_type)
        if core_type:
            g.add((individual_uri, RDF.type, core_type))

        # Parse JSON-LD for additional properties and relationships
        if entity.rdf_json_ld:
            try:
                json_data = json.loads(entity.rdf_json_ld) if isinstance(entity.rdf_json_ld, str) else entity.rdf_json_ld
                self._add_properties_from_jsonld(g, individual_uri, json_data, existing_individuals, case_ns)
            except Exception as e:
                logger.debug(f"Could not parse JSON-LD for {entity.entity_label}: {e}")

        # Add definition if available
        if entity.entity_definition:
            g.add((individual_uri, SKOS.definition, Literal(entity.entity_definition)))

        # Add provenance
        g.add((individual_uri, PROV.generatedAtTime, Literal(datetime.utcnow())))
        g.add((individual_uri, PROV.wasGeneratedBy, Literal(f"ProEthica Case {case_id} Temporal Extraction")))

    def _add_properties_from_jsonld(
        self,
        g: Graph,
        subject_uri: URIRef,
        json_data: Dict,
        existing_individuals: Dict[str, URIRef],
        case_ns: Namespace
    ):
        """
        Add properties from JSON-LD data, creating relationships to existing individuals.
        """
        # Extract common properties
        if 'proeth:description' in json_data:
            g.add((subject_uri, SKOS.definition, Literal(json_data['proeth:description'])))

        if 'proeth:agent' in json_data:
            agent_name = json_data['proeth:agent']
            # Try to find matching role
            normalized_agent = agent_name.lower().strip()
            for label, uri in existing_individuals.items():
                if normalized_agent in label or label in normalized_agent:
                    g.add((subject_uri, URIRef(str(PROETHICA) + "performedBy"), uri))
                    break

        if 'proeth:temporalMarker' in json_data:
            g.add((subject_uri, URIRef(str(PROETHICA) + "temporalMarker"),
                   Literal(json_data['proeth:temporalMarker'])))

        # Handle ethical context for actions
        if 'proeth:ethical_context' in json_data:
            ctx = json_data['proeth:ethical_context']

            # Link to violated obligations
            if isinstance(ctx, dict) and 'obligations_violated' in ctx:
                for obl in ctx.get('obligations_violated', []):
                    normalized_obl = obl.lower().strip()
                    for label, uri in existing_individuals.items():
                        if normalized_obl in label or label in normalized_obl:
                            g.add((subject_uri, URIRef(str(PROETHICA) + "violates"), uri))
                            break

            # Link to fulfilled obligations
            if isinstance(ctx, dict) and 'obligations_fulfilled' in ctx:
                for obl in ctx.get('obligations_fulfilled', []):
                    normalized_obl = obl.lower().strip()
                    for label, uri in existing_individuals.items():
                        if normalized_obl in label or label in normalized_obl:
                            g.add((subject_uri, URIRef(str(PROETHICA) + "fulfills"), uri))
                            break

        # Handle causal chains
        if 'proeth:cause' in json_data:
            cause_label = json_data['proeth:cause']
            cause_uri = case_ns[f"Action_{self._make_safe_uri(cause_label)}"]
            g.add((subject_uri, URIRef(str(PROETHICA) + "hasCause"), cause_uri))

        if 'proeth:effect' in json_data:
            effect_label = json_data['proeth:effect']
            effect_uri = case_ns[f"Event_{self._make_safe_uri(effect_label)}"]
            g.add((subject_uri, URIRef(str(PROETHICA) + "hasEffect"), effect_uri))

        # Handle Allen relations
        if 'time:intervalRelation' in json_data:
            g.add((subject_uri, URIRef("http://www.w3.org/2006/time#intervalRelation"),
                   Literal(json_data['time:intervalRelation'])))


# Module-level convenience functions
def commit_temporal_entities(case_id: int) -> Dict[str, Any]:
    """
    Convenience function to commit temporal entities for a case.

    Called after enhanced temporal extraction completes.
    """
    from app.services.commit.auto_commit_service import AutoCommitService
    service = AutoCommitService()
    return service.commit_temporal_entities(case_id)


def clear_case_ontology(case_id: int, reset_committed: bool = True) -> Dict[str, Any]:
    """
    Clear a case's OntServe ontology before re-running extraction.

    This should be called when re-extracting a case to avoid circular matches
    (entities matching to themselves from a previous run).

    Args:
        case_id: The case ID to clear
        reset_committed: If True, also mark all committed entities as uncommitted
                        so they can be recommitted fresh

    Returns:
        Dict with summary of what was cleared
    """
    from app.services.commit.auto_commit_service import AutoCommitService
    service = AutoCommitService()
    return service.clear_case_ontology(case_id, reset_committed=reset_committed)
