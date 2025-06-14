# Root Directory Cleanup Summary

## Overview
Cleaned up the root directory by moving SQL files and utility Python scripts to organized locations under `/utils/`.

## Files Moved

### SQL Files → `/utils/sql/`
- **`init-pgvector.sql`** → `/utils/sql/` (generic infrastructure)
- **`cleanup_orphaned_guidelines.sql`** → `/utils/sql/maintenance/` (domain-specific maintenance)
- **`cleanup_orphaned_triples.sql`** → `/utils/sql/maintenance/` (domain-specific maintenance)
- **`create_missing_guideline_tables.sql`** → `/utils/sql/maintenance/` (domain-specific maintenance)

### Python Utilities Organized by Purpose

#### Database Setup → `/utils/database/`
- `create_deconstruction_tables.py` - Create case deconstruction tables
- `create_test_data.py` - Generate test data

#### Debugging Tools → `/utils/debugging/`
- `debug_association_error.py` - Debug association issues
- `examine_detailed_data.py` - Examine database data
- `examine_guideline_data.py` - Examine guideline-specific data
- `simple_cleanup_check.py` - Check for cleanup needs
- `demo_enhanced_schema.py` - Demo enhanced schema features
- `simple_test.py` - Simple testing utility
- `quick_type_test.py` - Quick type system testing

#### Migration Scripts → `/utils/migration/`
- `add_entity_type_to_term_links.py` - Add entity types to term links
- `fix_unmapped_concept_types.py` - Fix unmapped concept types
- `run_type_mapping_migrations.py` - Run type mapping migrations
- `update_pending_concept_mappings.py` - Update pending mappings
- `update_term_links_entity_types.py` - Update term link entity types

#### General Utilities → `/utils/`
- `run_debug_app.py` - Debug application runner

## Updated Utils Structure
```
/utils/
├── analyze_schema.py              # Schema analysis
├── create_test_user.py            # User management
├── entity_manager.py              # Entity management
├── run_debug_app.py               # Debug runner
├── test_simple_database_validation.py
├── database/                      # Database setup utilities
│   ├── create_deconstruction_tables.py
│   └── create_test_data.py
├── debugging/                     # Debugging and examination tools
│   ├── debug_association_error.py
│   ├── demo_enhanced_schema.py
│   ├── examine_detailed_data.py
│   ├── examine_guideline_data.py
│   ├── quick_type_test.py
│   ├── simple_cleanup_check.py
│   └── simple_test.py
├── migration/                     # Database migration scripts
│   ├── add_entity_type_to_term_links.py
│   ├── fix_unmapped_concept_types.py
│   ├── run_type_mapping_migrations.py
│   ├── update_pending_concept_mappings.py
│   └── update_term_links_entity_types.py
├── sql/                          # SQL scripts
│   ├── init-pgvector.sql         # Generic infrastructure
│   └── maintenance/              # Domain-specific maintenance
│       ├── cleanup_orphaned_guidelines.sql
│       ├── cleanup_orphaned_triples.sql
│       └── create_missing_guideline_tables.sql
├── nspe-tools/                   # NSPE-specific tools
├── other/                        # Domain-specific tests
└── test/                         # Generic test suite
```

## Root Directory Status
The root directory is now much cleaner with utility scripts and SQL files properly organized. Remaining files in root are:
- Core application files (config.py, run.py, setup_project.py)
- Documentation (README.md, CLAUDE.md)
- Configuration files (.env, .gitignore, etc.)
- Application entry points

This organization supports the domain generalization effort by:
1. Separating generic utilities from domain-specific ones
2. Organizing by function (database, debugging, migration)
3. Making it easier to identify what needs to be generalized
4. Providing clear structure for future utilities