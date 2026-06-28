"""Authoritative seeder for the obligations extraction prompt (facts + discussion passes).

SINGLE SOURCE for the obligations prompt. Supersedes the pass-less 'obligations' entry in
dual_extractor_template_seeder.py (the legacy hardcoded block diverged from the curated DB rows
and is no longer authoritative). This is the worked reference for the Phase-3 per-component
verticals: the other seven components copy this module's shape.

The prompt TEXT lives in a SINGLE body prompts/obligations.md, seeded to both the facts and
discussion pass rows; the two differ only by the runtime {{ pass_directive }} slot. The body
references the ontology-derived slot {{ obligation_schema }} (the controlled field contract read
from the SHACL ObligationDefinitionShape) resolved at injection time by concept_ontology_slots(),
plus the pipeline-supplied case/existing-entity variables. The shared METADATA (system prompt,
output schema, documented variables, per-pass name/description) lives in prompts/obligations_meta.json.
This module wires them into ExtractionPromptTemplate rows, mirroring seed_roles_prompt.py.
See .claude/plans/prompt-harmonization-playbook.md and .claude/plans/extraction-architecture-spec.md (O section).

Run: python -m app.utils.seed_obligations_prompt [--replace]
"""
import json
import logging
import sys
from pathlib import Path

from app import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate

logger = logging.getLogger(__name__)
_DIR = Path(__file__).parent / "prompts"


def seed_obligations_prompt(replace_existing: bool = False):
    """Seed the obligations facts + discussion templates from the sidecar files. Idempotent: skips
    existing unless replace_existing. Returns (created, updated, skipped)."""
    meta = json.loads((_DIR / "obligations_meta.json").read_text())
    created = updated = skipped = 0

    # Smoke test: the body references the ontology-derived {{ obligation_schema }} slot (read from the
    # SHACL ObligationDefinitionShape). Fail the seed loudly if it resolves empty (an unreadable shapes
    # file or a missing shape), so the "{{ obligation_schema }} renders to ''" failure cannot reach
    # production silently; the schema-wire is caught at seed time, not at extraction time. pass_directive
    # is checked alongside so a pass-split row never ships without its per-pass directive.
    from app.services.prompt_variable_resolver import concept_ontology_slots
    _required = ('obligation_schema', 'pass_directive')
    for st in meta["passes"]:
        slots = concept_ontology_slots('obligations', st)
        missing = [k for k in _required if not slots.get(k)]
        if missing:
            raise RuntimeError(f"obligations seed aborted: ontology slots empty for pass '{st}': {missing}")

    # The obligations prompt is now pass-split (facts/discussion); deactivate the stale pre-migration
    # pass-less ('all') row so the live extractor stops falling back to it.
    for legacy in ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='obligations', pass_type='all', is_active=True).all():
        legacy.is_active = False
        logger.info("Deactivated legacy obligations 'all' template id %s", legacy.id)

    for pass_type, p in meta["passes"].items():
        template_text = (_DIR / p["template_file"]).read_text()
        existing = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case', concept_type='obligations', pass_type=pass_type, is_active=True).first()
        if existing and not replace_existing:
            logger.info("obligations/%s already exists, skipping", pass_type)
            skipped += 1
            continue
        t = existing or ExtractionPromptTemplate(
            extraction_type='case', concept_type='obligations', pass_type=pass_type,
            is_active=True, created_by='seed_obligations_prompt', version=0)
        t.name = p["name"]
        t.description = p["description"]
        t.template_text = template_text
        t.system_prompt = meta["system_prompt"]
        t.output_schema = meta["output_schema"]
        t.variable_builders = meta["variable_builders"]
        t.variables_schema = meta["variable_builders"]
        t.step_number = meta["step_number"]
        t.domain = meta["domain"]
        t.source_file = "app/utils/seed_obligations_prompt.py"
        t.version = (t.version or 0) + 1
        if existing:
            updated += 1
            logger.info("Updated obligations/%s -> v%s", pass_type, t.version)
        else:
            db.session.add(t)
            created += 1
            logger.info("Created obligations/%s", pass_type)

    db.session.commit()
    logger.info("obligations prompt seed: %d created, %d updated, %d skipped", created, updated, skipped)
    return created, updated, skipped


if __name__ == '__main__':
    from app import create_app
    with create_app().app_context():
        seed_obligations_prompt(replace_existing='--replace' in sys.argv)
