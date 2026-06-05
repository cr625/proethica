"""Fail-loud-in-dev guard (R4, 2026-06-04).

Several pipeline paths catch an infrastructure failure (OntServe DB unreachable,
embedding service crash, MCP server down) and substitute a DEGRADED result that
silently masquerades as a valid one:
  * an empty OntServe class cache reads as "no existing classes" -> every entity is
    minted as new (permanent vocabulary proliferation),
  * an embedding-service error reads as "no match" -> mint new,
  * an MCP-down reads as "enrich locally / not found" -> degraded definitions.
Each violates the global "do not use fallbacks in development mode" rule and can
corrupt committed data invisibly (the operator sees only one WARN line).

`fail_loud_in_dev` re-raises such failures in development so they are loud, and lets
the caller fall back in production so a long batch is not broken by a transient blip.
Override with PROETHICA_DEV_FAIL_LOUD=1 (force raise) / =0 (force swallow).
"""
import logging
import os

logger = logging.getLogger(__name__)


def fail_loud_in_dev(exc: Exception, context: str) -> None:
    """Re-raise `exc` (wrapped) in development; return (let caller fall back) in
    production. `context` describes the masked failure for the message and log.

    Raises:
        RuntimeError: in development (or when PROETHICA_DEV_FAIL_LOUD=1).
    """
    override = os.environ.get('PROETHICA_DEV_FAIL_LOUD')
    if override == '1':
        loud = True
    elif override == '0':
        loud = False
    else:
        loud = not _is_production()
    if loud:
        raise RuntimeError(
            f"{context} -- failing loud in development. This infrastructure failure "
            f"would otherwise silently degrade to a corrupting result; fix the cause, "
            f"or set PROETHICA_DEV_FAIL_LOUD=0 to swallow. Cause: {exc}"
        ) from exc
    logger.warning("%s -- swallowed in production (degraded result): %s", context, exc)


def _is_production() -> bool:
    try:
        from flask import current_app
        return current_app.config.get('ENVIRONMENT') == 'production'
    except Exception:
        # No app context (standalone script): treat as development (fail loud)
        # unless explicitly overridden via PROETHICA_DEV_FAIL_LOUD.
        return False
