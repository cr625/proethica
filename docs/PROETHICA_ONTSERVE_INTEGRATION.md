# ProEthica ↔ OntServe Integration Mechanisms

**Last Updated:** November 17, 2025
**Purpose:** Document how ProEthica interacts with OntServe for refactoring compatibility

---

## Overview

ProEthica integrates with OntServe through **three primary mechanisms**:

1. **Direct HTTP REST API** (Port 5003) - Ontology editing & entity queries
2. **MCP (Model Context Protocol) Server** (Port 8082) - JSON-RPC tool calls
3. **Internal MCP Client** (Port 5002) - Legacy fallback (being phased out)

---

## 1. Direct HTTP REST API Integration (Primary Method)

### Service: `OntServeAnnotationService`
**File:** `app/services/ontserve_annotation_service.py`
**Port:** 5003 (OntServe web interface)
**Protocol:** HTTP REST with requests.Session

### Key Endpoints Used:

```python
# Base URL: http://localhost:5003

# 1. Get Ontology Entities
GET /editor/api/ontologies/{ontology_name}/entities
Returns: {
  "entities": {
    "classes": [...],
    "properties": [...]
  }
}

# 2. Get World Ontology Mapping
# Stored in World.ontserve_mapping or World.world_metadata['ontserve_mapping']
# Example mapping:
{
  'core': {'name': 'proethica-core', 'priority': 1},
  'intermediate': {'name': 'proethica-intermediate', 'priority': 2},
  'domain': {'name': 'engineering-ethics', 'priority': 3}
}
```

### Use Cases:
- **Document Annotation:** Fetch concepts from ontologies for text annotation
- **Concept Lookup:** Search entities by label, definition, type
- **Ontology Prioritization:** Cascade annotation through core → intermediate → domain layers
- **Caching:** Maintains in-memory cache of ontology concepts

### Files Using This Method:
- `app/services/definition_based_annotation_service.py`
- `app/services/document_annotation_pipeline.py`
- `app/services/simplified_llm_annotation_service.py`
- `app/routes/annotation_versions.py`
- `app/routes/annotations.py`

### Data Format Transformation:
```python
# OntServe API Response → ProEthica Format
{
  'uri': entity.get('id', entity.get('uri', '')),
  'label': entity.get('label', entity.get('name', '')),
  'definition': entity.get('description', entity.get('definition', '')),
  'type': entity.get('category', entity.get('type', 'Unknown')),
  'ontology': ontology_name,
  'properties': entity.get('properties', {})
}
```

---

## 2. MCP (Model Context Protocol) Integration

### Service: `ExternalMCPClient`
**File:** `app/services/external_mcp_client.py`
**Port:** 8082 (OntServe MCP server)
**Protocol:** JSON-RPC 2.0 over HTTP POST

### Environment Configuration:
```bash
ENABLE_EXTERNAL_MCP_ACCESS=true
EXTERNAL_MCP_URL=http://localhost:8082
ONTSERVE_MCP_URL=http://localhost:8082
```

### JSON-RPC Methods Used:

#### 1. List Tools
```json
POST http://localhost:8082
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "list_tools",
  "params": {}
}
```

#### 2. Call Tool - Get Entities by Category
```json
POST http://localhost:8082
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "call_tool",
  "params": {
    "name": "get_entities_by_category",
    "arguments": {
      "category": "Role",           # Role, Principle, Obligation, etc.
      "domain_id": "engineering-ethics",
      "status": "approved"
    }
  }
}
```

#### 3. Response Format
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"entities\": [...], \"count\": 42}"
    }]
  }
}
```

### Use Cases:
- **Concept Extraction:** Fetch approved role/principle/obligation entities during extraction
- **LLM Context:** Provide ontology entities to LLM for mention-first extraction
- **Entity Validation:** Check if extracted concepts match existing ontology entities

### Files Using This Method:
- `app/services/external_mcp_client.py` (primary interface)
- `app/routes/agent.py` (shows MCP integration in demo)
- Various extraction services (via external_mcp_client)

### Available MCP Tools (OntServe):
```python
# Common tools (as of Nov 2025):
- get_entities_by_category(category, domain_id, status)
- get_entity_by_uri(uri)
- search_entities(query, entity_type)
- get_entity_relationships(entity_uri)
- list_domains()
- get_domain_stats(domain_id)
```

---

## 3. Internal MCP Client (Legacy)

### Service: `MCPClient`
**File:** `app/services/mcp_client.py`
**Port:** 5002 (ProEthica internal MCP stub)
**Status:** Being phased out - functionality moved to OntServe

### Methods:
```python
# Basic ontology queries
get_guidelines(world_name)
get_world_entities(ontology_source, entity_type)
get_ontology_entities(ontology_source, entity_type)
```

### Current State:
- Used by `claude_service.py` for world context
- Mock fallback mode enabled by default
- Will eventually redirect to OntServe MCP (port 8082)

---

## 4. Stub Services (Compatibility Layer)

### Service: `OntologyEntityService`
**File:** `app/services/ontology_entity_service.py`
**Status:** STUB - Returns empty results

```python
# All methods return empty/None
get_entities_for_world(world) → []
get_entity_by_uri(uri) → None
search_entities(query) → []
get_entity_relationships(uri) → []
```

**Note:** This is a compatibility shim. Real functionality has moved to OntServe.

### Files Depending on This Stub:
- `app/services/case_role_matching_service.py` (tries to use, falls back gracefully)
- `app/services/role_description_service.py` (tries to use, falls back gracefully)

---

## 5. Data Flow Patterns

### Pattern A: Annotation Pipeline
```
User uploads document
    ↓
ProEthica: OntServeAnnotationService.get_world_ontology_mapping(world_id)
    → Query World model for ontology names
    ↓
ProEthica: OntServeAnnotationService.get_ontology_concepts(ontology_names)
    → HTTP GET /editor/api/ontologies/{name}/entities
    ← Returns: classes, properties, definitions
    ↓
ProEthica: Transform to standardized format
    → Cache results in memory
    ↓
ProEthica: LLM annotation with concepts as context
    ↓
Store annotations in DocumentConceptAnnotation table
```

### Pattern B: Concept Extraction (9-Concept System)
```
Extract concepts from case (Pass 1-3)
    ↓
ProEthica: ExternalMCPClient.get_entities_by_category("Role")
    → JSON-RPC POST to http://localhost:8082
    → Call tool: get_entities_by_category
    ← Returns: List of approved Role entities
    ↓
ProEthica: Provide entities to LLM as context
    ↓
LLM: Extract mentions with reference to known ontology
    ↓
Store in TemporaryRDFStorage (staging)
    ↓
User reviews
    ↓
Commit selected entities to OntServe (via MCP)
```

### Pattern C: World Guidelines (Legacy)
```
User selects world
    ↓
ProEthica: MCPClient.get_guidelines(world_name)
    → HTTP GET to http://localhost:5002/api/guidelines/{world_name}
    ← Returns: Mock fallback data
    ↓
Use guidelines in LLM system prompt
```

---

## 6. Critical Dependencies for OntServe Refactoring

### Must Maintain:

1. **REST API Structure** (Port 5003):
   ```
   GET /editor/api/ontologies/{name}/entities
   → Returns: {"entities": {"classes": [...], "properties": [...]}}
   ```

2. **MCP JSON-RPC Interface** (Port 8082):
   ```
   method: "call_tool"
   params: {
     "name": "get_entities_by_category",
     "arguments": {"category": "Role", "domain_id": "...", "status": "..."}
   }
   ```

3. **Entity Data Schema**:
   - Fields: `id/uri`, `label/name`, `description/definition`, `category/type`
   - ProEthica handles dual naming via transformation layer

4. **World Ontology Mapping**:
   - Format: `{'core': {'name': '...', 'priority': N}}`
   - Stored in: `World.ontserve_mapping` or `World.world_metadata['ontserve_mapping']`

### Can Change:

1. **Internal OntServe architecture** - ProEthica doesn't care how you store/manage ontologies
2. **Database schema** - As long as API responses match expected format
3. **MCP tool names** - Update ExternalMCPClient method names accordingly
4. **Additional features** - ProEthica uses subset of OntServe capabilities

---

## 7. Recommended Improvements for OntServe Refactoring

### Option A: Unified MCP-Only Interface
```python
# Consolidate all ProEthica interactions through MCP (port 8082)
# Deprecate direct HTTP REST API (port 5003)

# Benefits:
- Single integration point
- Better versioning via JSON-RPC
- Tool discovery via list_tools
- Easier to extend

# Implementation:
1. Add MCP tools for all /editor/api/* endpoints
2. Migrate OntServeAnnotationService to use ExternalMCPClient
3. Remove direct HTTP calls
```

### Option B: Keep Dual Interface (Current State)
```python
# HTTP REST (port 5003): Human-facing web UI + simple queries
# MCP (port 8082): Machine-facing LLM integration + complex operations

# Benefits:
- Separation of concerns
- Different auth/rate limiting strategies
- Easier debugging

# No changes needed
```

### Option C: Enhanced REST API
```python
# Add versioned REST endpoints
GET /api/v1/domains/{domain_id}/entities?category=Role&status=approved
GET /api/v1/entities/search?q=engineer&type=Role
POST /api/v1/entities/batch  # Bulk operations

# Benefits:
- Standard REST patterns
- Better caching with HTTP headers
- OpenAPI/Swagger documentation
```

---

## 8. Testing OntServe Integration

### Test ProEthica → OntServe Connection:

```bash
# 1. Check MCP Server (Port 8082)
curl -X POST http://localhost:8082 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"list_tools","params":{}}'

# Expected: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

# 2. Check REST API (Port 5003)
curl http://localhost:5003/editor/api/ontologies/engineering-ethics/entities

# Expected: {"entities":{"classes":[...],"properties":[...]}}

# 3. Test from ProEthica Python
python -c "
from app.services.external_mcp_client import ExternalMCPClient
client = ExternalMCPClient('http://localhost:8082')
print(client.list_tools())
"

# 4. Test REST from ProEthica
python -c "
from app.services.ontserve_annotation_service import OntServeAnnotationService
service = OntServeAnnotationService('http://localhost:5003')
print(service.get_ontology_concepts(['engineering-ethics']))
"
```

---

## 9. Breaking Changes to Avoid

### DO NOT CHANGE:

1. **Port numbers** without updating `.env.production.example` and all clients
2. **JSON-RPC response structure** - ProEthica parses `result.content[0].text`
3. **Entity field names** - ProEthica transforms `id`→`uri`, `label`→`name`, etc.
4. **HTTP status codes** - ProEthica expects 200 for success
5. **Tool argument names** - `category`, `domain_id`, `status` are hardcoded

### SAFE TO CHANGE:

1. Internal database schema
2. Add new MCP tools (ProEthica won't call them)
3. Add new REST endpoints (ProEthica won't use them)
4. Performance optimizations
5. Add new entity fields (ProEthica ignores unknown fields)

---

## 10. Contact Points in Code

### Files to Update if OntServe API Changes:

1. **`app/services/ontserve_annotation_service.py`**
   - Line 56: REST endpoint URL
   - Lines 76-85: Entity transformation logic

2. **`app/services/external_mcp_client.py`**
   - Line 26: MCP server URL
   - Lines 125-150: Tool call methods
   - Line 108: JSON response parsing

3. **`.env.production.example`**
   - Lines with ONTSERVE_MCP_URL, EXTERNAL_MCP_URL

4. **`CLAUDE.md`**
   - Integration documentation section

---

## Summary

**Primary Integration:** Direct HTTP REST API (port 5003)
**Secondary Integration:** MCP JSON-RPC (port 8082)
**Status:** Both actively used, stable, well-tested

**For OntServe Refactoring:**
- Maintain API contracts above
- Test integration points after changes
- Consider migrating to MCP-only for simplicity
- Document any breaking changes in advance

**Questions?** Check ProEthica implementation files listed above or test with curl commands.
