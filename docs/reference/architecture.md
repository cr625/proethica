# System Architecture

This document describes the ProEthica system architecture.

## High-Level Architecture

ProEthica follows a three-tier architecture with specialized components:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Processing                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │     LLM       │  │   LangGraph   │  │    Celery     │       │
│  │  (Claude)     │  │ Orchestration │  │    Tasks      │       │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
└──────────┼──────────────────┼──────────────────┼───────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Knowledge                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │   Ontology    │  │   Case Base   │  │   Embeddings  │       │
│  │  (OntServe)   │  │  (PostgreSQL) │  │   (pgvector)  │       │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
└──────────┼──────────────────┼──────────────────┼───────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Infrastructure                            │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │     MCP       │  │   Database    │  │    Redis      │       │
│  │  (JSON-RPC)   │  │  (PostgreSQL) │  │   (Queue)     │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Overview

### Processing Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| LLM | Claude (Anthropic) | Natural language extraction |
| LangGraph | Python orchestration | Multi-step workflows |
| Celery | Distributed tasks | Background processing |

### Knowledge Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| Ontology | OntServe + OWL | Concept definitions |
| Case Base | PostgreSQL | Case storage and retrieval |
| Embeddings | pgvector | Semantic similarity |

### Infrastructure Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| MCP | JSON-RPC 2.0 | Ontology communication |
| Database | PostgreSQL 14+ | Persistent storage |
| Queue | Redis | Message broker |

## Service Architecture

### Flask Application

```
proethica/
├── app/
│   ├── __init__.py          # App factory
│   ├── routes/              # HTTP endpoints (48+ files)
│   │   ├── scenario_pipeline/  # Pipeline steps
│   │   └── ...
│   ├── services/            # Business logic (120+ files)
│   │   ├── extraction/      # 9-concept extractors
│   │   └── ...
│   ├── models/              # Database models (62+ files)
│   └── templates/           # Jinja2 templates
├── config.py                # Configuration
├── run.py                   # Entry point
└── celery_config.py         # Task configuration
```

### Service Layer

Services encapsulate business logic:

| Category | Services | Purpose |
|----------|----------|---------|
| LLM | claude_service, llm_service | AI integration |
| Extraction | dual_*_extractor (9) | Concept extraction |
| Analysis | guideline_analysis, case_synthesis | Case processing |
| Storage | case_entity_storage, entity_service | Data management |
| Integration | ontserve_mcp_client | External systems |

### Route Structure

| Module | Endpoints | Purpose |
|--------|-----------|---------|
| cases | /cases/* | Case management |
| scenario_pipeline | /scenario_pipeline/* | Analysis workflow |
| precedents | /cases/precedents/* | Similarity search |
| pipeline_dashboard | /pipeline/* | Automation |

## Data Flow

### Extraction Pipeline

```
Case Document
       │
       ▼
┌──────────────────┐
│   Section Parser │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  Pass 1 Extract  │────▶│  Entity Review   │
│  (R, S, Rs)      │     │  + OntServe      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│  Pass 2 Extract  │────▶│  Entity Review   │
│  (P, O, Cs, Ca)  │     │  + OntServe      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│  Pass 3 Extract  │────▶│  Entity Review   │
│  (A, E)          │     │  + OntServe      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│  Case Analysis   │────▶│  Transformation  │
│  (Rules, Actions)│     │  Classification  │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│    Scenario      │────▶│   Interactive    │
│   Generation     │     │  Visualization   │
└──────────────────┘     └──────────────────┘
```

### Entity Storage Flow

```
LLM Response
      │
      ▼
┌─────────────────────┐
│ ExtractionPrompt    │◀─────┐
│ (prompt + response) │      │
└──────────┬──────────┘      │
           │                 │
           │ extraction_     │
           │ session_id      │
           │                 │
           ▼                 │
┌─────────────────────┐      │
│TemporaryRDFStorage  │──────┘
│ (classes + individ) │
└──────────┬──────────┘
           │
           │ on commit
           ▼
┌─────────────────────┐
│    OntServe         │
│ (permanent ontology)│
└─────────────────────┘
```

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `documents` | Case documents |
| `document_sections` | Parsed sections with embeddings |
| `temporary_rdf_storage` | Extracted entities (staging) |
| `extraction_prompts` | LLM prompt/response records |
| `pipeline_runs` | Pipeline execution tracking |

### Analysis Tables

| Table | Purpose |
|-------|---------|
| `case_provisions` | Code references |
| `case_questions` | Ethical questions |
| `case_conclusions` | Board conclusions |
| `case_institutional_analysis` | Rule analysis |
| `case_transformation` | Transformation data |

### Scenario Tables

| Table | Purpose |
|-------|---------|
| `scenario_participants` | Character profiles |
| `scenario_relationship_map` | Relationships |
| `scenario_timeline` | Decision points |

### Provenance Tables

| Table | Purpose |
|-------|---------|
| `provenance_agents` | Acting agents |
| `provenance_activities` | Processing activities |
| `provenance_entities` | Produced entities |
| `provenance_derivations` | Derivation chains |

## External Integrations

### OntServe MCP

Communication via Model Context Protocol:

```
ProEthica ──JSON-RPC──▶ OntServe MCP (8082)
                              │
                              ▼
                       ┌─────────────┐
                       │  PostgreSQL │
                       │ (ontologies)│
                       └─────────────┘
```

Methods:
- `get_entities_by_category()` - Fetch classes
- `sparql_query()` - Execute queries
- `submit_candidate_concept()` - Add concepts

### LLM Integration

```
ProEthica ──HTTP──▶ Anthropic API
                         │
                         ▼
              ┌─────────────────┐
              │   Claude Model  │
              │ (sonnet/opus)   │
              └─────────────────┘
```

Features:
- Retry with exponential backoff
- Response streaming
- Token tracking
- Cost monitoring

## Deployment Architecture

### Local Development

```
┌─────────────────────────────────────────┐
│            Developer Machine            │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ProEthica│  │OntServe │  │PostgreSQL│ │
│  │ :5000   │  │ :8082   │  │ :5432   │ │
│  └─────────┘  └─────────┘  └─────────┘ │
│                    │                    │
│              ┌─────┴─────┐             │
│              │   Redis   │             │
│              │   :6379   │             │
│              └───────────┘             │
└─────────────────────────────────────────┘
```

### Production (DigitalOcean)

```
┌─────────────────────────────────────────┐
│         DigitalOcean Droplet            │
│                                         │
│  ┌─────────┐      ┌─────────┐          │
│  │  nginx  │──────│gunicorn │          │
│  │ (proxy) │      │ProEthica│          │
│  └─────────┘      └─────────┘          │
│       │                │                │
│       │          ┌─────┴─────┐         │
│       │          │  OntServe │         │
│       │          │   MCP     │         │
│       │          └───────────┘         │
│       │                │                │
│       ▼                ▼                │
│  ┌──────────────────────────┐          │
│  │       PostgreSQL         │          │
│  └──────────────────────────┘          │
└─────────────────────────────────────────┘
           │
           │ HTTPS
           ▼
    proethica.org
```

## Security Architecture

### Authentication

- Session-based authentication
- CSRF protection
- Secure cookie configuration

### Authorization

- Role-based access control
- Admin-only endpoints
- API key management

### Data Protection

- Database credentials in environment
- API keys never logged
- Secure session storage

## Scalability Considerations

### Horizontal Scaling

- Celery workers can scale independently
- Redis cluster for high availability
- Database read replicas possible

### Performance Optimization

- Connection pooling
- Query optimization
- Embedding caching
- Result pagination

## Related Documentation

- [Nine-Concept Framework](../concepts/nine-concepts.md)
- [Ontology Integration](ontology-integration.md)
- [Installation Guide](../getting-started/installation.md)
