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

from app.services.step4_synthesis.template_loader import get_step4_template
from app.services.step4_synthesis.qc_refs import board_explicit_only

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
    summary = {'checked': 0, 'overridden': 0, 'cleared': 0, 'unmatched': 0, 'error': None,
               'analytical_skipped': 0}

    # A decision point aligned only with generated analysis has no Board
    # choice to verify: its flags are cleared and it is kept out of the
    # checker payload (case 8 DP5 was "confirmed" against a generated
    # conclusion -- lesson L3).
    dps = []
    for dp in canonical_points:
        if not _options_of(dp):
            continue
        if getattr(dp, 'synthesis_method', '') == 'analytical_extension':
            for o in _options_of(dp):
                o['is_board_choice'] = False
            summary['analytical_skipped'] += 1
            continue
        dps.append(dp)
    if not dps:
        return summary
    # The template says "based ONLY on the Board's conclusions": feed it only
    # the board_explicit ones, never the Step-4 generated conclusions.
    board_conclusions = board_explicit_only(
        [c for c in (conclusions or []) if isinstance(c, dict)], 'C')
    concl_text = "\n".join(
        f"- {(c.get('conclusion_text') or c.get('text') or '').strip()}"
        for c in board_conclusions
    ).strip()
    if not concl_text:
        logger.warning(f"Board-choice verifier: case {case_id} has no Board conclusion text; skipping")
        return summary

    payload = [{
        'id': getattr(dp, 'focus_id', f'DP{i}'),
        'question': getattr(dp, 'decision_question', ''),
        'options': [o.get('label') for o in _options_of(dp)],
    } for i, dp in enumerate(dps, 1)]

    prompt = get_step4_template('step4_dp_board_verify').render(
        concl_text=concl_text,
        payload_json=json.dumps(payload, indent=1),
    )

    if llm_client is None:
        from app.utils.llm_utils import get_llm_client
        llm_client = get_llm_client()
    model = ModelConfig.get_tier_model("default")
    from app.services.llm.factory import provider_for_client
    provider = provider_for_client(llm_client, model)

    data = None
    for attempt in range(1, 4):
        try:
            resp = provider.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000, temperature=None, model=model)
            txt = resp.text.strip()
            stop = resp.metadata.get("stop_reason") or resp.metadata.get("finish_reason")
            if txt and stop not in ("max_tokens", "length"):
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
