"""
Step 4 shared constants and helpers.

Separate module to avoid circular imports between step4.py and its
sub-modules (step4_run_all, step4_phase3, etc.).
"""

from models import ModelConfig

# All Step 4 extraction prompts use this section_type for consistency.
# Steps 1-2 use 'facts'/'discussion'; Step 4 always uses 'synthesis'
# because each task analyses the full case text, not a single section.
STEP4_SECTION_TYPE = 'synthesis'

# LLM model constants -- all Step 4 code should use these instead of
# hardcoded model ID strings.  Resolved once at import time from ModelConfig.
STEP4_DEFAULT_MODEL = ModelConfig.get_claude_model("default")    # claude-sonnet-4-6
STEP4_POWERFUL_MODEL = ModelConfig.get_claude_model("powerful")  # claude-opus-4-6

# All extraction_type values produced by Step 4 (used for scoped counts/queries).
STEP4_EXTRACTION_TYPES = [
    'code_provision_reference',       # 2A
    'precedent_case_reference',       # 2B
    'ethical_question',               # 2C
    'ethical_conclusion',             # 2C
    'causal_normative_link',          # 2E
    'question_emergence',             # 2E
    'resolution_pattern',             # 2E
    'canonical_decision_point',       # Phase 3
    'argument_generated',             # Phase 3
    'argument_validation',            # Phase 3
]


def reset_step4_case_features(case_id: int):
    """Clear all CasePrecedentFeatures fields populated by Step 4 extraction.

    Fields populated at ingestion (outcome_type, provisions_cited, subject_tags,
    etc.) are NOT cleared -- only fields written by Step 4 tasks:
      - cited_case_numbers, cited_case_ids (2B)
      - transformation_type/pattern (2D)
      - principle_tensions, obligation_conflicts (2E)

    Called by both clear_step4_data() and step4_run_all._clear_step4_data().
    """
    from app.models import CasePrecedentFeatures
    features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
    if features:
        features.transformation_type = None
        features.transformation_pattern = None
        features.principle_tensions = None
        features.obligation_conflicts = None
        features.cited_case_numbers = None
        features.cited_case_ids = None
