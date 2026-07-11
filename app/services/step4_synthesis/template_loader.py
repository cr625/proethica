"""Fetch-or-fail loader for the Step-4 synthesis prompt templates.

The Step-4 family lives in extraction_prompt_templates as step_number=4 /
pass_type='all' rows seeded from the sidecars in app/utils/prompts/step4/
by app/utils/seed_step4_prompts.py. Builders assemble their
variables dict, fetch here, render, and apply post-stages (glossary
enrichment, normative-status append) unchanged. No hardcoded fallback:
an unseeded template is a deployment error, not a degraded mode.
"""

from app.models.extraction_prompt_template import ExtractionPromptTemplate

STEP4_STEP_NUMBER = 4


def get_step4_template(concept_type: str) -> ExtractionPromptTemplate:
    template = ExtractionPromptTemplate.get_active_template(
        STEP4_STEP_NUMBER, concept_type
    )
    if template is None:
        raise RuntimeError(
            f"Step-4 prompt template '{concept_type}' is not seeded. Run: "
            f"python -m app.utils.seed_step4_prompts --only {concept_type}"
        )
    return template
