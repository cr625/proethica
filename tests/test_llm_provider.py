"""
Tests for the LLM provider abstraction (branch feat/llm-provider-abstraction).

Phase 1: provider:model tier references and the capability registry.
Later phases extend this file with fake-provider contract tests. No network
or API key is required: provider clients are fakes with recorded calls.
"""

from types import SimpleNamespace

import pytest

from model_config import ModelConfig
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.capabilities import (
    ProviderCapabilities, UnsupportedCapabilityError, capabilities_for_ref,
    get_capabilities, require_capability,
)
from app.services.llm.factory import get_provider, get_tier_provider
from app.services.llm.manager import LLMManager
from app.services.llm.openai_provider import OpenAIProvider


class TestParseModelRef:
    def test_explicit_anthropic_ref(self):
        assert ModelConfig.parse_model_ref("anthropic:claude-sonnet-4-6") == (
            "anthropic", "claude-sonnet-4-6")

    def test_claude_alias_normalizes_to_anthropic(self):
        assert ModelConfig.parse_model_ref("claude:claude-opus-4-8") == (
            "anthropic", "claude-opus-4-8")

    def test_explicit_openai_ref(self):
        assert ModelConfig.parse_model_ref("openai:gpt-4o") == ("openai", "gpt-4o")

    def test_bare_claude_defaults_to_anthropic(self):
        assert ModelConfig.parse_model_ref("claude-haiku-4-5-20251001") == (
            "anthropic", "claude-haiku-4-5-20251001")

    def test_bare_gpt_defaults_to_openai(self):
        assert ModelConfig.parse_model_ref("gpt-4o-mini") == ("openai", "gpt-4o-mini")

    def test_unknown_bare_model_keeps_legacy_anthropic_default(self):
        assert ModelConfig.parse_model_ref("some-local-model") == (
            "anthropic", "some-local-model")


class TestTierRefs:
    def test_default_tier_matches_legacy_claude_model(self):
        assert ModelConfig.get_tier_model("default") == ModelConfig.get_claude_model("default")
        assert ModelConfig.get_tier_provider("default") == "anthropic"

    def test_gate_tier_matches_legacy(self):
        assert ModelConfig.get_tier_model("gate") == ModelConfig.get_claude_model("gate")

    def test_env_ref_repoints_tier(self, monkeypatch):
        monkeypatch.setenv("LLM_DEFAULT_REF", "openai:gpt-4o")
        assert ModelConfig.get_tier_ref("default") == "openai:gpt-4o"
        assert ModelConfig.get_tier_provider("default") == "openai"
        assert ModelConfig.get_tier_model("default") == "gpt-4o"

    def test_env_ref_accepts_bare_model(self, monkeypatch):
        monkeypatch.setenv("LLM_POWERFUL_REF", "gpt-5")
        assert ModelConfig.get_tier_ref("powerful") == "openai:gpt-5"

    def test_legacy_claude_model_still_wins_without_ref(self, monkeypatch):
        monkeypatch.delenv("LLM_DEFAULT_REF", raising=False)
        assert ModelConfig.get_tier_model("default") == ModelConfig.CLAUDE_MODELS["default"]


class TestCapabilities:
    def test_anthropic_schema_tier_and_explicit_caching(self):
        caps = get_capabilities("anthropic", "claude-sonnet-4-6")
        assert caps.structured_tier == "schema"
        assert caps.guarantees_schema is True
        assert caps.prompt_caching == "explicit"
        assert caps.supports_tool_use is True

    def test_anthropic_temperature_rejection_is_model_specific(self):
        assert get_capabilities("anthropic", "claude-opus-4-8").supports_temperature is False
        assert get_capabilities("anthropic", "claude-haiku-4-5-20251001").supports_temperature is True

    def test_anthropic_thinking_on_by_default(self):
        assert get_capabilities("anthropic", "claude-fable-5").thinking_on_by_default is True
        assert get_capabilities("anthropic", "claude-sonnet-4-6").thinking_on_by_default is False

    def test_openai_schema_for_strict_capable_models(self):
        assert get_capabilities("openai", "gpt-4o").structured_tier == "schema"
        assert get_capabilities("openai", "gpt-5").structured_tier == "schema"

    def test_openai_unknown_model_falls_back_to_json_object(self):
        caps = get_capabilities("openai", "gpt-3.5-turbo")
        assert caps.structured_tier == "json_object"
        assert caps.guarantees_schema is False

    def test_unknown_provider_is_prompt_only(self):
        caps = get_capabilities("ollama", "llama3")
        assert caps.structured_tier == "prompt_only"
        assert caps.supports_tool_use is False

    def test_capabilities_for_ref(self):
        caps = capabilities_for_ref("openai:gpt-4o")
        assert (caps.provider, caps.model) == ("openai", "gpt-4o")


# ----------------------------------------------------------------------
# Phase 2: Anthropic adapter contract (fake SDK client, no network)
# ----------------------------------------------------------------------

class _FakeStream:
    def __init__(self, chunks, final):
        self.text_stream = list(chunks)
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._final


def _anthropic_message(text):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        id="msg_fake", model="claude-sonnet-4-6", stop_reason="end_turn",
    )


class _FakeAnthropicClient:
    def __init__(self, text='{"ok": true}'):
        self.text = text
        self.create_calls = []
        self.stream_calls = []
        self.messages = SimpleNamespace(create=self._create, stream=self._stream)

    def _create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _anthropic_message(self.text)

    def _stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return _FakeStream([self.text], _anthropic_message(self.text))


class TestAnthropicProvider:
    def test_complete_maps_text_usage_and_metadata(self):
        client = _FakeAnthropicClient("hello")
        provider = AnthropicProvider(model="claude-sonnet-4-6", client=client)
        response = provider.complete([{"role": "user", "content": "hi"}], max_tokens=50)
        assert response.text == "hello"
        assert response.provider == "anthropic"
        assert response.usage.total_tokens == 18
        assert response.metadata["stop_reason"] == "end_turn"
        assert client.create_calls[0]["model"] == "claude-sonnet-4-6"

    def test_complete_omits_temperature_for_rejecting_model(self):
        client = _FakeAnthropicClient("x")
        provider = AnthropicProvider(model="claude-opus-4-8", client=client)
        provider.complete([{"role": "user", "content": "hi"}], temperature=0.2)
        assert "temperature" not in client.create_calls[0]

    def test_stream_text_joins_chunks(self):
        client = _FakeAnthropicClient("streamed")
        provider = AnthropicProvider(model="claude-sonnet-4-6", client=client)
        assert provider.stream_text([{"role": "user", "content": "hi"}]) == "streamed"
        assert client.stream_calls, "stream transport expected"

    def test_structured_schema_uses_output_config(self):
        client = _FakeAnthropicClient('{"label": "Duty"}')
        provider = AnthropicProvider(model="claude-sonnet-4-6", client=client)
        schema = {"type": "object", "properties": {"label": {"type": "string"}}}
        result = provider.structured([{"role": "user", "content": "extract"}], schema)
        assert result == {"label": "Duty"}
        assert client.stream_calls[0]["output_config"] == {
            "format": {"type": "json_schema", "schema": schema}}


class _PromptOnlyProvider(AnthropicProvider):
    """Anthropic transport with capabilities forced to prompt_only."""

    name = "anthropic"

    def capabilities(self, model=None):
        return ProviderCapabilities(provider="anthropic", model=model or "",
                                    structured_tier="prompt_only")


# ----------------------------------------------------------------------
# Phase 4: OpenAI adapter + factory (fake SDK client, no network)
# ----------------------------------------------------------------------

def _openai_response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5),
        id="chatcmpl_fake", model="gpt-4o",
    )


class _FakeOpenAIClient:
    def __init__(self, text='{"ok": true}'):
        self.text = text
        self.create_calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.create_calls.append(kwargs)
        if kwargs.get("stream"):
            return [SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=self.text))])]
        return _openai_response(self.text)


class TestOpenAIProvider:
    def test_complete_prepends_system_and_maps_usage(self):
        client = _FakeOpenAIClient("answer")
        provider = OpenAIProvider(model="gpt-4o", client=client)
        response = provider.complete(
            [{"role": "user", "content": "q"}], system="be terse")
        assert response.text == "answer"
        assert response.provider == "openai"
        assert response.usage.input_tokens == 13
        assert client.create_calls[0]["messages"][0] == {
            "role": "system", "content": "be terse"}

    def test_stream_text_joins_deltas(self):
        client = _FakeOpenAIClient("chunked")
        provider = OpenAIProvider(model="gpt-4o", client=client)
        assert provider.stream_text([{"role": "user", "content": "q"}]) == "chunked"

    def test_structured_schema_uses_strict_response_format(self):
        client = _FakeOpenAIClient('{"label": "Duty"}')
        provider = OpenAIProvider(model="gpt-4o", client=client)
        schema = {"type": "object", "properties": {"label": {"type": "string"}}}
        result = provider.structured([{"role": "user", "content": "extract"}], schema)
        assert result == {"label": "Duty"}
        fmt = client.create_calls[0]["response_format"]
        assert fmt["type"] == "json_schema"
        assert fmt["json_schema"]["strict"] is True
        assert fmt["json_schema"]["schema"] == schema

    def test_json_object_fallback_for_non_schema_model(self):
        client = _FakeOpenAIClient('{"a": 2}')
        provider = OpenAIProvider(model="gpt-3.5-turbo", client=client)
        result = provider.structured(
            [{"role": "user", "content": "extract"}], {"type": "object"})
        assert result == {"a": 2}
        assert client.create_calls[0]["response_format"] == {"type": "json_object"}


class TestFactory:
    def test_get_provider_by_ref(self):
        provider = get_provider("openai:gpt-4o", client=_FakeOpenAIClient())
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"

    def test_get_provider_bare_claude(self):
        provider = get_provider("claude-sonnet-4-6", client=_FakeAnthropicClient())
        assert isinstance(provider, AnthropicProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_provider("ollama:llama3")

    def test_tier_provider_defaults_to_anthropic(self, monkeypatch):
        monkeypatch.delenv("LLM_DEFAULT_REF", raising=False)
        provider = get_tier_provider("default", client=_FakeAnthropicClient())
        assert isinstance(provider, AnthropicProvider)

    def test_tier_provider_follows_env_ref(self, monkeypatch):
        monkeypatch.setenv("LLM_FAST_REF", "openai:gpt-4o-mini")
        provider = get_tier_provider("fast", client=_FakeOpenAIClient())
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o-mini"


# ----------------------------------------------------------------------
# Phase 3: LLMManager per-call dispatch (injected fake providers)
# ----------------------------------------------------------------------

def _manager_with_fakes(anthropic_text="from-anthropic", openai_text="from-openai"):
    anthropic_client = _FakeAnthropicClient(anthropic_text)
    openai_client = _FakeOpenAIClient(openai_text)
    providers = {
        "anthropic": AnthropicProvider(model="claude-sonnet-4-6", client=anthropic_client),
        "openai": OpenAIProvider(model="gpt-4o", client=openai_client),
    }
    manager = LLMManager(model="claude-sonnet-4-6", providers=providers)
    return manager, anthropic_client, openai_client


class TestManagerPerCallDispatch:
    def test_default_model_uses_construction_provider(self):
        manager, anthropic_client, openai_client = _manager_with_fakes()
        response = manager.complete([{"role": "user", "content": "hi"}])
        assert response.text == "from-anthropic"
        assert anthropic_client.create_calls and not openai_client.create_calls

    def test_per_call_openai_model_routes_to_openai(self):
        # Regression: complete() previously dispatched on the
        # construction-time provider, sending gpt-* ids to Anthropic.
        manager, anthropic_client, openai_client = _manager_with_fakes()
        response = manager.complete(
            [{"role": "user", "content": "hi"}], model="gpt-4o")
        assert response.text == "from-openai"
        assert response.provider == "openai"
        assert openai_client.create_calls and not anthropic_client.create_calls

    def test_per_call_anthropic_model_routes_back(self):
        manager, anthropic_client, openai_client = _manager_with_fakes()
        manager.complete([{"role": "user", "content": "hi"}], model="gpt-4o")
        response = manager.complete(
            [{"role": "user", "content": "hi"}], model="claude-opus-4-8")
        assert response.text == "from-anthropic"
        assert response.provider == "anthropic"

    def test_usage_tracking_and_cost_across_providers(self):
        manager, _, _ = _manager_with_fakes()
        manager.complete([{"role": "user", "content": "hi"}])
        manager.complete([{"role": "user", "content": "hi"}], model="gpt-4o")
        stats = manager.get_usage_stats()
        assert stats["total_calls"] == 2
        assert stats["total_cost_usd"] > 0

    def test_structured_and_stream_passthroughs(self):
        manager, _, _ = _manager_with_fakes(
            anthropic_text='{"x": 1}', openai_text='{"x": 2}')
        schema = {"type": "object"}
        assert manager.structured(
            [{"role": "user", "content": "e"}], schema) == {"x": 1}
        assert manager.structured(
            [{"role": "user", "content": "e"}], schema, model="gpt-4o") == {"x": 2}
        assert manager.stream_text(
            [{"role": "user", "content": "e"}], model="gpt-4o") == '{"x": 2}'

    def test_detect_provider_uses_ref_parsing(self):
        manager, _, _ = _manager_with_fakes()
        assert manager._detect_provider("openai:gpt-4o") == "openai"
        assert manager._detect_provider("claude-sonnet-4-6") == "anthropic"


# ----------------------------------------------------------------------
# Phase 5: capability guards on Anthropic-native call sites
# ----------------------------------------------------------------------

class TestCapabilityGuards:
    def test_require_schema_passes_for_capable_models(self):
        assert require_capability("anthropic:claude-sonnet-4-6", "schema").guarantees_schema
        assert require_capability("openai:gpt-4o", "schema").guarantees_schema

    def test_require_schema_raises_for_json_object_model(self):
        with pytest.raises(UnsupportedCapabilityError, match="does not declare"):
            require_capability("openai:gpt-3.5-turbo", "schema")

    def test_require_tool_use_raises_for_unknown_provider(self):
        with pytest.raises(UnsupportedCapabilityError):
            require_capability("ollama:llama3", "tool_use")

    def test_verifier_structured_stream_routes_openai_via_provider(self, monkeypatch):
        import app.services.llm.factory as factory
        from app.services.extraction.extraction_verifier import _structured_stream_json

        anthropic_client = _FakeAnthropicClient("{}")
        openai_client = _FakeOpenAIClient('{"results": []}')
        monkeypatch.setattr(
            factory, "get_provider",
            lambda ref, client=None: OpenAIProvider(model="gpt-4o", client=openai_client))
        result = _structured_stream_json(
            anthropic_client, "openai:gpt-4o", "prompt", {"type": "object"},
            max_tokens=100)
        assert result == {"results": []}
        assert not anthropic_client.stream_calls, (
            "the Anthropic client must not receive a non-Anthropic call")
        assert openai_client.create_calls[0]["response_format"]["type"] == "json_schema"

    def test_verifier_structured_stream_accepts_anthropic_model(self):
        from app.services.extraction.extraction_verifier import _structured_stream_json

        client = _FakeAnthropicClient('{"results": []}')
        # Fake stream lacks text_stream items shaped as verifier expects;
        # use create-shaped fake via stream chunks of JSON text.
        result = _structured_stream_json(client, "claude-sonnet-4-6", "prompt",
                                         {"type": "object"}, max_tokens=100)
        assert result == {"results": []}


class TestEdgeBaseOnOpenAIProvider:
    def test_stream_llm_routes_through_injected_openai_provider(self):
        from app.services.extraction.edge_extractor_base import StreamingEdgeExtractor

        class _Extractor(StreamingEdgeExtractor):
            def _system_prompt(self):
                return "SYSTEM"

        client = _FakeOpenAIClient("edge-json")
        provider = OpenAIProvider(model="gpt-4o", client=client)
        extractor = _Extractor(llm_client=provider, model="gpt-4o")
        assert extractor._stream_llm("USER") == "edge-json"
        # System prompt travels as the leading system message on OpenAI.
        assert client.create_calls[0]["messages"][0] == {
            "role": "system", "content": "SYSTEM"}
        assert extractor.last_raw_response == "edge-json"


class TestWaveCExtractorsOnOpenAI:
    def test_obligation_engagement_via_openai_provider(self, monkeypatch):
        import app.services.extraction.obligation_engagement as oe

        stub = SimpleNamespace(render_system=lambda **kw: "SYSTEM")
        monkeypatch.setattr(oe, "_load_obligation_engagement_template", lambda: stub)
        client = _FakeOpenAIClient('{"actions": []}')
        extractor = oe.ObligationEngagementExtractor(
            llm_client=OpenAIProvider(model="gpt-4o", client=client), model="gpt-4o")
        assert extractor._call_llm("USER") == '{"actions": []}'
        assert client.create_calls[0]["messages"][0]["content"] == "SYSTEM"

    def test_board_conclusions_via_openai_provider(self, monkeypatch):
        import app.services.extraction.board_conclusions as bc

        stub = SimpleNamespace(render_system=lambda **kw: "SYSTEM")
        monkeypatch.setattr(bc, "_load_board_conclusions_template", lambda: stub)
        client = _FakeOpenAIClient('{"conclusions": []}')
        extractor = bc.BoardConclusionExtractor(
            llm_client=OpenAIProvider(model="gpt-4o", client=client), model="gpt-4o")
        assert extractor._call_llm("USER") == '{"conclusions": []}'

    def test_factory_provider_for_client(self):
        from app.services.llm.factory import provider_for_client

        raw = _FakeAnthropicClient("x")
        wrapped = provider_for_client(raw, "claude-sonnet-4-6")
        assert isinstance(wrapped, AnthropicProvider)
        provider = OpenAIProvider(model="gpt-4o", client=_FakeOpenAIClient())
        assert provider_for_client(provider, "gpt-4o") is provider
        assert isinstance(provider_for_client(None, "gpt-4o"), OpenAIProvider)


class TestPrecedentFamilyOnProviders:
    def test_discovery_llm_text_via_injected_openai_provider(self):
        from app.services.precedent.precedent_discovery_service import (
            PrecedentDiscoveryService)

        client = _FakeOpenAIClient("relevant because both involve candor")
        service = PrecedentDiscoveryService(
            llm_client=OpenAIProvider(model="gpt-4o", client=client))
        text = service._llm_text("prompt", max_tokens=200, temperature=0.3)
        assert "candor" in text
        assert client.create_calls[0]["max_tokens"] == 200

    def test_discovery_no_client_guard_unchanged(self):
        from app.services.precedent.precedent_discovery_service import (
            PrecedentDiscoveryService)

        service = PrecedentDiscoveryService(llm_client=None)
        assert service.llm_client is None  # callers keep rule-based fallback

    def test_similarity_weights_via_injected_openai_provider(self, monkeypatch):
        from app.services.precedent.similarity_service import (
            PrecedentSimilarityService)

        weights_json = '{"facts_similarity": 0.5, "discussion_similarity": 0.5}'
        client = _FakeOpenAIClient(weights_json)
        service = PrecedentSimilarityService(
            llm_client=OpenAIProvider(model="gpt-4o", client=client))
        monkeypatch.setattr(service, "_get_case_features",
                            lambda case_id: {"title": "case"})
        monkeypatch.setattr(service, "_build_weight_prompt",
                            lambda features, focus: "weights prompt")
        weights = service.get_dynamic_weights(case_id=1)
        assert weights  # parsed through the existing weight parser
        assert client.create_calls, "provider completion expected"


class TestUnifiedExtractorRouting:
    def test_non_anthropic_model_routes_to_provider_structured(self, monkeypatch):
        import app.services.llm.factory as factory
        import app.utils.llm_utils as llm_utils
        from app.services.extraction.unified_dual_extractor.llm_calls import LLMCallMixin

        anthropic_client = _FakeAnthropicClient("{}")
        monkeypatch.setattr(llm_utils, "get_llm_client", lambda: anthropic_client)
        openai_client = _FakeOpenAIClient('{"new_entities": []}')
        monkeypatch.setattr(
            factory, "get_provider",
            lambda ref, client=None: OpenAIProvider(model="gpt-4o", client=openai_client))

        extractor = LLMCallMixin.__new__(LLMCallMixin)
        extractor.injection_mode = "full"
        extractor.llm_client = None
        extractor.mcp_client = None
        extractor.model_name = "gpt-4o"
        extractor.concept_type = "roles"
        extractor.config = {"max_tokens": 1000, "temperature": 0.1}
        extractor._structured_output_schema = {"type": "object"}
        extractor._rendered_system = ""

        result = extractor._call_llm("extract prompt")
        assert result == {"new_entities": []}
        assert not anthropic_client.stream_calls
        assert openai_client.create_calls, "OpenAI structured call expected"


class TestNarrativeFamilyOnOpenAI:
    def test_scenario_seed_llm_text_via_openai(self, monkeypatch):
        import app.services.narrative.scenario_seed_generator as mod

        stub_template = SimpleNamespace(render=lambda **kw: "PROMPT")
        monkeypatch.setattr(mod, "get_step4_template", lambda name: stub_template)
        client = _FakeOpenAIClient("LABEL: Report the hazard\nDESCRIPTION: Notify.")
        gen = mod.ScenarioSeedGenerator.__new__(mod.ScenarioSeedGenerator)
        gen.use_llm = True
        gen.llm_client = OpenAIProvider(model="gpt-4o", client=client)
        label, _desc = gen._generate_option_label_llm("Q?", 0, True, ["Duty"])
        assert label == "Report the hazard"
        assert client.create_calls[0]["max_tokens"] == 100

    def test_scenario_seed_raw_anthropic_client_still_wrapped(self):
        import app.services.narrative.scenario_seed_generator as mod

        gen = mod.ScenarioSeedGenerator.__new__(mod.ScenarioSeedGenerator)
        gen.use_llm = True
        gen.llm_client = _FakeAnthropicClient("plain text")
        assert gen._llm_text("p", max_tokens=10) == "plain text"


class TestStep4AnalyzersOnOpenAI:
    def test_conclusion_analyzer_llm_text_via_openai(self):
        from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer

        client = _FakeOpenAIClient("conclusions text")
        analyzer = ConclusionAnalyzer(
            llm_client=OpenAIProvider(model="gpt-4o", client=client))
        assert analyzer._llm_text("p", max_tokens=6000) == "conclusions text"
        assert analyzer.last_prompt is None  # constructor intact after migration
        assert client.create_calls[0]["max_tokens"] == 6000

    def test_question_analyzer_llm_text_via_openai(self):
        from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer

        client = _FakeOpenAIClient("questions text")
        analyzer = QuestionAnalyzer(
            llm_client=OpenAIProvider(model="gpt-4o", client=client))
        assert analyzer._llm_text("p", max_tokens=4000) == "questions text"
        assert analyzer.analytical_failed is False


class TestWaveHStreamingSitesOnOpenAI:
    def test_edge_resolution_multi_via_openai_provider(self):
        from rdflib import Namespace
        from app.services.extraction import edge_resolution as er

        case = Namespace("http://proethica.org/ontology/case/15#")
        items = [{"id": 1, "subj": case["R"], "desc": "d", "resource_label": "R",
                  "shortlist": [(case["A"], "A", 0.9), (case["B"], "B", 0.8)]}]
        client = _FakeOpenAIClient('{"1": [1]}')
        provider = OpenAIProvider(model="gpt-4o", client=client)
        out = er._llm_select_multi(items, client=provider, model="gpt-4o",
                                   prompt_builder=lambda items: "pick")
        assert out["1"] == [case["A"]]
        assert client.create_calls, "streamed provider call expected"

    def test_semantic_audit_judge_via_openai_provider(self, monkeypatch):
        import app.services.llm.factory as factory
        from app.services.qc import semantic_audit

        client = _FakeOpenAIClient('{"verdict": "pass"}')
        monkeypatch.setattr(
            factory, "get_tier_provider",
            lambda tier="default", client=None: OpenAIProvider(
                model="gpt-4o", client=_FakeOpenAIClient('{"verdict": "pass"}')))
        assert semantic_audit._judge("audit prompt") == {"verdict": "pass"}


class TestWaveISingleSites:
    def test_factory_detects_openai_shaped_client(self):
        from app.services.llm.factory import provider_for_client

        shaped = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: None)))
        provider = provider_for_client(shaped, "gpt-4o")
        assert isinstance(provider, OpenAIProvider)

    def test_board_choice_verifier_via_openai_provider(self, monkeypatch):
        import app.services.decision_point_synthesizer.board_choice_verifier as mod

        stub = SimpleNamespace(render=lambda **kw: "verify prompt")
        monkeypatch.setattr(mod, "get_step4_template", lambda name: stub)
        client = _FakeOpenAIClient('{"picks": []}')
        dp = SimpleNamespace(focus_id="DP1", decision_question="Q?",
                             options=[{"label": "A", "is_board_choice": True}])
        # Module reads option dicts via its own helper; empty picks = checked none.
        summary = mod.verify_board_choices(
            7, [dp], [{"conclusion_text": "x"}],
            llm_client=OpenAIProvider(model="gpt-4o", client=client))
        assert summary["error"] is None
        assert client.create_calls, "provider completion expected"

    def test_reconciliation_call_via_tier_provider(self, monkeypatch):
        import app.services.llm.factory as factory
        from app.services.entity.entity_reconciliation_service import (
            EntityReconciliationService)

        monkeypatch.setattr(
            factory, "get_tier_provider",
            lambda tier="default", client=None: OpenAIProvider(
                model="gpt-4o-mini",
                client=_FakeOpenAIClient('{"duplicates": []}')))
        service = EntityReconciliationService.__new__(EntityReconciliationService)
        assert service._call_llm("dedup prompt") == {"duplicates": []}


class TestRouteHelpersOnOpenAI:
    def test_precedent_route_helper_via_openai_provider(self):
        from app.routes.scenario_pipeline.step4.precedents import _precedent_llm_text

        client = _FakeOpenAIClient('{"precedents": []}')
        provider = OpenAIProvider(model="gpt-4o", client=client)
        assert _precedent_llm_text(provider, "find precedents") == '{"precedents": []}'
        assert client.create_calls[0]["max_tokens"] == 4096

    def test_precedent_route_helper_wraps_raw_anthropic_client(self):
        from app.routes.scenario_pipeline.step4.precedents import _precedent_llm_text

        raw = _FakeAnthropicClient("raw text")
        assert _precedent_llm_text(raw, "p") == "raw text"


class TestConsolidationTimeout:
    def test_tier_provider_carries_timeout(self, monkeypatch):
        monkeypatch.delenv("LLM_POWERFUL_REF", raising=False)
        provider = get_tier_provider("powerful", client=_FakeAnthropicClient(),
                                     timeout=300.0)
        assert provider.timeout == 300.0

    def test_provider_default_timeout_unchanged(self):
        provider = AnthropicProvider(model="claude-sonnet-4-6",
                                     client=_FakeAnthropicClient())
        assert provider.timeout is None  # adapter applies its 180s default


class TestConsolidationParityAndHelpers:
    @pytest.mark.parametrize("ref", [
        "anthropic:claude-sonnet-4-6", "claude:claude-opus-4-8", "openai:gpt-4o",
        "claude-haiku-4-5-20251001", "gpt-4o-mini", "o3-mini", "some-local-model",
        "ollama:llama3",
    ])
    def test_parse_model_ref_and_ref_provider_name_agree(self, ref):
        # Two parsers exist by necessity (ModelConfig is substituted by
        # MagicMock in some calibration tests, so the guard parser cannot
        # import it); this parity test is the single-source guarantee.
        from app.services.llm.capabilities import ref_provider_name

        assert ModelConfig.parse_model_ref(ref)[0] == ref_provider_name(ref)

    def test_complete_text_shared_helper(self):
        from app.services.llm.factory import complete_text

        client = _FakeOpenAIClient("shared")
        # Injected OpenAI-shaped raw client is detected by the factory.
        shaped = SimpleNamespace(
            chat=client.chat, available_models=["gpt-4o"])
        assert complete_text(shaped, "p", max_tokens=10) == "shared"

    def test_streaming_provider_for_client_none_for_non_streaming(self):
        from app.services.llm.factory import streaming_provider_for_client

        assert streaming_provider_for_client(object(), "claude-sonnet-4-6") is None
        provider = streaming_provider_for_client(
            _FakeAnthropicClient("x"), "claude-sonnet-4-6")
        assert isinstance(provider, AnthropicProvider)


class _FakeToolStream:
    def __init__(self, final):
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return []

    def get_final_message(self):
        return self._final


class TestToolLoopAdapters:
    TOOLS = [{"name": "get_class_definition", "description": "lookup",
              "input_schema": {"type": "object",
                               "properties": {"label": {"type": "string"}}}}]

    def test_anthropic_tool_loop_rounds_and_runner(self):
        tool_msg = SimpleNamespace(
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            content=[SimpleNamespace(type="tool_use", name="get_class_definition",
                                     input={"label": "X"}, id="tu_1")])
        end_msg = SimpleNamespace(
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            content=[SimpleNamespace(type="text", text='{"done": true}')])
        streams = [_FakeToolStream(tool_msg), _FakeToolStream(end_msg)]
        calls = []

        def _stream(**kwargs):
            calls.append(kwargs)
            return streams.pop(0)

        client = SimpleNamespace(messages=SimpleNamespace(stream=_stream))
        provider = AnthropicProvider(model="claude-sonnet-4-6", client=client)
        seen = []

        def runner(name, payload):
            seen.append((name, payload))
            return "definition text"

        from app.services.llm.protocol import ToolLoopResult
        result = provider.tool_loop("prompt", self.TOOLS, runner)
        assert isinstance(result, ToolLoopResult)
        assert result.text == '{"done": true}'
        assert result.rounds == 2
        assert seen == [("get_class_definition", {"label": "X"})]
        # Cache anchor on the initial prompt is preserved by the adapter.
        assert calls[0]["messages"][0]["content"][0]["cache_control"] == {
            "type": "ephemeral"}
        assert calls[0]["tools"] == self.TOOLS

    def test_openai_tool_loop_translates_and_runs(self):
        call = SimpleNamespace(
            id="call_1", type="function",
            function=SimpleNamespace(name="get_class_definition",
                                     arguments='{"label": "X"}'))
        first = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[call]),
                finish_reason="tool_calls")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            id="r1", model="gpt-4o")
        final = _openai_response('{"done": true}')
        responses = [first, final]
        calls = []

        def _create(**kwargs):
            calls.append(kwargs)
            return responses.pop(0)

        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=_create)))
        provider = OpenAIProvider(model="gpt-4o", client=client)
        seen = []
        result = provider.tool_loop(
            "prompt", self.TOOLS,
            lambda name, payload: seen.append((name, payload)) or "def text")
        assert result.text == '{"done": true}'
        assert seen == [("get_class_definition", {"label": "X"})]
        assert calls[0]["tools"][0]["function"]["name"] == "get_class_definition"
        tool_msgs = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
        assert tool_msgs and tool_msgs[0]["tool_call_id"] == "call_1"

    def test_extractor_tool_loop_routes_openai(self, monkeypatch):
        import app.services.llm.factory as factory
        import app.utils.llm_utils as llm_utils
        from app.services.extraction.unified_dual_extractor.llm_calls import LLMCallMixin

        monkeypatch.setattr(llm_utils, "get_llm_client",
                            lambda: _FakeAnthropicClient("{}"))
        monkeypatch.setattr(
            factory, "provider_for_client",
            lambda client, model: OpenAIProvider(
                model="gpt-4o", client=_FakeOpenAIClient('{"new_entities": []}')))
        extractor = LLMCallMixin.__new__(LLMCallMixin)
        extractor.model_name = "gpt-4o"
        extractor.concept_type = "roles"
        extractor.config = {"max_tokens": 1000, "temperature": 0.1}
        extractor._rendered_system = ""
        extractor.tool_call_count = 0
        result = extractor._call_llm_with_tools("label prompt")
        assert result == {"new_entities": []}


class TestStreamingCompletionShim:
    def test_delegates_through_wrapped_anthropic_client(self):
        from app.utils.llm_utils import streaming_completion

        client = _FakeAnthropicClient("shim text")
        text = streaming_completion(client, "claude-sonnet-4-6", 100, "prompt")
        assert text == "shim text"
        assert client.stream_calls, "streaming transport preserved"

    def test_thinking_budget_floor_preserved(self):
        from app.utils.llm_utils import streaming_completion

        client = _FakeAnthropicClient("ok")
        streaming_completion(client, "claude-fable-5", 100, "prompt")
        assert client.stream_calls[0]["max_tokens"] == 16000

    def test_truncation_warning_reemitted(self, caplog):
        import logging
        from types import SimpleNamespace as NS
        from app.utils.llm_utils import streaming_completion

        final = NS(content=[NS(type="text", text="partial")],
                   usage=NS(input_tokens=1, output_tokens=1),
                   id="m", stop_reason="max_tokens")
        stream = _FakeStream(["partial"], final)
        client = NS(messages=NS(stream=lambda **kw: stream))
        with caplog.at_level(logging.WARNING, logger="app.utils.llm_utils"):
            text = streaming_completion(client, "claude-sonnet-4-6", 50, "p")
        assert text == "partial"
        assert "hit max_tokens=50" in caplog.text


class TestStructuredLadderPromptOnly:
    def test_prompt_only_parses_markdown_fenced_json(self):
        client = _FakeAnthropicClient('```json\n{"a": 1}\n```')
        provider = _PromptOnlyProvider(model="claude-sonnet-4-6", client=client)
        result = provider.structured(
            [{"role": "user", "content": "extract"}], {"type": "object"})
        assert result == {"a": 1}
        assert "JSON Schema" in client.create_calls[0]["messages"][0]["content"]
