"""
Utilities for normalizing ontology entity labels.

Specifically targets Role labels to ensure consistent matching and creation.

Policy:
- Canonical Role labels include the word "Role" as a singular suffix, e.g.,
  "Public Official Role", "Client Representative Role".
- For matching and comparisons, we normalize by removing generic suffixes like
  "role"/"roles" and determiners, lowercasing, trimming whitespace, and collapsing spaces.
"""
from __future__ import annotations

import re


_ROLE_SUFFIX_RE = re.compile(r"\broles?\b\s*$", re.IGNORECASE)
_ARTICLES_RE = re.compile(r"\b(the|a|an)\b", re.IGNORECASE)
_SEPARATORS_RE = re.compile(r"[\-_]+")


def normalize_role_label(label: str) -> str:
    """Return a normalized key for role-label comparisons.

    Steps:
    - lower-case
    - strip leading/trailing whitespace
    - remove trailing 'role'/'roles'
    - remove articles (the, a, an)
    - replace separators ("-", "_") with space
    - collapse multiple spaces
    - very light singularization: drop trailing 's' for words > 3 chars (heuristic)
    """
    if not label:
        return ""
    s = str(label)
    s = _SEPARATORS_RE.sub(" ", s)
    s = _ROLE_SUFFIX_RE.sub("", s)
    s = _ARTICLES_RE.sub(" ", s)
    s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()

    # crude singularization for the final token only; avoids stemming complexities
    parts = s.split(" ")
    if parts:
        last = parts[-1]
        if len(last) > 3 and last.endswith("s"):
            parts[-1] = last[:-1]
        s = " ".join(parts)
    return s


def ensure_role_suffix(label: str) -> str:
    """Ensure the human-facing label ends with the singular word 'Role'.

    Examples:
    - "Public Official" -> "Public Official Role"
    - "Public Official Roles" -> "Public Official Role"
    - "Public Official Role" -> (unchanged)
    """
    if not label:
        return label
    # If already ends with 'Role' (case-insensitive), normalize to proper case
    if _ROLE_SUFFIX_RE.search(label) or label.strip().lower().endswith(" role"):
        base = _ROLE_SUFFIX_RE.sub("", label).rstrip()
        if base.lower().endswith(" role"):
            base = base[:-5].rstrip()
        return f"{base} Role"
    return f"{label.strip()} Role"


def strip_role_suffix(label: str) -> str:
    """Remove trailing 'Role'/'Roles' from a label for display/canonicalization.

    Examples:
    - "Electrical Engineer Role" -> "Electrical Engineer"
    - "Public Official Roles" -> "Public Official"
    - "Public Official" -> (unchanged)
    """
    if not label:
        return label
    base = _ROLE_SUFFIX_RE.sub("", str(label)).rstrip()
    # Also handle a trailing ' role' variant
    if base.lower().endswith(" role"):
        base = base[:-5].rstrip()
    return base


__all__ = ["normalize_role_label", "ensure_role_suffix", "strip_role_suffix"]

def ensure_no_role_suffix(label: str) -> str:
    """Ensure the human-facing label does NOT end with 'Role'/'Roles'.

    Examples:
    - "Public Official Role" -> "Public Official"
    - "Public Official Roles" -> "Public Official"
    - "Public Official" -> (unchanged)
    """
    if not label:
        return label
    base = _ROLE_SUFFIX_RE.sub("", label).rstrip()
    if base.lower().endswith(" role"):
        base = base[:-5].rstrip()
    return base

__all__.append("ensure_no_role_suffix")

def make_role_uri_fragment(label: str) -> str:
    """Create a URI fragment for a Role class with 'Role' suffix in CamelCase.

    Example: "electrical engineer" -> "ElectricalEngineerRole"
    """
    if not label:
        return "CustomRole"
    # remove role suffix first
    base = strip_role_suffix(label)
    parts = re.split(r"[^A-Za-z0-9]+", base)
    parts = [p for p in parts if p]
    if not parts:
        return "CustomRole"
    camel = parts[0].capitalize() + "".join(p.capitalize() for p in parts[1:])
    # ensure starts with a letter
    if not camel[0].isalpha():
        camel = "X" + camel
    return f"{camel}Role"

__all__.append("make_role_uri_fragment")
