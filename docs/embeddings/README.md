# Embeddings System Documentation

This directory contains comprehensive documentation for the embeddings system in the AI Ethical DM application.

## Documents Overview

- **[index.md](index.md)** - Complete overview of the embeddings system architecture and capabilities
- **[current_implementation.md](current_implementation.md)** - Detailed documentation of the current implementation
- **[improvement_plan.md](improvement_plan.md)** - Roadmap for enhancing embeddings with larger models, APIs, and visualizations
- **[troubleshooting.md](troubleshooting.md)** - Common issues and solutions for embeddings functionality

## Quick Reference

### Current System Status
- **Model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Storage**: PostgreSQL with pgvector extension  
- **Providers**: Local SentenceTransformers, OpenAI API, Claude API
- **Primary Use**: Section-level similarity search and guideline associations
- **Known Issues**: ⚠️ "Generate Section Embeddings" button error (fixed in latest version)

### Recent Fixes
- Fixed `'str' object has no attribute 'keys'` error in section embedding generation
- Improved metadata handling for both string and dictionary formats
- Enhanced error logging and debugging capabilities

### Key Services
- `EmbeddingService` - General embedding generation and similarity search
- `SectionEmbeddingService` - Document section-specific embedding management

### Common Operations
- Generate embeddings for document sections
- Search similar sections across cases
- Associate guidelines with case sections
- Update embeddings when content changes

## Getting Started

1. Review the [index.md](index.md) for system overview
2. Check [current_implementation.md](current_implementation.md) for technical details
3. See [troubleshooting.md](troubleshooting.md) if experiencing issues
4. Consult [improvement_plan.md](improvement_plan.md) for future enhancements