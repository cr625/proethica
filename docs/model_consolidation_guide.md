# Model Configuration Consolidation Guide

## Overview
This guide explains the new centralized model configuration system introduced to simplify model management and support the new Claude models (Opus 4 and Sonnet 4).

## Migration Steps

### 1. Update Environment Variables
Replace old environment variables:
- `CLAUDE_MODEL_VERSION` → `CLAUDE_DEFAULT_MODEL`
- `ANTHROPIC_MODEL` → `CLAUDE_DEFAULT_MODEL`

New environment variables:
- `CLAUDE_DEFAULT_MODEL`: Default model for general use (default: claude-sonnet-4-20250514)
- `CLAUDE_FAST_MODEL`: Fast model for quick responses (default: claude-sonnet-4-20250514)
- `CLAUDE_POWERFUL_MODEL`: Powerful model for complex tasks (default: claude-opus-4-20250514)

### 2. Update Code References

#### Import ModelConfig
```python
from config.models import ModelConfig
```

#### Get Model for Use Case
```python
# Instead of hardcoding:
# model = "claude-3-7-sonnet-20250219"

# Use:
model = ModelConfig.get_claude_model("default")  # General use
model = ModelConfig.get_claude_model("fast")     # Quick responses
model = ModelConfig.get_claude_model("powerful") # Complex tasks
```

#### For Backward Compatibility
```python
# This will check old env vars and map to new models
model = ModelConfig.get_default_model()
```

### 3. Service-Specific Updates

#### LLM Service
- Update `app/services/llm_service.py` to use ModelConfig
- Replace hardcoded model references

#### Claude Service
- Update `app/services/claude_service.py` to use ModelConfig
- Remove duplicate model definitions

#### MCP Servers
- Update all MCP server configurations to use ModelConfig
- Ensure consistent model usage across modules

### 4. Test Files
Test files can continue using specific model versions for reproducibility:
```python
# In test files only
test_model = ModelConfig.CLAUDE_MODELS["legacy_sonnet"]
```

## Model Mapping

| Old Model | New Model | Use Case |
|-----------|-----------|----------|
| claude-3-7-sonnet-20250219 | claude-sonnet-4-20250514 | Default |
| claude-3-sonnet-20240229 | claude-sonnet-4-20250514 | Default |
| claude-3-opus-20240229 | claude-opus-4-20250514 | Powerful |
| claude-3.5-sonnet-latest | claude-sonnet-4-20250514 | Default |
| claude-3.5-opus-latest | claude-opus-4-20250514 | Powerful |
| claude-3-haiku-20240307 | claude-3-haiku-20240307 | Legacy |

## Latest Claude Models (January 2025)

Based on Anthropic's latest release:
- **Claude Opus 4** (`claude-opus-4-20250514`): The world's best coding model with superior performance on complex tasks
  - Pricing: $15/$75 per million tokens (input/output)
  - Best for: Complex coding, long-running tasks, agent workflows
  
- **Claude Sonnet 4** (`claude-sonnet-4-20250514`): Significant upgrade with superior coding and reasoning
  - Pricing: $3/$15 per million tokens (input/output)
  - Best for: General use, fast responses with excellent quality

## Benefits

1. **Single Source of Truth**: All model configurations in one place
2. **Easy Updates**: Change models by updating environment variables
3. **Use Case Specific**: Different models for different needs
4. **Backward Compatible**: Old environment variables still work
5. **Future Proof**: Easy to add new models as they become available

## Next Steps

1. Update all services to use ModelConfig
2. Update deployment configurations
3. Test with new model versions
4. Remove hardcoded model references