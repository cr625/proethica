# System Architecture

This document describes the ProEthica system architecture.

## High-Level Architecture

ProEthica follows a three-tier architecture with specialized components:

```
+---------------------------------------------------------------+
|                        Processing                             |
|                                                               |
|  +--------------+  +--------------+  +--------------+         |
|  |     LLM      |  |  LangGraph   |  |   Celery     |         |
|  |   (Claude)   |  | Orchestration|  |   Tasks      |         |
|  +------+-------+  +------+-------+  +------+-------+         |
+---------|-----------------|-----------------|------------------+
          |                 |                 |
          v                 v                 v
+---------------------------------------------------------------+
|                        Knowledge                              |
|                                                               |
|  +--------------+  +--------------+  +--------------+         |
|  |   Ontology   |  |  Case Base   |  |  Embeddings  |         |
|  |  (OntServe)  |  | (PostgreSQL) |  |  (pgvector)  |         |
|  +------+-------+  +------+-------+  +------+-------+         |
+---------|-----------------|-----------------|------------------+
          |                 |                 |
          v                 v                 v
+---------------------------------------------------------------+
|                      Infrastructure                           |
|                                                               |
|  +--------------+  +--------------+  +--------------+         |
|  |     MCP      |  |   Database   |  |    Redis     |         |
|  |  (JSON-RPC)  |  | (PostgreSQL) |  |   (Queue)    |         |
|  +--------------+  +--------------+  +--------------+         |
+---------------------------------------------------------------+
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
│   ├── routes/              # HTTP endpoints (70+ files)
│   │   ├── scenario_pipeline/  # Pipeline steps
│   │   └── ...
│   ├── services/            # Business logic (260+ files)
│   │   ├── extraction/      # Concept extractors
│   │   └── ...
│   ├── models/              # Database models (60+ files)
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
| Extraction | dual_*_extractor | Concept extraction (10 extractors) |
| Analysis | guideline_analysis, case_synthesis | Case processing |
| Decision | decision_focus_extractor | Decision point extraction |
| Storage | case_entity_storage, entity_service | Data management |
| Commit | auto_commit_service | RDF commit to OntServe |
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
      |
      v
+------------------+
|  Section Parser  |
+--------+---------+
         |
         v
+------------------+     +------------------+
| Pass 1 Extract   |---->|  Entity Review   |
| (R, S, Rs)       |     |  + OntServe      |
+--------+---------+     +--------+---------+
         |                        |
         v                        v
+------------------+     +------------------+
| Pass 2 Extract   |---->|  Entity Review   |
| (P, O, Cs, Ca)   |     |  + OntServe      |
+--------+---------+     +--------+---------+
         |                        |
         v                        v
+------------------+     +------------------+
| Pass 3 Extract   |---->|  Entity Review   |
| (A, E)           |     |  + OntServe      |
+--------+---------+     +--------+---------+
         |                        |
         v                        v
+------------------+     +------------------+
| Case Analysis    |---->| Transformation   |
| (Q&C, Provs)     |     | Classification   |
+--------+---------+     +--------+---------+
         |                        |
         v                        v
+------------------+     +------------------+
| Decision Points  |---->| Commit to        |
| Extraction       |     | OntServe         |
+--------+---------+     +--------+---------+
         |                        |
         v                        v
+------------------+     +------------------+
| Scenario         |---->| Interactive      |
| Generation       |     | Visualization    |
+------------------+     +------------------+
```

### Entity Storage Flow

```
LLM Response
      |
      v
+---------------------+
| ExtractionPrompt    |<-----+
| (prompt + response) |      |
+----------+----------+      |
           |                 |
           | extraction_     |
           | session_id      |
           |                 |
           v                 |
+---------------------+      |
| TemporaryRDFStorage |------+
| (classes + individ) |
+----------+----------+
           |
           | on commit
           v
+---------------------+
|    OntServe         |
| (permanent ontology)|
+---------------------+
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

### Analysis Tables (Step 4)

Step 4 analysis entities use the standard RDF storage pattern in `temporary_rdf_storage`:

| extraction_type | entity_type | Purpose |
|-----------------|-------------|---------|
| `code_provision_reference` | resources | NSPE Code references |
| `ethical_question` | EthicalQuestion | Ethical questions posed |
| `ethical_conclusion` | BoardConclusion | Board conclusions |
| `decision_point` | DecisionPoint | Key decision points |
| `decision_option` | DecisionOption | Options at decision points |

Transformation classification stored in:

| Table | Purpose |
|-------|---------|
| `case_precedent_features` | Transformation type and pattern data |

### Scenario Tables

| Table | Purpose |
|-------|---------|
| `scenario_participants` | Character profiles |
| `scenario_relationship_map` | Relationships |
| `scenario_exploration_sessions` | Interactive exploration sessions |
| `scenario_exploration_choices` | User choices in explorations |

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
ProEthica ---JSON-RPC---> OntServe MCP (8082)
                                |
                                v
                         +-------------+
                         | PostgreSQL  |
                         | (ontologies)|
                         +-------------+
```

Methods:
- `get_entities_by_category()` - Fetch classes
- `sparql_query()` - Execute queries
- `submit_candidate_concept()` - Add concepts

### LLM Integration

```
ProEthica ---HTTP---> Anthropic API
                           |
                           v
                +-----------------+
                |  Claude Model   |
                |  (sonnet/opus)  |
                +-----------------+
```

Features:
- Retry with exponential backoff
- Response streaming
- Token tracking
- Cost monitoring

## Deployment Architecture

### Local Development

```
+-----------------------------------------+
|           Developer Machine             |
|                                         |
|  +-----------+  +-----------+  +------+ |
|  | ProEthica |  | OntServe  |  |Postgr| |
|  |   :5000   |  |   :8082   |  | :5432| |
|  +-----------+  +-----------+  +------+ |
|                      |                  |
|                +-----------+            |
|                |   Redis   |            |
|                |   :6379   |            |
|                +-----------+            |
+-----------------------------------------+
```

### Production (DigitalOcean)

```
+-----------------------------------------+
|         DigitalOcean Droplet            |
|                                         |
|  +-----------+      +-----------+       |
|  |   nginx   |------|  gunicorn |       |
|  |  (proxy)  |      | ProEthica |       |
|  +-----------+      +-----------+       |
|       |                  |              |
|       |            +-----------+        |
|       |            | OntServe  |        |
|       |            |    MCP    |        |
|       |            +-----------+        |
|       |                  |              |
|       v                  v              |
|  +-----------------------------+        |
|  |        PostgreSQL           |        |
|  +-----------------------------+        |
+-----------------------------------------+
              |
              | HTTPS
              v
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
- [Installation & Deployment](installation.md)
