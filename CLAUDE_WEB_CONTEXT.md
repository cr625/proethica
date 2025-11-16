# Claude Code Web - Current Context

**Branch:** `claude/review-proethica-dev-016ws2xyr26eTNk55FPSGLBh`
**Date:** November 16, 2025
**Purpose:** Repository cleanup and refactoring preparation

---

## What You Need to Know

### 1. This Branch Exposes Hidden Documentation

Previous state: `docs/`, `scripts/`, `CLAUDE.md`, and `.claude/` were in .gitignore
Current state: These directories are now visible for cleanup and refactoring work

### 2. Key Files for Your Review

**Main Planning:**
- [CLEANUP_REFACTORING.md](CLEANUP_REFACTORING.md) - Root-level summary (START HERE)
- [docs/CLEANUP_REFACTORING_PLAN.md](docs/CLEANUP_REFACTORING_PLAN.md) - Complete detailed plan

**Project Context:**
- [CLAUDE.md](CLAUDE.md) - Main project instructions and repository overview
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) - Production deployment procedures
- [docs/DEMO_CASES_ANALYSIS_GUIDE.md](docs/DEMO_CASES_ANALYSIS_GUIDE.md) - Case analysis workflow

**Agent Definitions:**
- [.claude/agents/git-deployment-sync.md](.claude/agents/git-deployment-sync.md) - Deployment automation
- [.claude/agents/repo-maintenance.md](.claude/agents/repo-maintenance.md) - Repository maintenance
- [.claude/agents/website-reviewer.md](.claude/agents/website-reviewer.md) - Production site review

**Deployment Scripts:**
- [scripts/backup_demo_database.sh](scripts/backup_demo_database.sh) - Database backup utility
- [scripts/restore_demo_database.sh](scripts/restore_demo_database.sh) - Database restore utility
- Other utility scripts in [scripts/](scripts/)

---

## Current Task: Cleanup & Refactoring

### Phase 1 Priority: Dependency Management

**Critical Issue:** No `requirements.txt` or `pyproject.toml` exists
**Action Required:** Create modern dependency management using `uv`

**Steps:**
1. Audit all Python imports (493 Python files)
2. Create `pyproject.toml` with dependencies
3. Generate `uv.lock` for reproducibility
4. Target: Python 3.12 (Ubuntu 24.04 LTS default)

### What Can Be Safely Removed

**Immediate cleanup candidates:**
- `/archive/` - 13 MB (JAR files from Neo4j era)
- `/backups/` - 26 MB (move to .gitignore, use cloud storage)
- `*.bak`, `*.backup` files - 11 files (git is the backup)
- `/realm/` - 107 KB (Materials Science Ontology, no longer needed)
- `/mclaren/` - 838 KB (Bruce McLaren framework, no longer needed)
- `/ttl_triple_association/` - Moved to OntServe
- `/ontology_editor/` - Stub that redirects to OntServe

### What Must Be Preserved

**OntServe Integration (CRITICAL):**
- MCP client implementations (4 different clients to consolidate)
- Entity categories: Role, Principle, Obligation, State, Resource, Constraint, Capability, Action, Event
- SPARQL endpoint access
- Route redirects: `/ontology/*` → OntServe

**Note:** OntServe refactoring maintains backward compatibility - no breaking changes expected

---

## Files Staged in This Branch

Current staged changes (47 files):
- Modified: `.gitignore` (exposed docs, scripts, CLAUDE.md)
- Added: `CLAUDE.md` (main project instructions)
- Added: `CLEANUP_REFACTORING.md` (root-level summary)
- Added: `.claude/agents/*.md` (3 agent definitions)
- Added: `scripts/*.py` (13 utility scripts)
- Added: `test_*.py` (14 test files at root - should move to /tests/)
- Added: `tests/*.py` (11 test files in proper location)
- Added: `tests/smoke_test_phase1.sh`
- Added: `app/services/test_data_reset_service.py`

---

## Test Files Issue

**Problem:** 14 test files at root level (test_*.py) - non-standard location

**Standard Practice:** Tests should be in `/tests/` directory

**Action Required:** Move root-level test files to `/tests/` as part of Phase 1.4

---

## Next Steps

1. Review [CLEANUP_REFACTORING.md](CLEANUP_REFACTORING.md) for complete plan
2. Confirm Phase 1 priorities
3. Begin dependency audit (scan 493 Python files for imports)
4. Create `pyproject.toml` using `uv`
5. Execute Phase 1 cleanup tasks

---

## Production Deployment Context

**Current Deployment:**
- Production: https://proethica.org
- Server: DigitalOcean droplet (209.38.62.85)
- Process: Pull main branch, restart nginx + gunicorn
- Database: PostgreSQL (ai_ethical_dm)

**Testing Environment:** Available for pre-production testing

**Deployment Scripts:**
- Backup: `./scripts/backup_demo_database.sh`
- Restore: `./scripts/restore_demo_database.sh`
- Deploy: `./scripts/deploy_production.sh`

---

## Important Notes

### This is a CLEANUP branch
- Purpose: Expose documentation for refactoring work
- Not intended for immediate production deployment
- Testing and review required before merging to main

### OntServe Integration is STABLE
- No breaking changes expected from OntServe refactoring
- All MCP tools maintain backward compatibility
- ProEthica compatibility explicitly tested in OntServe test suites

### Python Version
- Target: Python 3.12 (Ubuntu 24.04 LTS default)
- Required for modern tooling (uv, ruff, SQLAlchemy 2.0)

---

## Questions or Issues?

Refer to:
- [CLEANUP_REFACTORING.md](CLEANUP_REFACTORING.md) - Summary and decisions
- [docs/CLEANUP_REFACTORING_PLAN.md](docs/CLEANUP_REFACTORING_PLAN.md) - Complete details
- [CLAUDE.md](CLAUDE.md) - Project context and current status
