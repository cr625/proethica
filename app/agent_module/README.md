# Agent Module for ProEthica

This module provides a modular agent implementation that can be integrated with Flask-based applications. It includes support for user authentication to restrict agent access to authenticated users.

## Features

- **Modular Design**: Interfaces for each component allow easy customization and testing
- **Authentication Support**: Integrates with Flask-Login for user authentication
- **Session Management**: Manages conversation state across user sessions
- **API Endpoints**: Complete set of RESTful endpoints for agent interactions
- **Configurable**: Can be configured to require or disable authentication

## Authentication Implementation

The agent module supports two authentication modes:

1. **Authentication Required** (default): All agent routes require user authentication via Flask-Login
2. **Authentication Disabled**: All agent routes are accessible without authentication

### Using with Authentication

The default implementation requires users to be authenticated to access any agent route. 
This is implemented using the `FlaskLoginAuthAdapter` class, which wraps Flask-Login's 
`login_required` decorator.

```python
from app.agent_module import create_proethica_agent_blueprint

# Create agent blueprint with authentication
agent_bp = create_proethica_agent_blueprint(
    config={
        'require_auth': True,  # Authentication is required (default)
        'api_key': os.environ.get('ANTHROPIC_API_KEY'),
        'use_claude': app.config.get('USE_CLAUDE', True)
    },
    url_prefix='/agent'
)
```

### Using without Authentication

For development or testing purposes, authentication can be disabled:

```python
from app.agent_module import create_proethica_agent_blueprint

# Create agent blueprint without authentication
agent_bp = create_proethica_agent_blueprint(
    config={
        'require_auth': False,  # Authentication is NOT required
        'api_key': os.environ.get('ANTHROPIC_API_KEY'),
        'use_claude': app.config.get('USE_CLAUDE', True)
    },
    url_prefix='/agent'
)
```

## Testing Authentication

The module includes unit tests for both authentication modes. These tests use mock implementations
of the interfaces to avoid dependencies on external services.

To run the tests:

```bash
python -m pytest tests/test_agent_module.py -v
```

## API Endpoints

The module provides the following API endpoints:

- `GET /agent/`: Main agent interface (requires authentication if enabled)
- `POST /agent/api/message`: Send a message to the agent
- `GET /agent/api/suggestions`: Get suggested prompts
- `POST /agent/api/reset`: Reset the conversation
- `GET /agent/api/guidelines`: Get guidelines for a specific source
- `GET /agent/api/current-user`: Get information about the current user

## Custom Implementation

The module is designed to be customizable. You can implement your own versions of the interfaces
and create a custom blueprint:

```python
from app.agent_module import create_agent_blueprint, AuthInterface

# Create a custom auth implementation
class CustomAuthProvider(AuthInterface):
    # Implementation here...

# Create blueprint with custom components
agent_bp = create_agent_blueprint(
    source_interface=my_source_interface,
    context_provider=my_context_provider,
    llm_interface=my_llm_interface,
    auth_interface=CustomAuthProvider(),
    require_auth=True
)
