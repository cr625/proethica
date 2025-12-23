# ProEthica Test Management Command

You are a test management specialist for ProEthica. Help the user audit, run, and create tests.

## Project Context

- **Test directory**: `tests/`
- **Unit tests**: `tests/unit/` (fast, no database/LLM)
- **Integration tests**: `tests/integration/` (require database, may use LLM)
- **Smoke tests**: `tests/smoke_test_phase1.sh` (require running server)
- **Conftest**: `tests/conftest.py` (fixtures and mocks)
- **Mock LLM**: `tests/mocks/llm_client.py` (for unit testing without API calls)

## Test Database

- **Production**: `ai_ethical_dm` (PostgreSQL)
- **Testing**: `ai_ethical_dm_test` (isolated test database)

The test fixtures automatically use `ai_ethical_dm_test` when `FLASK_ENV=testing`.

## Test Runner Script

Use the convenience script for common test operations:

```bash
./scripts/run_tests.sh unit        # Fast unit tests only
./scripts/run_tests.sh integration # Database tests
./scripts/run_tests.sh new         # New feature tests only (entity analysis, interactive, synthesizer)
./scripts/run_tests.sh coverage    # All tests with coverage report
./scripts/run_tests.sh smoke       # Smoke tests (requires running server)
./scripts/run_tests.sh all         # All tests
```

Options: `-v` (verbose), `-x` (stop on first failure)

## Available Test Categories

### Unit Tests (Fast, No External Dependencies)
```bash
cd /home/chris/onto/proethica
source venv-proethica/bin/activate
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/ -v
```

### Integration Tests (Require Database)
```bash
cd /home/chris/onto/proethica
source venv-proethica/bin/activate
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/integration/ -v
```

### All Tests
```bash
cd /home/chris/onto/proethica
source venv-proethica/bin/activate
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/ -v
```

### Smoke Tests (Require Running Server)
```bash
cd /home/chris/onto/proethica
./tests/smoke_test_phase1.sh
```

### Test Specific File
```bash
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_extraction_roles.py -v
```

### Test with Coverage
```bash
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/ --cov=app --cov-report=html -v
```

## Current Test Coverage Status

### Existing Tests (as of December 2025)

| Category | File | Status |
|----------|------|--------|
| **Unit - Extractors** | | |
| | `test_extraction_roles.py` | EXISTS |
| | `test_extraction_states.py` | EXISTS |
| | `test_extraction_resources.py` | EXISTS |
| | `test_extraction_principles.py` | EXISTS |
| | `test_extraction_obligations.py` | EXISTS |
| | `test_extraction_constraints.py` | EXISTS |
| | `test_extraction_capabilities.py` | EXISTS |
| | `test_extraction_actions_events.py` | EXISTS |
| **Integration - Routes** | | |
| | `test_all_routes.py` | EXISTS |
| | `test_scenarios_routes.py` | EXISTS |
| | `test_auth_routes.py` | EXISTS |
| | `test_auth_security.py` | EXISTS (56 tests) |
| | `test_document_routes.py` | EXISTS |
| | `test_entities_routes.py` | EXISTS |
| | `test_worlds_routes.py` | EXISTS |
| **Integration - MCP** | | |
| | `test_mcp_api.py` | EXISTS |
| | `test_real_mcp_scenario.py` | EXISTS |
| **Integration - Pipeline** | | |
| | `test_pipeline_persistence.py` | EXISTS |

### New Feature Tests (December 2025)

| Feature | Service/Route | Test File | Status |
|---------|---------------|-----------|--------|
| **Entity Analysis Pipeline** | | | |
| E1-F1 Dataclasses | `entity_analysis/*.py` | `test_entity_analysis_pipeline.py` | 27 tests |
| F2 Argument Generator | `entity_analysis/argument_generator.py` | (needs tests) | PENDING |
| F3 Argument Validator | `entity_analysis/argument_validator.py` | (needs tests) | PENDING |
| **Case Synthesis** | | | |
| Case Synthesizer | `services/case_synthesizer.py` | `test_case_synthesizer.py` | 36 tests |
| Transformation Classifier | `services/transformation_classifier.py` | (needs tests) | PENDING |
| **Interactive Scenarios** | | | |
| Interactive Service | `services/interactive_scenario_service.py` | `test_interactive_scenario_service.py` | 23 tests |
| Step 5 Interactive Routes | `routes/scenario_pipeline/step5_interactive.py` | (needs integration tests) | PENDING |
| **Academic Frameworks** | | | |
| Moral Intensity | `academic_references/frameworks/moral_intensity.py` | (needs tests) | LOW |
| Role Ethics | `academic_references/frameworks/role_ethics.py` | (needs tests) | LOW |
| Transformation Classification | `academic_references/frameworks/transformation_classification.py` | (needs tests) | LOW |
| Extensional Principles | `academic_references/frameworks/extensional_principles.py` | (needs tests) | LOW |

**Total new tests: 86 passing**

### Authentication Security Tests (December 2025)

The `test_auth_security.py` file verifies authentication and authorization behavior:

| Test Class | Purpose | Environment | Tests |
|------------|---------|-------------|-------|
| `TestPublicPageAccess` | Public pages accessible without login | Testing | 8 |
| `TestDataModifyingRoutesRequireAuth` | Document route availability | Testing | 31 |
| `TestCSRFProtection` | CSRF tokens present in forms | Testing | 2 |
| `TestPipelineReviewPagesReadable` | Review pages publicly readable | Testing | 4 |
| **`TestProductionModeAuthEnforcement`** | **Write routes require auth in prod** | **Production** | **8** |
| **`TestAdminRoutesProductionMode`** | **Admin routes blocked in prod** | **Production** | **3** |

**Run auth security tests:**
```bash
# All tests
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/integration/test_auth_security.py -v

# Production-mode security tests only (CRITICAL)
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/integration/test_auth_security.py::TestProductionModeAuthEnforcement tests/integration/test_auth_security.py::TestAdminRoutesProductionMode -v
```

**Key security principles verified:**
- Unauthenticated users CAN read all public pages
- In PRODUCTION mode: unauthenticated users CANNOT modify data
- Admin routes require admin privileges in production
- LLM extraction and OntServe commit routes require authentication in production

**Note:** Auth decorators like `@auth_required_for_write` bypass auth in development/testing mode for convenience. The `TestProductionModeAuthEnforcement` tests simulate production to verify auth is enforced.

## Environment Awareness

### Development Environment
```bash
# Check services are running
pgrep -f "python run.py" && echo "Flask running" || echo "Flask NOT running"
pgrep -f "mcp_server.py" && echo "MCP running" || echo "MCP NOT running"
redis-cli ping 2>/dev/null && echo "Redis running" || echo "Redis NOT running"
```

### Production Checks
```bash
# NEVER run tests against production database
# Always verify FLASK_ENV before running
echo $FLASK_ENV
```

## Quick Commands

### Check Test Status
```bash
# Count existing tests
find /home/chris/onto/proethica/tests -name "test_*.py" -not -path "*/venv*" | wc -l

# List all test files
find /home/chris/onto/proethica/tests -name "test_*.py" -not -path "*/venv*" | sort
```

### Run Specific Test Category
```bash
# New feature tests (entity analysis, interactive, synthesizer)
./scripts/run_tests.sh new -v

# Or manually:
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_entity_analysis_pipeline.py tests/unit/test_interactive_scenario_service.py tests/unit/test_case_synthesizer.py -v

# Integration tests with database
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/integration/ -v --tb=short
```

### Check for Missing Coverage
```bash
# Find services without tests
for service in /home/chris/onto/proethica/app/services/*.py; do
    name=$(basename "$service" .py)
    if [ ! -f "/home/chris/onto/proethica/tests/unit/test_${name}.py" ] && \
       [ ! -f "/home/chris/onto/proethica/tests/integration/test_${name}.py" ]; then
        echo "MISSING TEST: $name"
    fi
done
```

## Mock LLM Client Usage

For unit tests that don't need real LLM calls:

```python
from tests.mocks import MockLLMClient

def test_extractor_with_mock(mock_llm_client):
    """Test uses mock LLM client fixture from conftest.py"""
    # mock_llm_client is automatically injected
    extractor = SomeExtractor(llm_client=mock_llm_client)
    result = extractor.extract(...)
    assert result is not None
```

## Test Fixtures Available

From `conftest.py`:
- `app` - Flask app with test config
- `client` - Test client for HTTP requests
- `app_context` - Application context
- `auth_client` - Authenticated test client
- `mock_llm_client` - Mock LLM for unit tests
- `sample_case_text` - Sample case text for extraction tests
- `sample_case_id` - Default case ID (7) for tests

## Common Tasks

1. **"Run all tests"** - Execute full test suite with verbose output
2. **"Check test coverage"** - Run with --cov and analyze gaps
3. **"Create tests for X"** - Generate test file for missing service
4. **"Run quick tests"** - Unit tests only (no database/LLM)
5. **"Smoke test"** - Verify production-like environment works

## Test Writing Guidelines

1. **Unit tests**: No external dependencies, use mocks
2. **Integration tests**: Can use test database, mark slow tests
3. **Use fixtures**: Leverage conftest.py fixtures
4. **Naming**: `test_<service>_<method>_<scenario>`
5. **Assertions**: Be specific, test edge cases
6. **Cleanup**: Tests should be isolated, don't leave state

## Running Tests Before Commit

Before committing changes, run:
```bash
cd /home/chris/onto/proethica
source venv-proethica/bin/activate
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/ -v --tb=short
```

For major changes, also run integration tests:
```bash
PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/ -v --tb=short
```
