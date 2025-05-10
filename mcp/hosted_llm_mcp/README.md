# Hosted LLM MCP Server

This MCP server integrates with hosted LLM services (Anthropic Claude and OpenAI) to enhance ontology agent capabilities in the ProEthica platform.

## Overview

The Hosted LLM MCP Server provides a bridge between the ProEthica ontology system and powerful hosted language models. It leverages both Anthropic's Claude and OpenAI's models to enhance ontology manipulation capabilities through a carefully designed routing system that directs different types of tasks to the most appropriate model.

### Key Features

- **Smart Model Routing**: Automatically routes ontology tasks to Claude or GPT based on their strengths
- **Fallback Mechanism**: Provides resilience by falling back to alternative models when needed
- **Result Caching**: Reduces API costs by caching results for configurable periods
- **Ontology Integration**: Seamlessly connects with the existing enhanced ontology MCP server

## Installation

### Prerequisites

- Python 3.8 or higher
- Anthropic API key
- OpenAI API key
- Running enhanced ontology MCP server

### Installation Steps

1. Install required packages:

```bash
cd mcp/hosted_llm_mcp
pip install -r requirements.txt
```

2. Set up environment variables for API keys:

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

## Configuration

The server can be configured using the `config.json` file or environment variables:

### Configuration Options

- **Models**:
  - `anthropic_model`: Anthropic model to use (default: "claude-3-opus-20240229") 
  - `openai_model`: OpenAI model to use (default: "gpt-4o")

- **Task Routing**:
  - `routing`: Maps tasks to preferred models
  - Default routing:
    - `analyze_concept`: Claude (better at conceptual analysis)
    - `suggest_relationships`: OpenAI (better at structured relationship suggestions)
    - `expand_hierarchy`: Claude (better at hierarchical reasoning)
    - `validate_ontology`: OpenAI (better at validation and consistency checking)
    - `explain_concept`: Claude (better at natural language explanations)
    - `classify_entity`: OpenAI (better at classification)

- **Performance**:
  - `cache_ttl`: Cache time-to-live in seconds (default: 3600)
  - `default_timeout`: Default request timeout in seconds (default: 30)

### Environment Variables

- `ANTHROPIC_API_KEY`: API key for Anthropic Claude
- `OPENAI_API_KEY`: API key for OpenAI
- `MCP_SERVER_URL`: URL for the enhanced ontology MCP server (default: "http://localhost:5001")

## Usage

### Starting the Server

To start the server:

```bash
cd mcp
python -m hosted_llm_mcp.server
```

### Available Tools

The server provides the following ontology manipulation tools:

1. **analyze_concept**:
   - Analyzes an ontology concept and extracts its properties and relationships
   - Example input: `{"concept": "Fairness", "context": "Engineering ethics"}`

2. **suggest_relationships**:
   - Suggests potential relationships between ontology concepts
   - Example input: `{"source_concept": "Engineer", "target_concept": "Society", "domain": "Engineering ethics"}`

3. **expand_hierarchy**:
   - Generates potential sub-concepts for a given concept
   - Example input: `{"concept": "Ethical Dilemma", "domain": "Medical ethics", "depth": 2}`

4. **validate_ontology**:
   - Validates the consistency and coherence of ontology concepts
   - Example input: `{"concepts": ["Engineer", "Client", "Public"], "relationships": [...]}`

5. **explain_concept**:
   - Generates a natural language explanation of an ontology concept
   - Example input: `{"concept": "Duty of Care", "audience": "novice", "detail_level": "detailed"}`

6. **classify_entity**:
   - Classifies an entity within the ontology hierarchy
   - Example input: `{"entity": "Civil Engineer", "description": "An engineer who designs and maintains infrastructure"}`

## Architecture

The server comprises several components:

### 1. Adapters
- `anthropic_adapter.py`: Connects to Anthropic's Claude API
- `openai_adapter.py`: Connects to OpenAI's API
- `model_router.py`: Directs tasks to the appropriate model

### 2. Tools
- `concept_analyzer.py`: Tools for analyzing and explaining concepts
- `relationship_tools.py`: Tools for suggesting and validating relationships
- `hierarchy_tools.py`: Tools for expanding hierarchies and classifying entities

### 3. Integration
- `ontology_connector.py`: Connects to the enhanced ontology MCP server

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Check that API keys are correctly set in environment variables or config
   - Verify API keys are valid and have not expired

2. **Connection Issues**:
   - Ensure the enhanced ontology MCP server is running
   - Check the URL in MCP_SERVER_URL environment variable

3. **Model Availability**:
   - If a model is unavailable, the system will attempt to use fallback models
   - Check model names in config if you experience persistent failures

### Logging

Logs are written to `hosted_llm_server.log` in the mcp/hosted_llm_mcp directory.

## Contributing

To extend or modify this server:

1. Add new task handlers in the respective tool classes
2. Update the routing configuration for new tasks
3. Add any new models to the adapters directory

## License

This project is licensed under the same license as the parent ProEthica platform.
