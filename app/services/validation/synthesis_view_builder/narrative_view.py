"""
Synthesis View Builder -- narrative view (Step 4 Phase 4).

get_narrative_view (the largest builder method: characters + ethical tensions +
opening states) split out as a mixin. Mixed into SynthesisViewBuilder; `self.`
resolution (e.g. self._fetch_class_definitions, kept on the class) is preserved by MRO.
"""

import json
import re
from typing import Dict, List, Optional, Any
from app.models import db, Document, TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document_section import DocumentSection

from .text_helpers import _CITATION_RE, _MATCH_STOPWORDS, _match_tokens


class NarrativeViewMixin:
    """Phase-4 narrative view. Mixed into SynthesisViewBuilder."""

    def get_narrative_view(self, case_id: int) -> Dict[str, Any]:
        """Get Narrative view content per paper \u00a73.2 (integrative view).

        Returns the character-driven retelling: characters drawn from
        extracted Roles, ethical tensions drawn from Obligations and
        Constraints (stored as `conflicts` in Phase 4 output), and an
        opening-context paragraph drawn from States (in second-person
        address).

        The Phase 4 JSON is nested
        (`narrative_elements.characters`, `narrative_elements.conflicts`,
        `scenario_seeds.opening_context`); this builder flattens those
        shapes so the template can render each section uniformly.
        """
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(
            ExtractionPrompt.created_at.desc()
        ).first()

        raw: Dict[str, Any] = {}
        if phase4_prompt and phase4_prompt.raw_response:
            try:
                raw = json.loads(phase4_prompt.raw_response)
            except json.JSONDecodeError:
                pass

        narrative_elements = raw.get('narrative_elements') or {}
        scenario_seeds = raw.get('scenario_seeds') or {}

        characters = narrative_elements.get('characters') or []
        raw_tensions = narrative_elements.get('conflicts') or []
        opening_context = scenario_seeds.get('opening_context') or ''

        # Filter spurious characters surfaced by the second-pass content
        # review (cases 11, 19, 60). The extractor sometimes promotes
        # citations to prior BER cases or non-person entities (states,
        # jurisdictions, cities) into the character set. These should
        # never reach a participant-facing Narrative card.
        #
        # Citation pattern: a label that references a prior BER opinion
        # ('Case NN-N', 'BER Case 19-3') anywhere -- as a prefix, suffix, or
        # mid-label -- names an actor from another opinion, not a present-case
        # person (case 60: "BER Case 04-11 Engineer State E Business Card",
        # "Engineer A BER Case 19-3 Standards Chair", "Engineer Intern BER Case
        # 20-1"). Place / jurisdiction patterns: labels beginning with 'State ',
        # 'City of ', 'Jurisdiction', 'Country' identify a place rather than a
        # person. See module-level _CITATION_RE.
        _PLACE_PREFIXES = ('state ', 'city of ', 'jurisdiction', 'country ')

        def _is_spurious_character(ch: Dict[str, Any]) -> bool:
            label = (ch.get('label') or '').strip()
            if not label:
                return False
            if _CITATION_RE.search(label):
                return True
            if label.lower().startswith(_PLACE_PREFIXES):
                return True
            return False

        characters = [c for c in characters if not _is_spurious_character(c)]

        protagonist_label = scenario_seeds.get('protagonist_label') or ''

        # Flatten tensions + attach a composite moral-intensity score (Jones 1991)
        # so the template can sort rated tensions above unrated ones. Each of the
        # five intensity dimensions maps to a 0-3 ordinal; the composite is the
        # sum. Unrated tensions score 0 and sink to the bottom of the list.
        INTENSITY_SCORES = {
            'low': 1, 'medium': 2, 'high': 3,
            'distal': 1, 'near-term': 2, 'immediate': 3,
            'indirect': 1, 'direct': 3,
            'dispersed': 1, 'concentrated': 3,
        }
        def _score(*values: str) -> int:
            return sum(INTENSITY_SCORES.get((v or '').lower(), 0) for v in values)

        tensions = []
        for c in raw_tensions:
            composite = _score(
                c.get('magnitude_of_consequences'),
                c.get('probability_of_effect'),
                c.get('temporal_immediacy'),
                c.get('proximity'),
                c.get('concentration_of_effect'),
            )
            tensions.append({
                'description': c.get('description') or '',
                'conflict_type': c.get('conflict_type') or '',
                'entity1_label': c.get('entity1_label') or '',
                'entity1_type': c.get('entity1_type') or '',
                'entity2_label': c.get('entity2_label') or '',
                'entity2_type': c.get('entity2_type') or '',
                'magnitude_of_consequences': c.get('magnitude_of_consequences') or '',
                'probability_of_effect': c.get('probability_of_effect') or '',
                'temporal_immediacy': c.get('temporal_immediacy') or '',
                'proximity': c.get('proximity') or '',
                'concentration_of_effect': c.get('concentration_of_effect') or '',
                'affected_role_labels': c.get('affected_role_labels') or [],
                'resolution_rationale': c.get('resolution_rationale') or '',
                'intensity_score': composite,
            })
        # Sort descending by composite intensity; stable for ties so the
        # extractor's emission order is preserved within equal-intensity bands.
        tensions.sort(key=lambda t: t['intensity_score'], reverse=True)
        rated_tension_count = sum(1 for t in tensions if t['intensity_score'] > 0)

        # Group tensions by the characters they affect. Each tension carries an
        # affected_role_labels list; a tension that implicates multiple roles
        # appears under each (no dedup) because the data signals "these
        # characters are co-implicated" and hiding that would lose the chain.
        # Match priority:
        #   1. Exact match of role-label against character.label or character.role.
        #   2. Case-insensitive substring match between role-label and character labels.
        #   3. Fallback: scan the tension's entity1_label/entity2_label for the
        #      character's short-name (first two words of label, e.g.,
        #      "Engineer A" extracted from "Engineer A Environmental Engineering
        #      Consultant"). The case-7 extraction often leaves
        #      affected_role_labels empty even when the tension's entity labels
        #      clearly name a character; the fallback rescues those.
        # If after all three passes nothing matches, the tension goes to
        # unassigned_tensions, rendered as an "Other tensions" section so the
        # participant doesn't lose them.
        char_lookup = {}
        for ch in characters:
            for key in (ch.get('label'), ch.get('role')):
                if key:
                    char_lookup.setdefault(key.strip().lower(), ch.get('label') or key)

        # Map each character's short-name (first 2 words of label) to the
        # full label, for the entity-label scan fallback. Characters whose
        # short-name is shared (e.g., four characters all starting "Engineer A")
        # all collect tensions that mention "Engineer A" in entity labels;
        # we accept that co-attribution because the extractor did not
        # disambiguate the role variant.
        short_name_lookup: Dict[str, List[str]] = {}
        for ch in characters:
            label = (ch.get('label') or '').strip()
            if not label:
                continue
            words = label.split()
            short = ' '.join(words[:2]).lower() if len(words) >= 2 else label.lower()
            short_name_lookup.setdefault(short, []).append(label)

        tensions_by_character: Dict[str, List[Dict[str, Any]]] = {
            ch['label']: [] for ch in characters if ch.get('label')
        }
        unassigned_tensions: List[Dict[str, Any]] = []

        for t in tensions:
            role_labels = t.get('affected_role_labels') or []
            matched_char_labels = set()
            for role_label in role_labels:
                if not role_label:
                    continue
                key = role_label.strip().lower()
                # Pass 1: exact match on label or role.
                if key in char_lookup:
                    matched_char_labels.add(char_lookup[key])
                    continue
                # Pass 2: substring match against full character labels.
                for ch in characters:
                    ch_label = (ch.get('label') or '').strip().lower()
                    if ch_label and (key in ch_label or ch_label in key):
                        matched_char_labels.add(ch.get('label'))

            # Pass 3: entity-label scan fallback (only if passes 1+2 produced
            # no match). Look at the tension's entity1_label and entity2_label
            # for any character's short-name.
            if not matched_char_labels:
                text_to_scan = (
                    (t.get('entity1_label') or '') + ' '
                    + (t.get('entity2_label') or '')
                ).lower()
                for short, full_labels in short_name_lookup.items():
                    if short and short in text_to_scan:
                        for full_label in full_labels:
                            matched_char_labels.add(full_label)

            if matched_char_labels:
                for label in matched_char_labels:
                    tensions_by_character.setdefault(label, []).append(t)
            else:
                unassigned_tensions.append(t)

        # Sort each character's tensions by intensity desc. (Already
        # globally sorted, but per-character sort guards against
        # ordering surprises when fallback matching reshuffles rows.)
        for label in tensions_by_character:
            tensions_by_character[label].sort(
                key=lambda t: t['intensity_score'], reverse=True
            )

        # Identify "main" characters: those whose short-name appears in
        # the opening_context text. The opening context is a 2nd-person
        # narration of the case from the protagonist's point of view; the
        # characters it names are central to the case's ethical structure.
        # Characters not named there are "additional" — present in the
        # case but secondary to the opening narrative.
        # Study-corrections A9: a character is also "main" if it is the agent
        # of >=2 timeline actions, even when the opening_context narration does
        # not name it (e.g. case 15's "Owner", who acts three times but is
        # absent from the second-person opening). This promotes only characters
        # the extractor already surfaced (the `characters` list is already
        # spurious-filtered above); it never invents a character. Composite/
        # institutional one-offs are excluded by the agent-count helper and the
        # >=2 threshold.
        import re
        # Resolve multi-action timeline agents to characters (A9). Returns the
        # set of character labels promoted by the >=2-action rule, matched on the
        # agent's role-context rather than the raw label string so descriptive
        # role-derived labels (case 103) resolve to their clean Step-3 agents.
        timeline_main_labels = self._timeline_main_character_labels(case_id, characters)
        main_short_names: set = set()
        main_short_name_order: Dict[str, int] = {}  # short-name -> first-occurrence index
        for idx, ch in enumerate(characters):
            label = (ch.get('label') or '').strip()
            if not label:
                ch['is_main'] = False
                continue
            short_name = ' '.join(label.split()[:2])
            in_opening = bool(short_name and opening_context and short_name in opening_context)
            acts_twice = label in timeline_main_labels
            if in_opening or acts_twice:
                ch['is_main'] = True
                main_short_names.add(short_name)
                if short_name not in main_short_name_order:
                    main_short_name_order[short_name] = idx
                # Provenance: mark characters promoted solely by the timeline
                # rule so the template / analysis can distinguish them from
                # opening-context-named mains.
                if acts_twice and not in_opening:
                    ch['promoted_by'] = 'timeline_actions'
            else:
                ch['is_main'] = False

        # Per-main-character tension sort: surface tensions that involve
        # OTHER main characters first, in the order those characters
        # appear in the character list. Tensions that only involve the
        # character themselves (intra-role conflicts, with the same
        # short-name on both sides) sink to the bottom, where the
        # template hides them behind a per-character "show more" toggle.
        #
        # The cross-main priority is computed per (character, tension)
        # pair without mutating the tension dict, because the same
        # tension can appear in multiple characters' lists with a
        # different cross-main perspective each time.
        def _cross_main_pos(t: Dict[str, Any], own_short: str) -> 'int | None':
            text = ' '.join([
                (t.get('entity1_label') or ''),
                (t.get('entity2_label') or ''),
                ' '.join(t.get('affected_role_labels') or []),
            ])
            best_pos: int | None = None
            for short, pos in main_short_name_order.items():
                if short == own_short:
                    continue
                if short and short in text and (best_pos is None or pos < best_pos):
                    best_pos = pos
            return best_pos

        def _linked_main_shorts(t: Dict[str, Any], own_short: str) -> List[str]:
            """List of OTHER main short-names implicated by this tension,
            in character-list order."""
            text = ' '.join([
                (t.get('entity1_label') or ''),
                (t.get('entity2_label') or ''),
                ' '.join(t.get('affected_role_labels') or []),
            ])
            shorts_with_pos: List[tuple] = []
            for short, pos in main_short_name_order.items():
                if short == own_short:
                    continue
                if short and short in text:
                    shorts_with_pos.append((pos, short))
            shorts_with_pos.sort()
            return [short for _, short in shorts_with_pos]

        # tensions_cross_count_by_character[label] = N means the first
        # N entries of tensions_by_character[label] are cross-main and
        # should render visible by default; the remaining are self-only
        # and the template hides them behind a "show more" toggle.
        # tensions_linked_by_character[label] is a parallel list-of-lists
        # giving the OTHER main short-names implicated by each tension
        # under that character (same order as tensions_by_character[label]).
        tensions_cross_count_by_character: Dict[str, int] = {}
        tensions_linked_by_character: Dict[str, List[List[str]]] = {}
        for char in characters:
            if not char.get('is_main'):
                continue
            label = char.get('label') or ''
            if label not in tensions_by_character:
                continue
            own_short = ' '.join(label.split()[:2])

            def _key(t: Dict[str, Any], _own=own_short) -> tuple:
                pos = _cross_main_pos(t, _own)
                if pos is not None:
                    return (0, pos, -t.get('intensity_score', 0))
                return (1, 0, -t.get('intensity_score', 0))

            tensions_by_character[label].sort(key=_key)
            cross_count = sum(
                1 for t in tensions_by_character[label]
                if _cross_main_pos(t, own_short) is not None
            )
            tensions_cross_count_by_character[label] = cross_count
            tensions_linked_by_character[label] = [
                _linked_main_shorts(t, own_short)
                for t in tensions_by_character[label]
            ]

        # Wrap each main short-name in opening_context with a popover
        # span. The popover content is the character's professional
        # position. When the same short-name maps to multiple character
        # variants (e.g. "Engineer A" -> four role variants), the popover
        # links to the first match; the alternative role cards remain
        # visible in the main-characters section below.
        opening_context_html = opening_context or ''
        if opening_context_html and main_short_names:
            short_to_char = {}
            for ch in characters:
                if not ch.get('is_main'):
                    continue
                label = (ch.get('label') or '').strip()
                short = ' '.join(label.split()[:2])
                short_to_char.setdefault(short, ch)

            sorted_shorts = sorted(short_to_char.keys(), key=len, reverse=True)
            pattern = re.compile(
                r'\b(' + '|'.join(re.escape(n) for n in sorted_shorts) + r')\b'
            )

            def _wrap(match: 're.Match') -> str:
                name = match.group(1)
                ch = short_to_char[name]
                pos_raw = (ch.get('professional_position') or '').strip()
                if len(pos_raw) > 200:
                    cut = pos_raw.rfind(' ', 0, 200)
                    if cut <= 0:
                        cut = 200
                    pos_raw = pos_raw[:cut].rstrip(' ,;:.') + '…'
                pos = pos_raw.replace('"', '&quot;')
                anchor = 'char-' + name.replace(' ', '-').lower()
                return (
                    f'<a class="char-mention" href="#{anchor}" '
                    f'data-bs-toggle="popover" data-bs-trigger="focus hover" '
                    f'data-bs-title="Role in the case" '
                    f'data-bs-content="{pos}" tabindex="0">{name}</a>'
                )

            opening_context_html = pattern.sub(_wrap, opening_context_html)

        # Collapse role-instance character cards under each named individual.
        # The extractor emits one character per role-instance (e.g., "Engineer A
        # Environmental Engineering Consultant" and "Engineer A Groundwater
        # Infrastructure Design Engineer" are two separate cards for the same
        # person). For the participant-facing view we group these under one
        # person card whose tensions are the union of the underlying role
        # instances' tensions. Each tension carries a chip naming which role
        # within the person it attaches to.
        from collections import OrderedDict
        grouped_chars: 'OrderedDict[str, Dict[str, Any]]' = OrderedDict()
        for ch in characters:
            label = (ch.get('label') or '').strip()
            if not label:
                continue
            parts = label.split()
            # Preserve single-letter disambiguators (NSPE naming convention:
            # "Engineer A", "Principal Engineer R", "City Engineer J"). When
            # parts[2] is a single uppercase letter, it identifies the
            # individual rather than a role suffix; include it in short_name.
            if (
                len(parts) >= 3
                and len(parts[2]) == 1
                and parts[2].isupper()
            ):
                short_name = ' '.join(parts[:3])
                role_suffix = ' '.join(parts[3:])
            elif len(parts) >= 2:
                short_name = ' '.join(parts[:2])
                role_suffix = ' '.join(parts[2:])
            else:
                short_name = label
                role_suffix = ''
            if short_name not in grouped_chars:
                grouped_chars[short_name] = {
                    'short_name': short_name,
                    'anchor': 'char-' + short_name.replace(' ', '-').lower(),
                    'role_suffixes': [],
                    'role_suffix_details': {},
                    '_positions': [],
                    '_stances': [],
                    'motivations': [],
                    'tensions': [],
                    '_tension_keys': set(),
                    'is_main': False,
                }
            g = grouped_chars[short_name]
            if role_suffix and role_suffix not in g['role_suffixes']:
                g['role_suffixes'].append(role_suffix)
            if ch.get('is_main'):
                g['is_main'] = True
            pos = (ch.get('professional_position') or '').strip()
            if pos and pos not in g['_positions']:
                g['_positions'].append(pos)
            stance = (ch.get('ethical_stance') or '').strip()
            if stance and stance not in g['_stances']:
                g['_stances'].append(stance)
            for m in (ch.get('motivations') or []):
                if m and m not in g['motivations']:
                    g['motivations'].append(m)
            char_tensions = tensions_by_character.get(label, [])
            char_linked = tensions_linked_by_character.get(label, [])
            for idx, t in enumerate(char_tensions):
                # Dedup key uses the truncated label form (matching the
                # template's |truncate(60)) plus sorted affected roles, so
                # tensions that display identically to the participant merge
                # even when their full extracted labels differ in extraction-
                # artifact suffixes ("Breached By..." vs "Violated By...")
                # past the visible-truncation point. The post-pilot extractor
                # pass will clean the underlying labels; this dedup prevents
                # visually-identical tensions from reaching the pilot.
                e1 = (t.get('entity1_label') or '').strip()
                e2 = (t.get('entity2_label') or '').strip()
                tkey = (
                    e1[:60].lower(),
                    e2[:60].lower(),
                    tuple(sorted(t.get('affected_role_labels') or [])),
                )
                if tkey in g['_tension_keys']:
                    continue
                g['_tension_keys'].add(tkey)
                linked = char_linked[idx] if idx < len(char_linked) else []
                g['tensions'].append({
                    'tension': t,
                    'role_suffix': role_suffix,
                    'linked_main_shorts': linked,
                })

        for g in grouped_chars.values():
            g['tensions'].sort(
                key=lambda x: x['tension'].get('intensity_score', 0),
                reverse=True,
            )
            g['professional_position'] = (
                max(g['_positions'], key=len) if g['_positions'] else ''
            )
            g['ethical_stance'] = ' '.join(g['_stances'])
            g['tension_count'] = len(g['tensions'])
            del g['_tension_keys']
            del g['_positions']
            del g['_stances']

        # Populate role_suffix_details with abstract role-class definitions
        # (rdfs:comment) from OntServe. Keyed by exact label match against
        # ontology_entities.label where entity_type='class'. Role suffixes
        # without a matching class entry (or with empty comment) are simply
        # omitted; the template renders those badges without a popover.
        all_role_suffixes = sorted({
            r for g in grouped_chars.values() for r in g['role_suffixes']
        })
        role_definitions = self._fetch_class_definitions(all_role_suffixes)
        for g in grouped_chars.values():
            g['role_suffix_details'] = {
                r: role_definitions[r]
                for r in g['role_suffixes']
                if r in role_definitions
            }

        grouped_main_characters = [g for g in grouped_chars.values() if g['is_main']]
        grouped_other_characters = [g for g in grouped_chars.values() if not g['is_main']]

        has_content = bool(characters or tensions or opening_context)

        return {
            'view_type': 'narrative',
            'has_content': has_content,
            'characters': characters,
            'tensions': tensions,
            'tensions_by_character': tensions_by_character,
            'tensions_cross_count_by_character': tensions_cross_count_by_character,
            'tensions_linked_by_character': tensions_linked_by_character,
            'unassigned_tensions': unassigned_tensions,
            'opening_context': opening_context,
            'opening_context_html': opening_context_html,
            'protagonist_label': protagonist_label,
            'character_count': len(characters),
            'grouped_main_characters': grouped_main_characters,
            'grouped_other_characters': grouped_other_characters,
            'grouped_main_character_count': len(grouped_main_characters),
            'tension_count': len(tensions),
            'rated_tension_count': rated_tension_count,
            'description': ('Characters with the ethical tensions their roles produce, '
                            'plus an opening-context account. Each character card lists '
                            'the tensions that implicate that role.'),
        }
