2025-04-28 - Fixed MCP Server Port Conflict Issue

### Issue Fixed

Fixed an issue where the ProEthica application failed to start with an `OSError: [Errno 98] address already in use` error on port 5001. This prevented the MCP server from starting properly.

### Root Cause Analysis

The issue occurred because:
1. Multiple scripts were attempting to start different variants of the MCP server
2. The process termination in the restart script was insufficient (only killing specific process patterns)
3. No port availability check was performed before starting the new server
4. Multiple server variants (enhanced_mcp_server.py and http_ontology_mcp_server.py) could run simultaneously on the same port

### Solution Implemented

1. **Enhanced MCP Server Restart Script**
   - Added comprehensive process cleanup for all MCP server variants
   - Implemented port availability checking before starting the server
   - Added lock file mechanism to prevent multiple instances

   - Added verification that the server is properly listening on the port

2. **Key Improvements**
   - More robust process detection and termination
   - Multiple detection methods (ps, pkill, lsof, netstat)
   - Explicit verification of port availability
   - Better error messages with troubleshooting guidance
   - Enhanced logging to a dedicated log file

### Benefits

- **More Reliable Startup**: Application startup is now more robust
- **Better Error Handling**: Clear error messages help with troubleshooting
- **Improved Logging**: Comprehensive logs make issue diagnosis easier
- **Process Management**: Better management of MCP server processes
- **Port Conflict Resolution**: Automatic detection and handling of port conflicts

This fix ensures the ProEthica application can start reliably without port conflicts from previously running MCP server instances.

## 2025-04-29 - Implemented Environment-Aware Configuration System

### Actions Taken

1. **Created Environment Configuration Framework**
   - Developed a robust, environment-aware configuration system in `config/`
   - Created separate configuration files for development and production environments
   - Implemented automatic environment detection based on ENVIRONMENT variable
   - Added comprehensive logging and error handling for configuration loading

## 2025-04-29 - Unified Environment Support System

### Actions Taken

1. **Implemented Unified Environment Detection**
   - Enhanced environment detection in `config/environment.py` to automatically detect:
     - GitHub Codespaces environment (via CODESPACES environment variable)
     - WSL environment (by examining /proc/version)
     - Explicitly configured environment (via ENVIRONMENT variable)
     - Default environment based on hostname and git branch

2. **Created Environment-Specific Configuration Files**
   - Added `config/environments/wsl.py` for WSL-specific settings
   - Added `config/environments/codespace.py` for GitHub Codespaces-specific settings
   - Maintained existing `development.py` and `production.py` configurations

3. **Enhanced Startup Scripts**
   - Modified `auto_run.sh` to handle all environment types automatically
   - Updated `start_proethica.sh` to provide environment-specific setup steps
   - Consolidated environment-specific logic in one codebase

4. **Added Documentation**
   - Created `docs/unified_environment_system.md` explaining the new system
   - Documented the implementation and benefits in detail

### Benefits

- **Branch Consolidation**: Eliminated need for separate environment branches
- **Simplified Git Workflow**: One development branch for all environments (WSL, Codespaces, etc.)
- **Reduced Merge Conflicts**: No need to sync changes between environment branches
- **Improved Developer Experience**: Environment is auto-detected, no manual configuration needed
- **Cleaner Version History**: Git history follows feature development, not environment tweaks

### How It Works

The system uses a priority-based detection mechanism:
1. First checks for GitHub Codespaces environment
2. Then checks for WSL environment
3. Falls back to explicit environment setting or inference from hostname/branch

This allows the code to automatically adapt to whatever environment it's running in, while
maintaining environment-specific optimizations for database connections, paths, and other
configuration details.

## 2025-04-29 - Repository Branch Structure Reorganization

### Branch Structure

The repository has been reorganized into three primary branches:

1. **`dev`**: Main development branch
   - Where all active development happens
   - Contains environment auto-detection system
   - Implements Docker PostgreSQL configuration
   - Automatically adapts to WSL, Codespaces, or standard environments

2. **`main`**: Stable branch for testing
   - Contains code that has been developed and is ready for testing
   - Used as an intermediary between development and production
   - Should always be in a runnable state

3. **`production`**: Deployment branch
   - The branch deployed to the production server at proethica.org
   - Contains Docker PostgreSQL setup and systemd configuration
   - Only updated through controlled merges from `main`

All environment-specific branches have been consolidated into this structure, with environment detection happening automatically at runtime.

### Working with Branches

**Development Work:**
```bash
# Clone the repository
git clone https://github.com/cr625/ai-ethical-dm.git
cd ai-ethical-dm

# Ensure you're on the dev branch
git checkout dev

# Create a feature branch
git checkout -b feature/my-new-feature

# After making changes, merge back to dev
git checkout dev
git merge feature/my-new-feature
git push origin dev
```

**Testing:**
```bash
# Move code from dev to main for testing
git checkout main
git merge dev
git push origin main
```

**Deployment:**
```bash
# After testing on main, deploy to production
git checkout production
git merge main
git push origin production

# Then on the production server:
cd /var/www/proethica
git pull origin production
sudo systemctl restart proethica-postgres.service mcp-server.service proethica.service
```

### Environment Start Commands

**Starting in any environment:**
```bash
# The auto-detection will configure for the current environment
./start_proethica.sh
```

**Specific environment variables:**
```bash
# Force a specific environment regardless of detection
ENVIRONMENT=development ./start_proethica.sh
ENVIRONMENT=production ./start_proethica.sh
```

### Deployment Process

1. **Prepare for deployment:**
   - Ensure all changes are merged to `main` and tested
   - Resolve any conflicts or issues
   - Create a backup of the production database if necessary

2. **Deploy to production:**
   - Merge `main` to `production` branch
   - Push to GitHub
   - Connect to the production server
   - Pull the latest changes
   - Restart the services

3. **Verify deployment:**
   - Check all services are running correctly
   - Verify the application is accessible
   - Monitor logs for any issues

4. **Rollback if needed:**
   - If issues are encountered, revert to the previous production commit
   - Restart services with the previous version

### Docker PostgreSQL Integration

The production environment uses Docker PostgreSQL with pgvector:

- **Container name:** `proethica-postgres-production`
- **Port:** 5433 (host) → 5432 (container)
- **Data persistence:** Docker volume
- **Automated backup/restore:** Scripts in `backups/` directory

To restore a database backup in production:
```bash
cd /var/www/proethica
./backups/docker_restore.sh backups/latest_backup.dump
```

The Docker PostgreSQL setup is managed by the systemd service `proethica-postgres.service`, which ensures the container starts automatically with the system.

## 2025-04-29 - Implemented Hosted LLM MCP Server

### Actions Taken

1. **Created New MCP Server for Ontology Enhancement**
   - Implemented `mcp/hosted_llm_mcp/` server that connects to hosted LLM services
   - Integrated with both Anthropic Claude and OpenAI models
   - Designed smart model router that directs tasks to the appropriate model based on strengths
   - Added fallback mechanisms for resilience when a model is unavailable
   - Implemented result caching to reduce API costs

2. **Developed Specialized Ontology Tools**
   - `concept_analyzer.py`: Tools for analyzing and explaining ontology concepts
   - `relationship_tools.py`: Tools for suggesting and validating ontology relationships
   - `hierarchy_tools.py`: Tools for expanding hierarchies and classifying entities
   - Each tool integrates seamlessly with the existing enhanced ontology MCP server

3. **Added Robust Model Adapters**
   - `anthropic_adapter.py`: Optimized for concept analysis, hierarchy expansion, and explanations
   - `openai_adapter.py`: Optimized for relationship suggestion, ontology validation, and classification
   - `model_router.py`: Intelligently routes tasks to the appropriate model with fallback capability

4. **Implemented Ontology Integration**
   - Created connector to interface with the existing enhanced ontology MCP server
   - Provides methods to retrieve and query ontology data
   - Supports submitting potential new ontology elements for validation

5. **Configuration and Documentation**
   - Added configurable routing of tasks to appropriate models based on their strengths
   - Implemented caching with configurable TTL to reduce API costs
   - Provided comprehensive documentation, including server setup and API usage
   - Created a detailed README with examples and troubleshooting guidance

### Usage Instructions

To use the new MCP server:

1. **Installation**:
   ```bash
   cd mcp/hosted_llm_mcp
   pip install -r requirements.txt
   ```

2. **Configuration**:
   - Set API keys:
     ```bash
     export ANTHROPIC_API_KEY="your_anthropic_api_key"
     export OPENAI_API_KEY="your_openai_api_key" 
     ```
   - Adjust `config.json` for model preferences if needed

3. **Starting the Server**:
   ```bash
   cd mcp
   python -m hosted_llm_mcp.run
   ```

4. **Available Tools**:
   - `analyze_concept`: Extract properties and relationships from a concept
   - `suggest_relationships`: Suggest meaningful connections between concepts
   - `expand_hierarchy`: Generate sub-concept hierarchies
   - `validate_ontology`: Check consistency and coherence
   - `explain_concept`: Generate natural language explanations
   - `classify_entity`: Determine where an entity fits in the ontology

This implementation combines the strengths of multiple LLM models to enhance the ontology capabilities of the ProEthica platform, providing more sophisticated tools for concept analysis, relationship suggestion, and hierarchical organization.

## 2025-05-01 - Fixed Codespace Environment Configuration Issue

### Issue Fixed

Fixed an application startup failure in GitHub Codespaces environment. The application was failing with a `KeyError: 'codespace'` when trying to access a non-existent configuration for the Codespace environment.

### Root Cause Analysis

The issue occurred because:
1. The enhanced environment detection system correctly identified the GitHub Codespaces environment
2. However, the `app/config.py` configuration dictionary didn't include a 'codespace' key
3. This caused a KeyError when the application tried to load the configuration for the Codespace environment

### Solution Implemented

1. **Updated Configuration Dictionary**
   - Added 'codespace' key to the configuration dictionary in `app/config.py`
   - Mapped it to use the DevelopmentConfig class, as Codespaces are development environments

### Benefits

- **Seamless Codespace Integration**: Application now starts correctly in GitHub Codespaces
- **Environment Consistency**: Maintains the same configuration behavior across different development environments
- **Improved Developer Experience**: Developers can now use Codespaces without manual configuration steps

## 2025-05-02 - Fixed MCP Server Start Failure Issue

### Issue Fixed

Fixed an issue where the ProEthica application failed to start with the error "Failed to start MCP server. See logs for details" when running the start_proethica.sh script.

### Root Cause Analysis

The issue occurred because:
1. A previous MCP server process was still running and bound to port 5001
2. The env_mcp_server.py script was unable to start a new server instance due to port conflict
3. Despite the restart script attempting to kill existing processes, one process remained active
4. The script was timing out after waiting for the port to become available

### Solution Implemented

1. **Manual Process Cleanup**
   - Identified the specific process ID of the lingering MCP server (PID 7377)
   - Manually terminated the process with `kill -9 7377`
   - Verified port 5001 was free before restarting

### Benefits

- **Application Successfully Started**: ProEthica now starts correctly with functional MCP server
- **Diagnostic Process Documented**: Clear steps identified for troubleshooting similar issues in the future
- **Enhanced Understanding**: Better insight into process/port handling during application startup

### Future Improvements

1. **Enhanced Process Cleanup**:
   - Add direct port-based process identification (e.g., using `fuser`)
   - Implement forceful cleanup with elevated privileges if necessary
   - Add explicit verification that port has been freed after process termination

2. **Improved Error Reporting**:
   - Include more detailed output about specific port conflicts
   - Display process information for conflicting processes
   - Provide automated remediation steps in error messages

## 2025-05-10 - Merged Hosted LLM MCP Feature Branch

### Actions Taken

1. **Merged Feature Branch into Dev**
   - Successfully merged `feature/hosted-llm-mcp` branch into `dev`
   - Resolved merge conflicts in `CLAUDE.md` and `app/config.py`
   - Tested the application to ensure proper functionality after merge

2. **Verified Feature Functionality**
   - Confirmed that the enhanced MCP server starts correctly
   - Tested the application's connection to the enhanced MCP server
   - Verified that the agent interface loads properly with the new capabilities
   - Confirmed that the new ontology tools are available and working

3. **Key Components Tested**
   - Application startup in Codespace environment
   - MCP server connection and API endpoints
   - Ontology data retrieval and query functionality
   - Scenario display and navigation
   - Agent interface with model selection

### Benefits

- **Enhanced Ontology Capabilities**: The merged changes provide more sophisticated tools for ontology manipulation
- **Improved Model Resilience**: Smart model routing with fallback mechanisms ensures system reliability
- **Cost Optimization**: Result caching reduces API costs for repeated operations
- **Seamless Integration**: All new features work with the existing enhanced ontology MCP server

The successful merge makes these features available in the development branch, ready for further testing and eventual promotion to the main branch.
