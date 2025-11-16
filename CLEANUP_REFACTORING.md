# ProEthica Repository Cleanup & Refactoring Plan

**Created:** November 16, 2025
**Status:** Planning Phase - Ready for Execution
**Last Updated:** November 16, 2025
**Branch:** claude/review-proethica-dev-016ws2xyr26eTNk55FPSGLBh

---

## FOR CLAUDE CODE WEB

This document provides context for cleanup and refactoring work on the ProEthica repository.

### Key Documentation Locations

**Primary Planning Document:**
- [docs/CLEANUP_REFACTORING_PLAN.md](docs/CLEANUP_REFACTORING_PLAN.md) - Complete multi-phase cleanup plan

**Project Context:**
- [CLAUDE.md](CLAUDE.md) - Project instructions and current status
- [proethica/CLAUDE.md](proethica/CLAUDE.md) - ProEthica-specific instructions
- [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) - Project purpose and goals
- [docs/STEP4_ENHANCED_SYNTHESIS.md](docs/STEP4_ENHANCED_SYNTHESIS.md) - Current architecture

**Deployment:**
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)
- [.claude/agents/git-deployment-sync.md](.claude/agents/git-deployment-sync.md)

### Current Work Context

**Active Branch:** `claude/review-proethica-dev-016ws2xyr26eTNk55FPSGLBh`

**Visibility Changes Made:**
This branch has modified .gitignore to expose documentation and scripts previously hidden:
- `/docs/` directory (was ignored, now visible)
- `/scripts/` directory (was ignored, now visible)
- `CLAUDE.md` files (were ignored, now visible)
- `.claude/` directory (was ignored, now visible for agent definitions)

**Why These Changes:**
Claude Code web needs visibility into:
1. Planning documents (cleanup/refactoring strategy)
2. Project architecture and current status
3. Deployment scripts and procedures
4. Agent definitions for specialized tasks

---

## Executive Summary

Based on comprehensive analysis of the proethica codebase (80 MB, 493 Python files, ~73K lines of core code), this plan outlines a multi-phase approach to cleanup and modernization while preserving all OntServe API integrations.

**Key Findings:**
- **Critical Issue**: No `requirements.txt` or dependency management file exists
- **~39 MB of removable content**: archives (13 MB) + backups (26 MB)
- **Multiple MCP client implementations**: 4 different clients need consolidation
- **Legacy modules**: Several stub/deprecated modules ready for removal
- **Modern tooling gap**: Missing 2025 Python tooling (uv, ruff, modern testing)
- **OntServe integration**: Currently stable but needs documentation and consolidation

**Codebase Metrics:**
- Total size: 80 MB
- Python files: 493
- Core code: ~73,596 lines (services + routes)
- Services: 100+ service files
- Routes: 50+ Flask blueprints
- Models: 60+ SQLAlchemy models
- Tests: 20 test files

---

## PHASE 1: CLEANUP & DEPENDENCY MANAGEMENT (PRIORITY)

### 1.1 Critical: Establish Dependency Management (MUST DO FIRST)

**Priority: CRITICAL - Blocking all other work**

**Current State:** No `requirements.txt`, `setup.py`, or `pyproject.toml` exists.

**Actions Required:**
1. Audit all Python imports across codebase
2. Create modern dependency file using `uv` (10-100x faster than pip)
3. Generate `pyproject.toml` with all dependencies
4. Create `uv.lock` file for reproducible builds
5. Document Python version requirement (Python 3.12 - Ubuntu 24.04 LTS default)

**Status:** ⬜ Not Started

### 1.2 Remove Archive & Backup Files (~39 MB)

**Archive Directory:** `/archive/` (~13 MB - SAFE TO DELETE)
- Old JAR files from Neo4j era
- Documented removal summaries
- Historical artifacts already in git history

**Backup Files:** `/backups/` (~26 MB - MOVE TO .gitignore)
- Database backups should not be in version control
- Add to cloud storage instead

**Service Backup Files:** `*.bak`, `*.backup` files (11 files)
- Git is the backup system
- Remove all backup file extensions

**Status:** ⬜ Not Started

### 1.3 Remove/Archive Stub & Legacy Modules

**Modules to Remove:**
- `/ttl_triple_association/` - Moved to OntServe
- `/realm/` - Materials Science Ontology (107 KB) - no longer needed
- `/mclaren/` - Bruce McLaren's framework (838 KB) - no longer needed
- `/ontology_editor/` - Stub that redirects to OntServe

**Modules to Reorganize:**
- `/nspe-pipeline/` - Keep as separate utility, move to `/app/data_pipelines/nspe/`

**Status:** ⬜ Not Started

### 1.4 Consolidate Test Infrastructure

**Current State:** Tests in `/utils/test/` (non-standard location)

**Target Structure:**
```
/tests/
  unit/              # Fast, hermetic unit tests
  integration/       # Database/service tests
  e2e/              # Full app tests
  fixtures/         # Shared fixtures
  conftest.py       # Pytest configuration
```

**Status:** ⬜ Not Started

---

## PHASE 2: MODERNIZATION & REFACTORING

### 2.1 Adopt Modern Python Tooling (2025 Best Practices)

**Package Management: UV**
- 10-100x faster than pip
- Built-in virtual environment management
- Lock files for reproducibility
- Replaces: pip, pip-tools, virtualenv, poetry

**Linting & Formatting: Ruff**
- 10-100x faster than black/flake8
- Single tool replaces 5+ tools
- Auto-fix capability

**Type Checking: MyPy**
- Catch type errors before runtime
- SQLAlchemy 2.0 compatible

**Status:** ⬜ Not Started

### 2.2 Migrate to SQLAlchemy 2.0

**Current State:** Likely using SQLAlchemy 1.4 (needs verification)

**Benefits:**
- Better type checking integration
- Performance improvements (SQL caching)
- Async support (future-ready)
- Modern Python idioms

**Status:** ⬜ Not Started

### 2.3 Consolidate MCP Client Implementations

**Current State: 4 MCP Client Implementations**
1. `mcp_client.py` (744 lines) - Basic MCPClient singleton
2. `enhanced_mcp_client.py` (972 lines) - High-level wrapper
3. `external_mcp_client.py` (319 lines) - External OntServe via ngrok
4. `ontserve_mcp_client.py` (200+ lines, async) - Async SPARQL

**Target:** Single unified MCP client architecture

**Status:** ⬜ Not Started

---

## PHASE 3: ONTSERVE INTEGRATION STABILITY

### 3.1 Document OntServe API Contract

**Tasks:**
1. Create comprehensive API documentation
2. Create integration tests
3. Add versioning

**Critical Preservation:**
- MCP Tool Interface (`get_world_entities()`, `get_concepts()`, `submit_candidate_concept()`)
- Entity Categories (Role, Principle, Obligation, State, Resource, Constraint, Capability, Action, Event)
- SPARQL Endpoint Access
- Route Redirects (`/ontology/*` → OntServe)

**Status:** ⬜ Not Started

---

## DECISIONS MADE

### 1. REALM and McLaren modules:
- ✅ **Decision:** Remove both directories - no longer needed
- `/realm/` - Materials Science Ontology (107 KB)
- `/mclaren/` - Bruce McLaren's framework (838 KB)

### 2. NSPE Pipeline:
- ✅ **Decision:** Keep as separate utility for modularity
- Used for ingesting NSPE cases (currently a few, eventually ~600 cases)
- Move to `/app/data_pipelines/nspe/`

### 3. OntServe Refactoring:
- ✅ **Status:** **NO BREAKING CHANGES** - OntServe modernization maintains backward compatibility
- All MCP tools remain stable
- ProEthica compatibility explicitly tested in OntServe test suites

### 4. Python Version:
- ✅ **Decision:** Use Python 3.12 (Ubuntu 24.04 LTS default)

### 5. Deployment:
- ✅ **Current:** Deployed to proethica.org
- **Process:** Pull main branch on Digital Ocean droplet, restart nginx + gunicorn
- **Testing:** Testing environment available

### 6. Priority:
- ✅ **Decision:** Start with Phase 1 (Cleanup & Dependency Management)

---

## SUCCESS METRICS

### Phase 1 Success Criteria:
- [ ] `pyproject.toml` exists with all dependencies
- [ ] Fresh install works: `uv sync && uv run flask run`
- [ ] Archive/ removed from git (39 MB saved)
- [ ] No .bak files in codebase
- [ ] Tests pass in new `/tests/` location

### Phase 2 Success Criteria:
- [ ] Ruff linting passes: `uv run ruff check .`
- [ ] SQLAlchemy 2.0 migration complete
- [ ] Single unified MCP client used throughout
- [ ] Test coverage >70%
- [ ] CI/CD pipeline running

### Phase 3 Success Criteria:
- [ ] ONTSERVE_INTEGRATION.md documentation complete
- [ ] All OntServe integration tests passing
- [ ] Mock OntServe client for testing
- [ ] Version compatibility documented

---

## IMPLEMENTATION ROADMAP

### Sprint 1: Foundation (Week 1-2)
- [ ] Create `pyproject.toml` and establish dependency management
- [ ] Set up uv and ruff tooling
- [ ] Move tests to `/tests/` directory
- [ ] Remove archive/ and backup files
- [ ] Remove .bak files

### Sprint 2: Structure (Week 3-4)
- [ ] Create new directory structure
- [ ] Move config.py to `/app/core/config.py`
- [ ] Consolidate MCP clients
- [ ] Begin SQLAlchemy 2.0 migration

### Sprint 3: Services (Week 5-6)
- [ ] Consolidate annotation services
- [ ] Consolidate guideline services
- [ ] Consolidate LLM services
- [ ] Add Pydantic schemas

### Sprint 4: Testing & Documentation (Week 7-8)
- [ ] Add test coverage for consolidated services
- [ ] Create ARCHITECTURE.md
- [ ] Create ONTSERVE_INTEGRATION.md
- [ ] Set up GitHub Actions CI

### Sprint 5: Final Cleanup (Week 9-10)
- [ ] Remove deprecated services
- [ ] Final SQLAlchemy 2.0 migration
- [ ] Performance testing
- [ ] Production deployment preparation

---

## NEXT STEPS

1. Review this plan with stakeholders
2. Begin Phase 1.1: Dependency management audit
3. Create `pyproject.toml` using uv
4. Execute Phase 1 cleanup tasks
5. Coordinate with OntServe team on integration testing

---

## REFERENCE

**Full Plan:** See [docs/CLEANUP_REFACTORING_PLAN.md](docs/CLEANUP_REFACTORING_PLAN.md) for complete details

**Change Log:**
- 2025-11-16: Planning decisions finalized
- 2025-11-16: Initial plan created
- 2025-11-16: Root-level summary created for Claude Code web
