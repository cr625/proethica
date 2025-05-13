"""
Run the application in debug mode for GitHub Codespaces.
"""

from flask import Flask
from app.routes.debug_routes import debug_bp
from app.template_filters import init_app as init_filters
from app.models import db

# Initialize Flask application
app = Flask(__name__)

# Configure the app
app.config.from_object('app.config')
app.config['DEBUG'] = True

# Initialize database
db.init_app(app)

# Initialize template filters
init_filters(app)

# Register blueprints
app.register_blueprint(debug_bp, url_prefix='/debug')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3334, debug=True)
