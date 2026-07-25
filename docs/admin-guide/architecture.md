# System Architecture

ProEthica is a multi-service application combining Flask web interface, PostgreSQL storage, Redis task queuing, and OntServe ontology integration.

## High-Level Architecture

```text
                         ProEthica Pipeline
+---------------+                                    +---------------+
| Case          |  upload    +-----------+  9 types  | Views         |
| Narrative     |--+-------->| Steps 1-3 |---------->| + CBR         |
| (NSPE BER)    |  | parse   | Extraction|           | Index         |
+---------------+  |         +-----------+           +---------------+
                   |               |                  ^      |
                   |               | entities         |      |
                   |               v                  |      v
                   |         +-----------+  8 types   |  +-----------+
                   |         |  Step 4   |------------+  |  Step 5   |
                   |         | Synthesis |               |Interactive|
                   |         +-----------+               | Scenario  |
                   |                                     +-----------+
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

| Service | Port | Purpose | Required |
|---------|------|---------|----------|
| ProEthica (Flask) | 5000 | Main web application | Always |
| OntServe MCP | 8082 | Ontology validation and queries | Always |
| PostgreSQL | 5432 | Data storage (two databases) | Always |
| Redis | 6379 | Task queue for pipeline automation | Pipeline Automation only |
| Celery Worker | - | Background task processing | Pipeline Automation only |

Single-case extractions run synchronously and do not require Redis or Celery. Batch processing across multiple cases via [Pipeline Automation](../analysis/pipeline-automation.md) requires both.

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
                               |
                               v
                   +-----------------------+
                   |       Step 5          |
                   | Interactive Scenario  |
                   | (Narrative, Timeline, |
                   |   Decision Wizard)    |
                   +-----------------------+
```

### LLM Request Flow

All extraction calls use the configured default model (`claude-sonnet-5`) via streaming, with the powerful tier (`claude-fable-5`) and the gate tier (`claude-opus-4-8`) reserved for complex analysis and verification judging. Prompts are stored as database templates editable through the Prompt Editor (`/tools/prompts`).

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

## Ontology Materialization and Conformance

Between extraction and the persisted case ontology, three mechanisms govern how extracted entities enter the shared knowledge graph.

### Entity Matching and Canonicalization

Each extracted entity is matched against existing OntServe classes to limit per-case class proliferation. A reviewer may override a match from the Entity Review interface by searching OntServe and selecting an alternative class. The override is type-safe: the target class must resolve to the same core component as the entity's extraction type, since the nine components form an `owl:AllDisjointClasses` set. A cross-category override (for example, typing an Obligation as a Resource) is rejected before commit. The target category is resolved through the curated category map first, then through the OntServe `parent_uri` subclass chain for case-local classes.

### Conformance Gate

Before a case ontology is persisted, candidate TTL passes a SHACL plus OWL-RL conformance check with a deterministic Tier-0 re-typing repair (`repair_conformance_ttl`). The gate runs against the merged core, intermediate, and case ontologies, so a committed case validates standalone under the Pellet OWL-DL reasoner.

### Edge Materialization

At commit, two families of relations are materialized as queryable, reasoner-visible triples, each carrying a PROV-O derivation node that attributes the edge to a source field.

| Family | Properties | Models |
|--------|-----------|--------|
| Dependency (R-P-O) | `hasObligation`, `adheresToPrinciple`, `derivedFromPrinciple` | The Role to Principle to Obligation chain |
| Defeasibility | `competesWith`, `prevailsOver`, `defeasibleUnder` | Obligation competition and defeat |

These edges replace earlier narrative encodings of competing-duty resolution, so non-monotonic reasoners and SPARQL queries consume them directly. The property definitions are listed in [Ontology Properties](../concepts/ontology-properties.md); the user-facing surface for the defeasibility edges is the [Defeasibility View](../viewing/defeasibility.md).

## Database Schema

```text
+-------------------------------------------------------+
|         ProEthica Database (ai_ethical_dm)            |
+-------------------------------------------------------+

+--------------+    +--------------+    +--------------+
|  documents   |    |doc_sections  |    |case_precedent|
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
|temporary_rdf |    |extraction_   |    |pipeline_runs |
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
| `PipelineRun` | `pipeline_runs` | Background pipeline execution tracking |
| `World` | `worlds` | Domain containers (e.g., Engineering Ethics) |
| `Guideline` | `guidelines` | Professional codes of conduct |
| `User` | `users` | Authentication and authorization |
| `CasePrecedentFeatures` | `case_precedent_features` | Embedding vectors (384D, all-MiniLM-L6-v2) |

## Code Organization

### Application Structure

| Component | Location | Purpose |
|-----------|----------|---------|
| Routes | `app/routes/` | Flask blueprints (31 registered) |
| Templates | `app/templates/` | Jinja2 HTML templates |
| Services | `app/services/` | Business logic and extraction |
| Models | `app/models/` | SQLAlchemy database models |
| Tasks | `app/tasks/` | Celery task definitions |
| Utils | `app/utils/` | Helpers and authentication |

### Route Packages

Large route files are decomposed into sub-module packages. Each package follows the same pattern: `__init__.py` creates the Blueprint and imports `register_*_routes()` functions from sub-modules.

| Package | Modules | Purpose |
|---------|---------|---------|
| `cases/` | 11 | Case listing, viewing, creation, editing, the defeasibility view |
| `worlds/` | 4 | World management and guideline browsing |
| `scenario_pipeline/` | 6 + subpackages | Steps 4-5 synthesis and interactive scenario; the `step4/` and `entity_review/` subpackages hold the synthesis phases, entity matching, and reconciliation |

Single-file routes handle focused concerns: `admin.py`, `annotations.py`, `dashboard.py`, `documents.py`, `guidelines.py`, `health.py`, `pipeline_dashboard.py`. The standalone `scenarios/` route package was retired; the `Scenario` model is retained as shared infrastructure for the case-derived scenario pipeline.

### Service Groups

| Group | Location | Purpose |
|-------|----------|---------|
| Extraction | `services/extraction/` | Unified dual extractor, prompt templates |
| LLM | `services/llm/` | Model management, streaming, response parsing |
| MCP Clients | `services/ontserve/mcp_transport.py`, `services/ontserve/external_mcp_client.py` | OntServe communication (FastMCP Streamable HTTP) |
| Annotation | 14 service files | Document concept annotation pipeline |
| Synthesis | `services/case_synthesizer.py`, `decision_point_synthesizer.py` | Step 4 analysis |
| OntServe | `services/ontserve_commit_service.py`, `auto_commit_service.py` | Entity commit workflow |

### OntServe Integration

MCP (Model Context Protocol) provides ontology services via 20 tools over FastMCP Streamable HTTP, grouped as 12 integration tools, 5 reasoning/BFO tools, and 3 conformance tools.

Integration tools:

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
| `wolfram_lookup` | Resolve a definitional lookup for ontology grounding |
| `store_extracted_entities` | Store ProEthica extraction results |
| `get_case_entities` | Retrieve stored entities for a specific case |

Reasoning and BFO tools run the Pellet OWL-DL reasoner over the merged core, intermediate, and case ontologies:

| Tool | Purpose |
|------|---------|
| `reason_ontology` | Consistency check and inference counts |
| `check_consistency` | Consistency flag and disjointness violations |
| `get_inferred_hierarchy` | Inferred subclass and type assertions |
| `get_inconsistent_classes` | Entities forced to `owl:Nothing` |
| `validate_bfo_compliance` | BFO, PROV-O, and intermediate compliance report |

Conformance tools run a SHACL plus OWL-RL check, with a deterministic re-typing repair:

| Tool | Purpose |
|------|---------|
| `validate_conformance` | SHACL and OWL-RL check of a stored case |
| `validate_conformance_ttl` | Same check over candidate TTL before commit |
| `repair_conformance_ttl` | Check plus deterministic Tier-0 re-typing repair |

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
