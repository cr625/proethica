"""
Tools routes for ProEthica utilities and reference pages.
"""

from flask import Blueprint, redirect

tools_bp = Blueprint('tools', __name__)


@tools_bp.route('/tools/references')
def references():
    """Academic references moved to the documentation site.

    The page content lives at docs/references.md (rendered at /docs/references/),
    where the citations mirror the verified definition-source records carried by
    the ontology classes. This redirect keeps existing public links working;
    fragment anchors (e.g. #nine-component) are preserved by the browser.
    """
    return redirect('/docs/references/', code=301)
