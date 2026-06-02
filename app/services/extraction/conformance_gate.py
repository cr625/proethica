"""Pre-commit conformance gate (C3 + deterministic Tier-0 repair).

After the commit serializer materialises a case TTL, this gate sends it to OntServe's
``repair_conformance_ttl`` MCP tool (SHACL + OWL-RL check + deterministic Tier-0 repair, no
LLM), writes any repaired TTL back to disk so the disk->DB sync persists the conforming
version, and records the conformance status in the commit result.

Why the check runs in OntServe (not here): it needs pyshacl + owlready2 + OntServe's own
``config`` package, none of which load cleanly in the ProEthica process (the two repos share a
top-level ``config`` name). The LLM repair tiers (D3 Tier 1/2: Haiku -> Sonnet -> Opus) are
deferred to the Section-C pilot, where they calibrate on regenerated output; so a residual the
deterministic tier cannot fix is LOGGED (actionable) and the case is flagged, NOT hard-refused
-- a rare residual must not halt a 119-case batch. The matcher chain-category gate (Phase A)
already prevents most violations upstream, so Tier-0 should resolve the rest.

Best-effort: a gate failure is logged and recorded but never raises, mirroring
``materialize_edges_on_ttl``, so the gate can never fail a commit.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def gate_case_ttl(case_id: int, ttl_path, domain: str = "engineering") -> Dict[str, Any]:
    """Validate + Tier-0-repair the case TTL in place via the OntServe MCP tool.

    Returns a status dict: ``status`` in {ok, no_ttl, gate_unavailable, gate_error},
    plus ``conforms`` / ``repairs_applied`` / ``residual`` when status == ok.
    """
    ttl_path = Path(ttl_path)
    if not ttl_path.exists():
        return {"status": "no_ttl"}
    try:
        from app.services.external_mcp_client import get_external_mcp_client

        client = get_external_mcp_client()
        content = ttl_path.read_text()
        resp = client.call_tool(
            "repair_conformance_ttl", {"ttl_content": content, "domain": domain}
        )
        if not resp.get("success"):
            logger.error(
                "conformance gate: repair_conformance_ttl MCP call failed for case %s: %s",
                case_id, resp.get("error"),
            )
            return {"status": "gate_unavailable", "error": resp.get("error")}

        data = resp.get("result") or {}
        if isinstance(data, str):
            data = json.loads(data)

        repaired = data.get("repaired_ttl")
        applied = int(data.get("repairs_applied") or 0)
        conforms = bool(data.get("conforms"))
        residual = (data.get("remaining") or {}).get("violations", []) or []

        if applied and repaired:
            ttl_path.write_text(repaired)  # persist the repaired (conforming) version
            logger.info(
                "conformance gate: case %s -- Tier-0 repaired %d violation(s)",
                case_id, applied,
            )
        if not conforms:
            logger.warning(
                "conformance gate: case %s does NOT conform after Tier-0 "
                "(%d residual; LLM repair tiers deferred to the pilot): %s",
                case_id, len(residual), residual[:3],
            )
        return {
            "status": "ok",
            "conforms": conforms,
            "repairs_applied": applied,
            "residual": len(residual),
        }
    except Exception as e:  # noqa: BLE001 -- best-effort overlay, never fail the commit
        logger.exception("conformance gate: error for case %s", case_id)
        return {"status": "gate_error", "error": str(e)}
