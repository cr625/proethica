"""
Case-independent NSPE provision lookup API.

Backs the shared provision popovers (static/js/shared/case_card.js): any
surface that has only provision CODES (the precedent similarity network,
the lineage view, future case cards) resolves display code, provision
text, and the OntServe entity URL here, without needing per-case Step-4
extraction rows.

Source of truth is the co-located NSPE Code TTL (the same file
tests/unit/test_provision_references.py validates the fragment rule
against), parsed once per process and cached. Text comes from
skos:definition, the user-facing code from dct:identifier.
"""

import logging
from threading import Lock

from flask import Blueprint, current_app, jsonify, request

from app.utils.provision_codes import (nspe_provision_fragment,
                                       provision_display_code)

logger = logging.getLogger(__name__)

provisions_api_bp = Blueprint('provisions_api', __name__, url_prefix='/api/provisions')

_cache_lock = Lock()
_provision_map = None  # dct:identifier -> {'label': ..., 'text': ...}


def _load_provision_map():
    """Parse the NSPE Code TTL once per process: identifier -> label/text."""
    global _provision_map
    with _cache_lock:
        if _provision_map is not None:
            return _provision_map
        mapping = {}
        try:
            from rdflib import Graph, URIRef
            from rdflib.namespace import RDFS, SKOS, DCTERMS
            from app.services.ontserve.ontserve_config import get_ontserve_base_path
            ttl_path = get_ontserve_base_path() / "ontologies" / "NSPE Code of Ethics.ttl"
            g = Graph()
            g.parse(str(ttl_path), format='turtle')
            for s, _, ident in g.triples((None, DCTERMS.identifier, None)):
                entry = {
                    'label': str(next(g.objects(s, RDFS.label), '') or ''),
                    'text': str(next(g.objects(s, SKOS.definition), '') or ''),
                }
                mapping[str(ident)] = entry
        except Exception as e:
            logger.error(f"NSPE provision map load failed: {e}")
            raise
        _provision_map = mapping
        return mapping


@provisions_api_bp.route('/info', methods=['GET'])
def provision_info():
    """Resolve provision codes to display code, text, and OntServe URL.

    GET /api/provisions/info?codes=II.1.a,I.4,Preamble
    -> {"II.1.a": {"display_code": "II.1.a", "label": ..., "text": ...,
                   "url": ...}, "I.4": {...}}

    Codes that do not normalize to a modern NSPE provision (historical
    Canons, duty names) come back with display_code/url null and no text;
    the client renders those as plain tags.
    """
    raw_codes = [c.strip() for c in (request.args.get('codes') or '').split(',') if c.strip()]
    if not raw_codes:
        return jsonify({}), 200
    if len(raw_codes) > 100:
        return jsonify({'error': 'too many codes (max 100)'}), 400

    provision_map = _load_provision_map()
    ontserve_base = current_app.config.get('ONTSERVE_WEB_URL', 'http://localhost:5003')

    result = {}
    for raw in raw_codes:
        display = provision_display_code(raw)
        frag = nspe_provision_fragment(raw)
        entry = provision_map.get(display) if display else None
        result[raw] = {
            'display_code': display,
            'label': (entry or {}).get('label'),
            'text': (entry or {}).get('text'),
            'url': (f"{ontserve_base}/entity/NSPE Code of Ethics/{frag}"
                    if frag and entry else None),
        }
    return jsonify(result), 200
