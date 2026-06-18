"""Split a case discussion into present-case analysis vs cited-precedent recaps.

NSPE Board of Ethical Review opinions recap the precedents they cite ("In BER Case 19-3,
Engineer A chairs a boiler code committee while Engineer B ...") and then analyze the present
case. Those recaps name the precedent's OWN actors and scenarios. When the entity extractors read
them, precedent content contaminates the present-case ontology, and the worst form -- a precedent
that shares the present case's engineer letter (case 60 = Engineer A; the cited BER Case 19-3 also
leads with "Engineer A") -- cannot be separated by any downstream label or quote filter, because
the actor identifier collides.

The reliable, general signal is structural, and it is already in the data: every "BER Case NN-N"
citation is an ``<a href=".../board-ethical-review-cases/...">`` link in the stored discussion
HTML, and NSPE convention is to recap precedents first, then turn to the present case. This module
demarcates the precedent-recap paragraphs once per case so the extractors only see present-case
text. It is a HYBRID classifier:

* deterministic when the structure is unambiguous -- precedent links exist and all of them precede
  a high-precision present-case cue ("turning to the facts of the present situation", "in the
  present case", ...). The recap region is then ``[first linked paragraph, cue)``.
* an LLM paragraph-classification fallback otherwise (links but no cue, e.g. case 19; or a link
  after the cue, where a present-case paragraph cites a precedent and the boundary is unclear).

A discussion with no precedent links needs no segmentation and is returned unchanged.

Fail-safe: the present-case text is reconstructed from whole paragraphs; if it would come back
empty or implausibly short, the full discussion is returned instead (we would rather under-segment
and let the thin marker safety-net catch a stray, than ever drop present-case content).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# A high-precision present-case transition cue. Kept deliberately small and unambiguous: when one
# of these is found and all precedent links precede it, the deterministic split is trusted. Weaker
# openers ("Here, ...") are intentionally excluded -- they route to the LLM fallback instead.
_PRESENT_CASE_CUE = re.compile(
    r"\bturning to (?:the )?(?:facts of (?:the )?)?present\b"
    r"|\bin the (?:present|instant) (?:case|matter|situation)\b"
    r"|\bthe present (?:case|matter|situation)\b"
    r"|\bin the case (?:at hand|before (?:us|the board))\b",
    re.IGNORECASE,
)

# NSPE BER citation, in link text or plain text: "BER Case 19-3", "Case 04-11", "BER 07-6".
_CITATION_RE = re.compile(r"\b(?:BER\s+)?(?:Case\s+)?(\d{2}-\d{1,2})\b")
_PRECEDENT_HREF = "board-ethical-review-cases"

# Reconstruction fail-safe: if the present-case text falls below this fraction of the original
# discussion length, abandon the split and use the full discussion.
_MIN_PRESENT_FRACTION = 0.20


@dataclass
class Paragraph:
    index: int
    text: str
    has_link: bool = False
    cited_cases: List[str] = field(default_factory=list)
    label: str = ""  # 'present' | 'recap' (assigned by the classifier)


@dataclass
class SegmentationResult:
    present_case_text: str
    precedent_recaps: List[dict]          # [{'cited_case': '19-3'|None, 'text': ...}]
    method: str                           # 'none' | 'deterministic' | 'llm' | 'fallback_full'
    paragraphs: List[Paragraph] = field(default_factory=list)


def _parse_paragraphs(discussion_html: str) -> List[Paragraph]:
    """Parse the discussion HTML into paragraphs, flagging precedent citation links."""
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover - bs4 is a project dependency
        return _parse_paragraphs_regex(discussion_html)

    soup = BeautifulSoup(discussion_html, "html.parser")
    blocks = soup.find_all("p")
    # Some sources wrap the whole discussion without <p>; treat the root as one block then.
    if not blocks:
        blocks = [soup]

    paras: List[Paragraph] = []
    for i, block in enumerate(blocks):
        text = block.get_text(" ", strip=True)
        if not text:
            continue
        links = [a for a in block.find_all("a", href=True)
                 if _PRECEDENT_HREF in a["href"]]
        cited = []
        for a in links:
            m = _CITATION_RE.search(a.get_text(" ", strip=True))
            if m:
                cited.append(m.group(1))
        paras.append(Paragraph(index=len(paras), text=text,
                               has_link=bool(links), cited_cases=cited))
    return paras


def _parse_paragraphs_regex(discussion_html: str) -> List[Paragraph]:
    """Fallback parser if bs4 is unavailable: split on </p>, detect links by href substring."""
    paras: List[Paragraph] = []
    for chunk in re.split(r"</p\s*>", discussion_html, flags=re.IGNORECASE):
        text = re.sub(r"<[^>]+>", " ", chunk)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        has_link = (_PRECEDENT_HREF in chunk)
        cited = [m.group(1) for m in _CITATION_RE.finditer(text)] if has_link else []
        paras.append(Paragraph(index=len(paras), text=text,
                               has_link=has_link, cited_cases=cited))
    return paras


def _deterministic_labels(paras: List[Paragraph]) -> Optional[List[str]]:
    """Return per-paragraph labels if the structure is unambiguous, else None.

    Confident iff at least one precedent link exists, a present-case cue is found, and EVERY
    linked paragraph precedes the cue (the clean recap-then-present shape). The recap region is
    then [first linked paragraph, cue)."""
    link_idxs = [p.index for p in paras if p.has_link]
    if not link_idxs:
        return None  # caller handles the no-precedent case separately
    cue_idx = next((p.index for p in paras if _PRESENT_CASE_CUE.search(p.text)), None)
    if cue_idx is None or any(li >= cue_idx for li in link_idxs):
        return None  # ambiguous -> LLM fallback
    first_link = min(link_idxs)
    return ["recap" if first_link <= p.index < cue_idx else "present" for p in paras]


def _llm_labels(paras: List[Paragraph]) -> Optional[List[str]]:
    """Classify each paragraph present vs recap via one LLM call. None on any failure."""
    try:
        from app.utils.llm_utils import get_llm_client
        from model_config import ModelConfig
        client = get_llm_client()
        if client is None:
            return None
        numbered = "\n".join(
            f"[P{p.index}]{' (cites precedent)' if p.has_link else ''}: {p.text}"
            for p in paras
        )
        prompt = (
            "You are segmenting an NSPE Board of Ethical Review case discussion. Each paragraph "
            "is labeled [P#]; some are marked '(cites precedent)'. Classify EACH paragraph as:\n"
            "  RECAP    = it narrates the facts/actors/scenario of a CITED prior case (a precedent)\n"
            "  PRESENT  = it analyzes the case under review (this may legitimately cite a "
            "precedent to APPLY its holding -- that is still PRESENT)\n\n"
            "A precedent's actors (its own 'Engineer A', 'Engineer B') belong to RECAP paragraphs. "
            "Return ONLY a JSON object mapping each paragraph number to \"recap\" or \"present\", "
            "e.g. {\"0\": \"recap\", \"1\": \"present\"}.\n\n" + numbered
        )
        text = client.messages.create(
            model=ModelConfig.get_claude_model("powerful"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = text.content[0].text if hasattr(text, "content") else str(text)
        import json
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        mapping = json.loads(m.group(0))
        labels = []
        for p in paras:
            v = str(mapping.get(str(p.index), "present")).lower()
            labels.append("recap" if v.startswith("recap") else "present")
        return labels
    except Exception:
        logger.debug("LLM discussion segmentation failed", exc_info=True)
        return None


def segment_discussion(discussion_html: str) -> SegmentationResult:
    """Segment a discussion (HTML) into present-case text + precedent recaps. See module docstring."""
    if not discussion_html or not discussion_html.strip():
        return SegmentationResult(present_case_text="", precedent_recaps=[], method="none")

    paras = _parse_paragraphs(discussion_html)
    full_text = "\n\n".join(p.text for p in paras)

    if not paras:
        return SegmentationResult(present_case_text=full_text, precedent_recaps=[], method="none")

    # No precedent citations -> nothing to segment.
    if not any(p.has_link for p in paras):
        for p in paras:
            p.label = "present"
        return SegmentationResult(present_case_text=full_text, precedent_recaps=[],
                                  method="none", paragraphs=paras)

    labels = _deterministic_labels(paras)
    method = "deterministic"
    if labels is None:
        labels = _llm_labels(paras)
        method = "llm"
    if labels is None:
        # LLM unavailable/failed and structure ambiguous: do not guess. Keep the full
        # discussion (under-segment) so we never drop present-case content.
        for p in paras:
            p.label = "present"
        logger.info("discussion segmentation ambiguous and LLM unavailable; using full discussion")
        return SegmentationResult(present_case_text=full_text, precedent_recaps=[],
                                  method="fallback_full", paragraphs=paras)

    for p, lab in zip(paras, labels):
        p.label = lab

    present_text = "\n\n".join(p.text for p in paras if p.label == "present").strip()
    recaps = [{"cited_case": (p.cited_cases[0] if p.cited_cases else None), "text": p.text}
              for p in paras if p.label == "recap"]

    # Fail-safe: never return implausibly little present-case text.
    if not present_text or len(present_text) < _MIN_PRESENT_FRACTION * max(len(full_text), 1):
        logger.info("discussion segmentation removed too much (method=%s); using full discussion",
                    method)
        for p in paras:
            p.label = "present"
        return SegmentationResult(present_case_text=full_text, precedent_recaps=[],
                                  method="fallback_full", paragraphs=paras)

    return SegmentationResult(present_case_text=present_text, precedent_recaps=recaps,
                              method=method, paragraphs=paras)
