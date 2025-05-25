# LLM Provider Configuration

## Supported Providers

### 1. Anthropic Claude (Primary)

**Models Available**:
- `claude-3-7-sonnet-20250219` (Default)
- `claude-3-opus-20240229` (Higher capability, higher cost)
- `claude-3-haiku-20240307` (Faster, lower cost)

**Configuration**:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219
USE_CLAUDE=true
```

**Key Features**:
- 200k token context window
- Strong reasoning capabilities
- Good at following complex instructions
- Supports system prompts
- No native function calling (use MCP instead)

**Rate Limits**:
- Tier 1: 50 requests/minute
- Tier 2: 1000 requests/minute
- Tier 3: 2000 requests/minute

### 2. OpenAI (Secondary)

**Models Available**:
- `gpt-4-turbo-preview`
- `gpt-4`
- `gpt-3.5-turbo`

**Configuration**:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

**Key Features**:
- Function calling support
- JSON mode for structured output
- Lower latency than Claude
- Smaller context window (128k for GPT-4 Turbo)

**Usage**:
Currently used for:
- Embedding generation (when Claude embeddings unavailable)
- Fallback for rate limit scenarios
- Specific tasks requiring function calling

### 3. Mock LLM (Development)

**Configuration**:
```bash
USE_MOCK_FALLBACK=true
```

**Features**:
- Deterministic responses for testing
- No API calls or costs
- Instant responses
- Configurable response patterns

**Response Patterns**:
```python
# In FakeListLLM configuration
responses = [
    "This is a mock response for testing.",
    "The ethical principle involved is public safety.",
    '{"facts": ["fact1", "fact2"], "issues": ["issue1"]}',
]
```

## Provider Selection Logic

```python
# Priority order in LLMService
1. Check USE_CLAUDE flag
   - If true and API key exists → Use Claude
   - If true but no API key → Fall back to mock
   
2. Check USE_MOCK_FALLBACK
   - If true → Use mock regardless
   
3. Check OPENAI_API_KEY
   - If exists → Use OpenAI as fallback
   
4. Default to mock with warning
```

## Provider-Specific Implementations

### Claude Implementation
```python
# app/services/claude_service.py
class ClaudeService:
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.model = os.getenv('CLAUDE_MODEL_VERSION')
        
    def generate(self, prompt, system=None):
        if not self.api_key:
            return self._mock_response(prompt)
            
        response = anthropic.Anthropic(
            api_key=self.api_key
        ).messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=4000
        )
        return response.content[0].text
```

### OpenAI Implementation
```python
# In langchain integration
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0.7,
    api_key=os.getenv('OPENAI_API_KEY')
)
```

### Mock Implementation
```python
# Using LangChain FakeListLLM
from langchain.llms.fake import FakeListLLM

mock_llm = FakeListLLM(
    responses=[
        "Mock response 1",
        "Mock response 2"
    ]
)
```

## Cost Considerations

### Claude Pricing (as of 2024)
- **Sonnet**: $3 per million input tokens, $15 per million output tokens
- **Opus**: $15 per million input tokens, $75 per million output tokens
- **Haiku**: $0.25 per million input tokens, $1.25 per million output tokens

### OpenAI Pricing
- **GPT-4 Turbo**: $10 per million input tokens, $30 per million output tokens
- **GPT-3.5 Turbo**: $0.50 per million input tokens, $1.50 per million output tokens

### Cost Optimization Strategies
1. Use Haiku for simple tasks
2. Cache responses for repeated queries
3. Implement prompt compression
4. Use mock for development
5. Monitor token usage

## Switching Providers

### Runtime Switching
```python
# Change provider at runtime
os.environ['USE_CLAUDE'] = 'false'
os.environ['OPENAI_API_KEY'] = 'sk-...'

# Reinitialize service
llm = LLMService()  # Will now use OpenAI
```

### Per-Request Provider
```python
# Not yet implemented, but planned
response = llm.complete(
    prompt="...",
    provider="openai",  # Force specific provider
    model="gpt-4"
)
```

## Provider Capabilities Matrix

| Feature | Claude 3.7 | GPT-4 Turbo | Mock |
|---------|------------|-------------|------|
| Context Window | 200k | 128k | Unlimited |
| Function Calling | Via MCP | Native | Simulated |
| Streaming | Yes | Yes | No |
| JSON Mode | Manual | Native | Pre-configured |
| System Prompts | Yes | Yes | Limited |
| Rate Limits | Tier-based | Tier-based | None |
| Cost | Medium | High | Free |

## Future Provider Support

### Planned Additions
1. **Local Models**
   - Ollama integration
   - HuggingFace models
   - GGUF format support

2. **Other Cloud Providers**
   - Google Gemini
   - Cohere
   - AI21 Labs

3. **Specialized Models**
   - Code-specific models
   - Domain-specific fine-tunes
   - Custom trained models

## Provider-Specific Best Practices

### Claude
- Use system prompts for role definition
- Structure outputs with clear formatting
- Leverage large context for few-shot examples
- Avoid unnecessary conversation history

### OpenAI
- Use function calling for structured data
- Enable JSON mode for reliable parsing
- Prefer GPT-4 Turbo for complex reasoning
- Use GPT-3.5 for simple extractions

### Mock
- Define comprehensive response sets
- Test edge cases and errors
- Use for regression testing
- Simulate rate limits and failures