# AI Ethical Decision-Making Simulator: Implementation Plans

This directory contains detailed implementation plans for enhancing the AI Ethical Decision-Making Simulator with advanced AI capabilities.

## Core Implementation Files

- **[comprehensive_next_steps_guide.md](comprehensive_next_steps_guide.md)**: The main guide outlining the overall enhancement plan, architecture, and implementation roadmap.

- **[embedding_model_implementation.md](embedding_model_implementation.md)**: Detailed implementation plan for the document embedding system using Sentence-Transformers, including code samples for document processing, embedding generation, and retrieval.

- **[langchain_langraph_enhancement.md](langchain_langraph_enhancement.md)**: Implementation plan for enhancing LangChain and LangGraph components with a focus on virtue ethics multi-agent system and temporal workflow.

- **[api_call_optimization.md](api_call_optimization.md)**: Strategies and implementation details for minimizing Anthropic API calls while maintaining quality, including caching, batching, and hybrid approaches.

- **[pgvector_integration.md](pgvector_integration.md)**: Implementation plan for integrating PostgreSQL's pgvector extension for efficient vector storage and retrieval, including database schema, SQLAlchemy models, and Flask routes.

## Directory Structure

- **archive/**: Contains older implementation files and scenario-specific templates that are kept for reference but are not part of the current implementation plan.

## Implementation Priorities

1. **Phase 1: Foundation (2-3 weeks)**
   - Set up Sentence-Transformers embedding pipeline
   - Implement pgvector schema and basic retrieval
   - Design virtue ethics agent framework

2. **Phase 2: Core Components (3-4 weeks)**
   - Implement professional role agent
   - Develop temporal context and character state nodes
   - Create document processing pipeline

3. **Phase 3: Integration (2-3 weeks)**
   - Connect embedding system with LangGraph workflow
   - Implement coordinator agent
   - Develop API call optimization strategies

4. **Phase 4: Testing and Refinement (2 weeks)**
   - Test with existing scenarios
   - Optimize performance
   - Refine agent interactions

## Key Technical Decisions

- **Embedding Model**: Using Sentence-Transformers `all-MiniLM-L6-v2` (384 dimensions) for a good balance of quality and efficiency
- **Vector Storage**: PostgreSQL with pgvector extension
- **Agent Architecture**: Multi-agent system with professional role, virtue ethics, and domain expert agents
- **Workflow Design**: Enhanced LangGraph workflow with temporal context and character state tracking
- **API Optimization**: Hybrid approach combining caching, batching, and embedding-based similarity
