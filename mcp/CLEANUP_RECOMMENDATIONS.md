# MCP Directory Cleanup Recommendations

Based on analysis of the MCP directory, here are cleanup recommendations to streamline the codebase:

## Files to Keep (Active Implementation)

### Core Server Files
- ✅ `enhanced_ontology_server_with_guidelines.py` - Main server
- ✅ `run_enhanced_mcp_server_with_guidelines.py` - Runner script
- ✅ `http_ontology_mcp_server.py` - Base HTTP server class
- ✅ `__init__.py` - Package initialization

### Modules Directory
- ✅ All files in `/modules/` - Active functionality
- ❓ `guideline_analysis_module_fix.py` - Check if fixes are incorporated into main module

### Support Files
- ✅ `enhanced_debug_logging.py` - Debug utilities
- ✅ `fix_flask_db_config.py` - DB config helpers
- ✅ `load_from_db.py` - Ontology loading

### Documentation & Resources
- ✅ `/docs/` - All documentation
- ✅ `/ontology/` - TTL fallback files
- ✅ `/mock_responses/` - Test data

## Files to Archive/Remove

### Alternative Implementations
- 📦 `enhanced_ontology_mcp_server.py` - Older version without guidelines
- 📦 `run_enhanced_mcp_server.py` - Runner for older version
- 📦 `unified_ontology_server.py` - Experimental unified approach
- 📦 `add_temporal_functionality.py` - Temporal experiment

### Experimental Features
- 📦 `/hosted_llm_mcp/` - Entire directory if not actively developed
- 📦 `/mseo/` - Materials science ontology if not actively used

## Action Items

### Immediate Actions
1. **Verify module fix**: Check if `guideline_analysis_module_fix.py` changes are in main module
2. **Archive old servers**: Move alternative implementations to `/archived/`
3. **Update imports**: Ensure all code references the active server

### Future Improvements
1. **Consolidate MSEO**: If keeping MSEO, merge multiple server files
2. **Document APIs**: Add OpenAPI/Swagger docs for HTTP endpoints
3. **Add tests**: Create test suite for MCP server functionality

## Proposed Directory Structure

```
/mcp/
├── README.md
├── __init__.py
├── enhanced_ontology_server_with_guidelines.py  # Main server
├── run_enhanced_mcp_server_with_guidelines.py   # Runner
├── http_ontology_mcp_server.py                  # Base class
├── enhanced_debug_logging.py
├── fix_flask_db_config.py
├── load_from_db.py
├── /modules/                    # Active modules
├── /docs/                       # Documentation
├── /ontology/                   # TTL files
├── /mock_responses/             # Test data
└── /archived/                   # Old implementations
    ├── enhanced_ontology_mcp_server.py
    ├── unified_ontology_server.py
    └── add_temporal_functionality.py
```

## Benefits of Cleanup

1. **Clarity**: Clear which implementation is active
2. **Maintainability**: Easier to understand and modify
3. **Performance**: Less code to load and parse
4. **Documentation**: Cleaner structure easier to document

## Implementation Steps

```bash
# 1. Create archived directory
mkdir -p /home/chris/ai-ethical-dm/mcp/archived

# 2. Move old implementations
mv enhanced_ontology_mcp_server.py archived/
mv run_enhanced_mcp_server.py archived/
mv unified_ontology_server.py archived/
mv add_temporal_functionality.py archived/

# 3. Update imports if needed
# grep -r "enhanced_ontology_mcp_server" ../ 

# 4. Test server still works
python run_enhanced_mcp_server_with_guidelines.py
```