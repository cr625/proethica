"""Static front-end integrity checks for the view layer.

Pure-pytest (no running server) so they run in the default suite and gate every
change. They formalize the ad-hoc checks used during the routes/templates/CSS/JS
modularization and catch the bug classes that slipped through before:

  * a template that fails to Jinja-compile (bad syntax / unknown filter);
  * a url_for('static', ...) link to a css/js file that does not exist
    (e.g. a broken <link>/<script src> after externalization);
  * Jinja that leaked into an externalized static .css/.js;
  * a {% block %} a template defines that NO ancestor renders, so its content
    is silently dropped (the dead {% block head %} CSS bug found 2026-06-20).

The companion Playwright suite in tests/e2e/ covers live rendering + behavior
against a running server; this module is the fast, server-free guard.
"""
import os
import re

import pytest

from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TPL_ROOT = os.path.join(HERE, "app", "templates")
STATIC_ROOT = os.path.join(HERE, "app", "static")

JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
STATIC_REF = re.compile(
    r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]\s*\)")
EXTENDS = re.compile(r"\{%-?\s*extends\s*['\"]([^'\"]+)['\"]")
BLOCKDEF = re.compile(r"\{%-?\s*block\s+(\w+)")

# Templates that intentionally (for now) define a block no ancestor renders, so
# the block content is dropped. These are the dormant dead-CSS templates left for
# a separate "is this subsystem still live?" decision (2026-06-20). New entries
# must NOT be added without justification -- the check exists to prevent them.
KNOWN_DROPPED_BLOCKS = {
    "experiment/index.html",
    "experiment/case_comparison.html",
    "experiment/conclusion_comparison.html",
    "experiment/conclusion_results.html",
    "experiment/conclusion_setup.html",
    "experiment/double_blind_comparison.html",
    "experiment/evaluate_prediction.html",
    "prompt_builder/index.html",
    "prompt_builder/registry.html",
    "prompt_builder/domain.html",
    "reasoning_inspector.html",
    "lineage_print.html",
}


def _all_templates():
    out = []
    for dp, _, fs in os.walk(TPL_ROOT):
        for f in fs:
            if f.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dp, f), TPL_ROOT))
    return sorted(out)


def _read(rel):
    with open(os.path.join(TPL_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def app():
    return create_app()


def test_all_templates_compile(app):
    """Every template parses in the real app Jinja env (custom filters loaded)."""
    bad = []
    with app.app_context():
        for t in _all_templates():
            try:
                app.jinja_env.get_template(t)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{t}: {exc}")
    assert not bad, "templates fail to compile:\n" + "\n".join(bad)


def test_static_asset_links_exist():
    """Every static url_for('static', filename='css/..'|'js/..') points at a real file."""
    missing = []
    for t in _all_templates():
        for fn in STATIC_REF.findall(_read(t)):
            if "{{" in fn or "{%" in fn:
                continue  # dynamically-computed filename, cannot resolve statically
            if not os.path.exists(os.path.join(STATIC_ROOT, fn)):
                missing.append(f"{t} -> static/{fn}")
    assert not missing, "templates reference missing static assets:\n" + "\n".join(missing)


def test_no_jinja_in_externalized_css():
    """Externalized .css must contain no Jinja (the byte-faithful invariant).

    Scoped to CSS: a static .js can legitimately contain `{{ }}` as string
    content (e.g. prompt-editor.js inserts Jinja-syntax text into prompts), so a
    blanket no-Jinja rule false-positives on JS. In CSS, `{{ }}`/`{% %}` is never
    legitimate -- it means an externalization left unprocessed Jinja behind.
    """
    leaks = []
    root = os.path.join(STATIC_ROOT, "css")
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".css"):
                p = os.path.join(dp, f)
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    if JINJA.search(fh.read()):
                        leaks.append(os.path.relpath(p, STATIC_ROOT))
    assert not leaks, "Jinja found in externalized CSS:\n" + "\n".join(leaks)


def _renderable_block_names(rel, _cache):
    """Block names that render for `rel` = the union defined across its extends chain.

    Walks parent -> grandparent -> ... A leaf block whose name is not in this set
    (and `rel` itself extends something) is dropped by Jinja at render time.
    """
    if rel in _cache:
        return _cache[rel]
    names = set()
    seen = set()
    cur = rel
    while True:
        if cur in seen or not os.path.exists(os.path.join(TPL_ROOT, cur)):
            break
        seen.add(cur)
        txt = _read(cur)
        if cur != rel:  # own blocks of an ancestor are renderable
            names.update(BLOCKDEF.findall(txt))
        m = EXTENDS.search(txt)
        if not m:
            break
        cur = m.group(1)
    _cache[rel] = names
    return names


def _top_level_blocks(txt):
    """Block names defined at nesting depth 0 (direct overrides of the parent).

    A block nested inside another block renders as part of its container, so only
    top-level blocks must match a parent block to be rendered.
    """
    top = set()
    depth = 0
    for m in re.finditer(r"\{%-?\s*(block\s+(\w+)|endblock)\b", txt):
        if m.group(1).startswith("block"):
            if depth == 0:
                top.add(m.group(2))
            depth += 1
        else:
            depth -= 1
    return top


def test_block_overrides_are_rendered():
    """No template defines a top-level {% block %} that no ancestor renders."""
    cache = {}
    dropped = []
    for t in _all_templates():
        txt = _read(t)
        if not EXTENDS.search(txt):
            continue  # root/standalone template: all its blocks render
        renderable = _renderable_block_names(t, cache)
        for blk in _top_level_blocks(txt):
            if blk not in renderable:
                dropped.append(f"{t}: {{% block {blk} %}}")
    offenders = sorted({d.split(":")[0] for d in dropped})
    new = [o for o in offenders if o not in KNOWN_DROPPED_BLOCKS]
    assert not new, (
        "templates define blocks no ancestor renders (content silently dropped):\n"
        + "\n".join(d for d in dropped if d.split(":")[0] in new)
    )
