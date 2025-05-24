# Ontology Management and MCP Enhancement Plan

**Created**: 2025-05-24  
**Status**: Planning Phase  
**Priority**: High - Database sync required

## Executive Summary

This document outlines the plan to optimize ontology storage and enhance the MCP server to provide Claude with better ontology query capabilities. The current system has the ontology file (`proethica-intermediate.ttl`) ahead of the database, requiring synchronization and architectural improvements.

## Current System Analysis

### Architecture Overview
- **Primary Storage**: PostgreSQL database with `ontologies` table
- **File Storage**: `ontologies/proethica-intermediate.ttl` (currently most updated)
- **MCP Server**: `enhanced_ontology_server_with_guidelines.py` on localhost:5001
- **Ontology Editor**: Database-driven CRUD operations via `EntityService`
- **Integration**: VSCode launch configuration runs Flask app with MCP server

### Current Issues
1. **Data Inconsistency**: Database is behind the TTL file
2. **Limited Query Tools**: Claude has minimal ontology query capabilities
3. **No Sync Process**: Manual management between file and database
4. **File-First Updates**: Latest changes in TTL file, not database

## Recommended Approach: Database-Primary with File Sync

### Why Database-Primary?
- **Concurrent Access**: Multiple processes can safely query/update
- **ACID Transactions**: Data integrity during updates
- **Performance**: Indexed queries faster than TTL parsing
- **Integration**: Ontology editor expects database storage
- **Version Control**: Existing `OntologyVersion` table

### Hybrid Strategy
1. **Database as runtime source** for all operations
2. **TTL file as export/backup** for version control and external sharing
3. **Bidirectional synchronization** to maintain consistency

## Implementation Phases

### Phase 1: Database Sync (IMMEDIATE - Priority 1)
**Goal**: Resolve current data inconsistency

#### Tasks:
1. **Create sync script** (`sync_ontology_to_database.py`)
   - Import `proethica-intermediate.ttl` to database
   - Update ontology record for domain `proethica-intermediate`
   - Create new version entry in `OntologyVersion`
   - Validate import success

2. **Verify MCP server access**
   - Test MCP server can load updated ontology
   - Confirm `get_world_entities` tool functions correctly

#### Success Criteria:
- [ ] Database contains latest TTL content
- [ ] MCP server returns current ontology data
- [ ] Ontology editor can access all entities

### Phase 2: Enhanced MCP Tools (Priority 2)
**Goal**: Provide Claude with powerful ontology query capabilities

#### New MCP Tools to Add:

##### Query Tools:
- `query_ontology_concepts(query_text)` - Natural language concept search using embeddings
- `search_entities_by_label(query, entity_type)` - Label-based search with type filtering
- `get_entity_details(entity_id)` - Full entity info including relationships
- `search_entities_by_property(property, value)` - Property-based filtering
- `find_related_entities(entity_id, relationship_type)` - Relationship traversal

##### Analysis Tools:
- `get_ontology_stats()` - Entity counts by type, relationship statistics
- `get_entity_hierarchy(entity_id, depth)` - Hierarchical structure navigation
- `find_similar_entities(description, threshold)` - Semantic similarity using embeddings
- `get_entities_by_type(type, limit)` - Type-filtered entity lists

#### Benefits for Claude:
Instead of massive TTL content in prompts, Claude can:
- Query specific concepts: "What engineering roles involve safety assessment?"
- Explore relationships: "Show me capabilities associated with structural engineers"
- Get targeted info: "Find entities related to conflict of interest"
- Understand structure: "What are main entity types in engineering ethics?"

### Phase 3: Bidirectional Sync Automation (Priority 3)
**Goal**: Maintain file/database consistency automatically

#### Database → File Export:
- **Hook in EntityService**: Auto-export after `create_entity()`, `update_entity()`, `delete_entity()`
- **Export script**: `export_ontology_to_file.py`
- **Validation**: Ensure exported TTL is valid RDF

#### File → Database Import:
- **Manual import command**: For external TTL updates
- **Change detection**: Compare file modification time vs database timestamp
- **Validation**: Parse and validate TTL before database update

#### Git Integration:
- **Automated commits**: Export triggers git commit with change description
- **Version tracking**: Link git commits to `OntologyVersion` records

## Technical Implementation Details

### Database Sync Script Structure
```python
# sync_ontology_to_database.py
def sync_ttl_to_database(ttl_path, domain_id):
    """
    Import TTL file to database ontology storage
    
    Args:
        ttl_path: Path to TTL file
        domain_id: Ontology domain identifier
    """
    # Load and validate TTL
    # Create/update ontology record
    # Create new version entry
    # Verify import success
```

### MCP Server Enhancements
Add to `enhanced_ontology_server_with_guidelines.py`:
- New tool definitions in `_handle_list_tools()`
- Tool implementations in `_handle_call_tool()`
- Caching layer for frequent queries
- Error handling for invalid queries

### Sync Automation Hooks
Modify `ontology_editor/services/entity_service.py`:
- Add export call after successful entity operations
- Include change description in export metadata
- Handle export failures gracefully

## File Organization

### Scripts Location:
- `sync_ontology_to_database.py` → root directory
- `export_ontology_to_file.py` → root directory
- Enhanced MCP tools → `mcp/enhanced_ontology_server_with_guidelines.py`

### Configuration:
- Environment variables for sync behavior
- TTL export path configuration
- Database connection validation

## Testing Strategy

### Database Sync Testing:
- [ ] Import current TTL file successfully
- [ ] Verify all entities present in database
- [ ] Test MCP server ontology access
- [ ] Validate ontology editor functionality

### MCP Tools Testing:
- [ ] Test each new query tool individually
- [ ] Verify Claude can use tools effectively
- [ ] Performance testing for complex queries
- [ ] Error handling for invalid inputs

### Sync Automation Testing:
- [ ] Database changes trigger file export
- [ ] File imports update database correctly
- [ ] Conflict resolution for simultaneous changes
- [ ] Git integration works properly

## Success Metrics

### Immediate (Phase 1):
- Database and file are synchronized
- MCP server provides current ontology data
- Ontology editor functions normally

### Short-term (Phase 2):
- Claude can query ontology effectively without large prompts
- Query response time < 2 seconds
- All entity types searchable and discoverable

### Long-term (Phase 3):
- Automatic sync maintains consistency
- No manual intervention required for normal operations
- Version history preserved in both git and database

## Risk Mitigation

### Data Loss Prevention:
- Backup current database before sync
- Validate TTL before import
- Rollback capability for failed imports

### Performance Considerations:
- Index database columns for common queries
- Cache frequent MCP queries
- Limit query result sizes

### Change Conflicts:
- File modification timestamps
- Database version numbers
- Manual conflict resolution procedures

## Next Steps

1. **Immediate**: Create and run database sync script
2. **Week 1**: Implement core MCP query tools
3. **Week 2**: Add sync automation
4. **Week 3**: Testing and refinement

## Progress Tracking

### Phase 1 - Database Sync:
- [ ] Create sync script
- [ ] Import TTL to database
- [ ] Verify MCP server access
- [ ] Test ontology editor

### Phase 2 - MCP Enhancement:
- [ ] Implement query tools
- [ ] Add analysis tools
- [ ] Test with Claude
- [ ] Performance optimization

### Phase 3 - Sync Automation:
- [ ] Database → File export
- [ ] File → Database import
- [ ] Git integration
- [ ] Error handling

---

**Document Status**: Initial planning complete, ready for implementation  
**Next Review**: After Phase 1 completion  
**Contact**: Chris (project owner)
