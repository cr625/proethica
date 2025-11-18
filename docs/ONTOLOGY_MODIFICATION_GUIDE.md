# OntServe Ontology Modification Guide

## Overview
This guide documents the proper way to make changes to ontologies in OntServe, based on analysis of the existing system architecture and versioning mechanisms.

## System Architecture

### Database Models
- **`Ontology`**: Main ontology metadata (name, base_uri, description, etc.)
- **`OntologyVersion`**: Version tracking with sequential numbering and content storage
- **`OntologyEntity`**: Extracted entities (classes, properties, individuals) with embeddings

### Key Files
- **Import Route**: `/home/chris/onto/OntServe/web/app.py:618` - Main import functionality
- **Models**: `/home/chris/onto/OntServe/web/models.py` - Database schema
- **OntologyManager**: `/home/chris/onto/OntServe/core/ontology_manager.py` - Core management logic

## Versioning System Details

### OntologyVersion Model Fields
```python
- id: Primary key
- ontology_id: Foreign key to Ontology
- version_number: Sequential integer (1, 2, 3...)
- version_tag: Human-readable version (e.g., "1.0.0", "1.1.0-draft")
- content: TTL content as text
- change_summary: Description of changes
- created_by: User/system that created version
- is_current: Boolean flag for active version
- is_draft: Boolean for draft vs published
- workflow_status: 'draft', 'review', 'published'
- meta_data: JSON metadata
```

## Proper Modification Methods

### 1. For New Ontologies
```python
# Via Import Route
POST /import
- source_type: 'url' or 'upload'
- name: ontology name
- description: description
- use_reasoning: true/false

# Via OntologyManager
result = app.ontology_manager.import_ontology(
    source=url_or_file_path,
    importer_type='prov',
    name=name,
    description=description,
    format='turtle'
)
```

### 2. For Updating Existing Ontologies
```python
# Create new version
version = OntologyVersion(
    ontology_id=ontology.id,
    version_number=next_version_number,  # Increment from last
    version_tag="1.1.0",  # Semantic version
    content=new_ttl_content,
    change_summary="Description of changes",
    created_by="system",
    is_current=True,  # Set to current
    is_draft=False,   # or True for drafts
    workflow_status='published'
)

# Set previous version to not current
OntologyVersion.query.filter_by(
    ontology_id=ontology.id, is_current=True
).update({'is_current': False})

# Add and commit
db.session.add(version)
db.session.commit()

# Re-extract entities
entity_counts = _extract_entities_from_content(ontology, new_ttl_content)
```

### 3. Via Draft API (Recommended)
```python
POST /editor/api/ontologies/<ontology_name>/draft
{
    "concepts": [...],  # Extracted concepts
    "base_imports": [...],  # Import dependencies
    "metadata": {...},
    "created_by": "system",
    "parent_ontology": "parent_name"  # Optional
}
```

## Entity Extraction Process

After creating/updating versions, entities are automatically extracted:

```python
# Done automatically by _extract_entities_from_content()
# Parses TTL content and creates OntologyEntity records for:
- Classes (owl:Class)
- Object Properties (owl:ObjectProperty) 
- Datatype Properties (owl:DatatypeProperty)
- Individuals (owl:NamedIndividual)

# Each entity gets:
- URI, label, comment
- Parent relationships (subClassOf)
- Domain/range for properties
- Vector embeddings for semantic search
```

## Version Number Management Rules

1. **Sequential Integers**: Version numbers must be sequential per ontology (1, 2, 3...)
2. **Unique Constraint**: `(ontology_id, version_number)` must be unique
3. **Current Version**: Only one version per ontology can have `is_current=True`
4. **Version Tags**: Use semantic versioning for human readability ("1.0.0", "1.1.0", "2.0.0")
5. **Draft Handling**: Drafts can exist alongside published versions

## Available APIs and Routes

### Import/Creation
- `POST /import` - Main import interface
- `POST /editor/api/ontologies/<name>/draft` - Create draft versions
- `app.ontology_manager.import_ontology()` - Programmatic import

### Updates
- `POST /ontology/<name>/save` - Save new version via editor
- `POST /editor/ontology/<name>/save` - Editor API save
- `POST /api/versions/<id>/make-current` - Switch current version

### Entity Management
- `POST /editor/api/extract-entities/<name>` - Re-extract entities
- Automatic extraction on version creation

## Content Format Requirements

- **Primary Format**: Turtle (TTL)
- **Auto-conversion**: From RDF/XML, JSON-LD, N-Triples, N3
- **Validation**: Content is parsed with rdflib before storage
- **Entity Extraction**: OWL classes, properties, and individuals extracted automatically

## Best Practices

1. **Always increment version numbers** - Never reuse version numbers
2. **Use meaningful version tags** - Follow semantic versioning conventions
3. **Document changes** - Use `change_summary` field to describe modifications

## Related Documentation

### Ontology Relationship Updates
See **[ONTOLOGY_RELATIONSHIPS_UPDATE.md](./ONTOLOGY_RELATIONSHIPS_UPDATE.md)** for detailed documentation on:
- New relationships identified from Chapter 2 literature analysis
- Role-State coupling (Dennis et al. 2016)
- Capability-Normative integration (Tolmeijer et al. 2021)
- Resource-Extensional definition (McLaren 2003)
- Action-Event temporal dynamics (Berreby et al. 2017)
- Implementation recommendations and priority order
4. **Test extraction** - Verify entities are extracted correctly after changes
5. **Handle drafts properly** - Use draft workflow for review before publishing
6. **Maintain parent relationships** - For derived ontologies, set `parent_ontology_id`

## Database Connection and Environment Setup

### Required Environment Variables
```bash
# CORRECTED DATABASE CREDENTIALS
export DATABASE_URL='postgresql://postgres:PASS@localhost:5432/ontserve'
export FLASK_CONFIG='development'
```

**IMPORTANT**: Previous documentation incorrectly showed `ontserve_user:ontserve_development_password`. The correct credentials are `postgres:PASS` as found in the OntServe `.env` file.

### Direct Database Update Method (TESTED AND WORKING)
```python
# Use this method for direct database updates when web interface isn't accessible
import os
import sys
sys.path.append('.')

# Set required environment variables
os.environ['DATABASE_URL'] = 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve'
os.environ['FLASK_CONFIG'] = 'development'

from web.models import db, Ontology, OntologyVersion, OntologyEntity
from flask import Flask
from web.config import Config
from datetime import datetime, timezone
import hashlib

# Create Flask app with minimal config
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
from web.models import init_db
init_db(app)

with app.app_context():
    # Your ontology update code here
    # (See full example below)
```

## Example Implementation - TESTED WORKING METHOD

```python
def update_ontology_database(ontology_name, ttl_file_path, version_tag, change_summary):
    """
    Update an ontology in the OntServe database with proper versioning.
    
    TESTED METHOD - Use this exact pattern for database updates.
    
    Args:
        ontology_name: Name of ontology to update (e.g., 'proethica-core')
        ttl_file_path: Path to TTL file with new content
        version_tag: Version tag (e.g., 'v2.0.0-bfo-corrected')
        change_summary: Description of changes made
    """
    
    import os
    import sys
    sys.path.append('.')
    
    # CRITICAL: Set environment variables first - CORRECTED CREDENTIALS
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5432/ontserve'
    os.environ['FLASK_CONFIG'] = 'development'
    
    from web.models import db, Ontology, OntologyVersion
    from flask import Flask
    from web.config import Config
    from datetime import datetime, timezone
    import hashlib
    
    # Create Flask app with minimal config
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize database
    from web.models import init_db
    init_db(app)
    
    with app.app_context():
        # Find existing ontology
        ontology = Ontology.query.filter_by(name=ontology_name).first()
        if not ontology:
            print(f'Ontology {ontology_name} not found - create it first!')
            return None
        
        print(f'Found existing ontology: {ontology.name} (ID: {ontology.id})')
        
        # Get next version number
        last_version = OntologyVersion.query.filter_by(
            ontology_id=ontology.id
        ).order_by(OntologyVersion.version_number.desc()).first()
        
        next_version = (last_version.version_number + 1) if last_version else 1
        print(f'Creating version {next_version}')
        
        # Read TTL content
        with open(ttl_file_path, 'r') as f:
            content = f.read()
        
        # Create content hash for integrity
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # IMPORTANT: Set all existing versions to not current
        OntologyVersion.query.filter_by(
            ontology_id=ontology.id
        ).update({'is_current': False})
        
        # Create new version
        new_version = OntologyVersion(
            ontology_id=ontology.id,
            version_number=next_version,
            version_tag=version_tag,
            content=content,
            content_hash=content_hash,
            change_summary=change_summary,
            created_by='ontology-update-script',
            is_current=True,    # Make this the current version
            is_draft=False,     # Published, not draft
            workflow_status='published',
            meta_data={
                'update_date': datetime.now(timezone.utc).isoformat(),
                'file_source': ttl_file_path
            }
        )
        
        db.session.add(new_version)
        db.session.commit()
        
        print(f'Successfully created version {next_version} with ID: {new_version.id}')
        return new_version.id

# EXAMPLE USAGE - BFO Alignment Update (2025-08-30)
# This exact pattern was used successfully to update both ontologies:

def update_proethica_ontologies():
    """Update both ProEthica ontologies with BFO corrections - TESTED AND WORKING"""
    
    # Update proethica-core
    update_ontology_database(
        ontology_name='proethica-core',
        ttl_file_path='/home/chris/onto/OntServe/ontologies/proethica-core.ttl',
        version_tag='v2.0.0-bfo-corrected',
        change_summary='Corrected BFO alignments: Capability→RealizableEntity, Resource→IndependentContinuant, added formal OWL structure with proper imports'
    )
    
    # Update proethica-intermediate  
    update_ontology_database(
        ontology_name='proethica-intermediate',
        ttl_file_path='/home/chris/onto/OntServe/ontologies/proethica-intermediate.ttl',
        version_tag='v9.0.0-bfo-corrected',
        change_summary='Corrected BFO alignments: Capability→RealizableEntity, Resource→IndependentContinuant, maintained consistency with proethica-core'
    )
```

## TTL File Validation Requirements

**CRITICAL**: TTL files must have all required prefix declarations or entity extraction will fail.

### Common Prefix Requirements
Ensure these prefixes are declared when using corresponding terms:
```turtle
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
```

**Failure Symptoms**: Entity extraction returns errors like:
```
Bad syntax (Prefix "dcterms:" not bound)
```

### Entity Extraction Trigger
After successful database update, manually trigger entity extraction:
```bash
# Trigger entity re-extraction (critical for ontology visibility)
curl -X POST http://localhost:5003/editor/api/extract-entities/<ontology-name>

# Verify success - should return {"success": true}
```

## Updated Database Schema Notes

Based on recent implementation, confirmed database table names:
- Tables use **plural names**: `ontologies`, `ontology_versions` (not singular)
- Column names: `metadata` (not `meta_data`)
- Fields `is_draft` and `workflow_status` may not exist in current schema

## Verification Commands

After database updates, verify success with:
```bash
# Check ontology content was updated
curl -s -H "Accept: text/turtle" http://localhost:5003/ontology/proethica-cases | grep -A 10 "FactualSection"

# Check enhanced definitions with scholarly references
curl -s -H "Accept: text/turtle" http://localhost:5003/ontology/engineering-ethics | grep -A 15 "CodeReferenceSection"

# Verify entities were extracted successfully
curl -s http://localhost:5003/api/ontologies | jq '.[] | select(.name == "proethica-cases")'
```

## Recent Updates and Lessons Learned (September 2025)

### Ontology-Driven LangExtract Integration
Successfully implemented ontology-driven LangExtract framework with enhanced section type definitions:

1. **Enhanced Section Types**: Added scholarly definitions with references from Chapter 2 literature review
2. **LangExtract Integration Properties**: 
   - `proeth-cases:hasLangExtractPrompt` - Custom extraction prompts
   - `proeth-cases:hasExtractionTarget` - Specific content targets
   - `proeth-cases:analysisPriority` - Processing order
3. **NSPE-Specific Extensions**: Domain-specific section types in engineering-ethics ontology

### Database Update Pattern (TESTED September 2025)
```python
# Successful pattern used for enhanced definitions update
def update_enhanced_definitions():
    # 1. Update TTL files with enhanced content
    # 2. Ensure all prefixes declared (especially dcterms:)
    # 3. Run database update script with correct credentials
    # 4. Trigger entity re-extraction via API
    # 5. Verify content visible in OntServe
```

**Files Updated**:
- `proethica-cases.ttl` → v6 with enhanced scholarly definitions
- `engineering-ethics.ttl` → v9 with NSPE-specific enhancements

## ProEthica 9-Concept Formalism Updates (September 2025)

### Resource and Role Definition Enhancement Project

Successfully completed comprehensive updates to Resource and Role definitions in proethica-intermediate ontology, aligning them with Chapter 2 literature review requirements.

#### Key Changes Made

**Resource Definitions Enhancement**:
1. **Scholarly Citations Added**: All resources now include `dcterms:source` with proper DOI references
2. **Professional Knowledge Focus**: Aligned definitions with McLaren's extensional principles approach
3. **Four Core Resource Types**: ProfessionalCode, CasePrecedent, ExpertInterpretation, TechnicalStandard
4. **Enhanced Definitions**: Added comprehensive `skos:definition` with professional context

**Role Definitions Enhancement**:
1. **Chapter 2 Alignment**: Incorporated Oakley & Cocking (2001), Dennis et al. (2016), Kong et al. (2020) requirements
2. **Role Function Theory**: Added professional role filtering and obligation generation concepts
3. **Identity Role Categories**: Added Provider-Client, Professional Peer, Employer Relationship, Public Responsibility roles
4. **Scholarly Grounding**: All major role types now include proper academic citations

#### Systematic Update Process

**Phase 1: Requirements Analysis**
```bash
# 1. Read and analyze Chapter 2 literature review requirements
# 2. Compare current definitions against scholarly framework
# 3. Identify gaps in professional knowledge representation
# 4. Plan enhancement strategy with proper citations
```

**Phase 2: Definition Enhancement**
```turtle
# Pattern used for enhanced definitions:
proeth:ResourceType a owl:Class ;
    rdfs:subClassOf proeth:ParentClass ;
    rdfs:label "Resource Label"@en ;
    iao:0000115 "Technical definition from BFO/IAO"@en ;
    skos:definition "Professional ethics definition with contextual meaning and extensional grounding"@en ;
    dcterms:source <https://doi.org/academic-citation>, <https://doi.org/secondary-source> ;
    proeth:standardsAuthority "Relevant professional standards" .
```

**Phase 3: Database Synchronization**
```bash
# 1. Add missing TTL prefix declarations (critical step)
# 2. Run refresh_entity_extraction.py to update database
# 3. Update DatabaseConceptManager subclass mappings
# 4. Verify entity extraction succeeded with proper error recovery
```

### Best Practices Learned

#### 1. Prefix Declaration Management
**Critical Requirement**: All TTL files must have complete prefix declarations before entity extraction.

```turtle
# REQUIRED prefixes for enhanced definitions:
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix iao: <http://purl.obolibrary.org/obo/IAO_> .
```

**Common Error**: `Bad syntax (Prefix "dcterms:" not bound)`
**Solution**: Always add prefix declarations BEFORE running entity extraction

#### 2. Entity Extraction Error Recovery
The refresh script includes automatic error recovery for missing prefixes:
```python
# Pattern: Parse with error recovery when initial parsing fails
try:
    # Parse normally
    g.parse(ttl_content, format='turtle')
except Exception as e:
    # Add missing prefixes and retry
    enhanced_content = add_missing_prefixes(ttl_content)
    g.parse(enhanced_content, format='turtle')
```

#### 3. DatabaseConceptManager Synchronization
**Must Update**: Subclass mappings whenever new entity types are added
```python
# Update storage/concept_manager_database.py subclass_mappings:
'Role': ['ProfessionalRole', 'EngineeringRole', 'EthicsReviewerRole',
         'ProviderClientRole', 'ProfessionalPeerRole', 'EmployerRelationshipRole', 'PublicResponsibilityRole'],
'Resource': ['ProfessionalCode', 'ExpertInterpretation', 'CasePrecedent', 'TechnicalStandard']
```

#### 4. Literature-Based Definition Pattern
**Successful Pattern**: Professional ethics definitions require both formal and contextual components
- `iao:0000115`: Technical/formal definition for reasoning
- `skos:definition`: Professional context and extensional meaning
- `dcterms:source`: Scholarly citations for academic grounding

#### 5. Verification Methods
```bash
# Query updated definitions
PGPASSWORD=PASS psql -h localhost -U postgres -d ontserve -c "
    SELECT label, uri FROM ontology_entities 
    WHERE label ILIKE '%role%' OR label ILIKE '%resource%' 
    ORDER BY label;"

# Verify scholarly enhancements
curl -s http://localhost:5003/ontology/proethica-intermediate | grep -A 5 "dcterms:source"
```

### Implementation Results

**Database Verification**: Successfully updated proethica-intermediate to version with:
- 88 classes extracted (up from 84)
- 28 properties maintained
- All new role types properly indexed
- No parsing errors with complete prefix declarations

**Scholarly Integration**: All major concepts now include:
- Academic citations from Chapter 2 literature review
- Professional ethics contextual definitions
- Proper alignment with ProEthica 9-concept formalism
- Extensional grounding through professional precedents

**MCP Server Compatibility**: Updated subclass mappings ensure:
- All role types returned in entity queries
- Proper filtering for professional contexts
- Consistent results between web interface and MCP server

## December 2025 Update: Role and State Hierarchy Enhancement

### Successfully Completed Ontology Enhancements

#### Role Hierarchy Implementation
**Added 4 Professional Role Categories to proethica-intermediate.ttl:**
```turtle
:ProviderClientRole rdfs:subClassOf :ProfessionalRole
:ProfessionalPeerRole rdfs:subClassOf :ProfessionalRole  
:EmployerRelationshipRole rdfs:subClassOf :ProfessionalRole
:PublicResponsibilityRole rdfs:subClassOf :ProfessionalRole
```

**Results:**
- 18 total role entities now available via MCP
- Clear hierarchy: Role → ProfessionalRole/ParticipantRole → Specific categories
- Each role includes skos:definition and dcterms:references to Chapter 2 literature
- DatabaseConceptManager subclass_mappings updated with all new roles

#### State Hierarchy Implementation  
**Added 18 State Classes to proethica-intermediate.ttl:**
- Conflict States: ConflictOfInterest, CompetingDuties
- Risk States: PublicSafetyAtRisk, EnvironmentalHazard
- Competence States: OutsideCompetence, QualifiedToPerform
- Relationship States: ClientRelationship, EmploymentTerminated
- Information States: ConfidentialInformation, PublicInformation
- Emergency States: EmergencySituation, CrisisConditions
- Regulatory States: RegulatoryCompliance, NonCompliant
- Decision States: JudgmentOverruled, UnderReview, DecisionPending

**Results:**
- 21 total state entities available via MCP
- All states include Chapter 2.2.4 literature references
- DatabaseConceptManager updated to include State in category mappings
- Extraction prompts now show "EXISTING STATES IN ONTOLOGY" section

#### MCP Integration Enhancements
**Updated Files:**
- `/home/chris/onto/OntServe/storage/concept_manager_database.py`: Added State to subclass retrieval
- `/home/chris/onto/proethica/app/routes/scenario_pipeline/step1.py`: Fetches existing states for prompts
- `/home/chris/onto/proethica/app/services/extraction/enhanced_prompts_states_capabilities.py`: Shows existing states

**Key Pattern for Future Ontology Updates:**
1. Update TTL file with new classes including skos:definition and dcterms:references
2. Update database using custom Python script (see update_role_entities.py example)
3. Update DatabaseConceptManager subclass_mappings
4. Restart MCP server to reflect changes
5. Verify via MCP client that new entities are available

## January 2025 Update: Obligation Hierarchy Enhancement

### Successfully Completed Obligation Entity Enhancement

#### Added 13 Obligation Types to Database
**IMPORTANT**: The new obligation classes were already in the TTL file but needed to be loaded into the database with proper `parent_uri` relationships.

**Process Used**:
1. Created `/home/chris/onto/OntServe/scripts/load_obligations_to_db.py` to directly insert entities
2. Set `parent_uri` to base Obligation URI for all subclasses (critical for hierarchy)
3. Used recursive CTE queries to retrieve all subclasses via parent_uri relationships

**New Obligation Classes Added**:
```python
- DisclosureObligation → "Requirement to inform stakeholders about conflicts..."
- SafetyObligation → "Duty to hold paramount the safety, health, and welfare..."
- CompetenceObligation → "Requirement to perform services only in areas of competence..."
- ConfidentialityObligation → "Duty to protect confidential information..."
- ReportingObligation → "Duty to report violations or unsafe conditions..."
- MandatoryObligation → "Obligations that MUST be fulfilled..."
- DefeasibleObligation → "Obligations that admit justified exceptions..."
- ConditionalObligation → "Obligations that apply only when specific conditions..."
- PrimaFacieObligation → "Obligations that hold at first appearance..."
- LegalObligation → "Obligations arising from legal requirements..."
- EthicalObligation → "Obligations arising from ethical principles..."
- CollegialObligation → "Duties toward professional peers..."
- ProfessionalObligation → "A duty or responsibility arising from professional role..."
```

**Results**:
- 14 total obligation entities now available via MCP (base + 13 specific)
- All retrieved using recursive CTE with parent_uri hierarchy
- UI shows "Found 14 obligation concepts organized by hierarchy"
- Pass 2 integration complete with Principles → Obligations relationship

#### Critical Pattern: Recursive CTE for Entity Retrieval
**MUST USE**: When retrieving entities by category, always use recursive CTE queries based on `parent_uri` relationships, NOT label matching:

```sql
WITH RECURSIVE category_hierarchy AS (
    SELECT uri, label, parent_uri FROM ontology_entities 
    WHERE label = 'Obligation' AND entity_type = 'class'
    UNION
    SELECT e.uri, e.label, e.parent_uri FROM ontology_entities e
    INNER JOIN category_hierarchy ch ON e.parent_uri = ch.uri
    WHERE e.entity_type = 'class'
)
```

This ensures semantically correct retrieval of all subclasses using actual subClassOf relationships.

---

*This guide should be referenced whenever making ontology modifications to ensure consistency with the existing OntServe architecture and versioning system. Last updated: January 2025 with Obligation hierarchy enhancements using recursive CTE pattern.*
