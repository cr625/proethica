#!/usr/bin/env python3
"""
Report-only smoke harness for the LLM provider abstraction.

Default mode makes no API calls: it prints the resolved tier references
and declared capabilities, which is the pre-flight check before repointing
a tier. Live mode (--live) makes one minimal completion and one minimal
structured call per requested tier and prints provider, model, usage, and
parse outcome. Live mode requires the provider API key in the environment
and costs a small amount per tier; it never writes to the database and
never changes configuration.

Usage:
    venv-proethica/bin/python scripts/llm_provider_smoke.py
    venv-proethica/bin/python scripts/llm_provider_smoke.py --tier default,gate
    OPENAI_API_KEY=... LLM_DEFAULT_REF=openai:gpt-4o \
        venv-proethica/bin/python scripts/llm_provider_smoke.py --live
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from model_config import ModelConfig  # noqa: E402
from app.services.llm.capabilities import capabilities_for_ref  # noqa: E402


def report(tiers):
    """Print resolved refs and capabilities. Returns list of tier refs."""
    refs = {}
    for tier in tiers:
        ref = ModelConfig.get_tier_ref(tier)
        caps = capabilities_for_ref(ref)
        refs[tier] = ref
        print(
            f"{tier}: ref={ref} structured={caps.structured_tier} "
            f"temperature={caps.supports_temperature} "
            f"thinking_default={caps.thinking_on_by_default} "
            f"tool_use={caps.supports_tool_use} caching={caps.prompt_caching}"
        )
    return refs


def live(refs):
    """One completion and one structured call per tier. Report only."""
    from app.services.llm.factory import get_provider

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    }
    for tier, ref in refs.items():
        provider = get_provider(ref)
        response = provider.complete(
            [{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=32, temperature=0.0,
        )
        print(
            f"{tier} complete: provider={response.provider} model={response.model} "
            f"in={response.usage.input_tokens} out={response.usage.output_tokens} "
            f"text={response.text[:60]!r}"
        )
        result = provider.structured(
            [{"role": "user", "content": "Return {\"ok\": true}."}],
            schema, max_tokens=64, temperature=0.0,
        )
        print(f"{tier} structured: parsed={result} schema_guaranteed="
              f"{provider.capabilities().guarantees_schema}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="fast,default,powerful,gate",
                        help="Comma-separated tiers to report (default: all)")
    parser.add_argument("--live", action="store_true",
                        help="Make real API calls (requires provider keys)")
    args = parser.parse_args()

    tiers = [t.strip() for t in args.tier.split(",") if t.strip()]
    refs = report(tiers)
    if args.live:
        live(refs)
    else:
        print("report-only: no API calls made (pass --live to call providers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
