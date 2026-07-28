from flask import Blueprint, send_from_directory, abort, current_app, render_template
from pathlib import Path

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Path to MkDocs build output
DOCS_DIR = Path(__file__).parent.parent.parent / 'site'

# Documentation paths withheld during the anonymous review window. The
# publications page and the conference PDFs name the authors and their
# institution. mkdocs.yml already excludes these from the build, so this guard
# is a second line of defence: it keeps the paths unreachable if a stale build
# from before the exclusion survives on a deployment target.
ANONYMOUS_WITHHELD_PREFIXES = ('papers',)


@docs_bp.route('/')
@docs_bp.route('/<path:path>')
def index(path='index.html'):
    """Serve documentation static files"""
    if not DOCS_DIR.exists():
        abort(404, description="Documentation not built. Run 'mkdocs build' first.")

    if current_app.config.get('ANONYMOUS_MODE', True):
        normalized = path.lstrip('/')
        if normalized.startswith(ANONYMOUS_WITHHELD_PREFIXES):
            return render_template('withheld.html'), 404

    # Handle clean URLs
    if path and not any(path.endswith(ext) for ext in ['.html', '.css', '.js', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ico', '.json', '.xml', '.pdf']):
        # Try path/index.html for clean URLs
        test_path = DOCS_DIR / path / 'index.html'
        if test_path.exists():
            path = f"{path}/index.html"
        else:
            path = f"{path}.html"

    if not path:
        path = 'index.html'

    try:
        return send_from_directory(DOCS_DIR, path)
    except FileNotFoundError:
        abort(404)
