"""
Characterization tests for app.services.document_text_extractors.

These lock the text-extraction behavior moved out of EmbeddingService (plan:
.claude/plans/services-modularization.md, Phase 2). TXT/HTML and the dispatcher
need no network, model, or DB. PDF/DOCX/URL paths require optional parsers or a
live request and are exercised elsewhere.
"""

from __future__ import annotations

import pytest

from app.services import document_text_extractors as dte


def test_extract_from_txt_roundtrip(tmp_path):
    p = tmp_path / "doc.txt"
    content = "Line one\nLine two\n"
    p.write_text(content, encoding="utf-8")
    assert dte.extract_from_txt(str(p)) == content


def test_extract_from_html_strips_script_and_style(tmp_path):
    p = tmp_path / "doc.html"
    p.write_text(
        "<html><head><style>.x{color:red}</style></head>"
        "<body><script>evil()</script><h1>Title</h1>"
        "<p>Hello world</p></body></html>",
        encoding="utf-8",
    )
    out = dte.extract_from_html(str(p))
    assert "evil()" not in out
    assert "color:red" not in out
    assert "Title" in out
    assert "Hello world" in out


def test_extract_text_dispatches_by_type(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("hello", encoding="utf-8")
    assert dte.extract_text(str(p), "txt") == "hello"
    assert dte.extract_text(str(p), "TXT") == "hello"  # case-insensitive
    assert dte.extract_text(str(p), "text") == "hello"


def test_extract_text_unsupported_type_raises(tmp_path):
    p = tmp_path / "doc.bin"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        dte.extract_text(str(p), "xyz")


def test_embedding_service_wrapper_delegates(tmp_path):
    """EmbeddingService._extract_text is a thin instance-method wrapper that
    does not touch instance state, so it delegates correctly even with a dummy
    self (avoids loading the embedding model)."""
    from app.services.embedding.embedding_service import EmbeddingService

    p = tmp_path / "doc.txt"
    p.write_text("delegated", encoding="utf-8")
    assert EmbeddingService._extract_text(object(), str(p), "txt") == "delegated"
