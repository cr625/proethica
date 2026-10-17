"""Post-commit update of case_precedent_features.entity_classes.

entity_classes maps each singular entity type to the ontology class URIs the
case's committed individuals are typed with; the entity-review case-overlap
tool (matching_ops.py) computes its Jaccard comparison from it. The hook that
wrote it lived only in AutoCommitService, so the live pipeline path
(OntServeCommitService.commit_selected_entities, used by the staged runner and
the pipeline dashboard) left the column NULL. This module derives the mapping
for any commit path, idempotently.

Source of the types: the committed case graph (rdf:type of every
owl:NamedIndividual in the case TTL) whenever the case has a committed
ontology, the working store (temporary_rdf_storage rdf_json_ld.types)
otherwise. The working store is rewritten by later canonicalization passes,
so for case 24-1 it named a class (CompetenceSelfAssessmentCapability) that
no committed individual bears and omitted two classes committed individuals
do bear (2026-10 review).
"""

import json
import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text

from app.models import db, TemporaryRDFStorage

logger = logging.getLogger(__name__)

_TYPE_SINGULAR = {
    'roles': 'role', 'states': 'state', 'resources': 'resource',
    'principles': 'principle', 'obligations': 'obligation',
    'constraints': 'constraint', 'capabilities': 'capability',
    'actions': 'action', 'events': 'event',
    'temporal_dynamics_enhanced': 'temporal',
}

_CORE_NS = 'http://proethica.org/ontology/core#'

# Direct core type of a committed individual -> entity_classes key.
_CORE_CATEGORY_SINGULAR = {
    'Role': 'role', 'State': 'state', 'Resource': 'resource',
    'Principle': 'principle', 'Obligation': 'obligation',
    'Constraint': 'constraint', 'Capability': 'capability',
    'Action': 'action', 'Event': 'event',
}


def entity_classes_from_graph(graph) -> dict:
    """entity_classes from a committed case graph: for each owl:NamedIndividual
    whose direct core type is one of the nine categories, its other rdf:type
    URIs (the intermediate or case classes), grouped by category. The core
    type itself and owl:NamedIndividual are not classes of the mapping, which
    keeps the shape of the working-store derivation."""
    from rdflib import RDF
    from rdflib.namespace import OWL

    named_individual = str(OWL.NamedIndividual)
    entity_classes = defaultdict(list)
    for subject in graph.subjects(RDF.type, OWL.NamedIndividual):
        types = [str(t) for t in graph.objects(subject, RDF.type)]
        category = next(
            (t[len(_CORE_NS):] for t in types
             if t.startswith(_CORE_NS) and t[len(_CORE_NS):] in _CORE_CATEGORY_SINGULAR),
            None)
        if category is None:
            continue
        key = _CORE_CATEGORY_SINGULAR[category]
        for t in types:
            if t == named_individual or t.startswith(_CORE_NS):
                continue
            if t not in entity_classes[key]:
                entity_classes[key].append(t)
    return dict(entity_classes)


def entity_classes_from_working_store(case_id: int) -> dict:
    """entity_classes from the published working-store rows: the fallback for
    a case without a committed ontology."""
    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, is_published=True, storage_type='individual'
    ).filter(TemporaryRDFStorage.extraction_type.in_(list(_TYPE_SINGULAR))).all()

    entity_classes = defaultdict(list)
    for row in rows:
        rdf = row.rdf_json_ld or {}
        for t in rdf.get('types') or []:
            key = _TYPE_SINGULAR[row.extraction_type]
            if t and t not in entity_classes[key]:
                entity_classes[key].append(t)
    return dict(entity_classes)


def derive_entity_classes(case_id: int) -> tuple:
    """(entity_classes, source), source being 'committed_graph' when the case
    has a committed ontology and 'working_store' otherwise."""
    from app.services.entity.committed_case_graph import committed_case_exists, load_case_graph
    if committed_case_exists(case_id):
        return entity_classes_from_graph(load_case_graph(case_id)), 'committed_graph'
    return entity_classes_from_working_store(case_id), 'working_store'


def update_entity_classes_from_storage(case_id: int) -> int:
    """Upsert entity_classes for the case from its committed individuals.

    Returns the number of entity types written (0 when nothing to write).
    Never raises: retrieval metadata must not fail a commit.
    """
    try:
        entity_classes, source = derive_entity_classes(case_id)

        if not entity_classes:
            logger.info("entity_classes: nothing to write for case %s (%s)", case_id, source)
            return 0

        exists = db.session.execute(
            text("SELECT id FROM case_precedent_features WHERE case_id = :c"),
            {'c': case_id}).fetchone()
        if exists:
            db.session.execute(text("""
                UPDATE case_precedent_features
                SET entity_classes = :ec,
                    extraction_metadata = COALESCE(extraction_metadata, '{}'::jsonb) ||
                        jsonb_build_object('entity_linking_updated_at', :ts,
                                           'entity_classes_source', :src)
                WHERE case_id = :c
            """), {'c': case_id, 'ec': json.dumps(entity_classes), 'src': source,
                   'ts': datetime.utcnow().isoformat()})
        else:
            db.session.execute(text("""
                INSERT INTO case_precedent_features (case_id, entity_classes, extraction_metadata, extracted_at)
                VALUES (:c, :ec, :meta, :ts)
            """), {'c': case_id, 'ec': json.dumps(entity_classes),
                   'meta': json.dumps({'entity_classes_source': source}),
                   'ts': datetime.utcnow()})
        db.session.commit()
        logger.info("entity_classes updated for case %s from %s: %d types",
                    case_id, source, len(entity_classes))
        return len(entity_classes)
    except Exception as e:
        logger.error("entity_classes update failed for case %s: %s", case_id, e)
        db.session.rollback()
        return 0
