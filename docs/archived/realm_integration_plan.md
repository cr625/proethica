# REALM Integration Plan

## Current Integration

REALM (Resource for Engineering and Advanced Learning in Materials) is currently integrated within the ProEthica repository as a subsystem. The integration allows both applications to share common infrastructure while maintaining separate functionality.

## Shared Components

1. **agent_module**: The agent orchestration capabilities
2. **Database Infrastructure**: Shared PostgreSQL instance
3. **MCP Server Architecture**: Common approach to ontology and LLM integration

## Repository Structure

The current structure includes:

- **realm/**: Contains REALM-specific application code
- **mcp/mseo/**: Materials Science & Engineering Ontology MCP server
- **scripts/**: Shared utility scripts
- **docs/realm_*.md**: REALM documentation

## Future Separation Plan

When it becomes necessary to separate REALM into its own repository, follow these steps:

### 1. Create a New Repository

```bash
mkdir realm-project
cd realm-project
git init
```

### 2. Copy REALM-Specific Components

```bash
# From original repository
cp -r realm/ /path/to/realm-project/
cp -r mcp/mseo/ /path/to/realm-project/mcp/
cp run_realm.py start_realm.sh /path/to/realm-project/
cp docs/realm_*.md /path/to/realm-project/docs/
```

### 3. Extract Shared Dependencies

```bash
# Create a shared library or submodule for agent functionality
mkdir -p /path/to/realm-project/app/agent_module
cp -r app/agent_module/ /path/to/realm-project/app/agent_module/
```

### 4. Setup Configuration

```bash
cp .env.example /path/to/realm-project/.env.example
# Create a realm-specific configuration
```

### 5. Database Setup

```bash
# Copy database setup scripts
cp scripts/setup_shared_postgres.sh /path/to/realm-project/scripts/
```

### 6. Update Import Paths

Review all Python files in the new repository and update import paths to reflect the new structure:

- Change `from app.agent_module...` to appropriate new paths
- Update relative imports as needed
- Ensure configuration paths are updated

### 7. Create Independent Package

Update `setup.py` to create a standalone REALM package:

```python
from setuptools import setup, find_packages

setup(
    name="realm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # List dependencies
    ],
    # Additional configuration
)
```

### 8. Initialize Git Repository

```bash
git add .
git commit -m "Initial REALM repository separation from ProEthica"
```

## Component Ownership

| Component | Owner | Future Home |
|-----------|-------|-------------|
| MSEO MCP Server | REALM | realm-project/mcp/ |
| REALM Web UI | REALM | realm-project/realm/ |
| Material Models | REALM | realm-project/realm/models/ |
| Agent Module | Shared | Both repositories or separate package |
| Database Infrastructure | Shared | Separate configuration in each repo |

## Version Control

The tag `pre-realm-v1.0` marks the state of ProEthica before REALM integration.
The branch `realm-integration` contains the integrated version with both applications.

For future reference, to extract REALM to its own repository while preserving history:

```bash
git clone --branch realm-integration <original-repo-url> realm-project
cd realm-project
# Keep only REALM-related files
git filter-branch --prune-empty --tree-filter '
  mkdir -p temp_preserve &&
  cp -r realm mcp/mseo docs/realm_* run_realm.py start_realm.sh temp_preserve/ &&
  rm -rf * &&
  mv temp_preserve/* . &&
  rm -rf temp_preserve
' HEAD
```
