# Ontology Enhancement Branch

This branch focuses on enhancing the ontology functionality in ProEthica, with emphasis on the engineering ethics applications through a unified, modular architecture.

## Key Features

- Unified modular architecture for ontology access
- Enhanced case analysis using ontology data
- Improved integration with LLMs for ontology-based reasoning
- Support for temporal functionality (planned)
- Comprehensive API for ontology access

## Getting Started

### Running the Server

To start the unified ontology server:

```bash
./start_unified_ontology_server.sh
```

This will:
- Set up the Python environment
- Start the server in the background on port 5001
- Show available modules and tools

The server provides:
- JSON-RPC API at `http://localhost:5001/jsonrpc`
- Direct API endpoints for certain operations
- Health check at `http://localhost:5001/health`
- Server info at `http://localhost:5001/info`

To stop the server:

```bash
./stop_unified_ontology_server.sh
```

### Testing Case Analysis

You can test the case analysis functionality with:

```bash
./test_case_analysis.py
```

Options:
- `--text "Your text here"` - Text to extract entities from
- `--case-id 123` - Case ID to analyze
- `--ontology-source engineering` - Ontology source to use
- `--mode [extract|analyze|summary|all]` - Test mode

Example:

```bash
./test_case_analysis.py --text "The engineer must consider safety implications before approving the design."
```

## Architecture

The unified ontology server uses a modular architecture:

```
UnifiedOntologyServer
├── BaseModule (abstract)
├── QueryModule
│   ├── get_entities
│   ├── execute_sparql
│   └── get_entity_info
├── CaseAnalysisModule
│   ├── extract_entities
│   ├── analyze_case_structure
│   ├── match_entities
│   └── generate_summary
└── [Future modules]
    ├── RelationshipModule (planned)
    └── TemporalModule (planned)
```

## API Documentation

For detailed API documentation, see:

- `docs/unified_ontology_server.md` - Server architecture and API
- `docs/case_analysis_using_ontology.md` - Case analysis guide
- `docs/ontology_enhancement_plan.md` - Enhancement plan

## Development Workflow

When implementing new features:

1. Create a new module extending `BaseModule`
2. Register tools in the module's `_register_tools` method
3. Update the server to load your module
4. Add comprehensive tests and documentation
5. Add any necessary UI components to interact with your module

Example module addition:

```python
from mcp.modules.base_module import BaseModule

class MyNewModule(BaseModule):
    @property
    def name(self) -> str:
        return "my_module"
        
    @property
    def description(self) -> str:
        return "My new functionality"
        
    def _register_tools(self) -> None:
        self.tools = {
            "my_tool": self.my_tool_method
        }
        
    def my_tool_method(self, arguments):
        # Implement functionality here
        return {"result": "success"}
