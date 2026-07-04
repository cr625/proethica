"""Committed case-graph access.

The committed per-case ontology TTL under the OntServe ontologies directory is
the authoritative record of an extracted case. This module is the single access
point for reading it from ProEthica view code: path resolution, existence check,
and a per-(path, mtime) parsed-graph cache shared by every consumer, so repeated
reads of the same case graph do not re-parse it.
"""

import logging
from pathlib import Path

import rdflib

from app.services.ontserve.ontserve_config import get_ontserve_base_path

logger = logging.getLogger(__name__)

_GRAPH_CACHE = {}


def case_ttl_path(case_id: int) -> Path:
    return get_ontserve_base_path() / "ontologies" / f"proethica-case-{case_id}.ttl"


def committed_case_exists(case_id: int) -> bool:
    """Whether the case has a committed ontology in OntServe.

    File existence is the gate signal: the TTL on the shared filesystem is the
    same artifact the popover lookups and the defeasibility view read.
    """
    return case_ttl_path(case_id).exists()


def load_case_graph(case_id: int) -> rdflib.Graph:
    path = case_ttl_path(case_id)
    if not path.exists():
        # A missing committed TTL is a genuine state (not every case is extracted),
        # surfaced to the caller rather than silently substituted.
        raise FileNotFoundError(f"No committed ontology for case {case_id}: {path}")
    # Cache the parsed graph per (path, mtime) so repeated reads of the same case
    # TTL do not re-parse it. Read-only use only. Stale mtimes for the same path
    # are dropped so re-commits do not accumulate dead graphs.
    key = (str(path), path.stat().st_mtime_ns)
    g = _GRAPH_CACHE.get(key)
    if g is None:
        for old in [k for k in _GRAPH_CACHE if k[0] == key[0]]:
            del _GRAPH_CACHE[old]
        g = rdflib.Graph()
        g.parse(str(path), format="turtle")
        _GRAPH_CACHE[key] = g
    return g
