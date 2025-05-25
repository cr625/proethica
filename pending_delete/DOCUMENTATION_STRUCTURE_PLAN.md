# Documentation Structure Plan

## Proposed Directory Structure

```
docs/
├── README.md                    # Main documentation index
├── current/                     # Current, actively maintained docs
│   ├── architecture/            # System architecture docs
│   │   ├── overview.md
│   │   ├── database_structure.md
│   │   └── technical_architecture.md
│   ├── features/               # Feature documentation
│   │   ├── section_triple_association.md
│   │   ├── document_processing.md
│   │   ├── ontology_integration.md
│   │   └── guideline_analysis.md
│   ├── guides/                 # How-to guides
│   │   ├── getting_started.md
│   │   ├── environment_setup.md
│   │   ├── deployment.md
│   │   └── debugging.md
│   └── api/                    # API documentation
│       ├── rest_api.md
│       └── mcp_server.md
├── planning/                   # Active planning documents
│   └── future_development_plans.md
└── archived/                   # Historical/outdated docs
    ├── plans/                  # Old planning documents
    ├── implementations/        # Superseded implementations
    └── experiments/            # Experimental features

cases/docs/                     # Case-specific documentation
├── README.md
├── current/
│   └── nspe_case_processing.md
└── archived/

experiment/docs/                # Experiment-specific documentation
├── README.md
└── experiment_technical_reference.md

guidelines/docs/                # Guidelines-specific documentation
├── README.md
└── guideline_section_integration.md

mcp/docs/                      # MCP server documentation
├── README.md
├── mcp_server_guide.md
└── ontology_mcp_integration_guide.md

ontology/docs/                 # Ontology documentation
├── README.md
├── ontology_comprehensive_guide.md
└── ontology_enhancement_plan.md
```

## Consolidation Actions

### Move to `docs/current/features/`:
- `SECTION_TRIPLE_ASSOCIATION.md`
- Essential parts of `features_implemented.md`
- Core functionality from various implementation docs

### Move to `docs/current/architecture/`:
- `database_structure.md`
- `technical_architecture.md`
- System design documentation

### Move to `docs/current/guides/`:
- `getting_started.md`
- `environment_setup.md`
- Setup and configuration guides

### Move to `docs/archived/plans/`:
- All historical planning documents
- Superseded implementation plans
- Old experiment designs

### Keep Module-Specific:
- Case processing docs stay in `cases/docs/`
- MCP docs stay in `mcp/docs/`
- Ontology docs stay in `ontology/docs/`
- Experiment docs stay in `experiment/docs/`

## Documentation Standards

1. **Current Documentation**:
   - Must reflect actual implementation
   - Include code examples
   - Maintain version information
   - Regular review and updates

2. **Planning Documents**:
   - Clear status indicators
   - Implementation checkpoints
   - Links to resulting features

3. **Archived Documents**:
   - Date of archival
   - Reason for archival
   - Links to replacement docs

## Implementation Steps

1. Create new directory structure
2. Move and consolidate documents
3. Update all internal links
4. Create comprehensive README files
5. Remove redundant documentation
6. Update CLAUDE.md to reference new structure