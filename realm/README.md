# REALM - Resource for Engineering And Learning Materials

REALM is an application that integrates the Materials Science Engineering Ontology (MSEO) from MatPortal.org with large language models through the Model Context Protocol (MCP).

## Overview

REALM provides access to materials science knowledge through a web interface and API, allowing users to:

- Search for materials and their properties
- Compare different materials
- Explore material categories
- Chat with an AI that has enhanced knowledge of materials science

The application uses the Model Context Protocol (MCP) to connect with the MSEO ontology server, enabling seamless integration between the knowledge base and AI models.

## Components

REALM consists of the following main components:

1. **MSEO MCP Server**: A server that provides access to the Materials Science Engineering Ontology through the Model Context Protocol
2. **Flask Web Application**: A web interface for interacting with the materials database and AI
3. **Services Layer**: Services for managing materials data and communicating with the MCP server
4. **Models Layer**: Domain models representing materials science concepts
5. **API**: RESTful API endpoints for programmatic access to the materials database

## Installation

### Prerequisites

- Python 3.8+
- pip
- RDFlib
- Flask
- Requests

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/your-username/ai-ethical-dm.git
   cd ai-ethical-dm
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Download the MSEO ontology:
   ```
   python -m mcp.mseo.setup_mseo
   ```

## Usage

### Starting the MSEO MCP Server

To start the MSEO MCP server:

```
python -m mcp.mseo.run_mseo_mcp_server
```

Options:
- `--host`: Host to bind to (default: localhost)
- `--port`: Port to run on (default: 8078)
- `--data-dir`: Directory for ontology data
- `--ontology-file`: Specific ontology file path
- `--debug`: Enable debug mode

### Starting the REALM Web Application

To start the REALM web application:

```
python run_realm.py
```

Options:
- `--host`: Host to bind to (default: localhost)
- `--port`: Port to run on (default: 5000)
- `--mseo-server`: URL of the MSEO MCP server (default: http://localhost:8078)
- `--auto-start-mseo`: Automatically start the MSEO server if not running
- `--debug`: Enable debug mode

### Accessing the Application

Once running, access the application in a web browser:

- Web Interface: http://localhost:5000
- API Documentation: http://localhost:5000/api
- Health Check: http://localhost:5000/health

## API Endpoints

REALM provides the following API endpoints:

- `GET /api/materials/search?q=<query>`: Search for materials
- `GET /api/materials/<uri>`: Get details for a specific material
- `GET /api/categories`: Get a list of material categories
- `GET /api/materials/compare?uri1=<uri1>&uri2=<uri2>`: Compare two materials
- `POST /api/chat`: Chat with the MSEO-enhanced LLM

## Development

### Project Structure

```
realm/
├── __init__.py         # Package initialization
├── config.py           # Configuration settings
├── models/             # Domain models
├── routes/             # Web routes and API endpoints
├── services/           # Services layer
├── static/             # Static files (CSS, JS, etc.)
└── templates/          # Jinja2 templates
```

### Adding New Features

To add new features:

1. Add models to `realm/models/` if needed
2. Add or modify services in `realm/services/`
3. Add routes in `realm/routes/`
4. Add templates in `realm/templates/`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [MatPortal.org](https://matportal.org) for the Materials Science Engineering Ontology
- The Model Context Protocol for enabling AI tool interactions
