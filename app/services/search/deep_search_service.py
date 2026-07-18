"""Deep search: ontology-mediated component ranking of cases (increment 6,
free mode per plan decision D8c).

No LLM is involved. The query is structured by the ontology: the entity lane's
matched concepts mark which of the nine components the scenario populates and
their stored embeddings fill the component vectors; implicated NSPE provisions
come from semantic match against the provision individuals; subject tags from
the D7 token matcher. Scoring reuses the precedent engine's conventions --
per-component cosine over the components BOTH sides carry (COMPONENT_WEIGHTS,
renormalized), plus provision and tag Jaccard, with the feature weights
renormalized per D8b over the features the query actually populated
(outcome_alignment always absent; the tension feature absent in free mode).
"""

import logging
import re

from sqlalchemy import create_engine, text

from app.concept_meta import COMPONENT_COLORS, COMPONENT_LABELS
from app.services.embedding.similarity_utils import cosine_similarity_list
from app.services.ontserve.ontserve_config import get_ontserve_db_url
from app.services.precedent.case_feature_extractor import COMPONENT_WEIGHTS
from app.services.precedent.similarity_service import PrecedentSimilarityService
from app.services.search.unified_search_service import query_tokens

logger = logging.getLogger(__name__)

CATEGORY_TO_CODE = {
    'Role': 'R', 'Principle': 'P', 'Obligation': 'O', 'State': 'S',
    'Resource': 'Rs', 'Action': 'A', 'Event': 'E', 'Capability': 'Ca',
    'Constraint': 'Cs',
}

# Concepts drawn on per component when building the query-side vector.
ENTITIES_PER_COMPONENT = 3

# Provisions implicated when their cosine clears this floor (same register as
# the entity lane's MIN_SEMANTIC_SCORE; provisions are short prescriptive
# sentences, so scores run slightly lower).
MIN_PROVISION_SCORE = 0.30
MAX_PROVISIONS = 5

_EMBEDDINGS_BY_URI_SQL = text("""
    SELECT DISTINCT ON (uri) uri, embedding
    FROM ontology_entities
    WHERE uri = ANY(:uris) AND embedding IS NOT NULL
    ORDER BY uri
""")

_PROVISION_MATCH_SQL = text("""
    SELECT oe.uri, oe.label,
           (oe.embedding <=> CAST(:qvec AS vector)) AS distance
    FROM ontology_entities oe
    JOIN ontologies o ON o.id = oe.ontology_id
    WHERE o.name ILIKE '%nspe%' AND oe.embedding IS NOT NULL
    ORDER BY oe.embedding <=> CAST(:qvec AS vector)
    LIMIT :limit
""")

_FEATURES_SQL = text("""
    SELECT case_id, provisions_cited, subject_tags,
           embedding_R, embedding_P, embedding_O, embedding_S, embedding_Rs,
           embedding_A, embedding_E, embedding_Ca, embedding_Cs
    FROM case_precedent_features
""")

_TAG_VOCAB_SQL = text("""
    SELECT DISTINCT unnest(subject_tags) FROM case_precedent_features
""")


def provision_code_from_uri(uri):
    """nspe#III_1_a -> iii.1.a (normalized lowercase; provisions_cited casing
    varies across the corpus, so comparison is case-insensitive)."""
    frag = uri.rsplit('#', 1)[-1]
    return frag.replace('_', '.').lower()


def _parse_vec(value):
    """pgvector values arrive as '[...]' strings over raw SQL."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return list(value)
    return [float(x) for x in str(value).strip('[]').split(',')]


def _mean_vec(vectors):
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(len(vectors[0]))]


class DeepSearchService:
    """Free-mode deep search over the precedent feature store."""

    def __init__(self, ontserve_engine=None, embed_fn=None, app_session=None):
        self._engine = ontserve_engine
        self._embed_fn = embed_fn
        self._app_session = app_session

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(get_ontserve_db_url())
        return self._engine

    @property
    def app_session(self):
        if self._app_session is None:
            from app import db
            self._app_session = db.session
        return self._app_session

    def _query_vector_str(self, query):
        if self._embed_fn is not None:
            vec = self._embed_fn(query)
        else:
            from app.services.embedding.embedding_service import EmbeddingService
            vec = EmbeddingService.get_instance()._get_local_embedding(query)
        if not vec or len(vec) != 384:
            raise ValueError(f'query embedding has dimension {len(vec) if vec else 0}, expected 384')
        return '[' + ','.join(str(x) for x in vec) + ']'

    def structure_query(self, query, entity_results):
        """Structure the scenario through the ontology (D8c).

        Returns {'components': {code: {'vector', 'entities': [labels]}},
        'provisions': [codes], 'provision_labels': [labels], 'tags': [tags]}.
        entity_results is the (already computed) entity lane for this query.
        """
        # Components: matched concepts per category mark the populated slots.
        picked = {}
        for e in entity_results:
            code = CATEGORY_TO_CODE.get(e.get('category'))
            if code is None:
                continue
            bucket = picked.setdefault(code, [])
            if len(bucket) < ENTITIES_PER_COMPONENT:
                bucket.append(e)

        uris = [e['uri'] for bucket in picked.values() for e in bucket]
        vec_by_uri = {}
        with self.engine.connect() as conn:
            if uris:
                for uri, emb in conn.execute(_EMBEDDINGS_BY_URI_SQL, {'uris': uris}):
                    vec_by_uri[uri] = _parse_vec(emb)

            components = {}
            for code, bucket in picked.items():
                vectors = [vec_by_uri[e['uri']] for e in bucket if e['uri'] in vec_by_uri]
                if vectors:
                    components[code] = {
                        'vector': _mean_vec(vectors),
                        'entities': [e['label'] for e in bucket],
                    }

            # Provisions: semantic match against the NSPE provision individuals.
            provisions, provision_labels = [], []
            try:
                qvec = self._query_vector_str(query)
                rows = conn.execute(_PROVISION_MATCH_SQL, {
                    'qvec': qvec, 'limit': MAX_PROVISIONS * 2,
                }).fetchall()
                for uri, label, distance in rows:
                    score = 1.0 - float(distance)
                    if score >= MIN_PROVISION_SCORE and len(provisions) < MAX_PROVISIONS:
                        provisions.append(provision_code_from_uri(uri))
                        provision_labels.append(label)
            except Exception as e:
                logger.warning(f"Provision matching unavailable for deep search: {e}")

        # Tags: the D7 token-subset match against the controlled vocabulary.
        q_tokens = set(query_tokens(query))
        tags = []
        if q_tokens:
            vocab = [r[0] for r in self.app_session.execute(_TAG_VOCAB_SQL).fetchall()]
            tags = [t for t in vocab if q_tokens <= set(query_tokens(t))]

        return {'components': components, 'provisions': provisions,
                'provision_labels': provision_labels, 'tags': tags}

    def rank_cases(self, structure, limit=10):
        """Score every case against the structured query (D8b weights)."""
        base = PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS
        active = {'component_similarity': base['component_similarity']}
        if structure['provisions']:
            active['provision_overlap'] = base['provision_overlap']
        if structure['tags']:
            active['tag_overlap'] = base['tag_overlap']
        # outcome_alignment and principle_overlap (tension) are absent in free
        # mode by design (D8b/D8c).
        total_w = sum(active.values())

        q_provisions = set(structure['provisions'])
        q_tags = set(structure['tags'])
        q_components = structure['components']

        ranked = []
        for row in self.app_session.execute(_FEATURES_SQL).fetchall():
            (case_id, provisions_cited, subject_tags,
             emb_r, emb_p, emb_o, emb_s, emb_rs, emb_a, emb_e, emb_ca, emb_cs) = row
            case_embs = {'R': emb_r, 'P': emb_p, 'O': emb_o, 'S': emb_s,
                         'Rs': emb_rs, 'A': emb_a, 'E': emb_e, 'Ca': emb_ca,
                         'Cs': emb_cs}

            # Component similarity over the components BOTH sides carry,
            # COMPONENT_WEIGHTS renormalized (the engine's own convention).
            per_comp = {}
            comp_sum, comp_w = 0.0, 0.0
            for code, qc in q_components.items():
                case_vec = _parse_vec(case_embs.get(code))
                if case_vec is None:
                    continue
                sim = cosine_similarity_list(qc['vector'], case_vec)
                per_comp[code] = sim
                w = COMPONENT_WEIGHTS.get(code, 0.0)
                comp_sum += w * sim
                comp_w += w
            if comp_w == 0.0:
                continue
            scores = {'component_similarity': comp_sum / comp_w}

            if 'provision_overlap' in active:
                cited = {c.lower() for c in (provisions_cited or [])}
                union = q_provisions | cited
                scores['provision_overlap'] = (
                    len(q_provisions & cited) / len(union) if union else 0.0)
            if 'tag_overlap' in active:
                case_tags = set(subject_tags or [])
                union = q_tags | case_tags
                scores['tag_overlap'] = (
                    len(q_tags & case_tags) / len(union) if union else 0.0)

            overall = sum(active[k] * scores[k] for k in active) / total_w
            ranked.append({
                'case_id': case_id,
                'score': overall,
                'per_component': per_comp,
                'feature_scores': scores,
                'provision_matches': sorted(q_provisions & {c.lower() for c in (provisions_cited or [])}),
                'tag_matches': sorted(q_tags & set(subject_tags or [])),
            })

        ranked.sort(key=lambda r: -r['score'])
        return ranked[:limit]


def component_display(per_comp, top=3):
    """Top contributing components as display chips (label + canonical color);
    values go to tooltips only (D7)."""
    ordered = sorted(per_comp.items(),
                     key=lambda kv: -(COMPONENT_WEIGHTS.get(kv[0], 0.0) * kv[1]))
    return [{'code': code,
             'label': COMPONENT_LABELS.get(code, code),
             'color': COMPONENT_COLORS.get(code),
             'value': round(sim, 2)}
            for code, sim in ordered[:top]]
