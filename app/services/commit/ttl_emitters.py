"""
Per-individual TTL property emission mixin for OntServeCommitService.

Extracted verbatim from ontserve_commit_service.py (god-file split, Item 1
Step 1.5): the per-individual property emission block (_emit_definitions
through _emit_synthesis_literal_marker) and the per-individual serializer
block (_add_individual_properties through _add_temporal_fields).
OntServeCommitService gains EmitterMixin as a base class so every
self._method(...) call site is unaffected.

rdflib namespace constants are redeclared locally rather than imported back
from ontserve_commit_service.py (which imports this module for the mixin),
to avoid a circular import; Namespace equality is string-based so this has
no behavioral effect. emit_cpr_enrichment / emit_decision_point_enrichment /
_readable_question_label / _readable_conclusion_label are imported directly
from enrichment.py (no circularity there: enrichment.py has no dependency on
this module or on ontserve_commit_service.py).
"""

import logging
from datetime import datetime

from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS

from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI
from app.services.commit.enrichment import (
    emit_cpr_enrichment,
    emit_decision_point_enrichment,
    _readable_question_label,
    _readable_conclusion_label,
)

logger = logging.getLogger(__name__)

# Namespaces (see ontserve_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
TIME = Namespace("http://www.w3.org/2006/time#")
PROV = Namespace("http://www.w3.org/ns/prov#")
PROETHICA_PROV = Namespace("http://proethica.org/provenance#")


class EmitterMixin:
    """Per-individual TTL property emission: the shared class/individual
    definition + provenance + match-decision + synthesis-marker helpers, and
    the single per-individual property serializer used by both commit paths."""

    def _emit_definitions(self, g: Graph, subject_uri: URIRef, entity, rdf_data: Dict) -> None:
        """Emit rdfs:comment + skos:definition (primary) and skos:scopeNote
        (alternates) for a class OR an individual.

        Single source of truth for definition serialization, shared by the class
        path and the individual path so the two cannot drift. Individuals
        previously received no definition triple at all: their definition survived
        only when it happened to be duplicated into a `properties` key
        (caseInvolvement / usedInContext / subject), under a non-canonical
        predicate. This restores symmetry with the class path.
        """
        definitions = (rdf_data or {}).get('definitions', [])
        if definitions:
            primary = next((d for d in definitions if d.get('is_primary')), definitions[0])
            if primary.get('text'):
                g.add((subject_uri, RDFS.comment, Literal(primary['text'])))
                g.add((subject_uri, SKOS.definition, Literal(primary['text'])))
            for defn in definitions:
                if defn is primary:
                    continue
                text = defn.get('text', '')
                if not text:
                    continue
                # Tag the scope note with its source so the review UI and OntServe
                # both read "Inherited from <X>". Prefer the source CLASS (e.g.
                # EngineerRole, the matched parent whose definition this is) so the
                # specific class survives the commit, not just the source ontology.
                # Fall back to the section (a second extraction definition), then the
                # source ontology, then the type.
                src_uri = defn.get('source_uri')
                src_class = src_uri.rsplit('#', 1)[-1].rsplit('/', 1)[-1] if src_uri else None
                source_tag = src_class or defn.get('source_section') or defn.get('source_ontology') or defn.get('source_type', '')
                tagged_text = f"[{source_tag}] {text}" if source_tag else text
                g.add((subject_uri, SKOS.scopeNote, Literal(tagged_text)))
        elif getattr(entity, 'entity_definition', None):
            g.add((subject_uri, RDFS.comment, Literal(entity.entity_definition)))
            g.add((subject_uri, SKOS.definition, Literal(entity.entity_definition)))

    def _ensure_match_annotation_decls(self, g: Graph, prov_ns: Namespace) -> None:
        """Emit the owl:AnnotationProperty declarations for the matcher-provenance
        predicates inline into the graph. The Pellet harness loads only
        core+intermediate+case (not provenance), so the IRI-valued
        matchedOntologyClass must be declared an annotation property in the graph
        it reads, or it would be auto-typed an ObjectProperty (punning the target
        class as an individual). Idempotent."""
        for local in self._MATCH_ANNOTATION_PROPS:
            decl = (prov_ns[local], RDF.type, OWL.AnnotationProperty)
            if decl not in g:
                g.add(decl)

    def _emit_match_decision(self, g: Graph, subject_uri: URIRef, rdf_data: Dict,
                             prov_ns: Namespace) -> None:
        """Persist the extraction matcher's decision as XAI annotation provenance
        on the subject (individual or class): which canonical class it matched, the
        confidence, whether it reused an existing class, and the rationale. All
        owl:AnnotationProperty, so this records WHY the rdf:type was chosen without
        affecting OWL-DL reasoning."""
        md = (rdf_data or {}).get('match_decision')
        if not isinstance(md, dict):
            return
        self._ensure_match_annotation_decls(g, prov_ns)
        if 'matches_existing' in md:
            g.add((subject_uri, prov_ns['matchesExisting'],
                   Literal(bool(md['matches_existing']), datatype=XSD.boolean)))
        matched_uri = md.get('matched_uri')
        # Record only a canonical (shared-layer) class IRI; a per-case copy would
        # re-introduce the injection pollution the curated-vocabulary filter removed.
        if matched_uri and '/ontology/case/' not in str(matched_uri):
            g.add((subject_uri, prov_ns['matchedOntologyClass'], URIRef(matched_uri)))
        if md.get('matched_label'):
            g.add((subject_uri, prov_ns['matchedOntologyLabel'], Literal(md['matched_label'])))
        conf = md.get('confidence')
        if conf is not None:
            try:
                g.add((subject_uri, prov_ns['matchConfidence'],
                       Literal(float(conf), datatype=XSD.decimal)))
            except (TypeError, ValueError):
                pass
        if md.get('reasoning'):
            g.add((subject_uri, prov_ns['matchReasoning'], Literal(md['reasoning'])))

    def _emit_provenance(self, g: Graph, subject_uri: URIRef, rdf_data: Dict) -> None:
        """Typed PROV-O / proeth-prov provenance from the extracted properties,
        shared by the class and individual paths (single source of truth). The
        individual path previously emitted these via the generic loop as untyped,
        lowercased proeth: literals (e.g. proeth:generatedattime), duplicating and
        mismatching the typed triples the class path emits. Routing both paths
        through this helper de-duplicates and types them consistently. Also emits
        per-section sourceText so the facts and discussion snippets both survive
        (the top-level source_texts dict that previously collapsed to one literal).
        """
        PP = PROETHICA_PROV
        props = (rdf_data or {}).get('properties', {}) or {}

        for ts in (props.get('generatedAtTime') or []):
            try:
                clean = ts.replace('Z', '+00:00') if ts.endswith('Z') else ts
                g.add((subject_uri, PROV.generatedAtTime, Literal(datetime.fromisoformat(clean), datatype=XSD.dateTime)))
            except Exception as e:
                logger.warning(f"Could not parse generatedAtTime {ts}: {e}")
        for attribution in (props.get('wasAttributedTo') or []):
            g.add((subject_uri, PROV.wasAttributedTo, Literal(attribution)))
        if props.get('firstDiscoveredInCase'):
            g.add((subject_uri, PP.firstDiscoveredInCase, Literal(int(props['firstDiscoveredInCase'][0]), datatype=XSD.integer)))
        if props.get('firstDiscoveredAt'):
            ts = props['firstDiscoveredAt'][0]
            try:
                clean = ts.replace('Z', '+00:00') if ts.endswith('Z') else ts
                g.add((subject_uri, PP.firstDiscoveredAt, Literal(datetime.fromisoformat(clean), datatype=XSD.dateTime)))
            except Exception as e:
                logger.warning(f"Could not parse firstDiscoveredAt {ts}: {e}")
        for case_id_val in (props.get('discoveredInCase') or []):
            g.add((subject_uri, PP.discoveredInCase, Literal(int(case_id_val), datatype=XSD.integer)))
        if props.get('discoveredInSection'):
            g.add((subject_uri, PP.discoveredInSection, Literal(props['discoveredInSection'][0])))
        if props.get('discoveredInStep'):
            g.add((subject_uri, PP.discoveredInStep, Literal(int(props['discoveredInStep'][0]), datatype=XSD.integer)))

        # sourceText: the props value plus every distinct per-section snippet from
        # the top-level source_texts dict (section attribution is on discoveredInSection).
        emitted_src = set()
        st = props.get('sourceText')
        if st:
            val = st[0] if isinstance(st, list) else st
            if val:
                g.add((subject_uri, PP.sourceText, Literal(val)))
                emitted_src.add(str(val).strip())
        for _section, text in ((rdf_data or {}).get('source_texts', {}) or {}).items():
            if text and str(text).strip() not in emitted_src:
                g.add((subject_uri, PP.sourceText, Literal(text)))
                emitted_src.add(str(text).strip())

    def _emit_synthesis_literal_marker(self, g: Graph, subject_uri: URIRef,
                                       rdf_data: Dict, prov_ns: Namespace) -> None:
        """Mark which of an individual's literal fields are kept synthesis inputs
        (CONTENT / ASSESSMENT in field_classification) as opposed to structural relations,
        derived literals, or provenance. Emitted as an owl:AnnotationProperty
        (proeth-prov:synthesisLiteral, one value per kept-literal local name), so the
        triple-vs-literal distinction is captured in the committed provenance and the
        synthesis layer can collect the kept literals by query rather than re-deriving the
        classification. Pellet-neutral (annotation property, like the matcher decision)."""
        from app.services.extraction.field_classification import (
            synthesis_literals, _normalize, classify, FieldKind)
        # Predicate names this individual carries, across the two storage shapes:
        # pass-1/2 keep them under 'properties'; temporal keeps proeth: keys at top level.
        props_dict = ((rdf_data or {}).get('properties', {}) or {})
        preds = list(props_dict.keys())
        temporal_preds = [k for k in (rdf_data or {}).keys()
                          if isinstance(k, str) and k.startswith('proeth:')]
        preds += temporal_preds
        kept = synthesis_literals(preds)

        def _value_of(p):
            if p in props_dict:
                return props_dict[p]
            return (rdf_data or {}).get(p)

        def _is_unkept_value(v):
            # Mirror the temporal serializer's value skips: dicts are dropped,
            # IRI strings are the converter's object references (skipped).
            if isinstance(v, dict):
                return True
            if isinstance(v, str) and v.startswith(('http://', 'https://')):
                return True
            if isinstance(v, list):
                return all(_is_unkept_value(x) for x in v) if v else True
            return False

        # Mirror the generic-loop emission skip (CMT-3/R1) plus the re-shaped
        # bags AND the temporal serializer's own skips, so the marker lists
        # exactly the literals the graph carries: a *Class key becomes the
        # rdf:type; roleCategory/roleKind/eventType are routing inputs;
        # attributes/additionalRelationships are re-shaped into per-key /
        # otherAttribute literals; dict values and IRI-string values are
        # dropped by the serializer (owlTimeURI, the agents decomposition
        # before its flatten). Without this the marker asserted triples that
        # do not exist (correspondence audit T2, verified on case-8 Engineer L;
        # extended to the temporal machinery in the A/E properties review).
        _reshaped = {'attributes', 'additionalRelationships', 'relationships'}
        _routing = ('roleCategory', 'roleKind', 'eventType')
        kept = [p for p in kept
                if not self._camelCase(p).endswith('Class')
                # temporal preds arrive proeth:-prefixed, so the routing check
                # must compare the normalized local name, not the raw key
                # (case-5 run 51 still minted eventType markers via the raw form)
                and self._camelCase(p) not in _routing
                and _normalize(p) not in _routing
                and self._camelCase(p) not in _reshaped
                and not _is_unkept_value(_value_of(p))]
        # The temporal serializer redirects literal values on OBJECT properties
        # to a <local>Text datatype sibling; list the shadow name the graph
        # actually carries. classify() gates out shadows registered DERIVED
        # (requiresCapabilityText, fromEntityText/toEntityText).
        for p in temporal_preds:
            if classify(p) is FieldKind.RELATION and not _is_unkept_value(_value_of(p)):
                shadow = f"{_normalize(p)}Text"
                if classify(shadow) in (FieldKind.CONTENT, FieldKind.ASSESSMENT):
                    kept.append(shadow)
        # The causalSequence list is flattened to per-step proeth:causalStep
        # literals; the marker lists the name the graph carries.
        kept = ['causalStep' if _normalize(p) == 'causalSequence' else p for p in kept]
        if not kept:
            return
        decl = (prov_ns['synthesisLiteral'], RDF.type, OWL.AnnotationProperty)
        if decl not in g:
            g.add(decl)
        emitted = set()
        for p in kept:
            local = _normalize(p)
            if local and local not in emitted:
                g.add((subject_uri, prov_ns['synthesisLiteral'], Literal(local)))
                emitted.add(local)

    def _add_individual_properties(self, g: Graph, uri: URIRef, entity: Any,
                                   rdf_data: Dict, case_ns: Namespace, ctx=None):
        """Add type-specific properties to an individual in the graph.

        SINGLE per-individual serializer shared by BOTH commit paths: the live
        append path (`_commit_individuals_to_case_ontology`, used by the pipeline
        / staged re-extraction / entity-review commit) and the versioned path
        (`_write_case_ttl_fresh`). It is the union of what the two paths had
        drifted into emitting separately: the rich Step-4 synthesis handlers
        (arguments, validations, decision points, conclusions, questions) AND the
        Step-1/2 generic handler that turns `attributes` into per-key triples and
        `relationships` into real proeth-core actor edges (resolved via
        `_rel_label_index`). Keeping one serializer is what stops the two paths
        re-drifting; do not reintroduce an inline copy in either caller.
        """
        # Per-commit state source (Step 2.1): the commit paths pass a
        # CommitContext; the instance-attribute fallback remains for direct
        # unit-test callers until Step 2.4 migrates them.
        if ctx is not None:
            role_edge_archetyped = ctx.role_edge_archetyped
            facet_to_agent = ctx.facet_to_agent
        else:
            if not hasattr(self, '_role_edge_archetyped'):
                self._role_edge_archetyped = set()
            role_edge_archetyped = self._role_edge_archetyped
            facet_to_agent = getattr(self, '_facet_to_agent', {}) or {}
        extraction_type = entity.extraction_type or ''

        # Universal per-individual serialization. Lives here (not in a caller) so
        # BOTH commit paths -- the append path (_commit_individuals_to_case_ontology)
        # and the versioned path (_write_case_ttl_fresh) -- emit them identically:
        # typed provenance, the matcher XAI decision (D16), and the definition
        # (rdfs:comment + skos:definition, symmetric with the class path; gated for
        # the synthesis/temporal types that carry their text in dedicated predicates).
        self._emit_provenance(g, uri, rdf_data)
        self._emit_match_decision(g, uri, rdf_data, PROETHICA_PROV)
        self._emit_synthesis_literal_marker(g, uri, rdf_data, PROETHICA_PROV)
        if extraction_type not in self._DEF_SKIP_TYPES and 'temporal_dynamics' not in extraction_type:
            self._emit_definitions(g, uri, entity, rdf_data)

        # Analysis-layer typing (2026-07-04): the Step-4 phase-2 artifacts and the
        # citation stubs previously fell through the dispatch below untyped (bare
        # owl:NamedIndividual), invisible to SHACL, the reasoner, and the case
        # display's Analysis Elements section. Typed here, ahead of the dispatch,
        # so the generic properties fallback still serializes their fields. The
        # classes are declared in proethica-cases v3.0.0. The former
        # argument_generated / argument_validation branches (retired argument
        # stage, zero rows ever committed) were removed at the same time.
        _ANALYSIS_TYPE_CLASSES = {
            'question_emergence': 'QuestionEmergence',
            'resolution_pattern': 'ResolutionPattern',
            'causal_normative_link': 'CausalNormativeLink',
            'code_provision_reference': 'CodeProvisionReference',
            'precedent_case_reference': 'PrecedentCaseReference',
        }
        _analysis_cls = _ANALYSIS_TYPE_CLASSES.get(extraction_type)
        if _analysis_cls:
            g.add((uri, RDF.type, PROETHICA_CASES[_analysis_cls]))

        # Citation-treatment term (proethica-cases v3.1.0 citationType; values
        # defined by the CitationTreatmentScheme concepts). Emitted since
        # 2026-07-09; earlier commits carried the term only in the extraction
        # JSON, so the treatment never reached the committed graph.
        if extraction_type == 'precedent_case_reference' and rdf_data \
                and rdf_data.get('citationType'):
            g.add((uri, PROETHICA_CASES['citationType'],
                   Literal(rdf_data['citationType'])))

        # Provision-application excerpts (intermediate relevantExcerpt,
        # 2026-07-11): the '[section] text' spans that apply the cited
        # provision, previously dropped by the nested-structure skip. The
        # appliesTo dicts become object edges via the analysis-edge applier.
        if extraction_type == 'code_provision_reference' and rdf_data:
            emit_cpr_enrichment(g, uri, rdf_data)

        if extraction_type == 'canonical_decision_point' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.DecisionPoint))
            if rdf_data.get('focus_id'):
                g.add((uri, PROETHICA['decisionPointId'], Literal(rdf_data['focus_id'])))
            if rdf_data.get('description'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['description'])))
            elif rdf_data.get('focus'):
                g.add((uri, PROETHICA['focus'], Literal(rdf_data['focus'])))
            if rdf_data.get('decision_question'):
                g.add((uri, PROETHICA['decisionQuestion'], Literal(rdf_data['decision_question'])))
            if rdf_data.get('role_label'):
                g.add((uri, PROETHICA['roleLabel'], Literal(rdf_data['role_label'])))
            # The analytic literals (Toulmin slots, board resolution, scores,
            # provisions, options incl. the board choice) come from the shared
            # enrichment helper so the backfill path cannot drift from this one.
            emit_decision_point_enrichment(g, uri, rdf_data)

        elif extraction_type == 'ethical_conclusion' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalConclusion))
            if rdf_data.get('conclusionText'):
                g.add((uri, PROETHICA['conclusionText'], Literal(rdf_data['conclusionText'])))
            if rdf_data.get('conclusionType'):
                g.add((uri, PROETHICA['conclusionType'], Literal(rdf_data['conclusionType'])))
            # Board disposition (violation/no_violation/compliance/recommendation/
            # interpretation, detected deterministically by ConclusionAnalyzer).
            # 'unknown' is a detector non-answer, not a disposition; skip it.
            if rdf_data.get('boardConclusionType') and rdf_data['boardConclusionType'] != 'unknown':
                g.add((uri, PROETHICA['boardConclusionType'],
                       Literal(rdf_data['boardConclusionType'])))
            if rdf_data.get('conclusionNumber'):
                g.add((uri, PROETHICA['conclusionNumber'], Literal(int(rdf_data['conclusionNumber']), datatype=XSD.integer)))
            # Readable rdfs:label, mirroring the question treatment
            # (2026-07-10): 'Board conclusion 1: <snippet>' /
            # 'Analytical conclusion 2: <snippet>'.
            _rl = _readable_conclusion_label(rdf_data)
            if _rl:
                g.remove((uri, RDFS.label, None))
                g.add((uri, RDFS.label, Literal(_rl)))
            if rdf_data.get('extractionReasoning'):
                g.add((uri, PROETHICA['extractionReasoning'], Literal(rdf_data['extractionReasoning'])))
            for i, prov in enumerate(rdf_data.get('citedProvisions', []) or []):
                g.add((uri, PROETHICA['citedProvision'], Literal(prov)))
            # Q&C relationship edge (proethica-cases v3.5.0): the
            # conclusion-to-question linkage is an object property to the
            # same-commit Question_<n> individual (edge-primary, CMT-3; the
            # former proeth:answersQuestion string literal is not emitted).
            for q in rdf_data.get('answersQuestions', []) or []:
                g.add((uri, PROETHICA_CASES['answersQuestion'],
                       case_ns[f"Question_{int(q)}"]))

        elif extraction_type == 'ethical_question' and rdf_data:
            g.add((uri, RDF.type, PROETHICA_CASES.EthicalQuestion))
            if rdf_data.get('questionText'):
                g.add((uri, PROETHICA['questionText'], Literal(rdf_data['questionText'])))
            if rdf_data.get('questionType'):
                g.add((uri, PROETHICA['questionType'], Literal(rdf_data['questionType'])))
            if rdf_data.get('questionNumber'):
                g.add((uri, PROETHICA['questionNumber'], Literal(int(rdf_data['questionNumber']), datatype=XSD.integer)))
            # Q&C relationship edge (proethica-cases v3.5.0): an analytical
            # question links to its source board question as an object
            # property (edge-primary, CMT-3; the proeth:sourceQuestion
            # integer literal is not emitted). The numbering offsets
            # (101/201/301/401) are category codes, not parent pointers;
            # this edge is the only parent linkage.
            if rdf_data.get('sourceQuestion') is not None:
                g.add((uri, PROETHICA_CASES['extendsQuestion'],
                       case_ns[f"Question_{int(rdf_data['sourceQuestion'])}"]))
            if rdf_data.get('ethicalFramework'):
                g.add((uri, PROETHICA['ethicalFramework'],
                       Literal(rdf_data['ethicalFramework'])))
            # Readable rdfs:label (2026-07-10 walkthrough): 'Question_102' is
            # opaque; the number encodes the category (board 1-9; analytical
            # offsets implicit=101+, tension=201+, theoretical=301+,
            # counterfactual=401+). Decode it and lead with a text snippet.
            _rl = _readable_question_label(rdf_data)
            if _rl:
                g.remove((uri, RDFS.label, None))
                g.add((uri, RDFS.label, Literal(_rl)))

        # Step-3 temporal dynamics (Actions / Events). These arrive as a
        # JSON-LD record (@type + proeth:* predicates) from the LangGraph
        # converter, a different shape from the unified Pydantic rdf_data above,
        # which is why they previously fell through to a bare stub.
        elif 'temporal_dynamics' in extraction_type and rdf_data:
            self._add_temporal_fields(g, uri, rdf_data)

        # Generic properties fallback
        elif rdf_data and rdf_data.get('properties'):
            for prop_name, prop_values in rdf_data['properties'].items():
                # Provenance keys are emitted as typed prov:/proeth-prov: triples by
                # _emit_provenance above; skip them here so they are not also emitted
                # as untyped proeth: literals (the double-emission this fixes).
                if prop_name in self._PROV_PROP_KEYS:
                    continue
                # The attributes dict (qualifications/credentials/rights) is emitted
                # as one queryable triple per key, not one opaque stringified-dict
                # literal. Mirrors the per-key convention already in
                # entity_triple_service (PROETHICA[key]).
                if prop_name == 'attributes':
                    import ast
                    attr_dict = prop_values
                    # Stored shape is a single-element list holding the attributes
                    # dict, usually stringified (the storage layer str()s dict
                    # values). Unwrap the list, then literal_eval a stringified dict
                    # -- mirrors the relationships branch below. A non-dict result
                    # falls through to the generic literal so nothing is lost.
                    if isinstance(attr_dict, list) and len(attr_dict) == 1:
                        attr_dict = attr_dict[0]
                    if isinstance(attr_dict, str):
                        try:
                            attr_dict = ast.literal_eval(attr_dict)
                        except Exception:
                            attr_dict = None
                    if isinstance(attr_dict, dict):
                        for attr_key, attr_val in attr_dict.items():
                            if attr_val in (None, '', [], {}):
                                continue
                            # Map recurring professional attributes to the controlled
                            # vocabulary (proeth:hasLicense, ...) so cross-case queries
                            # work. A genuinely case-specific key goes to the single
                            # declared proeth:otherAttribute as "key: value", so the
                            # datatype-predicate space stays finite + fully declared
                            # (closed vocabulary) while the data is preserved; logged so
                            # the tail stays visible for deliberate vocabulary growth.
                            # Normalise the key (snake_case / spaced -> the vocab's
                            # no-separator lowercase form) so 'entity_type' / 'years of
                            # experience' match 'entitytype' / 'yearsofexperience'.
                            _akey = str(attr_key).strip().lower().replace('_', '').replace(' ', '')
                            controlled = self._ATTRIBUTE_VOCAB.get(_akey)
                            if not controlled:
                                logger.info("attributes: case-specific key %r on %s -> "
                                            "proeth:otherAttribute (not in the controlled vocabulary)",
                                            attr_key, str(uri).split('#')[-1])
                            for v in (attr_val if isinstance(attr_val, list) else [attr_val]):
                                if v in (None, ''):
                                    continue
                                lit = v if isinstance(v, (str, int, float, bool)) else str(v)
                                if controlled:
                                    g.add((uri, PROETHICA[controlled], Literal(lit)))
                                else:
                                    g.add((uri, PROETHICA['otherAttribute'], Literal(f"{attr_key}: {lit}")))
                        continue
                # Relationships become real ROLE-to-ROLE edges via a proeth-core
                # relation, instead of opaque stringified dicts. Attached at the
                # ROLE-FACET level (the relationship holds between the role facets,
                # not the bearer Agents) so a defined relational archetype -- e.g.
                # ProviderClientRole equivalentClass Role and (hasClient some Role) --
                # classifies the role. The target must still resolve to a role-bearer's
                # facet; unresolvable / non-role targets are logged and skipped.
                if prop_name == 'relationships':
                    import ast
                    subj = uri  # the source role facet (was the bearer Agent)
                    rels = prop_values if isinstance(prop_values, list) else [prop_values]
                    for rel in rels:
                        r = rel
                        if isinstance(r, str):
                            try:
                                r = ast.literal_eval(r)
                            except Exception as e:
                                logger.warning(f"relationship parse failed, dropped: {rel!r} ({e})")
                                continue
                        if not isinstance(r, dict):
                            logger.warning(f"relationship entry not a dict, dropped: {rel!r}")
                            continue
                        rtype = r.get('type') or r.get('relation') or ''
                        tgt = r.get('target') or r.get('to') or ''
                        if not tgt:
                            logger.warning(f"relationship missing target, dropped: {r!r}")
                            continue
                        if not rtype:
                            logger.warning(f"relationship missing type, dropped: target={tgt!r}")
                            continue
                        tgt_uri = self._resolve_rel_target(str(tgt), ctx=ctx)
                        if tgt_uri is None:
                            logger.info(f"relationship target unresolved, skipped: type={rtype!r} target={tgt!r}")
                            continue
                        # Actor relations hold between role-bearers: validate the target
                        # resolved to a role-bearer's facet (reject a non-role node), but
                        # emit the edge ROLE-to-ROLE -- the target role facet is the object,
                        # not its bearer Agent.
                        if self._target_agent(g, facet_to_agent, tgt_uri) is None:
                            logger.warning(
                                f"relationship target is not a role-bearer, skipped: "
                                f"type={rtype!r} target={tgt!r} resolved={str(tgt_uri).split('#')[-1]}")
                            continue
                        obj = tgt_uri  # the target role facet (was the bearer Agent)
                        relprop, swap = self._rel_property_for(str(rtype))
                        if relprop == 'relatedTo':
                            logger.info(
                                f"relationship type {rtype!r} not in the actor-relation "
                                f"vocabulary; emitted as generic relatedTo")
                        # Orient the directional property: swap=True means the
                        # role-bearer is the object (e.g. a client naming its
                        # provider), so the edge runs target->subject.
                        edge_subj, edge_obj = (obj, subj) if swap else (subj, obj)
                        g.add((edge_subj, PROETHICA_CORE[relprop], edge_obj))
                        # R1 edge-primary relational archetype: materialize the Kong archetype as the
                        # bearing facet's DIRECT rdf:type (CMT-1 reflects the edge resolution). hasClient
                        # / employedBy classify their SUBJECT (provider / employee); the symmetric
                        # professionalPeerOf classifies both endpoints. Tracked so the role_category
                        # fallback is skipped for these facets (the edge wins on conflict).
                        archetype = self._REL_PROP_TO_RELATIONAL_ARCHETYPE.get(relprop)
                        if archetype:
                            g.add((edge_subj, RDF.type, PROETHICA[archetype]))
                            role_edge_archetyped.add(edge_subj)
                            if relprop in self._SYMMETRIC_REL_PROPS:
                                g.add((edge_obj, RDF.type, PROETHICA[archetype]))
                                role_edge_archetyped.add(edge_obj)
                        # PROV-O derivation for the edge (mirrors defeasibility edges);
                        # carries the per-relationship quote when the prompt supplied one.
                        self._emit_relationship_provenance(
                            g, case_ns, edge_subj, relprop, edge_obj, rtype, r.get('quote'))
                    continue
                # Overflow bag: relationships the LLM judged fit NO controlled type. Staged on the existing
                # declared proeth:otherAttribute with a 'rel:' prefix (no new predicate / re-extract needed for
                # the first cut) so the periodic promotion-candidate report can mine them; deliberately NOT
                # mapped to a controlled edge -- these are unvetted. Parallels the attributes->otherAttribute
                # tail; a dedicated proeth:otherRelationship reified node is the recommended refinement.
                # Storage camelCases field names (_to_camel_case in extraction_graph),
                # so the live key is 'additionalRelationships'; the snake_case form is
                # kept for pre-camelCase rows.
                if prop_name in ('additional_relationships', 'additionalRelationships'):
                    import ast
                    rels = prop_values if isinstance(prop_values, list) else [prop_values]
                    for rel in rels:
                        r = rel
                        if isinstance(r, str):
                            try:
                                r = ast.literal_eval(r)
                            except Exception:
                                continue
                        if not isinstance(r, dict):
                            continue
                        rtype = str(r.get('type') or r.get('relation') or '').strip()
                        tgt = str(r.get('target') or r.get('to') or '').strip()
                        if not rtype or not tgt:
                            continue
                        g.add((uri, PROETHICA['otherAttribute'], Literal(f"rel:{rtype} -> {tgt}")))
                        logger.info("additional_relationships: staged overflow rel:%s -> %s on %s",
                                    rtype, tgt, str(uri).split('#')[-1])
                    continue
                if not isinstance(prop_values, list):
                    prop_values = [prop_values]
                safe_prop = self._camelCase(prop_name)
                # CMT-3: do not persist the spec's "Not stored" shadows. A RELATION field is materialized as an
                # object-property edge elsewhere, and a *Class field is the rdf:type (reconstructable from the
                # type chain); writing either here re-introduces a literal shadow of the canonical form.
                # R1: role_category and role_kind are commit routing inputs (they drive the relational
                # archetype + the occupational typing) and are never stored as literals (spec "Not stored").
                from app.services.extraction.field_classification import classify, FieldKind
                if (safe_prop.endswith('Class')
                        or safe_prop in ('roleCategory', 'roleKind')
                        or classify(safe_prop) is FieldKind.RELATION):
                    continue
                prop_uri = PROETHICA[safe_prop]
                for value in prop_values:
                    if value:
                        lit = (self._confidence_literal(value)
                               if safe_prop == 'confidence' else Literal(value))
                        g.add((uri, prop_uri, lit))

        # R1 relational-archetype FALLBACK: a role facet that did NOT receive an edge-derived archetype
        # falls back to its role_category (the four Kong archetypes) for the relational type. Materialized
        # as the individual's direct rdf:type so it sits beside the edge route (edge primary, role_category
        # fallback, edge wins on conflict). Skipped when an actor edge already classified this facet.
        if self._is_role_individual(entity) and uri not in role_edge_archetyped:
            self._apply_role_category_fallback_archetype(g, uri, rdf_data)

    def _apply_role_category_fallback_archetype(self, g: Graph, uri: URIRef, rdf_data: Dict) -> None:
        """Type a role facet to its role_category relational archetype (the fallback when no actor edge
        classified it). role_category is one of the four Kong relational categories; participant /
        stakeholder were removed (occupational, carried by role_kind). public_responsibility lands here
        because owesDutyToward is not materialized per instance (R1)."""
        props = (rdf_data or {}).get('properties', {}) or {}
        rc = (props.get('roleCategory') or props.get('role_category')
              or (rdf_data or {}).get('role_category'))
        if isinstance(rc, list):
            rc = rc[0] if rc else None
        if not rc:
            return
        norm = str(rc).lower().replace(' ', '_').replace('-', '_')
        iri = CATEGORY_TO_ONTOLOGY_IRI.get('roles', {}).get(norm)
        if iri:
            g.add((uri, RDF.type, URIRef(iri)))

    def _object_property_locals(self) -> set:
        """Local names of every owl:ObjectProperty declared in core / intermediate.
        Cached per instance. Used so the temporal serializer never emits a literal
        on an object property (which would make the case OWL-DL inconsistent)."""
        if getattr(self, '_objprop_cache', None) is not None:
            return self._objprop_cache
        names = set()
        base = getattr(self, 'ontologies_dir', None)
        if not base:
            self._objprop_cache = names
            return names
        for fn in ('proethica-core.ttl', 'proethica-intermediate.ttl',
                   'proethica-intermediate-extended.ttl'):
            p = base / fn
            if not p.exists():
                continue
            try:
                gg = Graph()
                gg.parse(p, format='turtle')
            except Exception as e:
                logger.warning(f"Could not parse {fn} for object-property detection: {e}")
                continue
            for s in gg.subjects(RDF.type, OWL.ObjectProperty):
                names.add(str(s).split('#')[-1].split('/')[-1])
        self._objprop_cache = names
        return names

    def _add_temporal_fields(self, g: Graph, uri: URIRef, rdf_data: Dict):
        """Emit the descriptive triples for a temporal (Action/Event) individual
        from its JSON-LD record.

        Types the individual as the core Action/Event class (reasoner-visible,
        links to a real class), maps proeth:description to rdfs:comment, and
        copies the remaining proeth: scalar/list fields as literals. Deliberately
        skips: IRI-valued fields (e.g. proeth:causedByAction -- an ObjectProperty
        whose converter URI scheme differs from the committed individual URIs, so
        it would dangle), nested dicts, and the proeth-scenario:* teaching
        metadata.

        The temporal extractor sometimes carries a literal *description* of an
        obligation/capability under a predicate that is declared as an
        owl:ObjectProperty (e.g. proeth:fulfillsObligation, proeth:requiresCapability).
        Emitting a literal on an object property makes the case OWL-DL inconsistent,
        so such fields are redirected to a datatype sibling predicate (<local>Text)
        which preserves the text without the punning."""
        objprops = self._object_property_locals()
        jtype = rdf_data.get('@type', '')
        local_type = jtype.split(':')[-1] if jtype else ''
        # Type the individual against its 9-component class or its temporal-RDF
        # role class. Actions/Events get the core class (Pellet-visible 9-way
        # disjointness); Allen relations, causal chains, and timelines are
        # intermediate/OWL-Time classes that are not part of the 9-way axiom.
        if local_type in ('Action', 'Event'):
            g.add((uri, RDF.type, PROETHICA_CORE[local_type]))
        elif local_type in ('TemporalRelation', 'CausalChain'):
            g.add((uri, RDF.type, PROETHICA[local_type]))
        elif jtype == 'time:TemporalEntity':
            g.add((uri, RDF.type, TIME['TemporalEntity']))

        # Extraction-time generation timestamp, stamped by the temporal
        # converter (the only extraction-time point in the temporal path).
        # Distinct from the commit-time markers elsewhere in this file; the
        # generic proeth: literal loop below never sees the plain key.
        _gen = rdf_data.get('generatedAtTime')
        if _gen:
            try:
                g.add((uri, PROV.generatedAtTime,
                       Literal(datetime.fromisoformat(str(_gen)), datatype=XSD.dateTime)))
            except (ValueError, TypeError):
                logger.warning("unparseable generatedAtTime %r on temporal individual %s",
                               _gen, uri)

        # The Allen converter emits OWL-Time triples whose object IRI uses the
        # legacy http://proethica.org/cases/{id}#Action_X scheme, but committed
        # individuals live at http://proethica.org/ontology/case/{id}#<safe_label>.
        # Without a remap the time:* triples would dangle. Derive the case-ns
        # base from the subject URI (Allen relations sit in the same case_ns).
        uri_str = str(uri)
        case_ns_base = uri_str.split('#')[0] + '#' if '#' in uri_str else None

        def _remap_legacy_iri(v):
            if not (isinstance(v, str) and v.startswith('http://proethica.org/cases/')):
                return v
            frag = v.split('#')[-1] if '#' in v else v
            # convert_action_to_rdf / convert_event_to_rdf prefix the fragment
            # with Action_ / Event_; strip that to recover the bare label-safe-id
            # which matches commit_case_versioned's safe_label for typical labels.
            if frag.startswith(('Action_', 'Event_')):
                frag = frag.split('_', 1)[1]
            return case_ns_base + frag if case_ns_base else v

        for key, value in rdf_data.items():
            if key.startswith('time:'):
                # OWL-Time predicate (proeth:owlTimeProperty named one of 15
                # intervalBefore/intervalAfter/.../intervalEquals/before/after).
                local = key.split(':', 1)[1]
                for v in (value if isinstance(value, list) else [value]):
                    if v is None or v == '' or isinstance(v, dict):
                        continue
                    if isinstance(v, str) and v.startswith(('http://', 'https://')):
                        g.add((uri, TIME[local], URIRef(_remap_legacy_iri(v))))
                    elif isinstance(v, bool):
                        g.add((uri, TIME[local], Literal(v)))
                    else:
                        g.add((uri, TIME[local], Literal(v if isinstance(v, (int, float)) else str(v))))
                continue
            if not key.startswith('proeth:'):
                continue  # skip @context/@id/@type/rdfs:label and proeth-scenario:*
            local = key.split(':', 1)[1]
            if local == 'causalSequence':
                # The causal sequence is a nested list of step dicts that the generic
                # dict-skip below would drop. Flatten it to numbered literals
                # (proeth:causalStep1..N = "element -- description") so the step-by-step
                # chain survives commit (the decision-point option1..N convention).
                seq = value if isinstance(value, list) else [value]
                step_no = 0
                for step in seq:
                    if not isinstance(step, dict):
                        continue
                    element = str(step.get('proeth:element') or step.get('element') or '').strip()
                    desc = str(step.get('proeth:description') or step.get('description') or '').strip()
                    text = ' -- '.join(p for p in (element, desc) if p)
                    if text:
                        step_no += 1
                        g.add((uri, PROETHICA['causalStep'], Literal(f"{step_no}. {text}")))
                continue
            if local in ('discoveredInSection', 'sourceText', 'discoveredInStep'):
                # Temporal individuals carry provenance inline (no 'properties' wrapper for
                # _emit_provenance to read), so route these to the typed PROV-O predicates
                # here, giving the causal / temporal claims auditable source provenance.
                for v in (value if isinstance(value, list) else [value]):
                    if v in (None, ''):
                        continue
                    if local == 'discoveredInStep':
                        try:
                            g.add((uri, PROETHICA_PROV.discoveredInStep, Literal(int(v), datatype=XSD.integer)))
                        except (TypeError, ValueError):
                            pass
                    else:
                        g.add((uri, PROETHICA_PROV[local], Literal(str(v))))
                continue
            if local == 'eventType':
                # Routing input: drives the three-way origin subClassOf typing
                # (AgentCausedEvent/ExogenousEvent/AutomaticEvent) and is not
                # stored as a literal, matching the shape contract and the
                # class-path routing skip (correspondence audit B5; events
                # previously carried proeth:eventType literals).
                continue
            values = value if isinstance(value, list) else [value]
            for v in values:
                if v is None or v == '' or isinstance(v, dict):
                    continue
                if isinstance(v, str) and v.startswith(('http://', 'https://')):
                    continue  # IRI object refs (the converter's causedByAction reference, canonical case namespace) resolve post-commit via causal_edges; skip
                if local == 'description':
                    g.add((uri, RDFS.comment, Literal(v if isinstance(v, str) else str(v))))
                    continue
                # Redirect literal values on object properties to a datatype sibling
                # so a textual description never sits on an owl:ObjectProperty.
                pred_local = f"{local}Text" if local in objprops else local
                # Preserve native bool/int/float so declared datatype ranges are
                # satisfied (e.g. proeth:temporalSequence has range xsd:nonNegativeInteger;
                # a stringified "6" would violate it and make the case inconsistent).
                if pred_local == 'confidence':
                    lit = self._confidence_literal(v)
                else:
                    lit = Literal(v) if isinstance(v, (bool, int, float)) else Literal(str(v))
                g.add((uri, PROETHICA[pred_local], lit))
