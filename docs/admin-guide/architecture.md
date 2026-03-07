# System Architecture

ProEthica is a multi-service application combining Flask web interface, PostgreSQL storage, Redis task queuing, and OntServe ontology integration.

## High-Level Architecture

```text
                         ProEthica Pipeline
+---------------+                                    +---------------+
| Case          |  upload    +-----------+  9 types  | 7 Views       |
| Narrative     |--+-------->| Steps 1-3 |---------->| + CBR         |
| (NSPE BER)    |  | parse   | Extraction|           | Index         |
+---------------+  |         +-----------+           +---------------+
                   |               |                  ^
                   |               | entities         |
                   |               v                  |   
                   |         +-----------+  8 types   |
                   |         |  Step 4   |------------+
                   |         | Synthesis |
                   |         +-----------+
                   |
   PROCESSING      |      KNOWLEDGE            INFRASTRUCTURE
+----------+       |    +----------+           +----------+
| LLM      |       |    | Ontology |--serves-->| MCP      |
| Claude   |<......|....| ProEthica|   via     | OntServe |
| API      | constrains | Core     |           | :8082    |
+----------+       |    +----------+           +----------+
+----------+       |    +----------+           +----------+
| LangGraph|       |    | Case     |--CBR----->| Database |
| Orchestr.|       |    | Base     |  index    | SQL+Vec  |
+----------+       |    +----------+           +----------+
```

## System Overview

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
                                   | MCP (Streamable HTTP)
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

| Service | Port | Purpose |
|---------|------|---------|
| ProEthica (Flask) | 5000 | Main web application |
| OntServe MCP | 8082 | Ontology validation and queries |
| PostgreSQL | 5432 | Data storage (two databases) |
| Redis | 6379 | Task queue for pipeline automation |
| Celery Worker | - | Background task processing |

## Extraction Pipeline

The pipeline extracts nine component types across three steps, then synthesizes seven additional entity types in Step 4. For the full concept framework see [Nine-Component Framework](../concepts/nine-components.md); for step/pass/phase terminology see [Pipeline Terminology](../concepts/terminology.md).

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
|  +--------+  +--------+  +--------+  +---------+  +--------+          |
|  | Step 1 |->| Step 2 |->| Step 3 |->|Reconcile|->| Step 4 |          |
|  |Context |  |Normative| |Temporal|  |Dedup    |  |Synthesis|         |
|  +---+----+  +---+----+  +---+----+  +----+----+  +---+----+          |
|      |           |           |             |           |              |
|      v           v           v             |           v              |
|  +-----------------------------------------------------------+        |
|  |              temporary_rdf_storage (17 types)              |       |
|  |  Steps 1-3: R, S, Rs, P, O, Cs, Ca, A, E                   |       |
|  |  Step 4: provisions, precedents, questions, conclusions,   |       |
|  |    decision_points, resolution_patterns,                   |       |
|  |    causal_normative_links, question_emergence              |       |
|  +-----------------------------------------------------------+        |
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
                   | Verify all 17 types   |
                   +-----------------------+
```

### LLM Request Flow

All extraction calls use `claude-sonnet-4-6` via streaming. Prompts are stored as database templates editable through the Prompt Editor (`/tools/prompts`).

```text
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

## Database Schema

```text
+-------------------------------------------------------+
|         ProEthica Database (ai_ethical_dm)            |
+-------------------------------------------------------+

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

### Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Document` | `documents` | Cases and guidelines |
| `DocumentSection` | `document_sections` | Parsed case sections (Facts, Discussion) |
| `TemporaryRDFStorage` | `temporary_rdf_storage` | Extracted entities with RDF representation |
| `ExtractionPrompt` | `extraction_prompts` | LLM prompts and responses |
| `PipelineRun` | `pipeline_run` | Background pipeline execution tracking |
| `World` | `worlds` | Domain containers (e.g., Engineering Ethics) |
| `Guideline` | `guidelines` | Professional codes of conduct |
| `User` | `users` | Authentication and authorization |
| `CaseFeatures` | `case_features` | Embedding vectors (384D, all-MiniLM-L6-v2) |

## Code Organization

### Application Structure

| Component | Location | Purpose |
|-----------|----------|---------|
| Routes | `app/routes/` | Flask blueprints (42 registered) |
| Templates | `app/templates/` | Jinja2 HTML templates |
| Services | `app/services/` | Business logic and extraction |
| Models | `app/models/` | SQLAlchemy database models |
| Tasks | `app/tasks/` | Celery task definitions |
| Utils | `app/utils/` | Helpers and authentication |

### Route Packages

Large route files are decomposed into sub-module packages. Each package follows the same pattern: `__init__.py` creates the Blueprint and imports `register_*_routes()` functions from sub-modules.

| Package | Modules | Purpose |
|---------|---------|---------|
| `cases/` | 10 | Case listing, viewing, creation, editing, scenario generation |
| `worlds/` | 8 | World management, guidelines, triples, concept mapping |
| `scenario_pipeline/step4/` | 19 | Step 4 synthesis, entity management, streaming |
| `entity_review/` | 4 | Entity selection, OntServe matching, reconciliation |
| `scenarios/` | 6 | Scenario characters, resources, actions, events, decisions |

Single-file routes handle focused concerns: `admin.py`, `annotations.py`, `dashboard.py`, `documents.py`, `guidelines.py`, `health.py`, `pipeline_dashboard.py`.

### Service Groups

| Group | Location | Purpose |
|-------|----------|---------|
| Extraction | `services/extraction/` | Unified dual extractor, prompt templates |
| LLM | `services/llm/` | Model management, streaming, response parsing |
| MCP Clients | `services/mcp_transport.py`, `external_mcp_client.py` | OntServe communication (FastMCP Streamable HTTP) |
| Annotation | 14 service files | Document concept annotation pipeline |
| Synthesis | `services/case_synthesizer.py`, `decision_point_synthesizer.py` | Step 4 analysis |
| OntServe | `services/ontserve_commit_service.py`, `auto_commit_service.py` | Entity commit workflow |

### OntServe Integration

MCP (Model Context Protocol) provides ontology services via 11 tools over FastMCP Streamable HTTP:

| Tool | Purpose |
|------|---------|
| `get_entities_by_category` | Fetch existing ontology classes by component type |
| `get_entity_by_label` | Resolve entity definition by label |
| `get_entity_by_uri` | Resolve entity definition by URI |
| `get_entities_by_uris` | Batch resolve up to 20 entities by URI |
| `submit_candidate_concept` | Submit new class proposals |
| `update_concept_status` | Approve or reject candidate concepts |
| `get_candidate_concepts` | Retrieve pending concepts for review |
| `get_domain_info` | Domain metadata and statistics |
| `sparql_query` | Execute SPARQL queries against ontologies |
| `store_extracted_entities` | Store ProEthica extraction results |
| `get_case_entities` | Retrieve stored entities for a specific case |

## Deployment

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

| Variable | Purpose |
|----------|---------|
| `FLASK_ENV` | development/production mode |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | Claude API access |
| `ONTSERVE_MCP_URL` | OntServe server location |
| `REDIS_URL` | Redis connection for Celery |

## Related Documentation

- [Nine-Component Framework](../concepts/nine-components.md) - The 9 component types and theoretical foundations
- [Pipeline Terminology](../concepts/terminology.md) - Step/Pass/Phase definitions and processing order
- [Ontology Integration](ontology-integration.md) - OntServe MCP details
- [Installation & Deployment](installation.md) - Setup instructions
- [Pipeline Automation](../analysis/pipeline-automation.md) - Background processing
- [Settings](settings.md) - Configuration options
