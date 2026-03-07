# Ontology Integration

This document describes ProEthica's integration with OntServe for ontology management.

## Overview

ProEthica uses OntServe as its central ontology repository. The integration provides:

- Concept definitions for extraction validation
- Class hierarchy for entity classification
- SPARQL queries for knowledge retrieval
- Candidate concept submission

## Architecture

```text
ProEthica                            OntServe
+------------+                      +------------+
| MCP Client |-- Streamable HTTP -->| FastMCP 3  |
|            |<------ SSE ----------|   :8082    |
+------------+                      +------+-----+
                                           |
                                           v
                                    +------------+
                                    | PostgreSQL |
                                    | (ontologies|
                                    +------------+
```

## Model Context Protocol (MCP)

### Connection

ProEthica connects to OntServe via the MCP Streamable HTTP transport:

| Setting | Default |
|---------|---------|
| URL | http://localhost:8082 |
| Protocol | MCP (JSON-RPC 2.0 over Streamable HTTP) |
| Server | FastMCP 3.x |

### Configuration

Environment variables:

```bash
ONTSERVE_MCP_URL=http://localhost:8082
```

ProEthica auto-detects OntServe availability on startup and sets `ONTSERVE_MCP_ENABLED` accordingly.

## MCP Client

### Client Implementation

Two layers handle MCP communication:

| File | Purpose |
|------|---------|
| `app/services/mcp_transport.py` | Low-level MCP Streamable HTTP transport (session management, SSE parsing) |
| `app/services/external_mcp_client.py` | High-level tool wrappers used by extraction pipeline |

### Connection Management

```python
from app.services.external_mcp_client import get_external_mcp_client

client = get_external_mcp_client()
result = client.get_entities_by_category("Role")
```

## Available Methods

OntServe MCP provides 11 tools. The three most commonly used in ProEthica's extraction pipeline are documented below. See [Architecture](architecture.md) for the full tool list.

### get_entities_by_category

Retrieves entities of a specific type from the ontology.

**Request** (MCP call_tool format):
```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "get_entities_by_category",
    "arguments": {
      "category": "Role",
      "domain_id": "proethica-intermediate"
    }
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "{\"entities\": [{\"uri\": \"proeth:Engineer\", \"label\": \"Engineer\"}]}"
    }]
  },
  "id": 1
}
```

### sparql_query

Executes SPARQL queries against the ontology.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "sparql_query",
    "arguments": {
      "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
      "domain_id": "proethica-intermediate"
    }
  },
  "id": 2
}
```

### submit_candidate_concept

Submits new concept for ontology review.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "submit_candidate_concept",
    "arguments": {
      "label": "AI Verification",
      "category": "Capability",
      "definition": "Ability to verify AI-generated outputs",
      "source": "Case 24-2",
      "domain_id": "proethica-intermediate"
    }
  },
  "id": 3
}
```

## Ontology Structure

### Three-Layer Architecture

ProEthica uses a three-layer ontology:

| Layer | Purpose | Example Classes |
|-------|---------|-----------------|
| Core | 9 foundational concepts | Role, Principle, Obligation |
| Intermediate | Domain-specific | Engineer, PublicSafety |
| Case | Instance data | Case24_2_Engineer |

### Core Ontology (proethica-core)

Defines the 9 component types:

| Class | URI | Description |
|-------|-----|-------------|
| Role | proeth-core:Role | Professional positions |
| Principle | proeth-core:Principle | Abstract standards |
| Obligation | proeth-core:Obligation | Concrete duties |
| State | proeth-core:State | Situational context |
| Resource | proeth-core:Resource | Available knowledge |
| Action | proeth-core:Action | Professional behaviors |
| Event | proeth-core:Event | Precipitating occurrences |
| Capability | proeth-core:Capability | Permissions |
| Constraint | proeth-core:Constraint | Prohibitions |

### Intermediate Ontology (proethica-intermediate)

Domain-specific subclasses:

```turtle
proeth-int:Engineer rdfs:subClassOf proeth-core:Role .
proeth-int:CompetenceRequirement rdfs:subClassOf proeth-core:Obligation .
proeth-int:NSPECodeProvision rdfs:subClassOf proeth-core:Resource .
```

### Case Analysis Classes (Step 4)

Step 4 produces 8 additional entity types beyond the 9 base concepts:

| Class | Phase | Description |
|-------|-------|-------------|
| `CodeProvisionReference` | 2A | NSPE code sections cited in the case |
| `PrecedentCaseReference` | 2B | BER cases referenced in the discussion |
| `EthicalQuestion` | 2C | Questions posed to Board for ethical review |
| `EthicalConclusion` | 2C | Board's formal determinations |
| `CanonicalDecisionPoint` | Phase 3 | Points where ethical choices must be made (E1-E3 synthesis) |
| `ResolutionPattern` | 2E | Patterns of how ethical tensions are resolved |
| `CausalNormativeLink` | 2E | Connections between causal factors and normative principles |
| `QuestionEmergence` | 2E | How ethical questions arise from case facts |

Properties:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `hasOption` | DecisionPoint | DecisionOption | Links decision point to options |
| `involvesRole` | DecisionPoint | Role | Professional roles involved |
| `appliesProvision` | DecisionPoint | EthicalCode | Applicable code provisions |
| `isBoardChoice` | DecisionOption | boolean | Whether this option was chosen |
| `answersQuestion` | BoardConclusion | EthicalQuestion | Links conclusion to question |

The full extraction pipeline produces **17 entity types** across all 4 steps (9 base concepts + 8 Step 4 types).

## Entity Review Integration

### Available Classes Display

During entity review, ProEthica fetches available classes:

```python
# In entity_review.py
from app.services.external_mcp_client import get_external_mcp_client

def get_available_classes(category):
    client = get_external_mcp_client()
    return client.get_entities_by_category(category)
```

### Class Assignment

When user assigns entity to existing class:

1. Entity `class_uri` updated to match ontology class
2. Definition may be inherited or customized
3. Relationship to parent class preserved

### New Class Approval

When approving new class:

1. `submit_candidate_concept()` called
2. OntServe creates candidate entry
3. Admin reviews in OntServe
4. Approved classes added to ontology

## SPARQL Queries

### Common Queries

**Get all Roles:**
```sparql
PREFIX proeth: <http://proethica.org/ontology#>
SELECT ?role ?label ?definition
WHERE {
  ?role rdfs:subClassOf proeth:Role .
  ?role rdfs:label ?label .
  OPTIONAL { ?role rdfs:comment ?definition }
}
```

**Get Obligations for a Role:**
```sparql
PREFIX proeth: <http://proethica.org/ontology#>
SELECT ?obligation ?label
WHERE {
  ?role rdfs:label "Engineer" .
  ?obligation proeth:generatedBy ?role .
  ?obligation rdfs:label ?label .
}
```

### Query Execution

Via MCP client:

```python
query = """
SELECT ?s ?label WHERE {
  ?s rdfs:label ?label .
  ?s a proeth:Role .
}
"""
results = await client.sparql_query(query)
```

## Error Handling

### Connection Failures

If OntServe unavailable:

```python
try:
    entities = await client.get_entities_by_category("Role")
except MCPConnectionError:
    # Fallback to cached data or empty list
    entities = []
```

### Timeout Handling

Configurable timeout with retry:

```python
from app.services.mcp_transport import MCPTransport

transport = MCPTransport(timeout=30)
```

### Graceful Degradation

ProEthica continues functioning without OntServe:

- Available Classes section shows empty
- Extraction still works
- Entities stored locally
- Manual ontology sync later

## Caching

### Class Cache

Available classes cached to reduce queries:

| Setting | Value |
|---------|-------|
| Cache duration | 5 minutes |
| Invalidation | On new class approval |

### Query Cache

SPARQL results cached:

| Setting | Value |
|---------|-------|
| Cache duration | 1 minute |
| Key | Query hash |

## Monitoring

### Connection Status

Header shows connection status:

- Green: Connected
- Yellow: Degraded
- Red: Disconnected

### Health Check

Periodic health check:

```python
async def health_check():
    try:
        await client.get_entities_by_category("Role")
        return True
    except:
        return False
```

## Troubleshooting

### MCP Not Responding

1. Check OntServe MCP is running:
   ```bash
   curl -s http://localhost:8082/health
   ```

2. Verify port 8082 not blocked

3. Check OntServe logs

### Empty Available Classes

1. Verify MCP connection active
2. Check ontology loaded in OntServe
3. Query database directly:
   ```sql
   SELECT * FROM ontology_classes WHERE type = 'Role';
   ```

### Query Failures

1. Validate SPARQL syntax
2. Check ontology namespaces
3. Review OntServe error logs

## Related Documentation

- [System Architecture](architecture.md)
- [Entity Review](../analysis/entity-review.md)
- [Settings](settings.md)
