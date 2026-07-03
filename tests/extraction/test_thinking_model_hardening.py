"""Thinking-model hardening guards (2026-07 model split: Fable 5 powerful / Sonnet 5 default).

Sonnet 5 / Fable 5 return thinking blocks as ``content[0]``, so any raw
``response.content[0].text`` read raises ``AttributeError: 'ThinkingBlock' object has
no attribute 'text'`` once the env tiers flip; and thinking tokens spend from the SAME
``max_tokens`` budget as the visible text, so direct calls with small budgets get their
text truncated mid-generation (the run-14/run-17 failure class). These tests pin the
hardening invariants:

(a) no raw ``content[0].text`` read anywhere under app/ -- ``text_from_message`` is the
    one robust reader (its own docstring in llm_utils.py is the single allowed mention);
(b) ``direct_call_params`` floors ``max_tokens`` at 16000 for thinking-by-default models
    and includes ``temperature`` only when the model supports it;
(c) ``text_from_message`` reads the text through a thinking-first content list;
(d) the transformation classifier resolves the DEFAULT tier (all Step-4 synthesis
    phases ride the default model; the powerful tier is steps 1-3 extraction).

DB/LLM-free.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_config import ModelConfig
from app.utils.llm_utils import direct_call_params, text_from_message

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_DIR = _REPO_ROOT / "app"
# llm_utils.py documents the failure mode in the text_from_message docstring.
_ALLOWED_MENTIONS = {_APP_DIR / "utils" / "llm_utils.py"}


# ---------------------------------------------------------------------------
# (a) no raw content[0].text reads remain in app/
# ---------------------------------------------------------------------------

def test_no_raw_content0_text_reads_in_app():
    offenders = []
    for py in sorted(_APP_DIR.rglob("*.py")):
        if py in _ALLOWED_MENTIONS:
            continue
        for lineno, line in enumerate(
                py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "content[0].text" in line:
                offenders.append(f"{py.relative_to(_REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Raw content[0].text reads crash on thinking-first responses "
        "(Sonnet 5 / Fable 5); use app.utils.llm_utils.text_from_message:\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# (b) direct_call_params: budget floor + temperature gate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model", sorted(ModelConfig.THINKING_ON_BY_DEFAULT))
def test_direct_call_params_floors_thinking_by_default_models(model):
    params = direct_call_params(model, max_tokens=500, temperature=0.1)
    assert params["model"] == model
    assert params["max_tokens"] == 16000, (
        "thinking spends from the same max_tokens budget; small budgets truncate the text"
    )
    assert ("temperature" in params) == ModelConfig.supports_temperature(model)


def test_direct_call_params_does_not_cap_large_budgets():
    assert direct_call_params("claude-fable-5", max_tokens=32000)["max_tokens"] == 32000


def test_direct_call_params_preserves_non_thinking_call():
    params = direct_call_params("claude-sonnet-4-6", max_tokens=500, temperature=0.1)
    assert params == {"model": "claude-sonnet-4-6", "max_tokens": 500, "temperature": 0.1}


def test_direct_call_params_keeps_zero_temperature_when_supported():
    # temperature=0 is falsy; the gate must be an `is not None` check, not truthiness.
    params = direct_call_params("claude-haiku-4-5-20251001", max_tokens=4096, temperature=0)
    assert params["temperature"] == 0


def test_direct_call_params_omits_temperature_when_none():
    assert "temperature" not in direct_call_params("claude-sonnet-4-6", max_tokens=500)


def test_direct_call_params_omits_temperature_for_rejecting_models():
    for model in sorted(ModelConfig.TEMPERATURE_UNSUPPORTED):
        assert "temperature" not in direct_call_params(model, max_tokens=4096, temperature=0.2)


# ---------------------------------------------------------------------------
# (c) text_from_message reads through a thinking-first content list
# ---------------------------------------------------------------------------

def test_text_from_message_skips_thinking_first_block():
    message = SimpleNamespace(content=[
        SimpleNamespace(type="thinking", thinking="chain of thought"),
        SimpleNamespace(type="text", text="the answer"),
    ])
    assert text_from_message(message) == "the answer"


# ---------------------------------------------------------------------------
# (d) transformation classifier resolves the default tier
# ---------------------------------------------------------------------------

def test_transformation_classifier_resolves_default_tier(monkeypatch):
    from app.services.case_analysis.transformation_classifier import TransformationClassifier
    import app.utils.llm_utils as llm_utils

    captured = {}

    def fake_streaming_completion(client, model, max_tokens, prompt, temperature=0.1):
        captured["model"] = model
        return json.dumps({
            "transformation_type": "transfer",
            "confidence": 0.9,
            "reasoning": "test",
            "pattern_description": "test pattern",
            "supporting_evidence": [],
            "involved_roles": [],
            "obligation_shifts": [],
        })

    monkeypatch.setattr(llm_utils, "streaming_completion", fake_streaming_completion)
    # Sentinel tier map: the assertion is about WHICH tier is asked for, not the env value.
    monkeypatch.setattr(ModelConfig, "CLAUDE_MODELS", {
        "default": "sentinel-default-model",
        "powerful": "sentinel-powerful-model",
        "fast": "sentinel-fast-model",
    })

    # Dummy client: streaming_completion is patched, and a real client would need
    # a Flask app context (get_llm_client reads current_app config).
    classifier = TransformationClassifier(llm_client=SimpleNamespace())
    result = classifier.classify(
        case_id=0,
        questions=[{"entity_definition": "Was it ethical to proceed?", "rdf_json_ld": {}}],
        conclusions=[{"entity_definition": "It was not ethical.", "rdf_json_ld": {}}],
        resolution_patterns=[],
        use_llm=True,
        case_title="Test Case",
        case_facts="Engineer A proceeded without review.",
        all_entities={},
    )

    assert captured["model"] == "sentinel-default-model", (
        "transformation classifier must ride the default tier "
        "(2026-07 split: synthesis on the default model)"
    )
    assert result.transformation_type == "transfer"


def test_transformation_classifier_source_has_no_powerful_tier_reference():
    src = (_APP_DIR / "services" / "case_analysis" / "transformation_classifier.py").read_text()
    assert 'get_claude_model("powerful")' not in src
    assert 'get_claude_model("default")' in src
