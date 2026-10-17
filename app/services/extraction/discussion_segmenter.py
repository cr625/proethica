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
from app.utils.llm_utils import text_from_message

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

# Bumped whenever the segmentation rules change, so a cached segmentation computed under the old
# rules (doc_metadata['discussion_segmentation']) is recomputed instead of reused.
SEGMENTATION_VERSION = 2

# Sentence-level present-case cues inside a RECAP paragraph (case-8 review, lesson L3). NSPE
# recap paragraphs often close by turning to the present case ("We note a direct parallel between
# the 1984 case and the facts under consideration."); labeling the whole paragraph recap removed
# those sentences from the extractors, and with them the only mentions of II.1.a and BER Case
# 67-10 in case 8. A recap paragraph is split at the first sentence (after its opening sentence)
# that carries one of these cues; that sentence and the rest of the paragraph are present-case
# text. Phrases only; the present-case engineer letters are supplied per case (present_actors).
_PRESENT_TAIL_CUE = re.compile(
    r"\bwe (?:note|observe|find|conclude|believe|think|see no|do not (?:see|find|believe))\b"
    r"|\b(?:in|by) contrast\b"
    r"|\bturning to\b"
    r"|\bthe (?:present|instant) (?:case|matter|situation|facts)\b"
    r"|\bin the (?:present|instant) (?:case|matter|situation)\b"
    r"|\bthe facts (?:under consideration|before (?:us|the board)|at hand|now before)\b"
    r"|\bthe case (?:at hand|before (?:us|the board))\b"
    r"|\bhere,",
    re.IGNORECASE,
)

# Sentence boundary: terminal punctuation, whitespace, then an upper-case letter, a quote mark or
# a parenthesis. A period followed by a digit ("Case No. 67-10") or a lower-case letter does not
# split, so citation forms and abbreviations stay whole.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(“])")

# Concept types whose discussion-pass extractor receives the FULL discussion rather than the
# segmented present-case text. The resources pass lists the codes and precedents the case cites,
# and the recap paragraphs are where the cited precedents and their code sections are named
# (case 8: II.1.a and BER Case 67-10 appeared only there), so segmentation starves it.
SEGMENTATION_EXEMPT_CONCEPTS = frozenset({"resources"})


def section_text_for_concept(sections: dict, section_type: str, concept_type: str) -> str:
    """The text a concept's extractor receives for a section: the segmented present-case
    discussion for most concepts, the FULL discussion for the segmentation-exempt ones
    (SEGMENTATION_EXEMPT_CONCEPTS), and the section as stored otherwise. ``sections`` is the
    dict pipeline_tasks.get_case_sections returns."""
    if (section_type or "").lower() == "discussion" and (concept_type or "").lower() in SEGMENTATION_EXEMPT_CONCEPTS:
        return sections.get("discussion_full") or sections.get("discussion") or ""
    return sections.get(section_type) or ""


def _actor_cues(present_actors) -> List[re.Pattern]:
    return [re.compile(r"\b" + re.escape(str(a).strip()) + r"\b", re.IGNORECASE)
            for a in (present_actors or ()) if str(a).strip()]


def _split_recap_tail(text: str, actor_cues: List[re.Pattern]) -> tuple:
    """Split a recap paragraph into (recap head, present-case tail). The opening sentence always
    stays recap (a recap paragraph opens with the precedent). An actor cue is used for a paragraph
    only when the opening sentence does not itself name that actor: when the cited precedent shares
    the present case's engineer letter (case 60 and BER Case 19-3 both lead with Engineer A), the
    letter cannot tell the two apart and the phrase cues alone decide."""
    sentences = _SENTENCE_SPLIT.split(text)
    if len(sentences) < 2:
        return text, ""
    head = sentences[0]
    usable = [c for c in actor_cues if not c.search(head)]
    for i in range(1, len(sentences)):
        s = sentences[i]
        if _PRESENT_TAIL_CUE.search(s) or any(c.search(s) for c in usable):
            return " ".join(sentences[:i]).strip(), " ".join(sentences[i:]).strip()
    return text, ""


@dataclass
class Paragraph:
    index: int
    text: str
    has_link: bool = False
    cited_cases: List[str] = field(default_factory=list)
    label: str = ""  # 'present' | 'recap' (assigned by the classifier)
    present_tail: str = ""  # for a recap paragraph: its trailing present-case sentences, if any


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


def _load_segmenter_template():
    """Load the editable 'discussion_segmenter' prompt template (prompt editor -> Shared prompts ->
    Discussion segmenter). A separate function so a test can inject a stub without a DB / app context.
    Raises (no fallback) if unseeded; _llm_labels catches and returns None (the segmenter then keeps the
    full discussion, its documented under-segment fail-safe)."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'discussion_segmenter')
    if tmpl is None:
        raise RuntimeError(
            "No 'discussion_segmenter' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_discussion_segmenter_template.py")
    return tmpl


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
        # The segmentation prompt is an editable DB template (prompt editor -> Shared prompts ->
        # Discussion segmenter). Render it with the numbered paragraph list.
        prompt = _load_segmenter_template().render(numbered=numbered)
        from app.utils.llm_utils import direct_call_params
        text = client.messages.create(
            **direct_call_params(ModelConfig.get_claude_model("default"),
                                 max_tokens=1024),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = text_from_message(text)
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


def segment_discussion(discussion_html: str, present_actors=None) -> SegmentationResult:
    """Segment a discussion (HTML) into present-case text + precedent recaps. See module docstring.

    ``present_actors``: the present case's actor names ("Engineer L", ...), used as sentence-level
    cues when a recap paragraph turns to the present case (see _split_recap_tail)."""
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

    # A recap paragraph that turns to the present case in its trailing sentences keeps those
    # sentences in the present-case text (in document order); only its head is a recap span.
    actor_cues = _actor_cues(present_actors)
    present_parts: List[str] = []
    recaps: List[dict] = []
    for p in paras:
        if p.label == "present":
            present_parts.append(p.text)
            continue
        head, tail = _split_recap_tail(p.text, actor_cues)
        p.present_tail = tail
        recaps.append({"cited_case": (p.cited_cases[0] if p.cited_cases else None), "text": head})
        if tail:
            present_parts.append(tail)
    present_text = "\n\n".join(present_parts).strip()

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
