# LLM Integration Index

**Last Updated**: 2025-01-24  
**Status**: Active Implementation

## Core LLM Services

### 1. Base LLM Service (`/app/services/llm_service.py`)
Central service managing all LLM interactions in the application.

**Key Features**:
- Conversation history management
- Message formatting and role handling
- MCP client integration for tool use
- Provider abstraction (Claude, OpenAI, Mock)
- Error handling and retry logic

**Usage Example**:
```python
from app.services.llm_service import LLMService
llm_service = LLMService()
response = await llm_service.get_completion(messages, system_prompt)
```

### 2. Claude Service (`/app/services/claude_service.py`)
Anthropic Claude-specific implementation.

**Key Features**:
- API key validation
- Model selection (Claude 3.7 Sonnet)
- Mock fallback for testing
- Token management
- Streaming support

### 3. LangChain Integration (`/app/services/langchain_claude.py`)
Wrapper for using Claude with LangChain framework.

**Key Features**:
- Structured prompting
- Chain composition
- Memory management
- Tool integration

## Specialized LLM Services

### 4. Guideline Analysis (`/app/services/guideline_analysis_service.py`)
Extracts ontology concepts from ethical guidelines.

**Workflow**:
1. Parse guideline text
2. Extract ethical concepts using LLM
3. Map to ontology entities
4. Generate RDF triples

### 5. Decision Engine (`/app/services/decision_engine.py`)
LLM-powered ethical decision reasoning.

**Components**:
- Context gathering
- Ethical principle application
- Decision generation
- Justification creation

### 6. Case URL Processor (`/app/services/case_url_processor/llm_extractor.py`)
Extracts structured case data from web content.

**Process**:
1. Fetch URL content
2. Clean HTML
3. Extract case sections using LLM
4. Validate structure

## Experiment Services

### 7. Prediction Service (`/app/services/experiment/prediction_service.py`)
Core experiment service for case conclusion prediction.

**Modes**:
- **Ontology-Augmented**: Uses ontology concepts and relationships
- **Prompt-Only**: Direct LLM reasoning without ontology

**Versions**:
- `prediction_service.py` - Original implementation
- `prediction_service_fixed.py` - Bug fixes
- `prediction_service_ontology_fixed.py` - Enhanced ontology integration
- `prediction_service_clean.py` - Refactored version

### 8. Similar Case Finder (`/app/services/experiment/find_similar_cases.py`)
Uses embeddings to find similar cases for context.

## Agent Module Integration

### 9. Agent LLM Service (`/app/agent_module/services/llm_service.py`)
Specialized for agent-based interactions.

**Features**:
- Agent personality management
- Context window optimization
- Multi-turn conversations

### 10. ProEthica Adapter (`/app/agent_module/adapters/proethica.py`)
Adapts LLM for ProEthica-specific tasks.

## MCP LLM Integration

### 11. Hosted LLM MCP Server (`/mcp/hosted_llm_mcp/`)
Provides LLM capabilities through MCP protocol.

**Components**:
- `server.py` - Main server implementation
- `adapters/anthropic_adapter.py` - Claude integration
- `adapters/openai_adapter.py` - OpenAI integration
- `adapters/model_router.py` - Route between providers

### 12. Guideline Analysis Module (`/mcp/modules/guideline_analysis_module.py`)
MCP module for guideline concept extraction.

**Tools**:
- `extract_concepts` - Extract concepts from text
- `generate_triples` - Create RDF triples
- `match_to_ontology` - Map concepts to ontology

## Triple Association

### 13. LLM Section-Triple Associator (`/ttl_triple_association/llm_section_triple_associator.py`)
Associates document sections with ontology triples using LLM reasoning.

**Process**:
1. Analyze section content
2. Identify relevant ontology concepts
3. Generate associations with confidence scores
4. Store in database

## Configuration and Testing

### 14. Configuration Files
- `/config.py` - Main configuration with API keys
- `/app/config.py` - Application-specific settings
- `/app/config/codespace.py` - Environment-specific config

### 15. Test Scripts
- `/scripts/test_llm_api.py` - Test API connectivity
- `/scripts/check_claude_api.py` - Verify Claude access
- `/scripts/simple_claude_test.py` - Basic functionality test
- `/test/test_anthropic_integration.py` - Integration tests

## Utility Functions

### 16. LLM Utils (`/app/utils/llm_utils.py`)
Helper functions for LLM operations:
- Client instantiation
- Model selection
- Error handling
- Token counting

## Current Implementation Status

### Active Services
✅ Core LLM Service  
✅ Claude Integration  
✅ Guideline Analysis  
✅ Case Processing  
✅ Experiment Predictions  
✅ MCP Integration  

### In Development
🚧 Enhanced Decision Engine  
🚧 Multi-agent Orchestration  
🚧 Advanced Similarity Search  

### Planned
📋 GPT-4 Integration  
📋 Local Model Support  
📋 Streaming Responses  

## Usage Patterns

### 1. Direct LLM Call
```python
llm_service = LLMService()
response = llm_service.complete(prompt)
```

### 2. With Context
```python
llm_service = LLMService()
llm_service.add_message("user", user_input)
llm_service.add_message("assistant", previous_response)
response = llm_service.complete(new_prompt)
```

### 3. Ontology-Enhanced
```python
prediction_service = PredictionService()
result = prediction_service.predict_with_ontology(
    case_data, 
    ontology_concepts
)
```

## Performance Considerations

- **Rate Limiting**: Implemented in Claude service
- **Token Management**: Context window tracking
- **Caching**: Response caching for repeated queries
- **Fallback**: Mock LLM for development/testing