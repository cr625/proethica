# ProEthica Ontology Operations Guide

## Overview
This guide provides detailed instructions for modifying ontologies, managing the database, and understanding the extraction prompt system.

## Ontology Modification Procedures

### 1. TTL File Structure

#### Base Classes (proethica-core.ttl)
The 9 core ProEthica concepts must be defined here:
```turtle
@prefix proeth-core: <http://example.org/proethica-core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/BFO_> .
@prefix iao: <http://purl.obolibrary.org/obo/IAO_> .

# Role - WHO performs obligations
proeth-core:Role a owl:Class ;
    rdfs:subClassOf bfo:0000023 ;
    rdfs:label "Role"@en .

# Principle - WHY ethical foundations
proeth-core:Principle a owl:Class ;
    rdfs:subClassOf iao:0000030 ;
    rdfs:label "Principle"@en .

# Obligation - WHAT MUST be done
proeth-core:Obligation a owl:Class ;
    rdfs:subClassOf iao:0000030 ;
    rdfs:label "Obligation"@en .

# State - WHEN obligations activate
proeth-core:State a owl:Class ;
    rdfs:subClassOf bfo:0000015 ;
    rdfs:label "State"@en .

# Resource - WHAT guides decisions
proeth-core:Resource a owl:Class ;
    rdfs:subClassOf bfo:0000031 ;
    rdfs:label "Resource"@en .

# Action - Volitional behaviors
proeth-core:Action a owl:Class ;
    rdfs:subClassOf bfo:0000015 ;
    rdfs:label "Action"@en .

# Event - Temporal occurrences
proeth-core:Event a owl:Class ;
    rdfs:subClassOf bfo:0000003 ;
    rdfs:label "Event"@en .

# Capability - WHO CAN fulfill
proeth-core:Capability a owl:Class ;
    rdfs:subClassOf bfo:0000017 ;
    rdfs:label "Capability"@en .

# Constraint - WHAT CANNOT be done
proeth-core:Constraint a owl:Class ;
    rdfs:subClassOf iao:0000030 ;
    rdfs:label "Constraint"@en .
```

#### Subclasses (proethica-intermediate.ttl)
All specific types inherit from core classes:
```turtle
@prefix proeth: <http://example.org/proethica#> .
@prefix proeth-core: <http://example.org/proethica-core#> .

# Import core ontology
owl:imports <http://example.org/proethica-core> .

# Role is imported from proethica-core, not redefined here
# All role subclasses reference the core Role

proeth:ProfessionalRole a owl:Class ;
    rdfs:subClassOf proeth-core:Role ;  # MUST reference core
    rdfs:label "Professional Role"@en ;
    skos:definition "Role arising from professional qualifications and ethical obligations"@en ;
    dcterms:source <https://doi.org/10.1007/s10676-020-09526-2> .

proeth:ProviderClientRole a owl:Class ;
    rdfs:subClassOf proeth:ProfessionalRole ;
    rdfs:label "Provider-Client Role"@en ;
    skos:definition "Service delivery relationship with duties of competence"@en .
```

### 2. Database Operations

#### Direct Database Updates
When you need to update entities directly in the database:

```python
import psycopg2
from datetime import datetime

# Connect to OntServe database
conn = psycopg2.connect(
    host="localhost",
    database="ontserve",
    user="postgres",
    password="PASS"
)
cursor = conn.cursor()

# Get ontology ID
cursor.execute("""
    SELECT id FROM ontologies WHERE name = 'proethica-intermediate'
""")
ontology_id = cursor.fetchone()[0]

# Add new entity with proper parent_uri
base_class_uri = 'http://example.org/proethica-core#Role'
new_entity = {
    'uri': 'http://example.org/proethica#NewRole',
    'label': 'New Role Type',
    'comment': 'A new type of professional role'
}

cursor.execute("""
    INSERT INTO ontology_entities
    (ontology_id, uri, label, entity_type, parent_uri, comment, created_at)
    VALUES (%s, %s, %s, 'class', %s, %s, %s)
    ON CONFLICT (ontology_id, uri) DO UPDATE
    SET label = EXCLUDED.label,
        comment = EXCLUDED.comment,
        parent_uri = EXCLUDED.parent_uri
""", (ontology_id, new_entity['uri'], new_entity['label'],
      base_class_uri, new_entity['comment'], datetime.utcnow()))

conn.commit()
```

#### Refresh from TTL Files
After modifying TTL files, refresh the database:

```bash
cd /home/chris/onto/OntServe
python scripts/refresh_entity_extraction.py proethica-intermediate
```

The refresh script pattern:
```python
import sys
import os
sys.path.append('/home/chris/onto/OntServe')

from web.models import db, Ontology, OntologyEntity
from flask import Flask
from web.config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Set database URL
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5432/ontserve'

with app.app_context():
    # Read TTL file
    with open('ontologies/proethica-intermediate.ttl', 'r') as f:
        ttl_content = f.read()

    # Parse and extract entities
    from rdflib import Graph
    g = Graph()
    g.parse(data=ttl_content, format='turtle')

    # Update database...
```

### 3. MCP Server Database Queries

The MCP server uses recursive CTE queries to retrieve entity hierarchies:

```python
# In concept_manager_database.py
def get_role_hierarchy(self):
    query = """
    WITH RECURSIVE category_hierarchy AS (
        -- Base case: find Role class
        SELECT uri, label, parent_uri, comment
        FROM ontology_entities
        WHERE label = 'Role'
        AND entity_type = 'class'

        UNION

        -- Recursive case: find all subclasses
        SELECT e.uri, e.label, e.parent_uri, e.comment
        FROM ontology_entities e
        INNER JOIN category_hierarchy ch ON e.parent_uri = ch.uri
        WHERE e.entity_type = 'class'
    )
    SELECT * FROM category_hierarchy
    ORDER BY
        CASE
            WHEN label = 'Role' THEN 0
            WHEN parent_uri LIKE '%Role' THEN 1
            ELSE 2
        END,
        label
    """

    result = self.db.execute(text(query))
    return [dict(row) for row in result]
```

## Extraction Prompt System

### Action vs Event Apportionment Rules

**Critical Distinction**: Actions capture volition BY agents; Events capture occurrences AFFECTING agents.

#### When to Extract as Action
- Text emphasizes: DECISION, CHOICE, INTENTION, DELIBERATION
- Examples: "decides to report", "chooses to halt", "intends to disclose"
- Focus on: The volitional aspect of professional behavior

#### When to Extract as Event
- Text emphasizes: OCCURRENCE, HAPPENING, TRIGGER, DISCOVERY, CONSEQUENCE
- Examples: "report was filed", "construction halted", "incident occurred"
- Focus on: The temporal aspect that triggers obligations or state changes

#### Handling Dual Aspects
- Many scenarios contain both volitional and temporal aspects
- Extract the Action for the decision, Extract the Event for the occurrence
- Example: "Engineer reports safety issue"
  - Action: "Report Safety Issue" (the decision to report)
  - Event: "Safety Report Filed" (the occurrence of filing)

#### External Events
- Events without agent volition are ALWAYS extracted as Events
- Examples: earthquakes, equipment failures, regulatory changes
- These trigger professional obligations but aren't caused by professional actions

### 1. Prompt Structure

Each extractor follows this pattern:

```python
def create_enhanced_X_prompt(text: str,
                            include_mcp_context: bool = False,
                            existing_X: Optional[List] = None,
                            pass_context: Optional[Dict] = None) -> str:

    # 1. Fetch from MCP if needed
    if include_mcp_context and existing_X is None:
        from app.services.external_mcp_client import get_external_mcp_client
        external_client = get_external_mcp_client()
        existing_X = external_client.get_all_X_entities()

    # 2. Build theoretical grounding
    theoretical_section = """
    ## Theoretical Grounding
    Based on [Author et al. 2020], X represents...
    """

    # 3. Include existing ontology entities
    if existing_X:
        ontology_section = f"""
        ## EXISTING X IN ONTOLOGY ({len(existing_X)} concepts)

        The following X types are already defined:
        """
        for entity in existing_X:
            label = entity.get('label')
            definition = entity.get('definition', entity.get('comment', ''))
            ontology_section += f"- **{label}**: {definition}\n"

    # 4. Add extraction instructions
    extraction_section = """
    ## Extraction Instructions

    1. Identify X in the text
    2. Check if it matches existing ontology concepts
    3. Extract with proper context
    4. Return in JSON format
    """

    # 5. Include pass context if provided
    if pass_context:
        context_section = build_pass_context(pass_context)

    return theoretical_section + ontology_section + extraction_section + context_section
```

### 2. Pass Integration Context

#### Pass 1 Context (Contextual Framework)
```python
pass1_context = {
    'roles': [...],      # WHO acts
    'states': [...],     # WHEN activated
    'resources': [...]   # WHAT guides
}
```

#### Pass 2 Context (Normative Requirements)
```python
pass2_context = {
    'principles': [...],    # WHY (foundations)
    'obligations': [...],   # WHAT MUST
    'constraints': [...],   # WHAT CANNOT
    'capabilities': [...]   # WHO CAN
}
```

#### Pass 3 Context (Temporal Dynamics)
```python
pass3_context = {
    'actions': [...],    # Behavioral manifestations
    'events': [...],     # Temporal triggers
    'pass1': pass1_context,  # Include earlier passes
    'pass2': pass2_context
}
```

### 3. JSON Output Format with Enhanced Fields

All extractors must return this format with enhanced field preservation:

#### Basic Structure
```json
{
    "extracted_X": [
        {
            "text": "The engineer must report safety issues",
            "label": "Report Safety Issues",
            "type": "X",
            "subtype": "SpecificXType",
            "context": "Found in paragraph discussing obligations",
            "existing_match": "SafetyObligation",
            "confidence": 0.95
        }
    ],
    "metadata": {
        "total_extracted": 3,
        "existing_matches": 2,
        "new_concepts": 1,
        "pass_integration": {
            "related_roles": ["Engineer"],
            "triggered_by_states": ["Safety Risk Identified"]
        }
    }
}
```

#### Enhanced Fields for Roles
```json
{
    "label": "Safety Engineer",
    "description": "Professional responsible for safety assessment",
    "type": "role",
    "confidence": 0.9,
    "role_category": "professional_peer",        // Top-level access
    "obligations_generated": ["Safety Review"],   // Top-level access
    "ethical_filter_function": "Filters decisions through safety lens",
    "is_existing": false,                        // Ontology match status
    "ontology_match_reasoning": "New specialized role not in ontology",
    "theoretical_grounding": "Kong et al. (2020)",
    "debug": {
        "raw_llm_data": {...}  // Complete LLM response preserved
    }
}
```

#### Enhanced Fields for Resources
```json
{
    "label": "NSPE Code of Ethics",
    "description": "Professional engineering ethics code",
    "type": "resource",
    "confidence": 0.95,
    "resource_category": "professional_code",     // Top-level access
    "extensional_function": "Provides concrete ethical guidance",
    "authority_level": "primary",                 // Primary/secondary/supplementary
    "is_existing": true,                         // Ontology match status
    "ontology_match_reasoning": "Matches existing NSPE Code entity",
    "professional_knowledge_type": "codified_standards",
    "debug": {
        "raw_llm_data": {...}  // Complete LLM response preserved
    }
}
```

#### Enhanced Fields for Actions (Pass 3)
```json
{
    "label": "Report Safety Issue",
    "description": "Volitional decision to report identified safety concerns",
    "action_type": "Communication",
    "volitional_nature": "Deliberate choice to disclose safety information",
    "professional_context": "Engineering obligation to protect public welfare",
    "pass_integration": {
        "fulfills_obligations": ["Safety Reporting Obligation"],
        "requires_capabilities": ["Communication Skills", "Risk Assessment"],
        "constrained_by": ["Confidentiality Constraints"],
        "appropriate_states": ["Safety Risk Identified"]
    },
    "temporal_relationship": {
        "becomes_event": "Safety Report Filed",
        "triggered_by_events": ["Safety Incident Discovered"]
    },
    "confidence": 0.9
}
```

#### Enhanced Fields for Events (Pass 3)
```json
{
    "label": "Safety Report Filed",
    "description": "Temporal occurrence of safety report being submitted",
    "event_type": "Compliance",
    "temporal_nature": "Occurs after decision to report",
    "triggering_conditions": "Report submitted to authorities",
    "ethical_significance": "Triggers investigation and review processes",
    "pass_integration": {
        "triggers_obligations": ["Investigation Cooperation"],
        "changes_states": ["Under Review"],
        "affects_roles": ["Safety Officer", "Engineer"],
        "requires_capabilities": ["Incident Response"]
    },
    "causal_relationships": {
        "caused_by_actions": ["Report Safety Issue"],
        "leads_to_events": ["Investigation Initiated"],
        "is_external": "false"
    },
    "confidence": 0.85
}
```

## Academic Grounding Requirements

### Citation Format
All entity definitions must include scholarly references:

```turtle
proeth:EntityName a owl:Class ;
    rdfs:subClassOf proeth-core:BaseClass ;
    rdfs:label "Entity Name"@en ;
    iao:0000115 "Technical BFO-aligned definition"@en ;
    skos:definition "Professional ethics contextual definition with practical meaning"@en ;
    dcterms:source <https://doi.org/10.1234/example2020> ;
    dcterms:references "Kong et al. (2020); Dennis et al. (2016)" .
```

### Key Literature Sources
Primary references from Chapter 2:
- **Roles**: Kong et al. (2020), Oakley & Cocking (2001)
- **States**: Dennis et al. (2016), Berreby et al. (2017)
- **Resources**: McLaren (2003), Davis (1991)
- **Principles**: Beauchamp & Childress (2013), Ross (1930)
- **Obligations**: Brandt (1964), Von Wright (1963)
- **Constraints**: Moor (2006), Powers (2006)
- **Capabilities**: Tolmeijer et al. (2021), Anderson (2018)
- **Actions**: Wallach & Allen (2009), Arkin (2008)
- **Events**: Govindarajulu & Bringsjord (2017)

## UI Route Integration

### Step 1 (Pass 1: Contextual Framework)
```python
# In app/routes/scenario_pipeline/step1.py
@bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        # Get section text
        section_text = request.form.get('section_text')

        # Create enhanced prompts with MCP
        from app.services.extraction.enhanced_prompts_roles_resources import (
            create_enhanced_roles_prompt,
            create_enhanced_resources_prompt
        )
        from app.services.extraction.enhanced_prompts_states_capabilities import (
            create_enhanced_states_prompt
        )

        roles_prompt = create_enhanced_roles_prompt(
            section_text,
            include_mcp_context=True
        )
        states_prompt = create_enhanced_states_prompt(
            section_text,
            include_mcp_context=True
        )
        resources_prompt = create_enhanced_resources_prompt(
            section_text,
            include_mcp_context=True
        )

        # Extract entities...
```

### Step 2 (Pass 2: Normative Requirements)
```python
# In app/routes/scenario_pipeline/step2.py
@bp.route('/step2', methods=['GET', 'POST'])
def step2():
    # Similar pattern for principles, obligations, constraints, capabilities
    pass
```

### Step 3 (Pass 3: Temporal Dynamics)
```python
# In app/routes/scenario_pipeline/step3.py
@bp.route('/step3', methods=['GET', 'POST'])
def step3():
    # Actions and events with full pass context
    pass
```

## Testing Procedures

### 1. Test MCP Retrieval
```bash
cd /home/chris/onto/proethica
python scripts/test_all_extractors.py
```

### 2. Test Specific Entity Type
```python
# Example: Test obligations
from app.services.external_mcp_client import get_external_mcp_client

client = get_external_mcp_client()
obligations = client.get_all_obligation_entities()

print(f"Found {len(obligations)} obligations:")
for ob in obligations:
    print(f"  - {ob['label']}: {ob.get('definition', 'No definition')}")
```

### 3. Test UI Integration
1. Start all services
2. Navigate to http://localhost:5000
3. Select a case
4. Go to Step 1/2/3
5. Click extraction buttons
6. Verify prompts show ontology entities

## Critical Issues & Fixes

### CRITICAL FIX NEEDED: Duplicate Core Concept Definitions
**Problem**: The proethica-intermediate ontology is redefining all 9 core ProEthica concepts instead of importing them from proethica-core.

**Impact**:
- Database contains 2-3 copies of each core concept (Role, Principle, Obligation, etc.)
- Extraction returns duplicates requiring deduplication
- Violates proper ontology architecture

**Current Status** (December 2024):
```
Resource   | ✅ FIXED (serves as template)
Role       | ❌ Needs fix (3 copies)
Principle  | ❌ Needs fix (2 copies)
Obligation | ❌ Needs fix (2 copies)
State      | ❌ Needs fix (2 copies)
Action     | ❌ Needs fix (2 copies)
Event      | ❌ Needs fix (2 copies)
Capability | ❌ Needs fix (2 copies)
Constraint | ❌ Needs fix (2 copies)
```

**Fix Pattern** (follow Resource example):
1. Remove the class definition from proethica-intermediate.ttl
2. Add comment: `# [Concept] is imported from proethica-core, not redefined here`
3. Update ALL subclasses: `rdfs:subClassOf proeth-core:[Concept]`
4. Update ALL property ranges/domains to use `proeth-core:[Concept]`
5. Refresh database: `python scripts/refresh_entity_extraction.py proethica-intermediate`

## Troubleshooting

### Problem: Duplicate Entities
**Cause**: Both proethica-core and proethica-intermediate defining same class
**Solution**: Remove from intermediate, use `rdfs:subClassOf proeth-core:X`

### Problem: Missing Entities in MCP
**Cause**: MCP server not restarted after TTL changes
**Solution**:
```bash
pkill -f "mcp_server.py"
cd /home/chris/onto/OntServe && python servers/mcp_server.py
```

### Problem: Parser Errors
**Cause**: Missing prefixes in TTL file
**Solution**: Add all required prefixes:
```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix iao: <http://purl.obolibrary.org/obo/IAO_> .
@prefix bfo: <http://purl.obolibrary.org/obo/BFO_> .
```

### Problem: Wrong Entity Count
**Cause**: Not using recursive CTE for retrieval
**Solution**: Ensure using parent_uri based queries, not label matching

## Important Scripts

### Load Entities to Database
```python
# Pattern from load_actions_events_to_db.py
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="ontserve",
    user="postgres",
    password="PASS"
)

# Define entities with parent_uri
entities = [
    {
        'uri': 'http://example.org/proethica#NewEntity',
        'label': 'New Entity',
        'parent_uri': 'http://example.org/proethica-core#BaseClass',
        'comment': 'Description'
    }
]

# Insert with parent_uri for hierarchy
for entity in entities:
    cursor.execute("""
        INSERT INTO ontology_entities
        (ontology_id, uri, label, entity_type, parent_uri, comment)
        VALUES (%s, %s, %s, 'class', %s, %s)
        ON CONFLICT (ontology_id, uri) DO UPDATE
        SET parent_uri = EXCLUDED.parent_uri
    """, (ontology_id, entity['uri'], entity['label'],
          entity['parent_uri'], entity['comment']))
```

### Verify Database State
```sql
-- Check entity hierarchy
WITH RECURSIVE category_hierarchy AS (
    SELECT uri, label, parent_uri
    FROM ontology_entities
    WHERE label = 'Role' AND entity_type = 'class'
    UNION
    SELECT e.uri, e.label, e.parent_uri
    FROM ontology_entities e
    INNER JOIN category_hierarchy ch ON e.parent_uri = ch.uri
)
SELECT label, parent_uri FROM category_hierarchy ORDER BY label;
```

## Advanced Ontology Features

### Ontology Relationships (Based on Chapter 2 Literature)

Key relationships that should be added to better represent professional ethics:

#### Role-State Coupling (Dennis et al. 2016)
```turtle
proethica:activatesInContext rdfs:domain proethica:Role ;
                            rdfs:range proethica:State .
proethica:filtersObligationsIn rdfs:domain proethica:Role ;
                               rdfs:range proethica:State .
```

#### Capability-Normative Integration (Tolmeijer et al. 2021)
```turtle
proethica:enablesComplianceWith rdfs:domain proethica:Capability ;
                               rdfs:range proethica:Obligation .
proethica:operationalizes rdfs:domain proethica:Capability ;
                         rdfs:range proethica:Principle .
```

#### Resource-Extensional Definition (McLaren 2003)
```turtle
proethica:providesExtensionalDefinitionFor rdfs:domain proethica:Resource ;
                                          rdfs:range proethica:Principle .
proethica:containsPrecedentFor rdfs:domain proethica:Resource ;
                               rdfs:range proethica:Action .
```

#### Action-Event Temporal Dynamics (Berreby et al. 2017)
```turtle
proethica:causesEvent rdfs:domain proethica:Action ;
                     rdfs:range proethica:Event .
proethica:triggersAction rdfs:domain proethica:Event ;
                        rdfs:range proethica:Action .
```

### Ontology-Driven LangExtract Framework

The system supports ontology-driven document analysis using section type definitions:

#### Configuration
```bash
ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT=true  # In .env
```

#### Enhanced Section Types (proethica-cases.ttl)
```turtle
proeth-cases:FactualSection a owl:Class ;
    skos:definition "Environmental states and contextual factors"@en ;
    proeth-cases:hasLangExtractPrompt "Extract factual_statements, environmental_conditions"@en ;
    proeth-cases:hasExtractionTarget "factual_statements"@en ;
    proeth-cases:analysisPriority "1"^^xsd:integer .

proeth-cases:EthicalQuestionSection a owl:Class ;
    skos:definition "Professional judgment and decision-making contexts"@en ;
    proeth-cases:hasExtractionTarget "ethical_questions, moral_dilemmas"@en ;
    proeth-cases:analysisPriority "2"^^xsd:integer .
```

#### NSPE-Specific Types (engineering-ethics.ttl)
```turtle
eng-ethics:CodeReferenceSection a owl:Class ;
    skos:definition "Professional code citations with precedents"@en ;
    dcterms:source <https://www.nspe.org/resources/ethics/code-ethics> ;
    proeth-cases:hasExtractionTarget "code_provisions, precedent_interpretations"@en .
```

#### Integration Flow
1. Step1a queries OntServe for section type definitions
2. MCP returns scholarly-grounded definitions with extraction targets
3. LangExtract generates context-aware prompts
4. Results validated against extraction targets

---

*Last Updated: September 14, 2025*
*This guide consolidates multiple ontology-related documents including modification procedures, relationship updates, and LangExtract integration*