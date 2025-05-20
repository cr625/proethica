# ProEthica Project Development Log

## 2025-05-20: MCP Server Environment Variables Fix

Fixed an issue with environment variables not being passed to the MCP server:

**Issue**: When accessing the codespace from a different computer, the guideline concept extraction process was failing with the error "LLM client not available" despite the API keys being properly set in the .env file.

**Analysis**:
- The Flask app was correctly loading environment variables from .env
- The MCP server logs showed "ANTHROPIC_API_KEY not found in environment" warnings
- The issue was in how VS Code's tasks.json launches the MCP server through preLaunch task
- Child processes started through tasks.json don't automatically inherit environment variables from .env

**Solution**:
1. Created a helper shell script (`start_mcp_server_with_env.sh`) to properly source the .env file:
   ```bash
   #!/bin/bash
   # Load environment variables from .env file
   if [ -f .env ]; then
     export $(grep -v '^#' .env | xargs)
     echo "Loaded environment variables from .env file"
   fi
   
   # Start the MCP server
   python mcp/run_enhanced_mcp_server_with_guidelines.py
   ```

2. Updated `.vscode/tasks.json` to use this script:
   ```json
   {
       "label": "Start MCP Server with Live LLM",
       "type": "shell",
       "command": "./start_mcp_server_with_env.sh",
       "args": [],
   }
   ```

3. Created full documentation in `docs/anthropic_sdk_fix_2025_05_20.md`

4. Created a database backup (`ai_ethical_dm_backup_20250520_005033.dump`) as a precaution

**Prevention**:
For future development, ensure that:
- Use the helper script when starting the MCP server manually
- Environment variables are explicitly passed to child processes
- VSCode launch and task configurations are tested when accessing from different computers

## 2025-05-19: Python Environment Package Resolution Fix

Fixed an issue with Python module imports when accessing the codespace from a different system:

**Issue**: When accessing the codespace from a different system, the application was experiencing module import errors - first `ModuleNotFoundError: No module named 'langchain_core'` and then `ModuleNotFoundError: No module named 'langchain_anthropic'` despite these packages being included in requirements.txt.

**Analysis**: 
- The ProEthica application's Python dependencies are installed in the user site-packages directory (`/home/codespace/.local/lib/python3.12/site-packages`)
- When accessing the codespace from a different system, VSCode's debugger was using the conda Python environment (`/opt/conda/bin/python`)
- While some packages like langchain-core and langchain-anthropic were installed in the conda environment, they weren't installed in the user Python environment

**Solution**:
1. Manually installed the missing packages in the user Python environment:
   ```bash
   pip install --user langchain-core langchain-anthropic
   ```
2. Created a shell script (`fix_dependencies.sh`) to fix similar issues in the future:
   ```bash
   # Set Python to ignore the conda environment
   export USE_CONDA="false"
   
   # Add user site-packages to PYTHONPATH
   export PYTHONPATH="/home/codespace/.local/lib/python3.12/site-packages:$PYTHONPATH"
   
   # Force reinstall packages to user site-packages
   pip install --user --force-reinstall <package-name>
   ```

**Prevention**:
For future development, make sure to:
- Use the VSCode debugging configurations in launch.json which correctly set up the Python path
- Run the `scripts/ensure_python_path.sh` script before debugging
- For any new import errors, install the package directly to the user site-packages:
  ```bash
  pip install --user <package-name>
  ```
- If necessary, force reinstall packages to ensure they're in the correct location

## 2025-05-19: Ontology Enhancements

Updated the proethica-intermediate.ttl ontology with the following:

1. Enhanced temporal modeling aligned with Basic Formal Ontology (BFO):
   - Properly aligned temporal classes with BFO temporal region classes (BFO_0000038, BFO_0000148)
   - Improved temporal relation properties with appropriate domain and range constraints
   - Added temporal granularity concepts with proper BFO subclassing

2. Added decision timeline concepts:
   - Decision timeline classes for representing sequences of decisions and consequences
   - Alternative timeline classes for modeling hypothetical decision scenarios
   - Relations for connecting decisions to their temporal contexts and consequences

3. Enhanced ethical context modeling:
   - Added EthicalContext class with proper BFO alignment
   - Added properties to represent ethical weights and relationships
   - Created ethical agent concepts to represent decision makers

All ontology updates are properly aligned with BFO, using appropriate parent classes:
- Temporal entities are subclasses of BFO temporal region classes
- Material entities are properly aligned with BFO independent continuant hierarchy
- Properties have appropriate domain and range restrictions aligned with BFO types

The enhanced ontology provides improved representation capabilities for:
- Temporal aspects of ethical decision making
- Hypothetical reasoning about alternative decisions
- Contextual factors in ethical judgments

Next steps:
1. Test the enhanced ontology with existing ProEthica case data
2. Integrate with the temporal context service enhancements
3. Update the entity triple service to leverage new ontology concepts
