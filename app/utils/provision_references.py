"""Deterministic parsing of the board-stated NSPE Code references section.

Every NSPE BER case document carries a references section listing the Code
provisions the board cited: per provision, the section code, the verbatim
provision text, and the subject-reference labels. Until 2026-07-09 this
section was displayed as raw HTML and never parsed, so the per-case
provision set existed only through downstream regex extraction, which
diverged (case 7's case_precedent_features lacked I.1 while both the
references section and the Step-4 extraction carried it).

parse_references_html handles the structured Drupal markup of the scraped
cases (code in a field--name-name heading, text in field--name-description,
subject links under Subject Reference); parse_references_text is the
fallback for text-only content. harmonized_provision_codes unions the
board-stated set with the Step-4 analysis-found set, both normalized -- the
per-case provision vocabulary that case_precedent_features.provisions_cited
carries for the similarity system.
"""
import logging
import re
from typing import List, Optional

from app.utils.provision_codes import normalize_provision_code

logger = logging.getLogger(__name__)

_CODE_TOKEN = re.compile(r'^(Preamble|[IVX]+(?:\.\d+)?(?:\.[a-z])?)\.?$', re.IGNORECASE)
_TEXT_CODE = re.compile(r'\b([IVX]+(?:\.\d+)?(?:\.[a-z])?)\.\s+', re.IGNORECASE)


def parse_references_html(html: str) -> List[dict]:
    """Parse the references section HTML into
    [{code, code_raw, text, subjects}]. Returns [] when nothing parses."""
    if not html:
        return []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for name_div in soup.select('.field--name-name'):
        raw = name_div.get_text(strip=True)
        if not _CODE_TOKEN.match(raw):
            continue
        code = normalize_provision_code(raw)
        if code is None:
            continue
        item = name_div.find_parent(class_='field__item')
        text = ''
        subjects: List[str] = []
        if item is not None:
            desc = item.select_one('.field--name-description')
            if desc is not None:
                text = desc.get_text(' ', strip=True)
            subjects = [a.get_text(strip=True) for a in item.select('a')
                        if a.get_text(strip=True)]
        out.append({'code': code, 'code_raw': raw, 'text': text,
                    'subjects': subjects})
    return out


def parse_references_text(text: str) -> List[dict]:
    """Fallback parser over plain references text. Splits on provision-code
    tokens; the segment after each code (up to the next code) is its text,
    with a trailing 'Subject Reference ...' block separated off."""
    if not text:
        return []
    out = []
    matches = list(_TEXT_CODE.finditer(text))
    for i, m in enumerate(matches):
        code = normalize_provision_code(m.group(1))
        if code is None:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[m.end():end].strip()
        subjects: List[str] = []
        if 'Subject Reference' in segment:
            segment, _, subj_part = segment.partition('Subject Reference')
            subjects = [subj_part.strip()] if subj_part.strip() else []
        out.append({'code': code, 'code_raw': m.group(1), 'text': segment.strip(),
                    'subjects': subjects})
    return out


def parse_provision_references(doc_metadata: dict) -> List[dict]:
    """Parse a case's references section (HTML preferred, text fallback)."""
    sections = (doc_metadata or {}).get('sections_dual', {}) or {}
    ref = sections.get('references', {}) or {}
    if isinstance(ref, dict):
        parsed = parse_references_html(ref.get('html', ''))
        if parsed:
            return parsed
        return parse_references_text(ref.get('text', ''))
    return parse_references_text(str(ref))


def harmonized_provision_codes(case_id: int,
                               provision_references: Optional[List[dict]] = None) -> List[str]:
    """The harmonized per-case provision set: board-stated (references
    section) UNION analysis-found (Step-4 code_provision_reference rows),
    normalized. This is the derivation for
    case_precedent_features.provisions_cited."""
    from app.models import Document, TemporaryRDFStorage
    codes = set()
    if provision_references is None:
        doc = Document.query.get(case_id)
        provision_references = (doc.doc_metadata or {}).get('provision_references') \
            if doc else None
        if provision_references is None:
            provision_references = parse_provision_references(doc.doc_metadata or {}) if doc else []
    codes.update(p['code'] for p in provision_references if p.get('code'))

    rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='code_provision_reference').all()
    for r in rows:
        c = normalize_provision_code(r.entity_label)
        if c:
            codes.add(c)
    return sorted(codes)


def update_provisions_cited(case_id: int) -> List[str]:
    """Write the harmonized set to case_precedent_features.provisions_cited
    (creating no row if none exists; features rows are made at ingestion)."""
    from app.models import db
    from sqlalchemy import text as sql_text
    codes = harmonized_provision_codes(case_id)
    db.session.execute(
        sql_text("UPDATE case_precedent_features SET provisions_cited = :codes "
                 "WHERE case_id = :cid"),
        {'codes': codes, 'cid': case_id})
    db.session.commit()
    return codes
