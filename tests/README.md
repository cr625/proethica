# Route Tests

This directory contains tests for all the routes in the application. The tests are organized by route module and use pytest as the testing framework.

## Test Structure

- `conftest.py`: Contains shared fixtures and setup for all tests
- `test_auth_routes.py`: Tests for authentication routes (login, register, logout)
- `test_entities_routes.py`: Tests for entity management routes
- `test_scenarios_routes.py`: Tests for scenario management routes (scenarios, characters, resources, actions, events)
- `test_worlds_routes.py`: Tests for world management routes (worlds, cases, rulesets, references)
- `test_all_routes.py`: Imports and runs all route tests to ensure all routes are working correctly

## Running the Tests

To run all tests:

```bash
pytest
```

To run tests for a specific module:

```bash
pytest tests/test_scenarios_routes.py
```

To run all route tests at once:

```bash
pytest tests/test_all_routes.py
```

To run a specific test:

```bash
pytest tests/test_scenarios_routes.py::test_list_scenarios
```

To run tests with verbose output:

```bash
pytest -v
```

You can also use the run_tests.py script:

```bash
# Run all tests
./run_tests.py

# Run with verbose output
./run_tests.py -v

# Run specific test file
./run_tests.py tests/test_scenarios_routes.py

# Run all route tests
./run_tests.py tests/test_all_routes.py
```

## Test Coverage

The tests cover the following functionality:

### Authentication Routes
- Login
- Registration
- Logout
- Redirects for authenticated/unauthenticated users

### Entity Routes
- Creating entities
- Adding entities to events
- Error handling for invalid requests

### Scenario Routes
- API endpoints for scenarios
- Web routes for scenarios
- Character management
- Resource management
- Action management
- Event management
- Decision management
- References

### World Routes
- API endpoints for worlds
- Web routes for worlds
- Case management
- Ruleset management
- References

## Test Database

The tests use a separate test database that is created and destroyed for each test. This ensures that tests don't interfere with each other and that the production database is not affected.

## Mocking

Some tests use mocking to simulate external dependencies, such as the MCP client for ontology and reference operations. This allows testing these routes without requiring the actual external services to be available.
