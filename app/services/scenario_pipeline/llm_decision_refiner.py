"""LLM-assisted decision extraction and enrichment for direct scenario pipeline.

This module optionally refines which events are true decision points and enriches them
with improved titles, questions, and option sets using an LLM provider (Anthropic / OpenAI / etc.).

Activation: set env DIRECT_SCENARIO_LLM_REFINEMENT=true and provide provider-specific API key.
Config (env vars):
  DIRECT_SCENARIO_LLM_PROVIDER=anthropic|openai|google (default anthropic)
  DIRECT_SCENARIO_LLM_MODEL=claude-sonnet-4-6 (or provider-specific default)
  DIRECT_SCENARIO_LLM_MAX_DECISIONS=12
"""
from __future__ import annotations
import os
import json
import logging
from typing import List, Dict, Any, Optional

try:
    # Lazy import ModelRouter components; optional if hosted_llm_mcp not installed
    from mcp.hosted_llm_mcp.adapters.model_router import ModelRouter  # type: ignore
    from mcp.hosted_llm_mcp.adapters.anthropic_adapter import AnthropicAdapter  # type: ignore
    from mcp.hosted_llm_mcp.adapters.openai_adapter import OpenAIAdapter  # type: ignore
    ROUTER_AVAILABLE = True
except Exception:  # broad: we only care if not importable
    ROUTER_AVAILABLE = False

from models import ModelConfig

logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = os.environ.get('DIRECT_SCENARIO_LLM_MODEL', ModelConfig.get_claude_model("default"))

PROMPT_TEMPLATE = """You are analyzing an engineering ethics case timeline. Below are participants (if any) and then a numbered list of event summaries.\nYour task: identify the MOST significant ethical decision points (not routine steps). Return STRICT JSON ONLY matching:\n{\n  \"decisions\": [\n    {\"event_index\": <int 1-based>, \"title\": \"concise decision title\", \"question\": \"neutral user-facing decision question\", \"options\": [\n       {\"label\": \"Option A\", \"description\": \"short description\"}\n    ]}\n  ]\n}\nGuidelines:\n- Max {max_decisions} decisions.\n- Favor dilemmas involving safety, public welfare, professional duty, reporting, escalation, conflicts of interest, integrity of data.\n- event_index must match numbering.\n- Question should start with What / How / Should and be impartial.\n- Provide 3-5 distinct strategic options (action paths), not trivial phrasing variants.\n- Omit any option that merely paraphrases another.\nParticipants: {participants}\n\nEvents:\n{events_block}\n\nReturn ONLY JSON, no commentary."""


def _build_events_block(events: List[Dict[str, Any]], max_chars: int = 140) -> str:
    lines = []
    for i, ev in enumerate(events, start=1):
        snippet = ev['text'][:max_chars].replace('\n', ' ')
        lines.append(f"{i}. [{ev['kind']}] {snippet}")
    return "\n".join(lines)


def _build_participants_summary(events: List[Dict[str, Any]]) -> str:
    unique = set()
    for ev in events:
        for p in ev.get('participants', []) or []:
            unique.add(p)
    if not unique:
        return 'None'
    return ", ".join(sorted(unique))


def _get_router() -> Optional[ModelRouter]:
    if not ROUTER_AVAILABLE:
        return None
    # Instantiate minimal adapters using env keys; defer failures gracefully
    try:
        akey = os.environ.get('ANTHROPIC_API_KEY')
        okey = os.environ.get('OPENAI_API_KEY')
        anth = AnthropicAdapter(api_key=akey) if akey else None
        opn = OpenAIAdapter(api_key=okey) if okey else None
        if not (anth or opn):
            return None
        # Provide dummies if one missing (ModelRouter expects both)
        if not anth:
            class DummyAnth:  # minimal stub
                async def complete(self, *a, **k):
                    return {'success': False, 'error': 'Anthropic disabled'}
            anth = DummyAnth()  # type: ignore
        if not opn:
            class DummyOpen:  # minimal stub
                async def complete(self, *a, **k):
                    return {'success': False, 'error': 'OpenAI disabled'}
            opn = DummyOpen()  # type: ignore
        routing = {
            'decision_selection': os.environ.get('DIRECT_SCENARIO_LLM_PROVIDER', 'anthropic')
        }
        return ModelRouter(anthropic_adapter=anth, openai_adapter=opn, routing_config=routing)
    except Exception as e:
        logger.warning(f"Router init failed: {e}")
        return None


def refine_decisions_with_llm(events: List[Dict[str, Any]]) -> None:
    """Mutates events list updating decision events via LLM selection.
    Keeps existing structure if refinement disabled or fails.
    """
    provider_enabled = os.environ.get('DIRECT_SCENARIO_LLM_REFINEMENT', 'false').lower() == 'true'
    if not provider_enabled:
        return

    provider = os.environ.get('DIRECT_SCENARIO_LLM_PROVIDER', 'anthropic').lower()
    max_decisions = int(os.environ.get('DIRECT_SCENARIO_LLM_MAX_DECISIONS', '12'))
    include_participants = os.environ.get('DIRECT_SCENARIO_INCLUDE_PARTICIPANTS', 'true').lower() != 'false'

    try:
        events_block = _build_events_block(events)
        participants_summary = _build_participants_summary(events) if include_participants else 'None'
        prompt = PROMPT_TEMPLATE.format(events_block=events_block, max_decisions=max_decisions, participants=participants_summary)
        logger.info(f"LLM decision refinement invoked provider={provider}")

        raw_response = None
        router = _get_router()
        if router:
            import asyncio
            try:
                result = asyncio.run(router.route('decision_selection', prompt, temperature=0, max_tokens=1500))
                if result.get('success'):  # result['result'] may be JSON or string
                    rr = result.get('result')
                    if isinstance(rr, dict):
                        # shortcut: already parsed JSON
                        data = rr
                        decisions = data.get('decisions') or []
                        if decisions:
                            _apply_refined_decisions(events, decisions)
                        return
                    else:
                        raw_response = str(rr)
                else:
                    logger.warning(f"Router task failure: {result.get('error')}")
            except Exception as e:
                logger.warning(f"Router invocation failed: {e}")
        else:
            logger.info('ModelRouter unavailable; falling back to direct provider invocation.')

        # Fallback direct Anthropic (legacy path) if router missing and provider anthropic
        if raw_response is None and provider == 'anthropic':
            try:
                import anthropic
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                if not api_key:
                    logger.warning('ANTHROPIC_API_KEY missing; cannot refine decisions.')
                    return
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model=DEFAULT_ANTHROPIC_MODEL,
                    max_tokens=1200,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_response = "".join(part.text for part in msg.content if hasattr(part, 'text'))
            except Exception as e:
                logger.warning(f"Direct anthropic fallback failed: {e}")
                return
        elif raw_response is None:
            logger.warning('No viable LLM path; skipping refinement.')
            return

        if not raw_response:
            logger.warning('Empty LLM response for decision refinement.')
            return

        # Attempt to isolate JSON
        json_start = raw_response.find('{')
        json_end = raw_response.rfind('}')
        if json_start == -1 or json_end == -1:
            logger.warning('LLM response lacked JSON braces.')
            return
        payload_str = raw_response[json_start:json_end+1]
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning('Failed to parse LLM JSON for decisions.')
            return

        decisions = data.get('decisions') or []
        if not isinstance(decisions, list) or not decisions:
            logger.info('LLM returned no decisions; keeping heuristic results.')
            return
        _apply_refined_decisions(events, decisions)

    except Exception as e:
        logger.error(f"LLM decision refinement failed: {e}")
        # Fail silently without breaking pipeline
        return


def _apply_refined_decisions(events: List[Dict[str, Any]], decisions: List[Dict[str, Any]]) -> None:
    # Reset existing decisions to action/context; we'll reassign
    for ev in events:
        if ev['kind'] == 'decision':
            ev['kind'] = 'action'
            ev.pop('options', None)
    applied = 0
    for d in decisions:
        try:
            idx = int(d.get('event_index')) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(events):
            ev = events[idx]
            ev['kind'] = 'decision'
            ev['refined'] = True
            ev['title'] = d.get('title') or ev.get('title') or 'Decision'
            ev['question'] = d.get('question')
            opts = d.get('options') or []
            normalized_opts = []
            for opt in opts[:6]:
                if not isinstance(opt, dict):
                    continue
                label = opt.get('label') or 'Option'
                desc = opt.get('description') or ''
                normalized_opts.append({'label': label, 'description': desc})
            if normalized_opts:
                ev['options'] = normalized_opts
            applied += 1
    logger.info(f"Applied {applied} refined decision points (LLM)")
