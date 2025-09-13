# MCP Integration Tracking Document

## Overview
This document tracks the MCP integration status and patterns that work for ProEthica extractors.

## What Works ✅

### 1. MCP Server Architecture
- **MCP Server**: Runs on port 8082 (`cd /home/chris/onto/OntServe && python servers/mcp_server.py`)
- **OntServe Web**: Runs on port 5003 (separate from MCP)
- **ProEthica**: Runs on port 5000

### 2. Successful MCP Integration Pattern

The working pattern from Roles, States, and Resources extractors:

```python
def _create_XXX_prompt_with_mcp(self, text: str) -> str:
    try:
        from app.services.external_mcp_client import get_external_mcp_client
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("Fetching XXX context from external MCP server...")
        
        external_client = get_external_mcp_client()
        existing_entities = external_client.get_all_XXX_entities()
        
        # Build context with actual definitions
        ontology_context = f"Found {len(existing_entities)} existing concepts:\n"
        for entity in existing_entities:
            label = entity.get('label', 'Unknown')
            definition = entity.get('definition', entity.get('description', ''))
            ontology_context += f"- {label}: {definition}\n"
        
        # Include in prompt...
    except Exception as e:
        logger.error(f"Failed to get MCP context: {e}")
        # Fallback to standard prompt
```

### 3. Verified Working Extractors

| Extractor | MCP Method | Entities Retrieved | Definitions Included |
|-----------|------------|-------------------|---------------------|
| **Roles** | `get_all_role_entities()` | 15 | ✅ Dynamic |
| **States** | `get_all_state_entities()` | 20 | ✅ Dynamic |
| **Resources** | `get_all_resource_entities()` | 5 | ✅ Dynamic |
| **Principles** | `get_all_principle_entities()` | 12 | ✅ Dynamic |
| **Obligations** | `get_all_obligation_entities()` | 14 | ✅ Dynamic |

## What Doesn't Work ❌

### 1. Enhanced Extractors (Step 2) - FIXED for Principles
- ✅ `enhanced_prompts_principles.py` - Now fetches MCP data dynamically
- ⚠️ Other enhanced extractors still need updates

### 2. Missing MCP Methods
Some extractors call methods that don't exist in `external_mcp_client.py`:
- `get_all_action_entities()` - needs implementation
- `get_all_event_entities()` - needs implementation  
- `get_all_capability_entities()` - needs implementation
- `get_all_constraint_entities()` - needs implementation

## Pattern to Apply

For each extractor that needs MCP integration:

1. **In main extractor file** (`XXX.py`):
   - Add `_get_prompt_for_preview()` method
   - Add `_create_XXX_prompt_with_mcp()` method
   - Fetch entities using `external_client.get_all_XXX_entities()`
   - Include FULL definitions in prompt

2. **For enhanced extractors** (Step 2):
   - **CRITICAL PATTERN**: Must fetch MCP data dynamically when include_mcp_context=True
   - Don't rely on existing_entities parameter being provided
   - Add dynamic fetching block:
   ```python
   if include_mcp_context:
       try:
           if existing_entities is None:
               from app.services.external_mcp_client import get_external_mcp_client
               external_client = get_external_mcp_client()
               existing_entities = external_client.get_all_XXX_entities()
               # Also fetch related entities for Pass context
           # Build hierarchical context...
       except Exception as e:
           logger.error(f"Failed to fetch MCP context: {e}")
   ```
   - Pass definitions to prompt generator
   - Ensure definitions are included in prompt

## Testing Pattern

```python
# Quick test script
from app.services.extraction.XXX import XXXExtractor
extractor = XXXExtractor()
prompt = extractor._get_prompt_for_preview("test text")
print("MCP integrated:" if "EXISTING" in prompt else "No MCP")
print(f"Prompt length: {len(prompt)}")
```

## Key Insights

1. **Definitions are critical**: The LLM needs the actual definitions, not just labels
2. **Dynamic fetching**: Definitions must come from MCP server at runtime
3. **Graceful fallback**: Always have fallback if MCP unavailable
4. **Count verification**: Dynamic counts prove MCP integration is working

## Critical Requirements

### Recursive CTE Query Pattern (MUST USE)
**IMPORTANT**: MCP must use recursive CTE queries to find entity subclasses via `parent_uri` relationships, NOT label matching. This is the semantically correct approach using actual subClassOf relationships.

```sql
WITH RECURSIVE category_hierarchy AS (
    -- Base: Find the category class (e.g., Obligation)
    SELECT uri, label, parent_uri 
    FROM ontology_entities 
    WHERE label = 'CategoryName' AND entity_type = 'class'
    
    UNION
    
    -- Recursive: Find all subclasses via parent_uri
    SELECT e.uri, e.label, e.parent_uri
    FROM ontology_entities e
    INNER JOIN category_hierarchy ch ON e.parent_uri = ch.uri
    WHERE e.entity_type = 'class'
)
```

This pattern is implemented in `/home/chris/onto/OntServe/storage/concept_manager_database.py` and MUST be used for all entity categories.

## Next Steps

1. ✅ Roles - Complete
2. ✅ States - Complete  
3. ✅ Resources - Complete
4. ✅ **Principles** - Complete (12 entities, both extractors working)
5. ✅ **Obligations** - Complete (14 entities, both extractors working)
6. ✅ **Constraints** - Complete (17 entities, enhanced prompt working)
7. ⚠️ Actions - Missing MCP method
8. ⚠️ Events - Missing MCP method
9. ⚠️ Capabilities - Missing MCP method
