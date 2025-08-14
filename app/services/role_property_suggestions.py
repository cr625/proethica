import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from app.models.document import Document
from app.models.guideline_semantic_triple import GuidelineSemanticTriple

logger = logging.getLogger(__name__)


class RolePropertySuggestionsService:
    """Aggregate hasObligation/adheresToPrinciple/pursuesEnd/governedByCode suggestions per role.

    Reads saved guideline doc_metadata (extracted_concepts, extracted_relationships)
    and returns a world-level summary suitable for a roles view.
    """

    PREDICATES = {
        'hasObligation': 'http://proethica.org/ontology/intermediate#hasObligation',
        'adheresToPrinciple': 'http://proethica.org/ontology/intermediate#adheresToPrinciple',
        'pursuesEnd': 'http://proethica.org/ontology/intermediate#pursuesEnd',
        'governedByCode': 'http://proethica.org/ontology/intermediate#governedByCode',
    }

    @classmethod
    def build_for_world(cls, world_id: int) -> Dict[str, Any]:
        """Return JSON-serializable aggregate of role property suggestions for a world."""
        # Load guideline documents for this world that have extraction metadata
        q = Document.query.filter_by(world_id=world_id, document_type='guideline')
        suggestions: Dict[str, Dict[str, Any]] = {}
        # Build a combined uri->info mapping across all docs (from their cached concepts)
        global_uri_to_info: Dict[str, Dict[str, str]] = {}

        for doc in q:
            meta = doc.doc_metadata or {}
            rels: List[Dict[str, Any]] = meta.get('extracted_relationships') or []
            concepts: List[Dict[str, Any]] = meta.get('extracted_concepts') or []

            # Build a quick uri->label/type map from concepts
            uri_to_info: Dict[str, Dict[str, str]] = {}
            for c in concepts:
                match = (c.get('ontology_match') or {})
                uri = match.get('uri')
                if not uri:
                    # derive a synthetic uri if needed to keep grouping, but skip if blank
                    continue
                uri_to_info[uri] = {
                    'label': c.get('label') or uri.split('#')[-1],
                    'type': (c.get('type') or c.get('primary_type') or 'concept').lower(),
                }
            # Also add to global map for cross-doc label lookups
            for uri, info in uri_to_info.items():
                if uri not in global_uri_to_info:
                    global_uri_to_info[uri] = info

            # 1) Cached relationships from doc metadata
            for r in rels:
                subj = r.get('subject') or r.get('subject_uri')
                obj = r.get('object') or r.get('object_uri')
                pred = r.get('predicate')
                if not subj or not obj or not pred:
                    continue

                # Only track the four predicates of interest
                bucket: Optional[str] = None
                if pred == cls.PREDICATES['hasObligation']:
                    bucket = 'obligations'
                elif pred == cls.PREDICATES['adheresToPrinciple']:
                    bucket = 'principles'
                elif pred == cls.PREDICATES['pursuesEnd']:
                    bucket = 'ends'
                elif pred == cls.PREDICATES['governedByCode']:
                    bucket = 'codes'
                if not bucket:
                    continue

                srec = suggestions.setdefault(subj, {
                    'subject_uri': subj,
                    'subject_label': (uri_to_info.get(subj) or global_uri_to_info.get(subj) or {}).get('label', subj.split('#')[-1]),
                    'subject_type': (uri_to_info.get(subj) or global_uri_to_info.get(subj) or {}).get('type', 'role'),
                    'obligations': [], 'principles': [], 'ends': [], 'codes': [],
                    'sources': set(),
                })
                srec[bucket].append({
                    'uri': obj,
                    'label': (uri_to_info.get(obj) or global_uri_to_info.get(obj) or {}).get('label', obj.split('#')[-1]),
                    'type': (uri_to_info.get(obj) or global_uri_to_info.get(obj) or {}).get('type', 'concept'),
                })
                srec['sources'].add(doc.id)

            # 2) Stored triples in DB for this guideline
            try:
                db_triples = GuidelineSemanticTriple.get_by_guideline(doc.id, approved_only=False)
            except Exception:
                db_triples = []
            for t in db_triples:
                subj = t.subject_uri
                obj = t.object_uri
                pred = t.predicate
                if not subj or not obj or not pred:
                    continue

                bucket: Optional[str] = None
                if pred == cls.PREDICATES['hasObligation']:
                    bucket = 'obligations'
                elif pred == cls.PREDICATES['adheresToPrinciple']:
                    bucket = 'principles'
                elif pred == cls.PREDICATES['pursuesEnd']:
                    bucket = 'ends'
                elif pred == cls.PREDICATES['governedByCode']:
                    bucket = 'codes'
                if not bucket:
                    continue

                srec = suggestions.setdefault(subj, {
                    'subject_uri': subj,
                    'subject_label': (global_uri_to_info.get(subj) or {}).get('label', subj.split('#')[-1]),
                    'subject_type': (global_uri_to_info.get(subj) or {}).get('type', 'role'),
                    'obligations': [], 'principles': [], 'ends': [], 'codes': [],
                    'sources': set(),
                })
                srec[bucket].append({
                    'uri': obj,
                    'label': (global_uri_to_info.get(obj) or {}).get('label', obj.split('#')[-1]),
                    'type': (global_uri_to_info.get(obj) or {}).get('type', 'concept'),
                })
                srec['sources'].add(doc.id)

        # Normalize sets and de-duplicate by uri within buckets
        for subj, rec in suggestions.items():
            rec['sources'] = sorted(list(rec['sources']))
            for bucket in ('obligations', 'principles', 'ends', 'codes'):
                seen = set()
                uniq = []
                for item in rec[bucket]:
                    if item['uri'] in seen:
                        continue
                    seen.add(item['uri'])
                    uniq.append(item)
                rec[bucket] = uniq

        return {
            'world_id': world_id,
            'subjects': list(suggestions.values()),
            'counts': {
                'subjects': len(suggestions),
                'links_total': sum(len(rec['obligations']) + len(rec['principles']) + len(rec['ends']) + len(rec['codes'])
                                   for rec in suggestions.values())
            }
        }

    @classmethod
    def backfill_triples_from_cache(cls, world_id: int) -> Dict[str, Any]:
        """Populate guideline_semantic_triples from cached doc_metadata relationships for a world."""
        q = Document.query.filter_by(world_id=world_id, document_type='guideline')
        inserted = 0
        skipped = 0
        docs = 0
        for doc in q:
            docs += 1
            rels: List[Dict[str, Any]] = (doc.doc_metadata or {}).get('extracted_relationships') or []
            if not rels:
                continue
            # Clear prior triples for our predicates for this doc
            try:
                from sqlalchemy import text
                from app.models import db
                del_q = text(
                    """
                    DELETE FROM guideline_semantic_triples
                    WHERE guideline_id = :guideline_id AND predicate IN (
                        'http://proethica.org/ontology/intermediate#hasObligation',
                        'http://proethica.org/ontology/intermediate#adheresToPrinciple',
                        'http://proethica.org/ontology/intermediate#pursuesEnd',
                        'http://proethica.org/ontology/intermediate#governedByCode'
                    )
                    """
                )
                db.session.execute(del_q, { 'guideline_id': doc.id })
            except Exception:
                pass

            seen = set()
            for r in rels:
                s = r.get('subject') or r.get('subject_uri')
                p = r.get('predicate')
                o = r.get('object') or r.get('object_uri')
                if not s or not p or not o:
                    skipped += 1
                    continue
                if p not in (
                    cls.PREDICATES['hasObligation'],
                    cls.PREDICATES['adheresToPrinciple'],
                    cls.PREDICATES['pursuesEnd'],
                    cls.PREDICATES['governedByCode'],
                ):
                    skipped += 1
                    continue
                key = (s, p, o)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                try:
                    from sqlalchemy import text
                    from app.models import db
                    ins_q = text(
                        """
                        INSERT INTO guideline_semantic_triples
                        (guideline_id, subject_uri, predicate, object_uri, confidence, inference_type, explanation)
                        VALUES (:guideline_id, :s, :p, :o, :conf, :inf, :exp)
                        """
                    )
                    db.session.execute(ins_q, {
                        'guideline_id': doc.id,
                        's': s,
                        'p': p,
                        'o': o,
                        'conf': r.get('confidence', 1.0),
                        'inf': r.get('inference_type', 'cached'),
                        'exp': r.get('explanation', '')
                    })
                    inserted += 1
                except Exception:
                    skipped += 1
            try:
                from app.models import db
                db.session.commit()
            except Exception:
                pass
        return { 'world_id': world_id, 'inserted': inserted, 'skipped': skipped, 'documents': docs }
