"""Post-commit update of case_precedent_features.entity_classes.

entity_classes maps each singular entity type to the ontology class URIs the
case's committed individuals are typed with; the entity-review case-overlap
tool (matching_ops.py) computes its Jaccard comparison from it. The hook that
wrote it lived only in AutoCommitService, so the live pipeline path
(OntServeCommitService.commit_selected_entities, used by the staged runner and
the pipeline dashboard) left the column NULL. This module derives the mapping
from the committed working-store rows instead of from commit-internal results,
so any commit path can call it idempotently.
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


def update_entity_classes_from_storage(case_id: int) -> int:
    """Upsert entity_classes for the case from its published individuals.

    Returns the number of entity types written (0 when nothing to write).
    Never raises: retrieval metadata must not fail a commit.
    """
    try:
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

        if not entity_classes:
            logger.info("entity_classes: nothing to write for case %s", case_id)
            return 0

        exists = db.session.execute(
            text("SELECT id FROM case_precedent_features WHERE case_id = :c"),
            {'c': case_id}).fetchone()
        if exists:
            db.session.execute(text("""
                UPDATE case_precedent_features
                SET entity_classes = :ec,
                    extraction_metadata = COALESCE(extraction_metadata, '{}'::jsonb) ||
                        jsonb_build_object('entity_linking_updated_at', :ts)
                WHERE case_id = :c
            """), {'c': case_id, 'ec': json.dumps(dict(entity_classes)),
                   'ts': datetime.utcnow().isoformat()})
        else:
            db.session.execute(text("""
                INSERT INTO case_precedent_features (case_id, entity_classes, extracted_at)
                VALUES (:c, :ec, :ts)
            """), {'c': case_id, 'ec': json.dumps(dict(entity_classes)),
                   'ts': datetime.utcnow()})
        db.session.commit()
        logger.info("entity_classes updated for case %s: %d types",
                    case_id, len(entity_classes))
        return len(entity_classes)
    except Exception as e:
        logger.error("entity_classes update failed for case %s: %s", case_id, e)
        db.session.rollback()
        return 0
