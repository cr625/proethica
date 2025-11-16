# ProEthica Repository Cleanup & Refactoring Plan

**Created:** November 16, 2025
**Status:** Planning Phase
**Last Updated:** November 16, 2025

---

## Executive Summary

Based on comprehensive analysis of the proethica codebase (80 MB, 493 Python files, ~73K lines of core code) and research into 2025 best practices, this plan outlines a multi-phase approach to cleanup and modernization while preserving all OntServe API integrations.

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

## PHASE 1: CLEANUP & DEPENDENCY MANAGEMENT

### 1.1 Critical: Establish Dependency Management (MUST DO FIRST)

**Priority: CRITICAL - Blocking all other work**

**Current State:** No `requirements.txt`, `setup.py`, or `pyproject.toml` exists.

#### Tasks:

1. **Audit all Python imports across codebase**
   - Scan all 493 Python files for import statements
   - Identify all third-party packages and versions
   - Document direct vs. transitive dependencies

2. **Create modern dependency file using uv**
   - Adopt `uv` as primary package manager (10-100x faster than pip)
   - Generate `pyproject.toml` with all dependencies
   - Create `uv.lock` file for reproducible builds
   - Include development dependencies separately

3. **Version pinning strategy**
   - Pin major versions for stability (e.g., `flask>=3.0,<4.0`)
   - Pin exact versions for critical packages (anthropic, openai)
   - Document why specific versions are chosen

4. **Verify installation**
   - Test fresh install in clean environment
   - Ensure all imports resolve correctly
   - Document Python version requirement (likely 3.11+)

**Files to Create:**
```
pyproject.toml          # Primary dependency file (PEP 621 compliant)
uv.lock                 # Lock file for exact reproducibility
.python-version         # Python version specification
```

**Rationale:** Without dependency management, the codebase cannot be reliably deployed, tested, or maintained.

**Status:** ⬜ Not Started

---

### 1.2 Remove Archive & Backup Files

**Priority: HIGH - Safe removal, significant space savings**

#### Archive Directory (~13 MB - SAFE TO DELETE)

**Location:** `/archive/`

**Contents:**
```
/archive/jars/                          # 13 MB - Old JAR files (Neo4j era)
/archive/neo4j-removed/                 # 91 KB - Documented removal (Aug 2025)
/archive/unused_root_20250815/          # 330 KB - Archived root files
```

**Rationale:** These are explicitly archived and documented. Neo4j was officially removed in August 2025 (see REMOVAL_SUMMARY.md).

**Action:**
- Move to git history (delete from working tree)
- Keep REMOVAL_SUMMARY.md in docs/ for historical reference
- **Space saved: ~13 MB**

**Status:** ⬜ Not Started

---

#### Backup Files (~26 MB - MOVE TO .gitignore)

**Location:** `/backups/`

**Rationale:** Database backups should not be in version control. They belong in:
- Production backup system (automated daily backups)
- Cloud storage (S3, DO Spaces, etc.)
- Local developer backups (via scripts, not git)

**Action:**
- Add `/backups/` to `.gitignore` (already there, enforce it)
- Create backup strategy documentation
- **Space saved: ~26 MB**

**Status:** ⬜ Not Started

---

#### Service Backup Files (11 files)

**Files to Remove:**
```python
app/services/claude_service.py.bak
app/services/guideline_analysis_service.py.backup
app/services/mcp_client.py.bak.*  # 4 versions
app/services/langchain_claude.py.bak
# ... and others
```

**Rationale:** Git is the backup system. `.bak` files create confusion and clutter.

**Action:**
- Delete all `.bak` and `.backup` files
- Rely on git history for code recovery
- Add `*.bak`, `*.backup` to `.gitignore`

**Status:** ⬜ Not Started

---

### 1.3 Remove/Archive Stub & Legacy Modules

**Priority: MEDIUM-HIGH - Reduces cognitive load**

#### Deprecated Modules (Already Moved to OntServe)

**1. TTL Triple Association** (`/ttl_triple_association/`)
- **Status:** Moved to OntServe, contains stub with redirect message
- **Action:** Delete directory, update documentation
- **Note:** Keep reference in migration docs
- **Status:** ⬜ Not Started

**2. Ontology Editor** (`/ontology_editor/`)
- **Status:** Stub that redirects to OntServe web interface
- **Action:**
  - Keep minimal blueprint for `/ontology/` route redirection
  - Remove local editor implementation
  - Document that editing happens in OntServe
- **Status:** ⬜ Not Started

---

#### Minimal/Empty Service Files

**Files to Audit:**
```python
app/services/engineering_ontology_service.py      # 1 KB, minimal implementation
app/services/ontology_entity_service.py           # 1 KB, stub
app/services/ontology_service_factory.py          # 2 KB, unclear if used
app/services/ontology_term_recognition_service.py # 1.5 KB, minimal
```

**Action:**
- Audit usage across codebase (grep for imports)
- If unused: delete
- If used: either implement properly or replace with OntServe calls
- Document decision rationale

**Status:** ⬜ Not Started

---

#### Legacy Route Files

**Files to Remove:**
```python
app/routes/experiment_backup.py
app/routes/step1a_langextract.py.archived
app/routes/step3_backup.py
app/routes/step4_streaming.py.broken
```

**Action:** Delete (git history preserves them if needed)

**Status:** ⬜ Not Started

---

### 1.4 Consolidate Standalone Applications

**Priority: MEDIUM - Architectural decision required**

#### REALM Application (`/realm/` - 107 KB)

- **Purpose:** Materials Science Ontology application
- **Status:** Separate application, not integrated with main ProEthica
- **Has:** Own models, routes, services, templates

**Options:**
1. **Archive it** - Move to separate repository if still active
2. **Integrate it** - Proper integration as a blueprint module
3. **Delete it** - If no longer maintained

**Decision Required:** ❓ User input needed

**Status:** ⬜ Not Started

---

#### McLaren Framework (`/mclaren/` - 838 KB)

- **Purpose:** Bruce McLaren's extensional definition approach implementation
- **Status:** Documented, appears to be research/experimental code
- **Has:** Database schema, processing pipeline, scripts

**Options:**
1. **Keep as experimental module** - Properly documented
2. **Integrate into main pipeline** - If actively used
3. **Separate repository** - If research-focused

**Recommendation:** Keep but reorganize under `/app/experimental/mclaren/` or similar

**Decision Required:** ❓ User input needed

**Status:** ⬜ Not Started

---

#### NSPE Pipeline (`/nspe-pipeline/` - 143 KB)

- **Purpose:** NSPE case scraping and processing
- **Status:** Standalone tools

**Recommendation:**
- Keep if actively used for data updates
- Move to `/app/data_pipelines/nspe/` for better organization
- Document when and how to run

**Decision Required:** ❓ User input needed

**Status:** ⬜ Not Started

---

### 1.5 Consolidate Test Infrastructure

**Priority: MEDIUM - Improves developer experience**

**Current State:**
- Tests in `/utils/test/` (non-standard location)
- `pytest.ini` points to `/tests/` (doesn't exist)
- 20 test files, good coverage

**Target Structure:**
```
/tests/
  unit/              # Fast, hermetic unit tests
  integration/       # Database/service tests
  e2e/              # Full app tests
  fixtures/         # Shared fixtures
  conftest.py       # Pytest configuration
```

**Action:**
1. Create proper `/tests/` directory at root level
2. Move all tests from `/utils/test/` to `/tests/`
3. Update `pytest.ini` configuration
4. Organize by test type (unit, integration, e2e)

**Status:** ⬜ Not Started

---

### 1.6 Clean Up Demo & Reference Files

**Priority: LOW - Minor cleanup**

#### Demo Directory (`/demo/`)

**Contents:**
```
demo/case7_static_analysis.html
demo/case7_static_analysis.json
demo/case7_static_analysis.py
```

**Options:**
1. Move to `/tests/fixtures/demo_cases/` if used for testing
2. Delete if just one-off mockup

**Decision Required:** ❓ User input needed

**Status:** ⬜ Not Started

---

#### References Directory (`/references/`)

- Research papers and documentation
- **Keep** but ensure not tracked in git if large PDFs
- Add to `.gitignore` if needed

**Status:** ⬜ Not Started

---

## PHASE 2: MODERNIZATION & REFACTORING

### 2.1 Adopt Modern Python Tooling (2025 Best Practices)

**Priority: HIGH - Foundation for all modernization**

#### Package Management: UV

**Installation:**
```bash
# Install uv (Rust-based, 10-100x faster than pip)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init

# Add dependencies
uv add flask sqlalchemy anthropic openai langchain
uv add --dev pytest ruff mypy
```

**Benefits:**
- 10-100x faster than pip
- Built-in virtual environment management
- Lock files for reproducibility
- Python version management
- Replaces: pip, pip-tools, virtualenv, poetry

**Status:** ⬜ Not Started

---

#### Linting & Formatting: Ruff

**Installation:**
```bash
uv add --dev ruff
```

**Configuration in pyproject.toml:**
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "C90"]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**Benefits:**
- 10-100x faster than black/flake8
- Single tool replaces 5+ tools
- Auto-fix capability
- Python-specific error detection

**Status:** ⬜ Not Started

---

#### Type Checking: MyPy

**Installation:**
```bash
uv add --dev mypy
```

**Configuration:**
```toml
[tool.mypy]
python_version = "3.11"
strict = false  # Start permissive, gradually enable
warn_return_any = true
warn_unused_configs = true
exclude = [
    "archive/",
    "backups/",
    "migrations/",
]
```

**Benefits:**
- Catch type errors before runtime
- Better IDE integration
- SQLAlchemy 2.0 compatible

**Status:** ⬜ Not Started

---

### 2.2 Migrate to SQLAlchemy 2.0

**Priority: HIGH - Required for modern Flask**

**Current State:** Likely using SQLAlchemy 1.4 (needs verification)

#### Migration Steps:

**1. Update Dependencies**
```toml
[project.dependencies]
sqlalchemy = ">=2.0,<3.0"
flask-sqlalchemy = ">=3.1,<4.0"
```

**2. Update Model Definitions**
```python
# OLD (1.4 style)
class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))

# NEW (2.0 style with type hints)
from sqlalchemy.orm import Mapped, mapped_column

class Document(db.Model):
    __tablename__ = 'documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
```

**3. Update Query Patterns**
```python
# OLD
results = db.session.query(Document).filter_by(id=doc_id).first()

# NEW
from sqlalchemy import select
results = db.session.execute(
    select(Document).where(Document.id == doc_id)
).scalar_one_or_none()
```

**4. Session Management**
```python
# Use context managers
with db.session.begin():
    db.session.add(document)
    # auto-commit on success, auto-rollback on exception
```

**Benefits:**
- Better type checking integration
- Performance improvements (SQL caching)
- Async support (future-ready)
- Modern Python idioms

**Status:** ⬜ Not Started

---

### 2.3 Consolidate MCP Client Implementations

**Priority: HIGH - Critical for OntServe stability**

**Current State: 4 MCP Client Implementations**

1. **`mcp_client.py`** (744 lines) - Basic MCPClient singleton, mock fallback
2. **`enhanced_mcp_client.py`** (972 lines) - High-level wrapper, entity standardization
3. **`external_mcp_client.py`** (319 lines) - External OntServe via ngrok, tool calling
4. **`ontserve_mcp_client.py`** (200+ lines, async) - Async SPARQL, retry logic

**Problems:**
- Duplication and confusion
- Different interfaces for same functionality
- Hard to maintain OntServe compatibility
- Unclear which services should use which client

---

#### Phase 2.3.1: Create Unified MCP Client Architecture

**Target Structure:**
```python
# app/clients/ontserve/
├── __init__.py
├── base.py              # Abstract base client
├── sync_client.py       # Synchronous implementation
├── async_client.py      # Async implementation
├── retry_policy.py      # Shared retry logic
├── entity_mapper.py     # Entity standardization
└── exceptions.py        # Custom exceptions
```

#### Phase 2.3.2: Define Standard Interface

```python
# base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class OntServeClient(ABC):
    """Unified interface for OntServe MCP integration"""

    @abstractmethod
    def get_entities(self, category: str, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch entities by category (Role, Principle, etc.)"""
        pass

    @abstractmethod
    def execute_sparql(self, query: str) -> List[Dict]:
        """Execute SPARQL query"""
        pass

    @abstractmethod
    def submit_candidate_concept(self, concept: Dict) -> Dict:
        """Submit new concept via MCP tool"""
        pass
```

#### Phase 2.3.3: Implementation Strategy

1. **Create new unified client** (don't break existing code immediately)
2. **Migrate services one-by-one** to new client
3. **Add deprecation warnings** to old clients
4. **Remove old clients** once all migrations complete

**Benefits:**
- Single source of truth for OntServe integration
- Easier to maintain OntServe API compatibility
- Clear migration path when OntServe refactoring completes
- Better error handling and retry logic

**Status:** ⬜ Not Started

---

### 2.4 Adopt Modern Flask Project Structure

**Priority: MEDIUM - Improves maintainability**

**Current Structure:**
```
/app/
  __init__.py           # App factory (GOOD)
  models/               # 60+ models (GOOD)
  routes/               # 50+ blueprints (GOOD, but needs organization)
  services/             # 100+ services (TOO MANY, needs consolidation)
  utils/                # Helper utilities (GOOD)
```

**Recommended Structure (2025 Best Practices):**
```
/app/
  __init__.py                    # App factory

  /core/                         # Core application logic
    extensions.py                # Flask extension initialization
    config.py                    # Config classes (move from root)

  /models/                       # Database models (current structure good)
    __init__.py
    document.py
    world.py
    ...

  /schemas/                      # NEW - Pydantic/Marshmallow validation
    document_schema.py           # Request/response validation
    world_schema.py

  /routes/                       # API blueprints
    /api/                        # REST API routes
      __init__.py
      documents.py
      worlds.py
      scenarios.py
    /web/                        # Web UI routes
      __init__.py
      dashboard.py

  /services/                     # Business logic (consolidate similar services)
    /domain/                     # Domain services
      document_service.py
      world_service.py
    /integration/                # External integrations
      ontserve_service.py        # Consolidated OntServe integration
      llm_service.py             # Consolidated LLM (Anthropic/OpenAI)
    /pipeline/                   # Processing pipelines
      scenario_pipeline.py
      extraction_pipeline.py

  /clients/                      # NEW - External API clients
    /ontserve/
      sync_client.py
      async_client.py
    /llm/
      anthropic_client.py
      openai_client.py

  /utils/                        # Utilities
    /helpers/
    /validators/

  /templates/                    # Jinja2 templates
  /static/                       # CSS/JS/images
```

**Migration Strategy:**
- **Phase 1:** Create new structure alongside existing
- **Phase 2:** Move files incrementally
- **Phase 3:** Update imports
- **Phase 4:** Remove old structure

**Status:** ⬜ Not Started

---

### 2.5 Service Layer Consolidation

**Priority: MEDIUM - Reduces complexity**

**Current State:** 100+ services with overlapping concerns

**Problems:**
- **6 different annotation services**
- **4 MCP clients** (covered in 2.3)
- **Multiple guideline services** with unclear boundaries
- **Temporal services** spread across files

---

#### Consolidation Plan:

**Annotation Services → Single Annotator**
```python
# Current (6 services)
ontserve_annotation_service.py
ontserve_commit_service.py
ontserve_data_fetcher.py
enhanced_guideline_annotator.py
guideline_annotation_service.py
ontology_driven_langextract_service.py

# Target (1 service with strategy pattern)
app/services/domain/annotation_service.py
  - OntServeAnnotationStrategy
  - GuidelineAnnotationStrategy
  - LangExtractStrategy
```

**Guideline Services → Unified Pipeline**
```python
# Current (multiple versions)
guideline_analysis_service.py
guideline_analysis_service_v2.py
guideline_analysis_service_clean.py
guideline_analysis_service_dynamic.py

# Target
app/services/domain/guideline_service.py
  - Single implementation
  - Version selection via config
  - Remove old versions after migration
```

**LLM Services → Provider Pattern**
```python
# Current (scattered)
claude_service.py
langchain_claude.py
llm_service.py (if exists)

# Target
app/services/integration/llm_service.py
  - AbstractLLMProvider
  - AnthropicProvider (Claude)
  - OpenAIProvider
  - ConfigurableProvider (switch via config)
```

**Status:** ⬜ Not Started

---

### 2.6 Add Schema Validation (Pydantic)

**Priority: MEDIUM - Improves API robustness**

**Current State:** Direct request data access, minimal validation

**Target:** Add Pydantic schemas for request/response validation

```python
# app/schemas/document_schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    case_type: Optional[str] = None

    @validator('title')
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True  # SQLAlchemy model compatibility
```

**Benefits:**
- Automatic validation and error messages
- OpenAPI/Swagger documentation generation
- Type safety
- Clear API contracts

**Status:** ⬜ Not Started

---

### 2.7 Improve Testing Infrastructure

**Priority: MEDIUM-HIGH - Ensures refactoring safety**

#### Current State (Good foundation, needs expansion)
- 20 test files in `/utils/test/`
- pytest configured
- PostgreSQL test database
- Good fixtures

#### Improvements Needed:

**1. Move to standard location** (`/tests/` not `/utils/test/`)

**2. Organize by type:**
```
/tests/
  /unit/              # Fast, no DB
  /integration/       # DB required
  /e2e/              # Full app tests
  /fixtures/         # Shared fixtures
  conftest.py
```

**3. Add coverage requirements:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=app --cov-report=html --cov-report=term"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 70  # Start at 70%, gradually increase
```

**4. Add GitHub Actions CI:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      - run: uv sync
      - run: uv run pytest
```

**5. Add test types:**
- Unit tests for services
- Integration tests for routes
- MCP client mocking
- LLM response mocking (don't call real APIs in tests)

**Status:** ⬜ Not Started

---

### 2.8 Documentation Improvements

**Priority: MEDIUM - Helps onboarding and maintenance**

#### Create Missing Documentation:

**1. README.md** (root level comprehensive version)
- Project overview
- Quick start guide
- Development setup with uv
- Testing instructions
- Deployment guide

**2. ARCHITECTURE.md**
- System architecture diagram
- Component responsibilities
- Data flow
- OntServe integration points
- LLM integration strategy

**3. API.md**
- REST API documentation
- Route organization
- Authentication
- Example requests/responses

**4. CONTRIBUTING.md**
- Development workflow
- Code style (ruff configuration)
- Testing requirements
- Pull request process

**5. CHANGELOG.md**
- Track significant changes
- Migration guides for breaking changes

#### Update Existing Documentation:
- **DEPLOYMENT_CHECKLIST.md** - Update with new tooling (uv, ruff)
- **DEMO_CASES_ANALYSIS_GUIDE.md** - Ensure still accurate

**Status:** ⬜ Not Started

---

### 2.9 Configuration Management

**Priority: MEDIUM - Improves deployment**

**Current State:**
- `config.py` with 4 environments (good)
- Environment variables for secrets (good)
- Feature flags (good)

**Improvements:**

**1. Move config.py into app/core/**
```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://..."

    # OntServe
    ontserve_mcp_url: str = "http://localhost:8082"
    ontserve_web_url: str = "https://ontserve.ontorealm.net"

    # LLM
    anthropic_api_key: str
    openai_api_key: Optional[str] = None

    # Feature Flags
    enable_ontology_driven_langextract: bool = True
    enable_external_mcp_access: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
```

**2. Environment-specific configs:**
```
/config/
  .env.development
  .env.production
  .env.test
```

**3. Validation on startup:**
- Check required API keys exist
- Verify database connection
- Check MCP server availability
- Log configuration status

**Status:** ⬜ Not Started

---

### 2.10 Async Support (Future-Ready)

**Priority: LOW-MEDIUM - Future optimization**

**Current State:**
- Some async code exists (async MCP client)
- Mostly synchronous Flask routes

**Recommendation:**
- **Don't rush this** - Flask 3.x has async support but migration is complex
- Consider for new routes only
- Good candidates:
  - LLM streaming responses
  - Long-running scenario generation
  - Batch processing pipelines

**When to implement:**
- After other refactoring complete
- When performance bottlenecks identified
- When deploying with async-capable server (Hypercorn, Uvicorn)

**Status:** ⬜ Not Started

---

## PHASE 3: ONTSERVE INTEGRATION STABILITY

### 3.1 Document OntServe API Contract

**Priority: HIGH - Ensures future compatibility**

#### Tasks:

**1. Create comprehensive API documentation:**

Create: `docs/ONTSERVE_INTEGRATION.md`

**Contents:**
- MCP Tools Used
  - `get_world_entities()`
  - `get_concepts()`
  - `submit_candidate_concept()`
- SPARQL Queries
  - Entity hierarchy queries
  - Concept relationship queries
- API Endpoints
  - `/ontology/*` (redirect to OntServe)
  - `/api/mcp/*` (internal MCP proxy)
- Data Models
  - Entity categories (Role, Principle, Obligation, etc.)
  - Field mappings between ProEthica and OntServe
- Migration Guide
  - How to handle OntServe API changes
  - Version compatibility matrix

**2. Create integration tests:**

```python
# tests/integration/test_ontserve_integration.py
def test_ontserve_mcp_connection():
    """Verify MCP server connection"""

def test_entity_retrieval():
    """Verify entity retrieval works"""

def test_sparql_queries():
    """Verify SPARQL queries work"""
```

**3. Add versioning:**

```python
# app/clients/ontserve/version.py
ONTSERVE_API_VERSION = "2025.1"
MINIMUM_COMPATIBLE_VERSION = "2025.0"
```

**Status:** ⬜ Not Started

---

### 3.2 Create OntServe Mock for Testing

**Priority: MEDIUM - Improves test reliability**

**Purpose:** Don't depend on live OntServe for tests

```python
# tests/fixtures/ontserve_mock.py
from unittest.mock import MagicMock

class MockOntServeClient:
    """Mock OntServe client for testing"""

    def get_entities(self, category, filters=None):
        return {
            "Role": [{"id": 1, "label": "Engineer"}],
            "Principle": [{"id": 2, "label": "Public Safety"}],
        }.get(category, [])

    def execute_sparql(self, query):
        return []

@pytest.fixture
def mock_ontserve(monkeypatch):
    mock = MockOntServeClient()
    monkeypatch.setattr("app.clients.ontserve.client", mock)
    return mock
```

**Status:** ⬜ Not Started

---

## PHASE 4: IMPLEMENTATION ROADMAP

### Suggested Timeline (Iterative Approach)

#### Sprint 1: Foundation (Week 1-2)
- [ ] Create `pyproject.toml` and establish dependency management
- [ ] Set up uv and ruff tooling
- [ ] Move tests to `/tests/` directory
- [ ] Remove archive/ and backup files
- [ ] Remove .bak files

**Status:** ⬜ Not Started

---

#### Sprint 2: Structure (Week 3-4)
- [ ] Create new directory structure (`/app/clients/`, `/app/schemas/`)
- [ ] Move config.py to `/app/core/config.py`
- [ ] Consolidate MCP clients (create unified interface)
- [ ] Begin SQLAlchemy 2.0 migration (models first)

**Status:** ⬜ Not Started

---

#### Sprint 3: Services (Week 5-6)
- [ ] Consolidate annotation services
- [ ] Consolidate guideline services
- [ ] Consolidate LLM services
- [ ] Add Pydantic schemas for key models

**Status:** ⬜ Not Started

---

#### Sprint 4: Testing & Documentation (Week 7-8)
- [ ] Add test coverage for consolidated services
- [ ] Create ARCHITECTURE.md
- [ ] Create ONTSERVE_INTEGRATION.md
- [ ] Set up GitHub Actions CI

**Status:** ⬜ Not Started

---

#### Sprint 5: Final Cleanup (Week 9-10)
- [ ] Remove deprecated services
- [ ] Final SQLAlchemy 2.0 migration
- [ ] Performance testing
- [ ] Production deployment preparation

**Status:** ⬜ Not Started

---

## CRITICAL COMPATIBILITY NOTES

### OntServe Integration Stability

#### What MUST be preserved:

**1. MCP Tool Interface:**
- `get_world_entities()`
- `get_concepts()`
- `submit_candidate_concept()`

**2. Entity Categories:**
- Role, Principle, Obligation, State, Resource, Constraint, Capability, Action, Event

**3. SPARQL Endpoint Access:**
- Keep SPARQL query capability
- Document all queries used

**4. Route Redirects:**
- `/ontology/*` routes redirect to OntServe web interface
- Keep these even if minimal

#### What CAN be changed safely:

**1. Internal client implementation:**
- Consolidate 4 clients → 1 unified client
- Improve error handling and retry logic
- Add caching layer

**2. Service layer:**
- How services call MCP clients
- Internal data transformation
- Business logic organization

**3. Testing:**
- Add mocks for OntServe
- Integration tests for real OntServe

#### Migration Safety:
- Create unified client WITHOUT removing old ones initially
- Gradual service migration
- Run integration tests after each migration
- Keep old clients until 100% migrated

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
- [ ] SQLAlchemy 2.0 migration complete (all models updated)
- [ ] Single unified MCP client used throughout codebase
- [ ] Test coverage >70%
- [ ] CI/CD pipeline running on GitHub Actions

### Phase 3 Success Criteria:
- [ ] ONTSERVE_INTEGRATION.md documentation complete
- [ ] All OntServe integration tests passing
- [ ] Mock OntServe client for testing
- [ ] Version compatibility documented

### Overall Success:
- [ ] Codebase reduced by >40% (file count and complexity)
- [ ] All tests passing
- [ ] Production deployment successful
- [ ] OntServe integration stable
- [ ] Developer onboarding time reduced by 50%

---

## RISKS & MITIGATION

### Risk 1: Breaking OntServe Integration
**Mitigation:**
- Comprehensive integration tests before changes
- Document current API usage
- Gradual migration with old code preserved
- Coordinate with OntServe team on their refactoring

### Risk 2: Lost Functionality in Cleanup
**Mitigation:**
- Audit usage before deletion (grep for imports)
- Git preserves all history
- Keep archive branch with old code
- Document what was removed and why

### Risk 3: SQLAlchemy 2.0 Migration Issues
**Mitigation:**
- Use SQLAlchemy 1.4 compatibility mode first
- Migrate models incrementally
- Comprehensive test suite
- Database backup before production migration

### Risk 4: Dependency Conflicts
**Mitigation:**
- Use uv's lock file for exact versions
- Test in clean environment
- Document known conflicts
- Pin problematic dependencies

---

## OPEN QUESTIONS

Before proceeding with implementation, clarification needed on:

### 1. REALM and McLaren modules:
- ❓ Are these still actively used/developed?
- ❓ Should they be integrated, archived, or separated?

### 2. NSPE Pipeline:
- ❓ How often is this run?
- ❓ Should it be part of main app or separate tool?

### 3. OntServe Refactoring:
- ❓ Do you have access to OntServe refactoring docs?
- ❓ Can we coordinate API compatibility?
- ❓ What's the timeline for OntServe changes?

### 4. Python Version:
- ❓ What Python version is currently deployed?
- ❓ Can we upgrade to 3.11 or 3.12?

### 5. Deployment:
- ❓ Is this currently deployed to proethica.org?
- ❓ What's the deployment process?
- ❓ Can we test in staging environment?

### 6. Priority:
- ❓ Which phase should we tackle first?
- ❓ Are there specific pain points to address immediately?

---

## CONCLUSION

This multi-phase plan provides a comprehensive roadmap for cleaning up and modernizing the proethica codebase while maintaining stability and OntServe compatibility. The plan is designed to be executed iteratively, with each phase building on the previous one and providing measurable improvements.

**Key Benefits:**
- **Reduced complexity:** ~40% reduction in codebase size
- **Modern tooling:** uv, ruff, SQLAlchemy 2.0
- **Better organization:** Clear service boundaries, standard structure
- **Improved stability:** Better testing, documentation, type safety
- **Future-ready:** Async support, modern Python idioms
- **Maintained compatibility:** OntServe integration preserved and documented

**Next Steps:**
1. Review this plan
2. Answer clarifying questions
3. Prioritize phases based on business needs
4. Begin Phase 1 execution (dependency management)

---

## CHANGE LOG

### 2025-11-16 - Initial Plan Created
- Comprehensive codebase analysis completed
- Multi-phase cleanup and refactoring plan created
- Research into 2025 Python best practices (uv, ruff, SQLAlchemy 2.0)
- OntServe integration points documented
- Success metrics and risk mitigation strategies defined
