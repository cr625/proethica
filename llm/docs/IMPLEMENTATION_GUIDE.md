# LLM Implementation Guide

## Getting Started

### 1. Configuration Setup

Set the required environment variables in `.env`:

```bash
# Primary LLM Provider
ANTHROPIC_API_KEY=your-anthropic-key
CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219
USE_CLAUDE=true

# Optional: OpenAI as fallback
OPENAI_API_KEY=your-openai-key

# Development/Testing
USE_MOCK_FALLBACK=false  # Set to true for testing without API calls
```

### 2. Basic LLM Usage

#### Simple Completion
```python
from app.services.llm_service import LLMService

# Initialize service
llm = LLMService()

# Get a completion
response = llm.complete("What are the key ethical principles in engineering?")
print(response)
```

#### With Conversation History
```python
# Add messages to maintain context
llm.add_message("user", "What is professional responsibility?")
llm.add_message("assistant", "Professional responsibility refers to...")
llm.add_message("user", "How does it apply to software engineering?")

# Get contextual response
response = llm.complete("Provide specific examples")
```

### 3. Specialized Services

#### Guideline Analysis
```python
from app.services.guideline_analysis_service import GuidelineAnalysisService

service = GuidelineAnalysisService()
result = service.extract_concepts(
    guideline_text="Engineers shall hold paramount the safety...",
    guideline_name="NSPE Code Section I.1"
)

# Result contains:
# - concepts: List of extracted ethical concepts
# - triples: RDF triples representing relationships
# - metadata: Additional analysis information
```

#### Case Prediction (Experiments)
```python
from app.services.experiment.prediction_service import PredictionService

predictor = PredictionService()

# Predict with ontology enhancement
result = predictor.predict_with_ontology(
    case_data={
        "facts": "Engineer discovers safety issue...",
        "questions": ["Should the engineer report?"],
        "discussion": "Analysis of ethical obligations..."
    },
    ontology_concepts=["public_safety", "confidentiality"]
)

# Predict without ontology (baseline)
baseline = predictor.predict_prompt_only(case_data)
```

#### Decision Engine
```python
from app.services.decision_engine import DecisionEngine

engine = DecisionEngine()
decision = engine.make_decision(
    scenario="Engineer faces conflict between employer and public",
    context={
        "stakeholders": ["employer", "public", "profession"],
        "principles": ["loyalty", "public_safety", "honesty"],
        "constraints": ["employment_contract", "professional_code"]
    }
)
```

### 4. MCP Integration

#### Using MCP Tools
```python
from app.services.enhanced_mcp_client import EnhancedMCPClient

mcp_client = EnhancedMCPClient()

# Get ontology entities
entities = await mcp_client.get_entities(entity_type="Condition")

# Query relationships
relationships = await mcp_client.get_entity_relationships(
    entity_uri="http://proethica.org/ontology#PublicSafety"
)

# Use in LLM context
llm = LLMService()
llm.mcp_client = mcp_client
response = llm.complete_with_tools(
    "What conditions affect public safety?",
    available_tools=["get_entities", "get_entity_relationships"]
)
```

### 5. Error Handling

#### API Failures
```python
try:
    response = llm.complete(prompt)
except Exception as e:
    if "rate_limit" in str(e):
        # Handle rate limiting
        time.sleep(60)
        response = llm.complete(prompt)
    elif "api_key" in str(e):
        # Fall back to mock
        llm.use_mock = True
        response = llm.complete(prompt)
    else:
        raise
```

#### Mock Mode
```python
# Force mock mode for testing
import os
os.environ['USE_MOCK_FALLBACK'] = 'true'

llm = LLMService()  # Will use FakeListLLM
response = llm.complete("Test prompt")  # Returns predictable test response
```

### 6. Advanced Usage

#### Custom Prompts
```python
from app.services.llm_service import LLMService

llm = LLMService()

# With system prompt
response = llm.complete(
    prompt="Analyze this case",
    system_prompt="You are an expert in engineering ethics with 20 years experience."
)

# With structured output
response = llm.complete(
    prompt="Extract key facts from: " + case_text,
    system_prompt="Return a JSON object with keys: facts, actors, issues"
)
```

#### Streaming Responses
```python
# Note: Streaming not yet fully implemented
async def stream_response(prompt):
    async for chunk in llm.stream_complete(prompt):
        print(chunk, end='', flush=True)
```

#### Token Management
```python
# Check token usage
from app.utils.llm_utils import count_tokens

prompt = "Long text..."
token_count = count_tokens(prompt, model="claude-3-sonnet")

if token_count > 100000:  # Claude's context limit
    # Truncate or summarize
    prompt = truncate_to_token_limit(prompt, 100000)
```

### 7. Testing

#### Unit Tests
```python
def test_llm_service():
    # Use mock for deterministic testing
    os.environ['USE_MOCK_FALLBACK'] = 'true'
    
    llm = LLMService()
    response = llm.complete("Test")
    
    assert response is not None
    assert isinstance(response, str)
```

#### Integration Tests
```python
@pytest.mark.integration
def test_claude_api():
    # Skip if no API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        pytest.skip("No API key available")
    
    llm = LLMService()
    response = llm.complete("Hello")
    assert len(response) > 0
```

### 8. Performance Tips

1. **Caching**: Implement response caching for repeated queries
2. **Batching**: Group similar requests to reduce API calls
3. **Context Management**: Keep conversation history concise
4. **Async Operations**: Use async methods for concurrent requests
5. **Rate Limiting**: Implement backoff strategies

### 9. Common Patterns

#### Ontology-Enhanced Generation
```python
# Pattern: Retrieve context, then generate
entities = mcp_client.get_entities("Role")
context = format_entities_for_llm(entities)

response = llm.complete(
    f"Given these roles:\n{context}\n\nAnalyze the case..."
)
```

#### Multi-Step Reasoning
```python
# Pattern: Break complex tasks into steps
step1 = llm.complete("Extract facts from: " + case_text)
step2 = llm.complete(f"Given facts: {step1}\nIdentify ethical issues")
step3 = llm.complete(f"Given issues: {step2}\nPropose resolution")
```

#### Validation and Retry
```python
# Pattern: Validate and retry with clarification
def get_structured_response(prompt, max_retries=3):
    for i in range(max_retries):
        response = llm.complete(prompt)
        try:
            # Validate structure
            data = json.loads(response)
            if all(key in data for key in ['facts', 'issues']):
                return data
        except:
            prompt += "\nPlease return valid JSON with 'facts' and 'issues' keys."
    raise ValueError("Failed to get valid response")
```

## Troubleshooting

### Common Issues

1. **API Key Errors**: Check `.env` file and environment variables
2. **Rate Limits**: Implement exponential backoff
3. **Context Too Long**: Truncate or summarize inputs
4. **Invalid JSON**: Add explicit format instructions to prompts
5. **Mock Not Working**: Ensure `USE_MOCK_FALLBACK=true` is set

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Support

For issues or questions:
1. Check existing tests in `/test/`
2. Review examples in `/scripts/`
3. Consult team documentation