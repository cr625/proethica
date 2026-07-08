"""Board-choice verification pass for canonical decision points.

The 2026-07-08 Phase-B audit (step4-decisions-analysis.md) confirmed a
generation defect that survived explicit prompt rules: in violation-type
cases, the refinement marks the party's ACTUAL (condemned) conduct as
is_board_choice -- case 7 marked "Perform Only Cursory Review Before
Sealing" and "Upload Confidential Data Without Prior Consent" as the
Board's choice when the Board held both to be the violations themselves.

Generation-embedded marking has proven unreliable for exactly this shape,
so the flag is verified by a single-purpose checker: given ONLY the options
and the full board conclusions, pick the option the Board held to be the
ethical course (or none, when the Board made no such determination), and
override the flags accordingly. One LLM call per case; failures leave the
flags unchanged and are logged, never fatal.
"""
import json
import logging
import time
from typing import List, Optional

from model_config import ModelConfig

logger = logging.getLogger(__name__)


def _options_of(dp) -> Optional[list]:
    opts = getattr(dp, 'options', None)
    if isinstance(opts, list) and opts and all(isinstance(o, dict) for o in opts):
        return opts
    return None


def verify_board_choices(case_id: int, canonical_points: List, conclusions: List[dict],
                         llm_client=None) -> dict:
    """Verify and, where needed, override is_board_choice on each decision
    point's options. Returns a summary dict {checked, overridden, cleared,
    unmatched, error}."""
    summary = {'checked': 0, 'overridden': 0, 'cleared': 0, 'unmatched': 0, 'error': None}

    dps = [dp for dp in canonical_points if _options_of(dp)]
    if not dps:
        return summary
    concl_text = "\n".join(
        f"- {(c.get('conclusion_text') or c.get('text') or '').strip()}"
        for c in (conclusions or []) if isinstance(c, dict)
    ).strip()
    if not concl_text:
        logger.warning(f"Board-choice verifier: case {case_id} has no conclusion text; skipping")
        return summary

    payload = [{
        'id': getattr(dp, 'focus_id', f'DP{i}'),
        'question': getattr(dp, 'decision_question', ''),
        'options': [o.get('label') for o in _options_of(dp)],
    } for i, dp in enumerate(dps, 1)]

    prompt = f"""For each decision point below, identify which option is the course of action the
Board of Ethical Review held to be the ETHICAL one, based ONLY on the Board's conclusions.

Rules:
- The Board's choice is the conduct the Board endorsed or required. When the Board found
  the party's actual conduct unethical, the endorsed course is the compliant alternative,
  NEVER the condemned conduct.
- When the conclusions make no determination that selects among the options, return null.
- Return the option label EXACTLY as given.

BOARD CONCLUSIONS:
{concl_text}

DECISION POINTS:
{json.dumps(payload, indent=1)}

Return STRICT JSON only:
{{"picks": [{{"id": "DP1", "board_option_label": "<exact label or null>", "reason": "<one clause>"}}]}}"""

    if llm_client is None:
        from app.utils.llm_utils import get_llm_client
        llm_client = get_llm_client()
    model = ModelConfig.get_claude_model("default")

    data = None
    for attempt in range(1, 4):
        try:
            resp = llm_client.messages.create(
                model=model, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}])
            txt = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
            if txt and resp.stop_reason != "max_tokens":
                from app.utils.llm_utils import extract_json_from_response
                data = extract_json_from_response(txt)
                break
        except Exception as exc:  # noqa: BLE001 - retried, then reported
            logger.warning(f"Board-choice verifier case {case_id} attempt {attempt}: {exc}")
        time.sleep(3 * attempt)
    if data is None:
        summary['error'] = 'no valid checker response'
        logger.warning(f"Board-choice verifier: case {case_id} got no valid response; flags unchanged")
        return summary

    picks = {p.get('id'): p for p in data.get('picks', []) if isinstance(p, dict)}
    for i, dp in enumerate(dps, 1):
        dp_id = getattr(dp, 'focus_id', f'DP{i}')
        pick = picks.get(dp_id)
        if not pick:
            continue
        summary['checked'] += 1
        opts = _options_of(dp)
        label = pick.get('board_option_label')
        current = next((o.get('label') for o in opts if o.get('is_board_choice')), None)
        if label is None:
            if current is not None:
                for o in opts:
                    o['is_board_choice'] = False
                summary['cleared'] += 1
                logger.info(f"Board-choice verifier case {case_id} {dp_id}: cleared "
                            f"(no board determination; was {current!r}) -- {pick.get('reason','')[:120]}")
            continue
        match = next((o for o in opts if (o.get('label') or '').strip().lower()
                      == str(label).strip().lower()), None)
        if match is None:
            summary['unmatched'] += 1
            logger.warning(f"Board-choice verifier case {case_id} {dp_id}: pick {label!r} "
                           f"matches no option; flags unchanged")
            continue
        if not match.get('is_board_choice'):
            for o in opts:
                o['is_board_choice'] = (o is match)
            summary['overridden'] += 1
            logger.info(f"Board-choice verifier case {case_id} {dp_id}: {current!r} -> "
                        f"{match.get('label')!r} -- {pick.get('reason','')[:120]}")
    return summary
