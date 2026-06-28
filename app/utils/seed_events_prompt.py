"""Authoritative seeder for the events extraction prompt (single Step-3 pass).

SINGLE SOURCE for the events prompt field contract. Mirrors the worked reference
seed_obligations_prompt.py (the Phase-3 per-component vertical template), with one structural
difference: events are SINGLE-PASS, not pass-split. Events are extracted once in Step 3 (no
facts/discussion split), so this seeds a single pass_type='all' row and registers no per-pass
directive.

LIVE-PATH NOTE (the editable-prompt exception, extraction-architecture-spec.md E section): the
running Step-3 LangGraph path builds its event prompt inline in
app/services/temporal_dynamics/extractors/event_extractor.py, NOT from this DB template. This
seeded row is therefore the single-source field contract (read by the prompt editor and the
{{ event_schema }} schema-wire) and a parallel artifact; it is not the live runtime prompt. To
fully realize the spec on the live path, _build_event_extraction_prompt would be trimmed to the
fields enumerated here (a separate change, flagged, not done here).

The prompt TEXT lives in prompts/events.md and references the ontology-derived slot {{ event_schema }}
(the light field contract read from the SHACL EventDefinitionShape) resolved at injection time by
concept_ontology_slots(). The shared METADATA lives in prompts/events_meta.json. See
.claude/plans/prompt-harmonization-playbook.md and .claude/plans/extraction-architecture-spec.md (E section).

Run: python -m app.utils.seed_events_prompt [--replace]
"""
import json
import logging
import sys
from pathlib import Path

from app import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate

logger = logging.getLogger(__name__)
_DIR = Path(__file__).parent / "prompts"


def seed_events_prompt(replace_existing: bool = False):
    """Seed the single events template from the sidecar files. Idempotent: skips existing unless
    replace_existing. Returns (created, updated, skipped)."""
    meta = json.loads((_DIR / "events_meta.json").read_text())
    created = updated = skipped = 0

    # Smoke test: the body references the ontology-derived {{ event_schema }} slot (read from the
    # SHACL EventDefinitionShape). Fail the seed loudly if it resolves empty (an unreadable shapes
    # file or a missing shape), so the "{{ event_schema }} renders to ''" failure cannot reach
    # production silently; the schema-wire is caught at seed time, not at extraction time. Events are
    # single-pass, so pass_directive is intentionally empty and not required.
    from app.services.prompt_variable_resolver import concept_ontology_slots
    _required = ('event_schema',)
    for st in meta["passes"]:
        slots = concept_ontology_slots('events', st)
        missing = [k for k in _required if not slots.get(k)]
        if missing:
            raise RuntimeError(f"events seed aborted: ontology slots empty for pass '{st}': {missing}")

    # Events stay single-pass ('all'); there is no facts/discussion split to migrate to, so the
    # existing 'all' row is updated in place rather than deactivated.
    for pass_type, p in meta["passes"].items():
        template_text = (_DIR / p["template_file"]).read_text()
        existing = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='events', pass_type=pass_type, is_active=True).first()
        if existing and not replace_existing:
            logger.info("events/%s already exists, skipping", pass_type)
            skipped += 1
            continue
        t = existing or ExtractionPromptTemplate(
            extraction_type='case', concept_type='events', pass_type=pass_type,
            is_active=True, created_by='seed_events_prompt', version=0)
        t.name = p["name"]
        t.description = p["description"]
        t.template_text = template_text
        t.system_prompt = meta["system_prompt"]
        t.output_schema = meta["output_schema"]
        t.variable_builders = meta["variable_builders"]
        t.variables_schema = meta["variable_builders"]
        t.step_number = meta["step_number"]
        t.domain = meta["domain"]
        t.source_file = "app/utils/seed_events_prompt.py"
        t.version = (t.version or 0) + 1
        if existing:
            updated += 1
            logger.info("Updated events/%s -> v%s", pass_type, t.version)
        else:
            db.session.add(t)
            created += 1
            logger.info("Created events/%s", pass_type)

    db.session.commit()
    logger.info("events prompt seed: %d created, %d updated, %d skipped", created, updated, skipped)
    return created, updated, skipped


if __name__ == '__main__':
    from app import create_app
    with create_app().app_context():
        seed_events_prompt(replace_existing='--replace' in sys.argv)
