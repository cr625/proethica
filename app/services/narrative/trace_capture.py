"""LLM-trace capture helpers for the narrative pipeline.

The phase-4 narrative sub-extractors accumulate ``llm_traces`` (dicts with
``stage``/``prompt``/``response``); this module turns them into the
prompt/response texts an ``ExtractionPrompt`` row records. Deliberately free
of route and Flask imports so both the batch synthesis service and the SSE
routes can import it without the step4 route-package cycle.
"""


def join_llm_traces(traces) -> tuple:
    """Join an llm_traces list into (prompt_text, response_text).

    The batch phase-4 row stored a placeholder while the real prompts sat in
    result.llm_traces; the two route paths each had their own joiner with a
    10k truncation. Single shared joiner, NO truncation: prompt_text and
    raw_response are db.Text, and a truncated capture defeats the audit
    purpose of the row. Returns ('', '') when no usable traces exist (the
    caller keeps its fallback label)."""
    prompts, responses = [], []
    for trace in traces or []:
        if not isinstance(trace, dict):
            continue
        stage = trace.get('stage', 'UNKNOWN')
        if trace.get('prompt'):
            prompts.append(f"=== {stage} ===\n{trace['prompt']}")
        if trace.get('response'):
            responses.append(f"=== {stage} ===\n{trace['response']}")
    return "\n\n".join(prompts), "\n\n".join(responses)
