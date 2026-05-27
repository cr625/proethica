"""Shared ProEthica output-style clause for hardcoded prose prompts.

The DB-backed extraction templates (`extraction_prompt_templates`) carry this
clause in their FORMATTING line (see `docs-internal/scripts/apply_style_guide_prompt.py`).
The Step-3 temporal-dynamics extractors, the rich-analysis passes, and the
Phase-4 narrative passes build their prompts as hardcoded f-strings in code, so
they need the same clause appended directly. Import `STYLE_FORMATTING_LINE` and
append it to any prompt whose output is shown to participants or written into
the case narrative.
"""

STYLE_FORMATTING_LINE = (
    "FORMATTING (ProEthica style): Do not use em dashes or en dashes in output "
    "text. Do not dodge that by substituting stacked parentheticals or excessive "
    "colons or semicolons. Write plain sentences: use commas, or split into two "
    "sentences."
)
