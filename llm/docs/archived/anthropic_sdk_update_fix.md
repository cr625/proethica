# Anthropic SDK Compatibility Fix

## Issue

The AI-Ethical-DM project experienced an issue with JSON responses from the Anthropic Claude API. The code was attempting to use the `response_format` parameter which is not supported in the current Anthropic SDK version, resulting in warning messages:

```
LLM returned natural language instead of JSON. Attempting to generate fallback concepts.
```

And error logs:
```
First approach failed: AsyncMessages.create() got an unexpected keyword argument 'response_format'
```

## Root Cause

The `response_format` parameter is not supported in the installed version of the Anthropic SDK. Unlike OpenAI's API which has a dedicated `response_format` parameter for JSON output, Anthropic's recommended approach is to handle structured output through prompt engineering.

## Solution

The fix (implemented on 2025-05-18) simplified the approach in `mcp/modules/guideline_analysis_module.py` by:

1. Removing the attempt to use the `response_format` parameter
2. Using only the prompt engineering approach (which was previously the fallback method)
3. Updating the logging messages to be clearer

The code now follows Anthropic's recommended approach for structured output as documented at:
https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency#chain-prompts-for-complex-tasks

## Benefits

- Eliminated warning messages during guideline concept extraction
- Simplified code with a single approach instead of multi-tier fallback
- Improved reliability by using the confirmed working method
- Follows best practices recommended by Anthropic

## Future Considerations

If a future version of the Anthropic SDK adds support for the `response_format` parameter, the code could be updated to use that parameter for more reliable JSON output. However, the current prompt engineering approach is working well and provides good results.
