# LLM Integration Documentation

This directory contains comprehensive documentation for all Large Language Model (LLM) integrations in the ProEthica AI Ethical Decision-Making system.

## Overview

The ProEthica system uses LLMs for various tasks including:
- Case analysis and information extraction
- Ethical guideline interpretation
- Ontology concept mapping
- Decision reasoning and simulation
- Experiment prediction tasks

## Directory Structure

### `/docs/` - Documentation
- **[INDEX.md](docs/INDEX.md)** - Complete index of LLM integration points
- **[IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** - How to use LLM services
- **[PROVIDERS.md](docs/PROVIDERS.md)** - LLM provider configurations
- **[USE_CASES.md](docs/USE_CASES.md)** - Detailed use cases for LLM integration

### Archived Documentation
Historical and planning documents have been consolidated here from various locations in the repository.

## Quick Start

1. **For Developers**: Start with [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)
2. **For Configuration**: See [PROVIDERS.md](docs/PROVIDERS.md)
3. **For Architecture**: Review [INDEX.md](docs/INDEX.md)

## Key Services

### Core LLM Service
- **Location**: `/app/services/llm_service.py`
- **Purpose**: Central service for all LLM interactions
- **Features**: Conversation management, MCP integration, provider abstraction

### Claude Service
- **Location**: `/app/services/claude_service.py`
- **Purpose**: Anthropic Claude-specific implementation
- **Features**: API key management, mock fallback, error handling

### Experiment Services
- **Location**: `/app/services/experiment/`
- **Purpose**: LLM-powered case analysis experiments
- **Features**: Prediction with/without ontology, similarity search

## Configuration

LLM settings are managed through environment variables:
```bash
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
USE_CLAUDE=true
CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219
```

## Testing

Mock LLM mode is available for testing without API calls:
```bash
USE_MOCK_FALLBACK=true
```

## Current Status

- **Primary Provider**: Anthropic Claude 3.7 Sonnet
- **Fallback**: Mock LLM for development/testing
- **Integration Points**: 40+ locations throughout the codebase
- **Active Use Cases**: Case processing, guideline analysis, experiments