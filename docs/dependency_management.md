# Dependency Management Guide

This guide explains how to manage dependencies in the AI Ethical DM project to reduce overhead from unnecessary packages, particularly those with heavy dependencies like CUDA-enabled libraries.

## Understanding Project Dependencies

The project uses different sets of Python packages depending on which features are active:

### Core Dependencies (Always Required)

Core dependencies are essential for the application to run, regardless of which features are enabled:

- **Flask and related packages**: Web framework and essential extensions
- **Database**: SQLAlchemy, PostgreSQL driver
- **MCP Server**: RDFLib, AIOHTTP
- **HTTP Client**: Requests
- **Development Tools**: pytest, black, flake8, etc.

### Feature-Specific Dependencies

Additional packages are only needed when specific features are active:

1. **Agent/Claude Integration**
   - Required packages: anthropic, langchain, langchain-core, etc.
   - Controlled by `USE_CLAUDE` and `USE_AGENT_ORCHESTRATOR` in `.env`

2. **Document Processing**
   - Required packages: PyPDF2, python-docx, beautifulsoup4
   - Used for document upload and processing features

3. **Vector Embeddings**
   - Required packages: pgvector, sentence-transformers, chromadb
   - Heavy dependencies with CUDA requirements
   - Controlled by `EMBEDDING_PROVIDER_PRIORITY` in `.env`

4. **Zotero Integration**
   - Required package: pyzotero
   - Controlled by Zotero API credentials in `.env`

5. **MCP CLI Tools**
   - Required package: mcp[cli]
   - Only needed if directly using MCP CLI tools

## Dependency Management Script

A utility script is provided to help manage dependencies based on active features:

```bash
# Analyze which features are active and display required packages
python scripts/manage_dependencies.py analyze

# Install only the core dependencies
python scripts/manage_dependencies.py install-core

# Install dependencies for a specific feature
python scripts/manage_dependencies.py install-feature agent
python scripts/manage_dependencies.py install-feature embedding
python scripts/manage_dependencies.py install-feature documents
python scripts/manage_dependencies.py install-feature zotero

# Install all dependencies for all features
python scripts/manage_dependencies.py install-all
```

## Minimizing CUDA Dependencies

To avoid installing unnecessary CUDA-related packages:

1. If you're not using embedding features, don't install the embedding dependencies
2. Modify `.env` to disable unused features (e.g., set `EMBEDDING_PROVIDER_PRIORITY=''`)
3. Only install the dependencies for the features you need

## Reference Files

Two reference requirements files are provided:

1. `requirements-final.txt`: Categorized list of all dependencies with comments
2. `requirements.txt`: Original complete requirements file

## Example: Minimal Installation

For a minimal installation that doesn't use embedding or document processing:

1. Edit `.env` to disable features:
   ```
   USE_CLAUDE=false
   USE_AGENT_ORCHESTRATOR=false
   EMBEDDING_PROVIDER_PRIORITY=
   ZOTERO_API_KEY=
   ZOTERO_USER_ID=
   ```

2. Install only core dependencies:
   ```bash
   python scripts/manage_dependencies.py install-core
   ```

## Example: Production Installation

For a production installation:

1. Analyze active features:
   ```bash
   python scripts/manage_dependencies.py analyze
   ```

2. Install required dependencies based on the analysis output:
   ```bash
   python scripts/manage_dependencies.py install-core
   python scripts/manage_dependencies.py install-feature agent
   # Add other feature dependencies as needed
   ```

## Troubleshooting

If you encounter errors related to missing packages:

1. Run `python scripts/manage_dependencies.py analyze` to check which features are active
2. Ensure you've installed dependencies for all active features
3. Check `requirements-final.txt` for additional packages that might be needed
