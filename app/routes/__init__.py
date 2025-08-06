# Import blueprints to make them available when importing from app.routes
from app.routes.scenarios import scenarios_bp
from app.routes.agent import agent_bp
from app.routes.auth import auth_bp
from app.routes.entities import entities_bp
from app.routes.worlds import worlds_bp
from app.routes.mcp_api import mcp_api_bp
from app.routes.documents import documents_bp
from app.routes.experiment import experiment_bp
from app.routes.guidelines import guidelines_bp
