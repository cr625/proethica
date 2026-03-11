"""
Entity Change Detector

Compares content hashes stored at commit time in ProEthica against
current hashes in OntServe to detect entities whose definitions have
changed since the case was committed.

Uses direct database connection to OntServe (same pattern as
ontserve_commit_service.py) rather than HTTP API to avoid requiring
the OntServe web server to be running.
"""

import logging
from typing import Dict, Set

import psycopg2

from app.services.ontserve_config import get_ontserve_db_config

logger = logging.getLogger(__name__)


def detect_changed_entities(case_id: int) -> Dict[str, dict]:
    """Check which published entities have changed in OntServe since commit.

    Returns a dict keyed by entity_uri with change details:
        {
            'http://...#Engineer': {
                'committed_hash': 'abc...',
                'current_hash': 'def...',
                'current_label': 'Engineer',
                'current_comment': 'Updated definition...',
            }
        }

    Entities not found in OntServe are excluded (they may have been
    removed, but that's a different concern).
    """
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    # Get all published entities for this case that have both a URI and a hash
    published = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.is_published == True,  # noqa: E712
        TemporaryRDFStorage.entity_uri.isnot(None),
        TemporaryRDFStorage.content_hash.isnot(None),
    ).all()

    if not published:
        return {}

    # Build lookup: uri -> committed hash
    committed = {e.entity_uri: e.content_hash for e in published}
    uris = list(committed.keys())

    # Query OntServe for current hashes
    try:
        conn = psycopg2.connect(**get_ontserve_db_config())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT uri, content_hash, label, comment
                    FROM ontology_entities
                    WHERE uri = ANY(%s)
                    """,
                    (uris,)
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except psycopg2.Error as e:
        logger.warning("Could not connect to OntServe DB for change detection: %s", e)
        return {}

    # Compare hashes
    changed = {}
    for uri, current_hash, label, comment in rows:
        committed_hash = committed.get(uri)
        if committed_hash and current_hash and committed_hash != current_hash:
            changed[uri] = {
                'committed_hash': committed_hash,
                'current_hash': current_hash,
                'current_label': label,
                'current_comment': comment,
            }

    if changed:
        logger.info(
            "Case %d: %d of %d published entities have changed in OntServe",
            case_id, len(changed), len(published)
        )

    return changed


def get_changed_entity_uris(case_id: int) -> Set[str]:
    """Convenience wrapper returning just the set of changed URIs.

    Use this in view functions to pass to templates for indicator display.
    """
    return set(detect_changed_entities(case_id).keys())
