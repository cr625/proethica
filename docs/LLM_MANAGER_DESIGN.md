# Centralized LLM Manager Design

**Created:** November 16, 2025
**Status:** Design Phase
**Goal:** Centralize LLM management with easy model switching and consistent configuration

---

## Problem Statement

The codebase currently has:
- **76 hardcoded model references** across 49 files
- **3 different client patterns** (llm_utils, direct Anthropic, ClaudeService)
- **Scattered timeout/retry logic** (CLAUDE.md documents Sonnet 4.5 timeouts, fixed ad-hoc)
- **Duplicated error handling** (mock fallback logic repeated)
- **Difficult model switching** (requires changing 49+ files)

## Design Goals

1. **Single Source of Truth** - One place to configure models
2. **Easy Model Switching** - Change model in one config file/env var
3. **Consistent Behavior** - Timeout, retry, error handling unified
4. **Provider Abstraction** - Support Anthropic, OpenAI, future providers
5. **Backward Compatible** - Incremental migration path
6. **Usage Tracking** - Built-in token usage and cost tracking

---

## Architecture

### 1. Core LLM Manager (`app/services/llm/manager.py`)

```python
class LLMManager:
    """Centralized LLM management with provider abstraction."""

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize with optional config, defaults to ModelConfig."""
        pass

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,  # Override default
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: Optional[Timeout] = None,
        retry_config: Optional[RetryConfig] = None,
        metadata: Optional[Dict] = None  # For tracking/logging
    ) -> LLMResponse:
        """
        Unified completion interface for all providers.

        Returns:
            LLMResponse with text, usage, metadata
        """
        pass

    def switch_model(self, model_name: str):
        """Dynamically switch model (useful for testing)."""
        pass

    def get_usage_stats(self) -> UsageStats:
        """Get token usage and estimated costs."""
        pass
```

### 2. Configuration (`app/services/llm/config.py`)

```python
@dataclass
class LLMConfig:
    """Configuration for LLM manager."""

    # Model selection
    default_model: str = field(default_factory=lambda: ModelConfig.get_default_model())
    fast_model: str = field(default_factory=lambda: ModelConfig.get_claude_model("fast"))
    powerful_model: str = field(default_factory=lambda: ModelConfig.get_claude_model("powerful"))

    # Timeout configuration (addresses Sonnet 4.5 issues documented in CLAUDE.md)
    default_timeout: Timeout = Timeout(connect=10.0, read=180.0, write=180.0, pool=180.0)

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 2.0  # Exponential backoff base

    # Provider fallback
    enable_provider_fallback: bool = True
    fallback_providers: List[str] = field(default_factory=lambda: ["anthropic", "openai"])

    # Usage tracking
    track_usage: bool = True
    log_requests: bool = False  # For debugging

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        return cls(
            default_model=os.getenv("LLM_DEFAULT_MODEL") or ModelConfig.get_default_model(),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            track_usage=os.getenv("LLM_TRACK_USAGE", "true").lower() == "true",
        )
```

### 3. Response Format (`app/services/llm/response.py`)

```python
@dataclass
class LLMResponse:
    """Unified response format across providers."""

    text: str
    model: str
    provider: str
    usage: Usage
    metadata: Dict[str, Any]

    # For provenance tracking integration
    request_id: Optional[str] = None
    timestamp: Optional[datetime] = None

@dataclass
class Usage:
    """Token usage information."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: Optional[float] = None  # Based on provider pricing
```

### 4. Provider Adapters (`app/services/llm/providers/`)

```python
class BaseProvider(ABC):
    """Abstract base for provider adapters."""

    @abstractmethod
    def complete(self, messages: List[Message], **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        pass

class AnthropicProvider(BaseProvider):
    """Anthropic/Claude provider with timeout handling."""

    def complete(self, messages, model, max_tokens, timeout, **kwargs):
        # Handles Sonnet 4 vs 4.5 logic
        # Applies timeout configuration
        # Parses markdown-wrapped JSON (common issue)
        pass

class OpenAIProvider(BaseProvider):
    """OpenAI provider."""
    pass
```

---

## Migration Strategy

### Phase 1: Infrastructure (Week 1)

1. ✅ Create LLM manager core modules
2. ✅ Write comprehensive tests
3. ✅ Add to pyproject.toml dependencies
4. ✅ Document usage patterns

### Phase 2: Service Integration (Week 2-3)

**Priority Order:**

1. **High-impact services** (most LLM calls):
   - `app/services/extraction/` - All extractors (~15 files)
   - `app/services/guideline_analysis_service.py`
   - `app/services/scenario_pipeline/` extractors (~5 files)

2. **Medium-impact services**:
   - `app/services/temporal_dynamics/extractors/` (~7 files)
   - Question/conclusion services (~4 files)

3. **Low-impact services**:
   - Experimental services
   - Legacy services

**Migration Pattern:**

```python
# BEFORE (hardcoded, scattered)
from app.utils.llm_utils import get_llm_client

llm_client = get_llm_client()
response = llm_client.messages.create(
    model="claude-sonnet-4-20250514",  # HARDCODED
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)
response_text = response.content[0].text

# AFTER (centralized, configurable)
from app.services.llm.manager import get_llm_manager

llm = get_llm_manager()
response = llm.complete(
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2000,
    metadata={"extraction_type": "roles"}
)
response_text = response.text
```

### Phase 3: Deprecation (Week 4)

1. Mark old patterns as deprecated
2. Add deprecation warnings
3. Update documentation
4. Remove fallback compatibility

---

## Configuration Examples

### Environment Variables

```bash
# Model Selection
LLM_DEFAULT_MODEL=claude-sonnet-4-20250514
LLM_FAST_MODEL=claude-sonnet-4-20250514
LLM_POWERFUL_MODEL=claude-opus-4-1-20250805

# Timeout Configuration
LLM_READ_TIMEOUT=180.0
LLM_CONNECT_TIMEOUT=10.0

# Retry Configuration
LLM_MAX_RETRIES=3
LLM_RETRY_DELAY=2.0

# Usage Tracking
LLM_TRACK_USAGE=true
LLM_LOG_REQUESTS=false  # Enable for debugging
```

### Python Configuration

```python
# config.py addition
class Config:
    # ... existing config ...

    # LLM Configuration
    LLM_DEFAULT_MODEL = os.getenv("LLM_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    LLM_TRACK_USAGE = os.getenv("LLM_TRACK_USAGE", "true").lower() == "true"
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
```

---

## Usage Examples

### Basic Usage

```python
from app.services.llm.manager import get_llm_manager

llm = get_llm_manager()

# Simple completion
response = llm.complete(
    messages=[
        {"role": "user", "content": "Extract roles from this text..."}
    ]
)

print(response.text)
print(f"Used {response.usage.total_tokens} tokens")
```

### Override Model

```python
# Use powerful model for complex reasoning
response = llm.complete(
    messages=[...],
    model=ModelConfig.CLAUDE_MODELS["powerful"],  # Opus 4.1
    max_tokens=4000
)
```

### With Timeout

```python
from httpx import Timeout

# Custom timeout for long operations
response = llm.complete(
    messages=[...],
    timeout=Timeout(read=300.0)  # 5 minutes
)
```

### Usage Tracking

```python
# Get usage stats
stats = llm.get_usage_stats()
print(f"Total tokens: {stats.total_tokens}")
print(f"Estimated cost: ${stats.total_cost_usd:.2f}")
print(f"Calls by model: {stats.model_breakdown}")
```

---

## Benefits

### For Development

- **Easy A/B Testing**: Switch models with one env var change
- **Consistent Behavior**: All services use same timeout/retry logic
- **Better Debugging**: Centralized logging and request tracking
- **Cost Monitoring**: Built-in token usage tracking

### For Production

- **Reliability**: Centralized retry and fallback logic
- **Performance**: Easy to switch to faster models for specific tasks
- **Cost Control**: Track and optimize token usage
- **Flexibility**: Add new providers without changing service code

### For Maintenance

- **Single Update Point**: Change timeout once, affects all services
- **Clear Migration Path**: Incremental refactoring
- **Type Safety**: Clear interfaces and type hints
- **Testing**: Mock LLM manager instead of mocking 49 files

---

## Related Issues Addressed

From CLAUDE.md:

1. **Sonnet 4.5 Timeout Issues** ✅
   - Centralized timeout configuration
   - Easy model switching for testing
   - Documented in one place

2. **URI Bloat in Prompts** ✅
   - Helper methods for sanitizing prompts
   - Consistent preprocessing

3. **JSON Parsing Failures** ✅
   - Centralized markdown-wrapped JSON detection
   - Consistent error handling

---

## Testing Strategy

### Unit Tests

```python
def test_llm_manager_anthropic():
    """Test Anthropic provider integration."""

def test_llm_manager_model_switching():
    """Test dynamic model switching."""

def test_llm_manager_timeout():
    """Test timeout configuration."""

def test_llm_manager_retry():
    """Test retry logic with exponential backoff."""

def test_llm_manager_usage_tracking():
    """Test token usage tracking."""
```

### Integration Tests

```python
def test_extraction_service_with_llm_manager():
    """Test roles extractor using LLM manager."""

def test_multiple_services_same_manager():
    """Test shared LLM manager across services."""
```

---

## Open Questions

1. **Caching Strategy**: Should we cache LLM responses for identical prompts?
2. **Rate Limiting**: Do we need built-in rate limiting for API quotas?
3. **Model Routing**: Should certain tasks automatically use specific models?
4. **Async Support**: Do we need async/await for concurrent LLM calls?

---

## References

- **Current Issues**: See CLAUDE.md Sections on Sonnet 4.5 timeouts, JSON parsing
- **Model Configuration**: `models.py` ModelConfig class
- **Utility Functions**: `app/utils/llm_utils.py`
- **Provider Docs**:
  - [Anthropic API](https://docs.anthropic.com/en/api/messages)
  - [OpenAI API](https://platform.openai.com/docs/api-reference/chat)

---

## Next Steps

1. Review this design with stakeholders
2. Create implementation branch
3. Implement Phase 1 (infrastructure)
4. Start Phase 2 migration with high-impact services
5. Monitor token usage and performance improvements
