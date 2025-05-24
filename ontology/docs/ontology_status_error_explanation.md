# Guideline Analysis Issue: LLM Client Initialization Error

## Problem Overview

When clicking on the "Analyze" button for guideline documents, users were encountering the following error message:

```
Error analyzing guideline: LLM client not available
```

This error occurred despite the system appearing to successfully extract concepts as shown in the console logs:

```log
2025-05-14 00:57:52,711 - app.services.guideline_analysis_service - INFO - Extracting concepts from guideline content with ontology source: engineering-ethics
2025-05-14 00:57:52,712 - app.services.guideline_analysis_service - INFO - Attempting to use MCP server at http://localhost:5001 for concept extraction
2025-05-14 00:57:52,717 - app.services.guideline_analysis_service - INFO - Successfully extracted concepts using MCP server
```

## Root Cause

The issue was found in the `guideline_analysis_service.py` file. While the service was successfully connecting to the MCP server and extracting concepts via the JSON-RPC API, it did not properly handle LLM client initialization errors in the fallback path. When the MCP server successfully processes a request but later parts of the workflow need the LLM client, the system would fail with an unhelpful error message.

Specifically:
1. The MCP server was correctly processing the initial concept extraction
2. Later operations such as concept matching or triple generation might still require the LLM client
3. The code was not properly catching and handling LLM client initialization errors

## Solution

The solution implements proper error handling for LLM client initialization in the guideline analysis service:

1. Added explicit try/except blocks around `get_llm_client()` calls
2. Added proper error messages that clearly indicate when the LLM client is unavailable
3. Ensured the error is propagated with a descriptive message to the user interface
4. Improved error status returns to include both the error message and an empty result set (instead of crashing)

The fix ensures that:
- The system provides clear error messages when the LLM client is not available
- Operations continue to work via the MCP server path when possible
- The UI shows a meaningful error message rather than a generic failure

## Code Changes

The main change was in the `extract_concepts`, `match_concepts`, and `generate_triples` methods of the `GuidelineAnalysisService` class. Each method now has robust error handling for LLM client initialization:

```python
# Before LLM processing
try:
    llm_client = get_llm_client()
except RuntimeError as e:
    logger.error(f"LLM client not available: {str(e)}")
    return {"error": "LLM client not available", "concepts": []}
except Exception as e:
    logger.error(f"Error initializing LLM client: {str(e)}")
    return {"error": f"Error initializing LLM client: {str(e)}", "concepts": []}
```

Similar handling was added to the other methods that use the LLM client, ensuring a consistent approach to error handling throughout the service.

## Related Systems

This change affects the following components:
- Guideline Analysis Service
- MCP Client integration
- LLM client initialization
- The Guidelines UI workflow

## Testing

The fix has been tested by:
1. Running the system with the updated service
2. Verifying that the system handles LLM client unavailability gracefully
3. Confirming the proper error message is shown in the UI

## Future Improvements

For future development:
1. Implement a more comprehensive status check for LLM client availability
2. Add a system-wide LLM client status indicator
3. Consider implementing a mock LLM client for testing and fallback purposes
4. Add configuration options to completely disable LLM fallback when only using MCP server
