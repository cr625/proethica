"""
Category-resolution mixin for OntServeCommitService.

Extracted verbatim from ontserve_commit_service.py (god-file split
CONTINUATION Item 4, Step 1.6): the core-category resolution helpers
(_established_core_category through _matched_class_override) and the
concept-category / subclass-routing helpers (_get_concept_category through
_canonicalize_with_role_axis_resweep), including the role-axis contradiction
guard. OntServeCommitService gains CategoryResolutionMixin as a base class so
every self._method(...) call site is unaffected.

The role-axis guard logic (_apply_role_axis_guard,
_canonicalize_with_role_axis_resweep) is behavior-sensitive (see the onto
memory reference_role-archetype-axis-semantics) and was moved byte-verbatim.

rdflib namespace constants are redeclared locally rather than imported back
from ontserve_commit_service.py (which imports this module for the mixin),
to avoid a circular import; Namespace equality is string-based so this has
no behavioral effect.
"""

import logging
from typing import Any, Dict, Optional

from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL

from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI

logger = logging.getLogger(__name__)

# Namespaces (see ontserve_commit_service.py module docstring for the shared definitions).
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")


class CategoryResolutionMixin:
    """Core-category resolution, subclass routing, and the role-axis guard."""

    def _established_core_category(self, class_local_name: str) -> Optional[str]:
        """Return the core category an EXISTING intermediate class already chains
        to (via rdfs:subClassOf*), or None if the class is unknown / has no core
        ancestor.

        Used to avoid re-declaring a category-derived parent for a class
        the ontology already defines: e.g. proeth:CompetenceSelfAssessmentCapability is
        subClassOf proeth-core:Capability in proethica-intermediate, so a commit
        must NOT add proeth-core:Principle just because an instance's routing
        category says "Principle" -- that second disjoint parent makes the case
        OWL-DL inconsistent. The ontology definition wins over the (lie-prone)
        routing category. Mirrors pellet_validate's skip-if-parent-exists rule
        at commit time rather than as an after-the-fact in-memory patch.

        Delegates to the shared CategoryResolver (one implementation, shared with
        the matcher cross-category gate), pinned to this service's ontologies_dir.
        """
        return self._base_ontology_index.established_core_category(class_local_name)

    def _base_core_category(self, class_local_name: str) -> Optional[str]:
        """Core category an IRI is reserved for in the IMMUTABLE base (core +
        intermediate ONLY, NOT the extended store).

        `_established_core_category` includes proethica-intermediate-extended, which
        a re-extraction is actively writing -- so once a colliding class is written
        there it masks the conflict (it would report the just-written category).
        The base is fixed during a run, so it is the authority for deciding whether
        a label collides with a reserved category. Cached per instance. e.g.
        CompetenceSelfAssessmentCapability -> Capability (reserved by proethica-intermediate),
        regardless of what a principle pass tries to write to the same IRI.
        """
        return self._base_ontology_index.base_core_category(class_local_name)

    _NINE_CORE = {'Role', 'Principle', 'Obligation', 'State', 'Resource',
                  'Action', 'Event', 'Capability', 'Constraint'}

    def _core_category_of_iri(self, iri: str) -> Optional[str]:
        """Core category an IRI resolves to: the IRI itself when it IS one of
        the nine core classes, else the base map (core + intermediate)."""
        local = str(iri).split('#')[-1].split('/')[-1]
        if str(iri).startswith(str(PROETHICA_CORE)) and local in self._NINE_CORE:
            return local
        return self._base_core_category(local)

    def _graph_core_category(self, g, class_uri) -> Optional[str]:
        """Core category a class's EXISTING subClassOf chain reaches, walking
        the given graph (the extended store being written) with the base map
        resolving parents declared outside it. None when the chain reaches no
        core class (the caller then has no ground to veto on)."""
        seen = set()

        def walk(cls):
            if cls in seen:
                return None
            seen.add(cls)
            cat = self._core_category_of_iri(str(cls))
            if cat:
                return cat
            for sup in g.objects(cls, RDFS.subClassOf):
                r = walk(sup)
                if r:
                    return r
            return None

        for sup in g.objects(class_uri, RDFS.subClassOf):
            r = walk(sup)
            if r:
                return r
        return None

    def _category_safe_class_local(self, class_local_name: str, concept_category: Optional[str]) -> str:
        """Disambiguate a class local name when it collides, in the immutable base,
        with a DIFFERENT (disjoint) core category than the entity's own.

        The nine core categories are mutually disjoint, so a Principle minted onto
        proeth:CompetenceSelfAssessmentCapability (reserved by the base for Capability) makes the
        case OWL-DL inconsistent. Rather than dual-class one IRI, give the new
        concept its own IRI by appending its category (CompetenceSelfAssessmentCapabilityPrinciple).
        No-op when there is no collision (the common case) or no category."""
        if not concept_category:
            return class_local_name
        base_cat = self._base_core_category(class_local_name)
        if base_cat and base_cat != concept_category:
            disambiguated = f"{class_local_name}{concept_category}"
            logger.info(
                "Cross-category IRI collision: %s is reserved for %s in the base but "
                "carries routing category %s; minting %s instead.",
                class_local_name, base_cat, concept_category, disambiguated)
            return disambiguated
        return class_local_name

    def _matched_class_override(self, rdf_data: Dict, concept_cat: Optional[str],
                                minted_type_uris) -> Optional[str]:
        """Matched-class honoring (definition-prompt audit Stage 2): the local name of the
        EXISTING ontology class to type this individual to instead of the minted
        near-duplicate, or None to keep the minted types exactly as today.

        The matcher's decision (matchesExisting + matchedOntologyClass) previously reached
        the case TTL only as XAI annotation provenance while the rdf:type still came from
        the minted class ref, so a run could commit proeth:DisclosureObligation while its
        own matchedOntologyClass said proeth:AttributionObligation with matchesExisting
        true. Honor the match, but ONLY after the matched class's curated subClassOf*
        chain (the same CategoryResolver the subclass-emission guard uses) resolves to the
        SAME core category as the component being committed -- the KI2026 lesson: never
        assert a class whose chain conflicts, and concepts# rows may have no chain to the
        component category at all. On chain failure, an unsafe local name, or any lookup
        error: fall back to the minted class exactly as today, logging the fallback.
        """
        try:
            md = (rdf_data or {}).get('match_decision') or {}
            if not md.get('matches_existing'):
                return None
            matched_uri = md.get('matched_uri')
            if not matched_uri or not concept_cat:
                return None
            matched_local = str(matched_uri).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
            if not matched_local:
                return None
            if self._safe_local_name(matched_local) != matched_local:
                # A local name the URI sanitizer would mangle (e.g. concepts#Non_Deception)
                # cannot round-trip through the minted-IRI conventions; keep the minted type.
                logger.info(
                    "Matched-class honoring fallback: matched class %s has a non-URI-safe "
                    "local name; keeping minted type(s).", matched_uri)
                return None
            minted_locals = {
                self._safe_local_name(str(u).rsplit('#', 1)[-1].rsplit('/', 1)[-1])
                for u in (minted_type_uris or [])
            }
            if matched_local in minted_locals:
                return None  # already typed to the matched class; nothing to honor
            chain_cat = self._established_core_category(matched_local)
            if chain_cat != concept_cat:
                logger.info(
                    "Matched-class honoring fallback: matched class %s chains to %s but the "
                    "component being committed is %s; keeping minted type(s) %s.",
                    matched_uri, chain_cat, concept_cat, sorted(minted_locals))
                return None
            logger.info(
                "Honoring matched ontology class %s (chain=%s) instead of minted type(s) %s.",
                matched_local, chain_cat, sorted(minted_locals))
            return matched_local
        except Exception as e:
            logger.warning(
                "Matched-class honoring lookup failed (%s); keeping minted type(s).", e)
            return None

    # Maps extraction_type (or entity_type for temporal_dynamics) to:
    #   (category_field_name, CATEGORY_TO_ONTOLOGY_IRI key, fallback core class URI)
    # Maps extraction_type (+ entity_type for temporal_dynamics) to the base
    # concept name used for display categorization in OntServe case views.
    _EXTRACTION_TO_CONCEPT = {
        'roles': 'Role',
        'principles': 'Principle',
        'obligations': 'Obligation',
        'states': 'State',
        'resources': 'Resource',
        'actions': 'Action',
        'events': 'Event',
        'capabilities': 'Capability',
        'constraints': 'Constraint',
    }

    def _get_concept_category(self, entity) -> str | None:
        """Derive base concept category from extraction_type/entity_type.

        Returns one of the 9 concept names (Role, Principle, ...) or None
        for non-concept entities (arguments, decision points, etc.).
        """
        ext_type = (entity.extraction_type or '').lower()

        # Direct match (steps 1-2)
        concept = self._EXTRACTION_TO_CONCEPT.get(ext_type)
        if concept:
            return concept

        # Step 3 temporal_dynamics: entity_type carries the concept
        if 'temporal_dynamics' in ext_type:
            etype = (entity.entity_type or '').lower().rstrip('s')
            for key, val in self._EXTRACTION_TO_CONCEPT.items():
                if key.startswith(etype):
                    return val

        return None

    _CONCEPT_CATEGORY_CONFIG = {
        'roles':        [('role_category',       'roles',                  f'{PROETHICA_CORE}Role')],
        'principles':   [('principle_category',  'principles',             f'{PROETHICA_CORE}Principle')],
        'obligations':  [('obligation_type',     'obligations',            f'{PROETHICA_CORE}Obligation')],
        'states':       [('state_category',      'states',                 f'{PROETHICA_CORE}State')],
        'resources':    [('resource_category',   'resources',              f'{PROETHICA_CORE}Resource')],
        'actions':      [('action_category',     'actions',                f'{PROETHICA_CORE}Action')],
        'events':       [('event_category',      'events',                 f'{PROETHICA_CORE}Event')],
        'capabilities': [('capability_category', 'capabilities',           f'{PROETHICA_CORE}Capability')],
        'constraints':  [('constraint_type',     'constraints',            f'{PROETHICA_CORE}Constraint')],
    }

    def _resolve_subclass_uris(self, entity, rdf_data: Dict) -> list[str]:
        """
        Resolve the rdfs:subClassOf target(s) for a class entity.

        Checks rdf_json_ld for category fields from the unified Pydantic schemas
        and looks them up in CATEGORY_TO_ONTOLOGY_IRI.  Falls back to the core
        concept class (e.g. proethica-core#Role) for legacy data without category.

        Multi-axis concepts (obligations, constraints) can produce two subclass
        URIs -- one per axis.
        """
        concept_type = (entity.extraction_type or '').lower()
        entity_type_lower = (entity.entity_type or '').lower()

        # For temporal_dynamics_enhanced, the entity_type carries the actual
        # concept (e.g. 'actions' or 'events') rather than extraction_type.
        if 'temporal_dynamics' in concept_type:
            key = entity_type_lower.rstrip('s') if entity_type_lower else concept_type
            # Normalize to plural form used in config
            for config_key in self._CONCEPT_CATEGORY_CONFIG:
                if config_key.startswith(key):
                    concept_type = config_key
                    break

        axes = self._CONCEPT_CATEGORY_CONFIG.get(concept_type)
        if not axes:
            # Unrecognized concept type -- try substring match for robustness
            for config_key, config_axes in self._CONCEPT_CATEGORY_CONFIG.items():
                if config_key in concept_type or config_key in entity_type_lower:
                    axes = config_axes
                    concept_type = config_key
                    break

        if not axes:
            logger.warning(f"No category config for extraction_type={entity.extraction_type}, "
                          f"entity_type={entity.entity_type}")
            return []

        result = []
        props = (rdf_data or {}).get('properties', {})

        for category_field, iri_map_key, fallback_uri in axes:
            # Check for category value in rdf_json_ld properties
            category_value = None
            if props:
                vals = props.get(category_field)
                if vals:
                    category_value = vals[0] if isinstance(vals, list) else vals
            # Also check top-level rdf_json_ld (unified extractor stores flat)
            if not category_value and rdf_data:
                category_value = rdf_data.get(category_field)

            if category_value:
                # Normalize enum value (Pydantic may store as 'provider_client' or 'ProviderClient')
                normalized = category_value.lower().replace(' ', '_').replace('-', '_')
                iri_map = CATEGORY_TO_ONTOLOGY_IRI.get(iri_map_key, {})
                iri = iri_map.get(normalized)
                if iri:
                    result.append(iri)
                elif fallback_uri:
                    if iri_map:
                        # A populated vocabulary missed the value: a retired kind or a
                        # typo, not the by-design empty actions map (ONT-4 bare Action).
                        logger.warning(
                            "Class routing: category value %r not in the %s vocabulary; "
                            "falling back to the bare core parent", normalized, iri_map_key)
                    result.append(fallback_uri)
            elif fallback_uri:
                # No category info (legacy data) -- use core class
                result.append(fallback_uri)

        # Occupational archetype axis for roles. The relational axis is handled above via
        # role_category; a role class chains through BOTH an occupational and a relational
        # archetype (multi-inheritance). The label carries the occupational signal. The
        # occupational archetype subClassOf*-chains to core:Role, so a bare core:Role
        # fallback becomes redundant and is dropped.
        if concept_type == 'roles':
            from app.services.extraction.role_archetype_resolver import resolve_occupational_archetype
            occ = resolve_occupational_archetype(entity.entity_label)
            core_role = f'{PROETHICA_CORE}Role'
            if occ:
                result = [r for r in result if r != core_role]
                if occ not in result:
                    result.append(occ)
            else:
                # roleKind backstop for the CLASS path, mirroring
                # _role_individual_occupational_parents (decision R1): when the
                # occupational resolver matches no head, the extraction's own
                # professional/participant call parents the minted class onto the
                # occupational axis, so the class chain carries the axis the roleKind
                # contract promises ("for a matched existing class the axis is carried
                # by the class chain"). Before this, a novel head with a stated
                # roleKind was minted at bare core:Role (the 2026-07-05 AffectedPartyRole/
                # BusinessManagerRole/MunicipalityRole mints), so a later case matching
                # it would inherit no axis. With neither signal the class stays bare
                # core:Role for the conformance gate to flag.
                rk = self._extract_role_kind(rdf_data)
                axis = {'professional': f'{PROETHICA}ProfessionalRole',
                        'participant': f'{PROETHICA}ParticipantRole'}.get(rk or '')
                if axis:
                    result = [r for r in result if r != core_role]
                    if axis not in result:
                        result.append(axis)

        return result

    def _role_individual_occupational_parents(self, rdf_data: Dict, type_class_name: str) -> list[str]:
        """OCCUPATIONAL archetype subClassOf URI(s) for the GENUINELY-NEW class a role INDIVIDUAL is
        typed under, with the role_kind backstop.

        The matcher sometimes types a role individual under a compound class that diverges from its own
        role_class entity. This attaches the OCCUPATIONAL axis (resolved from the de-camelCased type-class
        name) to the class the individual really bears. When the occupational resolver matches no head,
        the role_kind backstop types the class onto ProfessionalRole / ParticipantRole (decision R1 /
        professional-participant typing), closing the novel-role bare-core:Role gap without overriding the
        resolver; when role_kind is absent too, nothing is appended and the role stays bare core:Role for
        the conformance gate to flag.

        The RELATIONAL axis is no longer attached here (R-spec migration): the relational archetype is
        materialized edge-primary on the INDIVIDUAL as a direct rdf:type from the actor edge (with the
        role_category individual-fallback in _apply_role_category_fallback_archetype), so the edge can win
        on conflict. The class-level relational subClassOf for a new role CLASS is still emitted by
        _resolve_subclass_uris on the class-commit path."""
        import re
        parents: list[str] = []
        from app.services.extraction.role_archetype_resolver import resolve_occupational_archetype
        label = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', type_class_name or '')
        occ = resolve_occupational_archetype(label)
        if occ:
            parents.append(occ)
        else:
            rk = self._extract_role_kind(rdf_data)
            if rk == 'professional':
                parents.append(f'{PROETHICA}ProfessionalRole')
            elif rk == 'participant':
                parents.append(f'{PROETHICA}ParticipantRole')
        return parents

    @staticmethod
    def _extract_role_kind(rdf_data: Dict) -> Optional[str]:
        """The extraction's own professional-vs-participant call for a role
        individual (an R1 commit routing input, never stored as a literal),
        normalized to 'professional' / 'participant', or None when the signal
        is absent or unrecognized. Single reader shared by the occupational
        backstop and the role-axis contradiction guard."""
        props = (rdf_data or {}).get('properties', {}) or {}
        rk = (props.get('roleKind') or props.get('role_kind')
              or (rdf_data or {}).get('role_kind'))
        if isinstance(rk, list):
            rk = rk[0] if rk else None
        rk = str(rk).lower().strip() if rk else None
        return rk if rk in ('professional', 'participant') else None

    def _apply_role_axis_guard(self, g: Graph, role_kind_by_uri: Dict) -> int:
        """Professional/participant occupational-axis contradiction guard (the
        case-4 lesson).

        Run 20 committed a role individual typed BOTH proeth:PublicRole (a
        ParticipantRole descendant) AND proeth:PublicResponsibilityRole
        (rdfs:subClassOf ProfessionalRole -- explicit in intermediate since
        2026-07-02, previously only entailed via owesDutyToward's domain),
        which the ProfessionalRole owl:disjointWith ParticipantRole axiom makes
        Pellet-inconsistent. The Stage-2 chain guard cannot catch this: both
        classes chain to core:Role; the professional/participant axis sits
        BELOW the nine core categories.

        Runs once per commit over the FINALIZED graph, after every rdf:type
        source (the minted/matched type list, the edge-derived relational
        archetype, and the role_category fallback -- where public_responsibility
        lands). Each asserted class resolves to the axis via the curated
        subclass closure (RoleAxisResolver, the same tiers CategoryResolver
        reads), extended through case-local rdfs:subClassOf edges in THIS graph
        so a genuinely-new class parented onto an axis head by the role_kind
        backstop resolves too. The guard acts ONLY when one individual's
        classes provably land on BOTH sides: classes with no path to either
        head are ignored, and a one-sided individual passes through untouched
        (no count-reducing filter -- individuals are never dropped, only the
        contradicting type triples). On contradiction the side contradicting
        the extraction's own role_kind decision is dropped; with no role_kind
        signal the professional side is dropped (participant standing is the
        weaker commitment). Every drop is logged and surfaced in the commit
        stats (role_axis_vetoes), like the terminates veto.

        Returns the number of rdf:type triples removed.
        """
        from app.services.extraction.category_resolver import resolve_role_axis

        def _axes_of(cls) -> set:
            seen, stack, found = set(), [cls], set()
            while stack:
                c = stack.pop()
                if c in seen or not isinstance(c, URIRef):
                    continue
                seen.add(c)
                axis = resolve_role_axis(str(c))
                if axis:
                    found.add(axis)
                    continue
                stack.extend(g.objects(c, RDFS.subClassOf))
            return found

        dropped_total = 0
        for subj in set(g.subjects(RDF.type, None)):
            by_axis: Dict[str, list] = {}
            for t in set(g.objects(subj, RDF.type)):
                if not isinstance(t, URIRef):
                    continue
                axes = _axes_of(t)
                if len(axes) == 1:
                    by_axis.setdefault(next(iter(axes)), []).append(t)
                # len(axes) == 2 means the CLASS itself is two-sided; that is a
                # base/case-graph defect for Pellet to flag, not attributable to
                # one side here, so the class is left alone.
            prof = by_axis.get('professional')
            part = by_axis.get('participant')
            if not prof or not part:
                continue  # no provable two-sided contradiction; never touch
            rk = role_kind_by_uri.get(subj)
            drop, keep = (part, prof) if rk == 'professional' else (prof, part)
            for t in sorted(drop):
                g.remove((subj, RDF.type, t))
                dropped_total += 1
            logger.warning(
                "Role-axis guard: %s carried rdf:type classes on BOTH sides of "
                "the ProfessionalRole/ParticipantRole disjointness "
                "(professional=%s, participant=%s); role_kind=%s -> dropped %s, "
                "kept %s (the case-4 run-20 lesson).",
                str(subj).split('#')[-1],
                sorted(str(u).split('#')[-1] for u in prof),
                sorted(str(u).split('#')[-1] for u in part),
                rk,
                sorted(str(u).split('#')[-1] for u in drop),
                sorted(str(u).split('#')[-1] for u in keep),
            )
        return dropped_total

    def _prune_dangling_qc_edges(self, g: Graph) -> int:
        """Finalized-graph sweep: drop any answersQuestion / extendsQuestion
        edge whose target Question individual is not typed in the commit graph.

        The question numbers behind the edge URIs are raw LLM output
        (answersQuestions on conclusions, sourceQuestion on analytical
        questions). A hallucinated or stale number would mint an edge to a
        nonexistent individual, and the declared range then INFERS
        rdf:type EthicalQuestion onto the phantom node instead of failing,
        so the Pellet gate cannot catch it. Mirrors the backfill script's
        never-fabricate-an-endpoint rule; every drop is logged.
        """
        dropped = 0
        for pred in (PROETHICA_CASES['answersQuestion'],
                     PROETHICA_CASES['extendsQuestion']):
            for s, o in list(g.subject_objects(pred)):
                if (o, RDF.type, PROETHICA_CASES.EthicalQuestion) not in g:
                    g.remove((s, pred, o))
                    dropped += 1
                    logger.warning(
                        "Dropped dangling Q&C edge %s -> %s (%s): no "
                        "EthicalQuestion individual with that URI in the "
                        "commit graph", s, o, pred)
        return dropped

    def _canonicalize_with_role_axis_resweep(
        self, case_id, ttl_path, role_kind_by_uri: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Canonicalization + post-canonicalization role-axis RE-SWEEP: the
        single entry point for the commit-time canonicalization step.

        The ordering gap (model-split adversarial review): canonicalize_ttl
        runs AFTER _apply_role_axis_guard in every commit path and can retype
        a role individual from a compound facet class the guard could not
        classify (axis-unresolvable -> ignored) onto an AXIS-SIDED canonical
        role, recreating a provable professional/participant both-sides
        contradiction in the persisted TTL. The pre-canonicalization sweep is
        kept in place (belt and braces -- it sees the extraction's role_kind
        signal at full fidelity over the freshly built graph); this helper
        re-runs the SAME guard over canonicalize_ttl's post-rewrite graph.
        Cheap and idempotent: acts only on provable both-axes conflicts, logs
        every veto (inside the guard), and re-serializes the TTL only when it
        vetoed something.

        Returns the canonicalization stats dict (without the internal _graph
        handle) plus 'role_axis_vetoes_post_canonicalization'.
        """
        from app.services.extraction.canonicalization import canonicalize_ttl
        stats = canonicalize_ttl(case_id, ttl_path)
        # canonicalize_ttl contractually returns its post-rewrite graph under
        # '_graph'; a missing key means the contract changed underneath this
        # re-sweep, so fail loud (no re-parse fallback) via KeyError.
        g = stats.pop('_graph')
        post_vetoes = self._apply_role_axis_guard(g, role_kind_by_uri or {})
        if post_vetoes:
            logger.warning(
                "Role-axis re-sweep AFTER canonicalization vetoed %d rdf:type "
                "triple(s) for case %s: canonicalization retyped a compound "
                "role facet onto an axis-sided canonical role, recreating a "
                "professional/participant contradiction the pre-"
                "canonicalization sweep could not see.",
                post_vetoes, case_id,
            )
            self._sanitize_graph_literals(g)
            g.serialize(destination=str(ttl_path), format='turtle')
        stats['role_axis_vetoes_post_canonicalization'] = post_vetoes
        return stats
