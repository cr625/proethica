# ProEthica Testing Guide

This guide explains how to run tests in the ProEthica application using PostgreSQL.

## Testing Database Configuration

ProEthica uses PostgreSQL for both production and testing to ensure consistency:

- **Production**: Uses the main PostgreSQL database `ai_ethical_dm`
- **Testing**: Uses a dedicated PostgreSQL database `ai_ethical_dm_test`

We previously used SQLite in-memory for tests, but this approach had several issues:
- SQLite lacks some PostgreSQL features used in the app
- Differences in SQL dialects can cause tests to pass but fail in production
- Data type handling differences between SQLite and PostgreSQL
- Transaction behavior differences that could mask bugs

## Test Database Management

The test database is managed using scripts:

1. **manage_test_db.py**: Creates, drops, or resets the test database
   ```bash
   # Create the test database
   python scripts/manage_test_db.py --create
   
   # Drop the test database
   python scripts/manage_test_db.py --drop
   
   # Reset the test database (drop and recreate)
   python scripts/manage_test_db.py --reset
   ```

2. **run_tests_with_pg.py**: Sets up the test database and runs tests
   ```bash
   # Run all tests
   python scripts/run_tests_with_pg.py
   
   # Run with verbose output
   python scripts/run_tests_with_pg.py --verbose
   
   # Run a specific test
   python scripts/run_tests_with_pg.py tests/test_mcp_api.py
   
   # Only setup the database without running tests
   python scripts/run_tests_with_pg.py --setup-only
   ```

## Running Tests

The main `run_tests.py` script delegates to `run_tests_with_pg.py` to ensure the test database is properly set up:

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py -v

# Run a specific test file
python run_tests.py tests/test_mcp_api.py
```

## Test Fixtures

The test fixtures in `conftest.py` provide:

1. **Database Setup**: PostgreSQL test database creation and initialization
2. **Test Isolation**: Each test gets a clean database state
3. **Test Data**: Helper fixtures for creating test users, worlds, scenarios, etc.
4. **Authentication**: Helper fixtures for authenticated clients

## Best Practices

When writing tests:

1. **Use Fixtures**: Leverage the provided fixtures to create test data
2. **Isolate Tests**: Don't depend on data created by other tests
3. **Mock External Services**: Use unittest.mock to mock external services
4. **Clean Up**: Ensure tests clean up after themselves
5. **Test Edge Cases**: Include tests for error conditions

## PostgreSQL-Specific Considerations

Some PostgreSQL features that might need special attention in tests:

1. **JSON/JSONB**: ProEthica uses JSONB fields for flexible data storage
2. **Array Types**: PostgreSQL's array types differ from SQLite
3. **Full-Text Search**: PostgreSQL has powerful text search capabilities
4. **Transactions**: PostgreSQL has different transaction semantics

## Troubleshooting

If tests fail, check:

1. **Database Connection**: Ensure PostgreSQL is running and the test database exists
2. **Environment Variables**: Check if `TEST_DATABASE_URL` is set correctly
3. **Schema Issues**: Verify the test database schema matches the application models
4. **Test Isolation**: Ensure tests aren't interfering with each other
