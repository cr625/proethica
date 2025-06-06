# AI Ethical Decision-Making Simulator

A simulation platform for ethical decision-making in military medical triage scenarios, built with Flask, SQLAlchemy, LangChain, LangGraph, and Model Context Protocol.

## Overview

This project simulates event-based scenarios like military medical triage to train and evaluate ethical decision-making agents. The system combines rule-based reasoning with case-based and analogical reasoning from domain-specific ethical guidelines.

## Features

- Event-based simulation engine
- Character and resource management
- Decision tracking and evaluation
- Ethical reasoning framework
- Integration with LLMs via LangChain and LangGraph
- Model Context Protocol for extensibility
- Zotero integration for academic references and citations
- World and scenario reference management
- Asynchronous document processing for guidelines and references
- Vector embeddings for semantic search of documents

## Architecture

The application is built with:

- **Backend**: Flask, SQLAlchemy, PostgreSQL
- **AI Components**: LangChain, LangGraph
- **Extension**: Model Context Protocol

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL
- OpenAI API key (for LLM integration)

### Quick Setup

1. Clone the repository:
   ```
   git clone https://github.com/cr625/ai-ethical-dm.git
   cd ai-ethical-dm
   ```

2. Run the setup script:
   ```
   python setup_project.py
   ```
   
   This will:
   - Create a Python virtual environment
   - Install all required dependencies
   - Download NLTK resources
   - Create a .env file from template
   - Check database connectivity
   - Provide next steps

### Manual Installation

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up the database:
   ```
   createdb -U postgres ai_ethical_dm
   ```

5. Create a `.env` file with your configuration:
   ```
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://postgres:yourpassword@localhost/ai_ethical_dm
   OPENAI_API_KEY=your-openai-api-key
   
   # For Zotero integration (optional)
   ZOTERO_API_KEY=your-zotero-api-key
   ZOTERO_USER_ID=your-zotero-user-id
   ```
   
   See the [documentation index](docs/index.md) for more details on setting up the Zotero integration.

6. Initialize the database:
   ```
   export FLASK_APP="app:create_app"
   flask db upgrade
   ```

7. Run the application:
   ```
   # Development mode
   python run.py
   
   # Production mode with Gunicorn (recommended for stability)
   ./run_with_gunicorn.sh
   ```

## Usage

1. Access the web interface at `http://localhost:5000`
2. Create scenarios with characters and resources
3. Run simulations and observe decision-making
4. Evaluate ethical outcomes

## Testing

The application includes comprehensive tests for all routes. To run the tests:

```bash
# Run all tests
./run_tests.py

# Run with verbose output
./run_tests.py -v

# Run specific test file
./run_tests.py tests/test_scenarios_routes.py

# Run all route tests
./run_tests.py tests/test_all_routes.py

# Run specific test
pytest tests/test_scenarios_routes.py::test_list_scenarios
```

See `tests/README.md` for more details on the test structure and coverage.

## Documentation

The project includes detailed documentation in the `docs/` directory:

- `document_management.md`: Information about the document management system
- `multiple_guidelines.md`: How to use multiple guidelines per world
- `async_document_processing.md`: Details about the asynchronous document processing implementation
- `mcp_server_integration.md`: Information about the MCP server integration for ontology access

## License

GPL 3

## Contributors

- Christopher Rauch

## External Repositories

The external repository `agent_module` is now located in the `_src/agent_module` directory. Please ensure to update your local setup accordingly.
