"""
Test all routes in the application.
This file imports and runs all the route tests to ensure all routes are working correctly.
"""
import pytest
from tests.test_auth_routes import *
from tests.test_entities_routes import *
from tests.test_scenarios_routes import *
from tests.test_worlds_routes import *

if __name__ == "__main__":
    pytest.main(["-v", "tests/test_all_routes.py"])
