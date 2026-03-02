# System Architecture

ProEthica is a multi-service application combining Flask web interface, PostgreSQL storage, Redis task queuing, and OntServe ontology integration.

## System Overview Diagram

```text
+-----------------------------------------------------------------------+
|                           ProEthica System                            |
+-----------------------------------------------------------------------+
|                                                                       |
|   +-----------+    +-----------+    +-----------+    +-----------+    |
|   |  Browser  |--->|   Flask   |--->|  Celery   |--->|   Redis   |    |
|   |  Client   |<---|   :5000   |<---|  Worker   |<---|   :6379   |    |
|   +-----------+    +-----+-----+    +-----+-----+    +-----------+    |
|                          |                |                           |
|                          v                v                           |
|                    +-----------+    +-----------+                     |
|                    |PostgreSQL |    |  Claude   |                     |
|                    |   :5432   |    |    API    |                     |
|                    +-----------+    +-----------+                     |
|                                                                       |
+-----------------------------------------------------------------------+
                                   |
                                   | MCP (JSON-RPC)
                                   v
+-----------------------------------------------------------------------+
|                           OntServe System                             |
+-----------------------------------------------------------------------+
|                                                                       |
|   +-----------+    +-----------+                                      |
|   |MCP Server |--->|PostgreSQL |                                      |
|   |   :8082   |<---|ontologies |                                      |
|   +-----------+    +-----------+                                      |
|                                                                       |
+-----------------------------------------------------------------------+
```

## Service Architecture

| Service | Port | Purpose |
|---------|------|---------|
| ProEthica (Flask) | 5000 | Main web application |
| OntServe MCP | 8082 | Ontology validation and queries |
| PostgreSQL | 5432 | Data storage (two databases) |
| Redis | 6379 | Task queue for pipeline automation |
| Celery Worker | - | Background task processing |

## Data Flow Diagram

```text
+-----------------------------------------------------------------------+
|                      Case Processing Pipeline                         |
+-----------------------------------------------------------------------+

   +---------+    +---------+    +---------+    +---------+
   |  Case   |--->| Section |--->|Embedding|--->|Precedent|
   | Upload  |    | Parsing |    |  Gen    |    |Matching |
   +---------+    +---------+    +---------+    +---------+
        |                                            |
        v                                            v
+-----------------------------------------------------------------------+
|                        Extraction Pipeline                            |
+-----------------------------------------------------------------------+
|                                                                       |
|  +--------+  +--------+  +--------+  +---------+  +--------+         |
|  | Step 1 |->| Step 2 |->| Step 3 |->|Reconcile|->| Step 4 |         |
|  |Context |  |Normative| |Temporal|  |Dedup    |  |Synthesis|        |
|  +---+----+  +---+----+  +---+----+  +----+----+  +---+----+         |
|      |           |           |             |           |              |
|      v           v           v             |           v              |
|  +-----------------------------------------------------------+       |
|  |              temporary_rdf_storage (16 types)              |       |
|  |  Steps 1-3: R, S, Rs, P, O, Cs, Ca, A, E                 |       |
|  |  Step 4: provisions, precedents, questions, conclusions,   |       |
|  |    decision_points, resolution_patterns,                   |       |
|  |    causal_normative_links, question_emergence              |       |
|  +-----------------------------------------------------------+       |
|                              |                                        |
+------------------------------+----------------------------------------+
                               |
                               v
                   +-----------------------+
                   | OntServe Commit       |
                   | (2 passes: Steps 1-3  |
                   |  then Step 4 entities)|
                   +-----------------------+
                               |
                               v
                   +-----------------------+
                   |   QC Audit (V0-V9)    |
                   | Verify all 16 types   |
                   +-----------------------+
```

## Database Schema Diagram

```text
+-----------------------------------------------------------------------+
|                  ProEthica Database (ai_ethical_dm)                   |
+-----------------------------------------------------------------------+

+--------------+    +--------------+    +--------------+
|  documents   |    |doc_sections  |    |case_features |
+--------------+    +--------------+    +--------------+
| id (PK)      |--->| id (PK)      |    | id (PK)      |
| title        |    | doc_id (FK)  |<---| case_id (FK) |
| content      |    | section_type |    | facts_embed  |
| source       |    | content      |    | discuss_embed|
| world_id(FK) |    | embedding    |    | created_at   |
| created_at   |    | created_at   |    +--------------+
+--------------+    +--------------+
       |
       v
+--------------+    +--------------+    +--------------+
|temp_rdf_     |    |extraction_   |    | pipeline_run |
|  storage     |    |  prompts     |    +--------------+
+--------------+    +--------------+    | id (PK)      |
| id (PK)      |    | id (PK)      |    | case_id (FK) |
| case_id (FK) |<-->| case_id (FK) |    | status       |
| session_id   |    | concept_type |    | current_step |
| entity_type  |    | section_type |    | entity_count |
| label        |    | prompt_text  |    | started_at   |
| definition   |    | response_text|    | completed_at |
| created_at   |    | llm_model    |    +--------------+
+--------------+    | created_at   |
                    +--------------+

+--------------+    +--------------+    +--------------+
|   worlds     |    |  guidelines  |    |    users     |
+--------------+    +--------------+    +--------------+
| id (PK)      |--->| id (PK)      |    | id (PK)      |
| name         |    | world_id(FK) |    | email        |
| description  |    | name         |    | password_hash|
| created_at   |    | content      |    | is_admin     |
+--------------+    | created_at   |    | created_at   |
                    +--------------+    +--------------+
```

## Component Details

### Web Application (Flask)

| Component | Location | Purpose |
|-----------|----------|---------|
| Routes | `app/routes/` | URL handlers for all features |
| Templates | `app/templates/` | Jinja2 HTML templates |
| Services | `app/services/` | Business logic and extraction |
| Models | `app/models/` | SQLAlchemy database models |
| Utils | `app/utils/` | Helpers and authentication |

### Extraction Pipeline

```text
LLM Request Flow:

   +----------+    +----------+    +----------+
   |  Prompt  |--->|  Claude  |--->| Response |
   |  Builder |    |   API    |    |  Parser  |
   +----------+    +----------+    +----------+
        |                               |
        v                               v
   +----------+                    +----------+
   | OntServe |                    |  Entity  |
   |   Defs   |                    |Extraction|
   +----------+                    +----------+
```

### OntServe Integration

MCP (Model Context Protocol) provides ontology services via 8 tools:

| Tool | Purpose |
|------|---------|
| `get_entities_by_category` | Fetch existing ontology classes by concept type |
| `search_entities` | Find matching classes by label or URI |
| `submit_candidate_concept` | Submit new class proposals |
| `list_ontologies` | Available ontology graphs |
| `sparql_query` | Execute SPARQL queries against ontologies |
| `commit_case_entities` | Commit extracted entities to ontology (TTL + DB) |
| `uncommit_case_entities` | Remove previously committed case entities |
| `get_ontology_stats` | Ontology statistics (class counts, entity counts) |

## Environment Configuration

| Variable | Purpose |
|----------|---------|
| `FLASK_ENV` | development/production mode |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | Claude API access |
| `ONTSERVE_MCP_URL` | OntServe server location |
| `REDIS_URL` | Redis connection for Celery |

## Deployment Topology

```text
Production (proethica.org):

+-----------------------------------------------------------------------+
|                       DigitalOcean Droplet                            |
+-----------------------------------------------------------------------+
|                                                                       |
|   +---------+    +-----------+    +-----------+                       |
|   |  nginx  |--->|  gunicorn |--->|   Flask   |                       |
|   |  :443   |    |  (socket) |    |    App    |                       |
|   +---------+    +-----------+    +-----+-----+                       |
|                                         |                             |
|   +-----------+    +-----------+        |                             |
|   |   Redis   |    |  Celery   |<-------+                             |
|   |   :6379   |<---|  Worker   |                                      |
|   +-----------+    +-----------+                                      |
|                                                                       |
|   +-----------+    +-----------+                                      |
|   |PostgreSQL |    | OntServe  |                                      |
|   |   :5432   |    |   :8082   |                                      |
|   +-----------+    +-----------+                                      |
|                                                                       |
+-----------------------------------------------------------------------+
```

## Related Documentation

- [Ontology Integration](ontology-integration.md) - OntServe MCP details
- [Installation & Deployment](installation.md) - Setup instructions
- [Pipeline Automation](../analysis/pipeline-automation.md) - Background processing
- [Settings](settings.md) - Configuration options
