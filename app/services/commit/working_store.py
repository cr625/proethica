"""
Write-back helpers for the working store (temporary_rdf_storage rows).

The commit stage derives facts that the review pages read back from the same
row: the composed definition of an individual (lesson L1 of the case-8 review)
and the rdf:type the matched-class honoring selected (lesson L4). Writing them
onto the row keeps the working store and the committed TTL in agreement. The
helpers accept the SQLAlchemy row or any attribute-bearing stand-in (the unit
tests pass ``types.SimpleNamespace``), so the TTL writers stay testable
without a database.
"""

import logging

logger = logging.getLogger(__name__)


def mark_row_modified(entity, attribute: str) -> bool:
    """Flag a JSON column as changed after an in-place mutation.

    SQLAlchemy does not track mutations inside a plain ``db.JSON`` value, so a
    dict updated in place would never reach the flush. Returns False for a
    stand-in object that is not an ORM instance.
    """
    try:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(entity, attribute)
        return True
    except Exception:  # noqa: BLE001 - not an ORM instance, or attribute unloaded
        return False


def write_back_definition(entity, text: str) -> bool:
    """Set ``entity_definition`` on a row that has none.

    An existing definition (extracted or hand-written) is never overwritten.
    Returns True when the row was written.
    """
    text = (text or '').strip()
    if not text or (getattr(entity, 'entity_definition', None) or '').strip():
        return False
    try:
        entity.entity_definition = text
    except Exception:  # noqa: BLE001 - read-only stand-in
        return False
    return True


def write_back_types(entity, rdf_data, type_uris) -> None:
    """Replace ``rdf_json_ld.types`` with the committed (honored) type IRIs.

    The update is applied in place to ``rdf_data`` (every later reader of the
    row in the same commit sees the honored type) and to the row's own JSON
    when the caller passed a copy, then the column is flagged modified so the
    session flush persists it.
    """
    types = [str(u) for u in type_uris]
    if isinstance(rdf_data, dict):
        rdf_data['types'] = list(types)
    row_json = getattr(entity, 'rdf_json_ld', None)
    if isinstance(row_json, dict) and row_json is not rdf_data:
        row_json['types'] = list(types)
    mark_row_modified(entity, 'rdf_json_ld')
