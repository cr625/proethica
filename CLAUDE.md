# ProEthica Development Notes

## Startup Script Troubleshooting

### Port 5001 Check Issue
If the `start_proethica_updated.sh` script hangs at the "Checking if port 5001 is already in use..." step, it's likely due to an issue with the `lsof` command in the script. The fix involves:

1. Replacing the `lsof` command with `netstat` for checking port availability
2. Using `fuser` as a fallback for process termination when possible

This issue has been fixed in the current version of the script, which now uses a more reliable approach to check port availability.

## Database Configuration in Codespace Environment

When running in GitHub Codespaces, the PostgreSQL container uses port 5433 (instead of the standard 5432) and the password for the 'postgres' user should be set to 'PASS' to match the configuration in the `.env` file.

The `start_proethica_updated.sh` script handles this automatically by:
1. Detecting the Codespace environment
2. Running `fix_db_password.sh` to set the PostgreSQL password to 'PASS'
3. Updating the `.env` file with the appropriate DATABASE_URL

If you encounter database connection issues, you can manually run:
```bash
./fix_db_password.sh
```

### Database Password Configuration Notes

There are two environments where the application can run:
- **WSL environment**: Uses 'PASS' as the database password
- **Codespace environment**: Originally uses 'postgres' as the default password but needs 'PASS' to match configuration

When `start_proethica_updated.sh` runs, it:
1. Detects the environment (WSL or Codespace)
2. For Codespace: Executes `fix_db_password.sh` to ensure the PostgreSQL user's password is set to 'PASS'
3. Updates the `.env` file with the correct DATABASE_URL for the environment

If you see a "password authentication failed" error when running the application, it typically means there's a mismatch between:
- The actual password set on the PostgreSQL container (check with `docker exec -it postgres17-pgvector-codespace psql -U postgres -c "SELECT 1"`)
- The password in the DATABASE_URL in the `.env` file

The fix involves ensuring both match by running `./fix_db_password.sh` to set the container password to 'PASS'.

## Script Organization

The project's scripts are organized as follows:

- **Root Directory Scripts**: Only essential scripts directly referenced by the main launcher remain in the root directory:
  - `start_proethica_updated.sh` - The main launcher script
  - `auto_run.sh` - Called by the main launcher
  - `fix_db_password.sh` - Used for database configuration
  - `fix_mcp_client.py` - Used for updating MCP client to use JSON-RPC API

- **Archived Scripts in scripts/archive/**: All files not directly referenced by the main launcher have been moved to improve organization:
  - Shell scripts:
    - Environment setup scripts (e.g., `codespace_launcher.sh`, `start_codespace_env.sh`)
    - Process-specific scripts (e.g., `process_case_187.sh`, `process_example_case.sh`)
    - Server management scripts (e.g., `restart_server.sh`, `start_unified_ontology_server.sh`)
    - Test scripts (e.g., `test_guideline_api.sh`, `run_guideline_mcp_test.sh`)
  
  - Python files:
    - Test-related files (e.g., `test_case_analysis.py`, `test_mcp_jsonrpc_connection.py`)
    - Update scripts (e.g., `update_claude_models_in_mcp_server.py`, `update_guidelines_in_CLAUDE_md.py`)
    - Fix scripts (e.g., `fix_all_model_imports.py`, `fix_circular_import.py`, `fix_entity_triples_query.py`)
    - Other utility scripts that aren't directly referenced by the main launcher

If you need functionality from an archived script, either:
1. Reference it directly from `scripts/archive/` directory
2. Create a new script in the `scripts/` directory that provides the needed functionality

This organization helps maintain a cleaner root directory while preserving all script functionality.

## Application Structure Notes

The application follows a modular structure with Flask blueprints:
- Each entity type (roles, resources, conditions, characters, events, etc.) has its own blueprint in app/routes/
- The debug blueprint (debug_bp) is imported from debug_routes.py into app/routes/debug.py
- Model relationships rely on proper imports in app/models/__init__.py

### Blueprint URL Routing in Templates

Flask blueprints change how URL endpoints are referenced. When routes are moved from the main application to blueprints, the endpoint naming changes from simple function names to `blueprint_name.function_name`.

For example, with the application structured as:
```python
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')
```

Templates must reference the endpoint as:
```html
<a href="{{ url_for('index.index') }}">Home</a>
```
instead of the old style:
```html
<a href="{{ url_for('index') }}">Home</a>
```

#### Recent Fix for URL Routing Errors

A 500 Internal Server Error related to blueprint URL routing was fixed in the following files:
- `app/templates/guidelines.html`
- `app/templates/guideline_concepts_review.html`
- `app/templates/guideline_content.html`
- `app/routes/auth.py`

The error occurred because these files were still using non-blueprint style URL references (`url_for('index')`) instead of the blueprint-prefixed style (`url_for('index.index')`).

For detailed information on this fix, including the specific changes made and recommendations for preventing similar issues, see `docs/template_routing_fix.md`.

### Model Imports and Database Schema

The application uses SQLAlchemy for ORM with models defined in the app/models/ directory. Important models include:
- Ontology - Represents knowledge structures
- OntologyImport - Manages relationships between ontologies
- OntologyVersion - Tracks ontology versions
- EntityTriple - Stores RDF-like triples for entities
- Guideline - Stores engineering ethics guidelines for analysis

When adding new models or changing relationships, ensure that:
1. The model is properly defined with appropriate relationships
2. The model is imported in `app/models/__init__.py`
3. Any circular imports are resolved (usually by importing models after db is defined)

Common errors when models aren't properly imported include:
- "name 'ModelName' is not defined" in SQLAlchemy mapper initialization
- "Could not build url for endpoint" in templates that reference routes using undefined models

To fix model import issues, examine the error message to identify the missing model, then add the appropriate import to app/models/__init__.py.

## Debug Routes and Troubleshooting

The application includes a debug blueprint that provides development and troubleshooting functionality:
- Located in `app/routes/debug_routes.py`
- Imported and registered in `app/routes/debug.py`
- Mounted at `/debug` URL prefix

### Debug Status Endpoint

The `/debug/status` endpoint is designed to check various system components:
- MCP server connectivity
- Database connectivity
- Ontology and guidelines status

If you encounter a 500 Internal Server Error when accessing this endpoint, it may indicate issues with:
1. Connection to the MCP server (JSON-RPC endpoint)
2. Database connectivity issues
3. Missing dependencies or libraries
4. Template URL routing errors (e.g., incorrect blueprint names in `url_for()` calls)

#### Troubleshooting Debug Routes

If the `/debug/status` endpoint is failing with a 500 error, check the application logs for detailed error messages. Common issues include:

1. **URL Routing Errors**: If you see errors like `BuildError: Could not build url for endpoint 'main.index'`, update the template to use the correct blueprint name. For example, change `url_for('main.index')` to `url_for('index.index')`.

2. **MCP Server Connection**: The system now uses JSON-RPC exclusively for communicating with the MCP server instead of REST endpoints. You may see 404 errors for endpoints like `/api/guidelines/engineering-ethics` in the logs, but these are not critical if the JSON-RPC endpoint is working.

3. **API Keys**: If the MCP server logs show warnings about missing API keys (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), the server will fall back to using a simple embeddings client, which may limit some functionality.

To diagnose specific connection issues:
- Check MCP server logs in `logs/enhanced_ontology_server_*.log`
- Verify database connectivity using `psql` or the `/debug/healthcheck` endpoint
- Check Flask application logs for detailed error messages

To restore a backup of the debug routes if needed:
```bash
cp app/routes/debug_routes.py.bak app/routes/debug_routes.py
```

## MCP Integration for Guidelines

The MCP server provides enhanced ontology and guidelines functionality:
- Runs on port 5001 via JSON-RPC
- Requires the GuidelineAnalysisModule for concept extraction
- Uses Claude 3.7 Sonnet (claude-3-7-sonnet-20250219) for analysis

For full documentation on guidelines implementation, refer to:
- `guidelines_implementation_status.md` - Current status
- `mcp_integration_plan.md` - Integration architecture
- `README_GUIDELINES_TESTING.md` - Testing procedures

## Flask Templates and Authentication

The application's templates use Jinja2 for rendering and have the following structure:
- Base template (`base.html`) provides the layout used by all other templates
- Each entity type has its own template files

### Authentication and User Management

The templates reference `current_user` which is typically provided by Flask-Login. If you encounter a Jinja2 error about `'current_user' is undefined`, this indicates one of the following issues:

1. Flask-Login is not properly initialized in the application
2. The templates are trying to access Flask-Login features but the extension is not being used

#### Temporary workaround:
We've modified the templates to check for `session.get('user_id')` instead of `current_user.is_authenticated`. This allows the templates to render correctly even without Flask-Login, though actual authentication features will be limited.

If you need proper authentication, consider:
1. Adding Flask-Login to the application
2. Initializing it in `app/__init__.py`
3. Creating a User model with the required interface
