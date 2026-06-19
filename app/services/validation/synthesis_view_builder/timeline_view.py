"""Timeline synthesis view for the user-study interface.

TimelineViewMixin: get_timeline_view plus its main-character helpers
(_timeline_agent_action_counts, _timeline_main_character_labels). Relocated
verbatim from builder.py; SynthesisViewBuilder inherits this mixin so self.
resolution is preserved via MRO. The main-character labeller uses the shared
citation regex / tokenizer from text_helpers.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.models import TemporaryRDFStorage

from .text_helpers import _CITATION_RE, _match_tokens


class TimelineViewMixin:
    """The Timeline synthesis view + main-character helpers."""


    def get_timeline_view(self, case_id: int) -> Dict[str, Any]:
        """Get Timeline view from Step 3 temporal extraction.

        Returns Actions and Events in temporal sequence with decision-point
        nesting and causal flow. Per HyperText'26 section 3.2:
        - Actions = volitional conduct by identified participants
        - Events = occurrences outside agent control
        - Decision points synthesized in Step 4 nest beneath the Action/Event
          they originate from.

        Data source: `temporal_dynamics_enhanced` rows in `temporary_rdf_storage`
        carry typed JSON-LD with `@type` = `proeth:Action` | `proeth:Event`,
        `proeth:temporalMarker`, `proeth-scenario:isDecisionPoint`,
        `proeth-scenario:alternativeActions`, and obligation links.
        """
        # Load all temporal rows; chronological ordering uses
        # `proeth:temporalSequence` (1-based int) when present and falls back
        # to `id` for cases the temporal-sequence backfill has not visited.
        # See docs-internal/scripts/backfill_temporal_sequence.py and the
        # roadmap entry "Timeline Chronological Ordering".
        temporal_entries = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).order_by(TemporaryRDFStorage.id).all()

        def _temporal_sort_key(row):
            seq = (row.rdf_json_ld or {}).get('proeth:temporalSequence')
            try:
                seq_int = int(seq) if seq is not None else None
            except (TypeError, ValueError):
                seq_int = None
            # Rows with a sequence sort before rows without one; among the
            # latter, fall back to id (extraction order) as a stable tiebreak.
            return (0, seq_int) if seq_int is not None else (1, row.id)

        temporal_entries = sorted(temporal_entries, key=_temporal_sort_key)

        entries = []
        causal_flow = []

        def _uri_fragment(uri: str) -> str:
            frag = uri.split('#')[-1] if '#' in uri else ''
            for prefix in ('Action_', 'Event_'):
                if frag.startswith(prefix):
                    frag = frag[len(prefix):]
                    break
            return frag

        seq = 0
        for row in temporal_entries:
            rdf = row.rdf_json_ld or {}
            at_type = rdf.get('@type', '') or ''
            if 'Action' in at_type:
                kind = 'action'
            elif 'Event' in at_type:
                kind = 'event'
            else:
                # Skip Timeline-skeleton, State, and other temporal types that
                # production also excludes from the rendered timeline.
                continue
            seq += 1
            alternatives = rdf.get('proeth-scenario:alternativeActions', []) or []

            fulfills = rdf.get('proeth:fulfillsObligation', []) or []
            violates = rdf.get('proeth:violatesObligation', []) or []
            raises = rdf.get('proeth:raisesObligation', []) or []

            entry_iri = rdf.get('@id', '')
            entry = {
                'sequence': seq,
                'kind': kind,
                'label': row.entity_label,
                'entity_iri': entry_iri,
                'fragment': _uri_fragment(entry_iri),
                'temporal_marker': rdf.get('proeth:temporalMarker', ''),
                'agent': rdf.get('proeth:hasAgent', ''),
                # Per-event role context (study-corrections A7/B4). Present on
                # backfilled and newly-extracted rows; legacy rows leave it ''
                # and the template falls back to splitting the "(role)" suffix
                # out of `agent` inline.
                'event_role_context': rdf.get('proeth:eventRoleContext', ''),
                'narrative_role': rdf.get('proeth-scenario:narrativeRole', ''),
                'description': rdf.get('proeth:description', ''),
                'alternative_count': len(alternatives) if isinstance(alternatives, list) else 0,
                'fulfills_obligations': fulfills if isinstance(fulfills, list) else [],
                'violates_obligations': violates if isinstance(violates, list) else [],
                'raises_obligations': raises if isinstance(raises, list) else [],
                'decision_points': [],  # filled below by fragment match
            }
            entries.append(entry)

            foreseen = rdf.get('proeth:foreseenUnintendedEffects', [])
            if isinstance(foreseen, list):
                for effect in foreseen:
                    causal_flow.append({
                        'from_label': row.entity_label,
                        'to_label': effect,
                        'relation': 'enables'
                    })

        # Match synthesized decision points to their temporal-entry host
        # (same URI-fragment strategy as the production step4 review helper).
        fragment_to_idx = {e['fragment']: i for i, e in enumerate(entries) if e['fragment']}
        dp_rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='canonical_decision_point'
        ).order_by(TemporaryRDFStorage.created_at).all()

        for dp_row in dp_rows:
            data = dp_row.rdf_json_ld or {}
            action_uris = data.get('involved_action_uris') or []
            if not action_uris:
                single = data.get('action_uri') or ''
                if single:
                    action_uris = [single]

            matched_indices = set()
            for uri in action_uris:
                frag = _uri_fragment(uri)
                if frag in fragment_to_idx:
                    matched_indices.add(fragment_to_idx[frag])

            if not matched_indices:
                continue

            # Primary host = earliest matching temporal entry.
            primary = min(matched_indices)
            entries[primary]['decision_points'].append({
                'focus_id': data.get('focus_id', ''),
                'focus_number': data.get('focus_number', 0),
                'entity_label': data.get('description', dp_row.entity_label),
                'options': data.get('options', []) or [],
            })

        entries_with_dps = sum(1 for e in entries if e['decision_points'])
        total_dps_attached = sum(len(e['decision_points']) for e in entries)

        return {
            'view_type': 'timeline',
            'count': len(entries),
            'action_count': sum(1 for e in entries if e['kind'] == 'action'),
            'event_count': sum(1 for e in entries if e['kind'] == 'event'),
            'decision_point_count': total_dps_attached,
            'entries_with_decision_points': entries_with_dps,
            'entries': entries,
            'causal_flow': causal_flow,
            'description': 'Actions and Events in temporal sequence with decision points '
                          'nested beneath their corresponding entries; causal flow shows '
                          'enables links between actions and events.'
        }

    def _timeline_agent_action_counts(self, case_id: int) -> Dict[str, int]:
        """Count timeline Actions per agent short-name (study-corrections A9).

        Returns {lowercased 2-word short-name -> number of Actions whose
        `proeth:hasAgent` resolves to that short-name}. Composite/conjunctive
        agents (still carrying a parenthetical role, "and"/"/" joiners after
        the A7/B4 split) are skipped: they name multiple actors and cannot be
        attributed to a single character. Events are excluded (no agent).
        """
        from collections import Counter
        rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='temporal_dynamics_enhanced'
        ).all()
        counts: Counter = Counter()
        for r in rows:
            rdf = r.rdf_json_ld or {}
            if 'Action' not in (rdf.get('@type', '') or ''):
                continue
            agent = (rdf.get('proeth:hasAgent') or '').strip()
            if not agent or agent.lower() == 'unknown':
                continue
            low = agent.lower()
            # Skip composites: a clean agent has no parenthetical role left
            # (A7/B4 split it into eventRoleContext) and no conjunctive joiner.
            if '(' in agent or ' and ' in low or ' and/or ' in low or '/' in agent:
                continue
            words = agent.split()
            short = ' '.join(words[:2]).lower() if len(words) >= 2 else low
            counts[short] += 1
        return dict(counts)

    def _timeline_main_character_labels(
        self, case_id: int, characters: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Resolve multi-action timeline agents to narrative characters.

        Returns ``{character_label: action_count}`` for every character that is
        the agent of >=2 timeline Actions, so the caller can mark it ``is_main``
        (study-corrections A9). This supersedes the old first-two-words label
        match in the promotion loop: Step-3 emits clean generic agent names
        ("City Council", "Professional Engineer") while Phase-4 characters carry
        descriptive role-derived labels ("City Municipal Government Client",
        "Part-Time City Engineer Advisory Design") that share no reliable key,
        so a raw label match promotes nothing (case 103 surfaced this).

        Two stages per agent:
          1. **Prefix match** — a character whose short-name (first two words,
             or three when word three is a single-letter NSPE disambiguator)
             equals the agent's short-name, or whose label starts with the
             agent string. This reproduces the prior behaviour for clean labels
             (case 60 "Engineer A", the existing fixtures).
          2. **Token-overlap fallback** (only when stage 1 finds nothing) —
             score each character by shared tokens between the agent text
             (``hasAgent`` + its ``eventRoleContext``) and the character text
             (label + role_type + professional_position). ``eventRoleContext``
             is what bridges the synonym gap ("municipal decision-making body"
             links "City Council" to "...Municipal Government Client"). Promote
             the argmax plus exact ties, requiring a minimum overlap and at most
             two ties so a non-distinctive match (e.g. the bare token "engineer"
             shared by every engineer character) promotes nobody.

        Cited-precedent agents ("Engineer A in BER Case 19-3") are skipped: they
        name actors from other opinions, not present-case agents. `characters`
        is the already-spurious-filtered list, so cited-case characters are not
        candidates either.
        """
        MIN_OVERLAP = 2
        MAX_TIES = 2

        rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='temporal_dynamics_enhanced'
        ).all()

        # Aggregate per distinct agent string: count + union of role contexts.
        agent_counts: Dict[str, int] = {}
        agent_contexts: Dict[str, set] = {}
        for r in rows:
            rdf = r.rdf_json_ld or {}
            if 'Action' not in (rdf.get('@type', '') or ''):
                continue
            agent = (rdf.get('proeth:hasAgent') or '').strip()
            if not agent or agent.lower() == 'unknown':
                continue
            low = agent.lower()
            if '(' in agent or ' and ' in low or ' and/or ' in low or '/' in agent:
                continue  # composite / conjunctive: names >1 actor
            if _CITATION_RE.search(agent):
                continue  # cited-precedent actor, not a present-case agent
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            ctx = (rdf.get('proeth:eventRoleContext') or '').strip()
            agent_contexts.setdefault(agent, set())
            if ctx:
                agent_contexts[agent].add(ctx)

        def _char_short(label: str) -> str:
            parts = label.split()
            if len(parts) >= 3 and len(parts[2]) == 1 and parts[2].isupper():
                return ' '.join(parts[:3]).lower()
            if len(parts) >= 2:
                return ' '.join(parts[:2]).lower()
            return label.lower()

        char_records = []
        for ch in characters:
            label = (ch.get('label') or '').strip()
            if not label:
                continue
            blob = ' '.join([
                label,
                ch.get('role_type') or '',
                ch.get('professional_position') or '',
            ])
            char_records.append({
                'label': label,
                'short': _char_short(label),
                'tokens': _match_tokens(blob),
            })

        promoted: Dict[str, int] = {}

        def _promote(label: str, count: int) -> None:
            promoted[label] = max(promoted.get(label, 0), count)

        for agent, count in agent_counts.items():
            if count < 2:
                continue
            agent_low = agent.lower()
            agent_short = ' '.join(agent.split()[:2]).lower()

            # Stage 1: prefix / short-name match.
            stage1 = [
                c for c in char_records
                if c['short'] == agent_short or c['label'].lower().startswith(agent_low)
            ]
            if stage1:
                for c in stage1:
                    _promote(c['label'], count)
                continue

            # Stage 2: token-overlap fallback bridged by eventRoleContext.
            agent_tokens = _match_tokens(
                agent + ' ' + ' '.join(sorted(agent_contexts.get(agent, set())))
            )
            if not agent_tokens:
                continue
            scored = [
                (len(agent_tokens & c['tokens']), c['label']) for c in char_records
            ]
            best = max((s for s, _ in scored), default=0)
            if best < MIN_OVERLAP:
                continue
            winners = [lbl for s, lbl in scored if s == best]
            if len(winners) > MAX_TIES:
                continue  # too ambiguous to attribute
            for lbl in winners:
                _promote(lbl, count)

        return promoted
