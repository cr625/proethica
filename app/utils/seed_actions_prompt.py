"""Authoritative seeder for the actions extraction prompt (single Step-3 pass).

Migrates Action off the orphaned DB-only template (its former source
app/services/extraction/dual_actions_extractor.py was deleted, leaving the live prompt a DB row with
no on-disk source) to the per-component .md/seeder pattern, matching seed_events_prompt.py. Action is
SINGLE-PASS (pass_type='all') and BARE (no SHACL DefinitionShape), so there is no {{ action_schema }}
slot; the smoke test verifies the ontology-derived TYPING slots {{ action_boundary }} +
{{ action_individuation }} (concept_ontology_slots('actions')) instead -- the disjointness boundary and
the scope-note individuation that Action previously hard-coded as "CRITICAL DISTINCTION FROM EVENTS".

The prompt TEXT lives in prompts/actions.md; the shared METADATA in prompts/actions_meta.json.

Run: python -m app.utils.seed_actions_prompt [--replace]
"""
import json
import logging
import sys
from pathlib import Path

from app import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate

logger = logging.getLogger(__name__)
_DIR = Path(__file__).parent / "prompts"


def seed_actions_prompt(replace_existing: bool = False):
    """Seed the single actions template from the sidecar files. Idempotent: skips existing unless
    replace_existing. Returns (created, updated, skipped)."""
    meta = json.loads((_DIR / "actions_meta.json").read_text())
    created = updated = skipped = 0

    # Smoke test: Action is bare (no SHACL shape), so verify the ontology-derived TYPING slots resolve
    # (the disjointness boundary + the scope-note individuation). Fail the seed loudly if either is
    # empty so a silent "{{ action_boundary }} renders to ''" cannot reach extraction.
    from app.services.prompt_variable_resolver import concept_ontology_slots
    _required = ('action_definition', 'action_boundary', 'action_individuation', 'pass_directive')
    for st in meta["passes"]:
        slots = concept_ontology_slots('actions', st)
        missing = [k for k in _required if not slots.get(k)]
        if missing:
            raise RuntimeError(f"actions seed aborted: ontology slots empty for pass '{st}': {missing}")

    for pass_type, p in meta["passes"].items():
        template_text = (_DIR / p["template_file"]).read_text()
        existing = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='actions', pass_type=pass_type, is_active=True).first()
        if existing and not replace_existing:
            logger.info("actions/%s already exists, skipping", pass_type)
            skipped += 1
            continue
        t = existing or ExtractionPromptTemplate(
            extraction_type='case', concept_type='actions', pass_type=pass_type,
            is_active=True, created_by='seed_actions_prompt', version=0)
        t.name = p["name"]
        t.description = p["description"]
        t.template_text = template_text
        t.system_prompt = meta["system_prompt"]
        t.output_schema = meta["output_schema"]
        t.variable_builders = meta["variable_builders"]
        t.variables_schema = meta["variable_builders"]
        t.step_number = meta["step_number"]
        t.domain = meta["domain"]
        t.source_file = "app/utils/seed_actions_prompt.py"
        t.version = (t.version or 0) + 1
        if existing:
            updated += 1
            logger.info("Updated actions/%s -> v%s", pass_type, t.version)
        else:
            db.session.add(t)
            created += 1
            logger.info("Created actions/%s", pass_type)

    db.session.commit()
    logger.info("actions prompt seed: %d created, %d updated, %d skipped", created, updated, skipped)
    return created, updated, skipped


if __name__ == '__main__':
    from app import create_app
    with create_app().app_context():
        seed_actions_prompt(replace_existing='--replace' in sys.argv)
