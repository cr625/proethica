"""
Debug routes for development - main blueprint module.
This module imports and re-exports the debug blueprint from debug_routes.py.
"""

# Import the debug blueprint from the actual implementation
from app.routes.debug_routes import debug_bp

# Re-export the blueprint with the same name for compatibility
# with the app/__init__.py imports
