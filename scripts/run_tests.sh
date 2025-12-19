#!/bin/bash
# ProEthica Test Runner Script
# Usage: ./scripts/run_tests.sh [options]
#
# Options:
#   unit        Run only unit tests (fast, no database)
#   integration Run only integration tests (requires database)
#   all         Run all tests
#   coverage    Run all tests with coverage report
#   smoke       Run smoke tests (requires running server)
#   new         Run only new tests (entity analysis, interactive, synthesizer)
#   -v          Verbose output
#   -x          Stop on first failure
#   --help      Show this help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
TEST_TYPE="all"
VERBOSE=""
FAIL_FAST=""

show_help() {
    echo "ProEthica Test Runner"
    echo ""
    echo "Usage: ./scripts/run_tests.sh [options]"
    echo ""
    echo "Test categories:"
    echo "  unit        Run only unit tests (fast, no database)"
    echo "  integration Run only integration tests (requires database)"
    echo "  all         Run all tests (default)"
    echo "  coverage    Run all tests with coverage report"
    echo "  smoke       Run smoke tests (requires running server)"
    echo "  new         Run only new tests (entity analysis, interactive, synthesizer)"
    echo ""
    echo "Options:"
    echo "  -v          Verbose output"
    echo "  -x          Stop on first failure"
    echo "  --help      Show this help"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_tests.sh unit -v     # Run unit tests verbosely"
    echo "  ./scripts/run_tests.sh new -x      # Run new tests, stop on failure"
    echo "  ./scripts/run_tests.sh coverage    # Run with coverage report"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        unit|integration|all|coverage|smoke|new)
            TEST_TYPE="$1"
            shift
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -x|--fail-fast)
            FAIL_FAST="-x"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check environment
check_environment() {
    echo -e "${YELLOW}Checking environment...${NC}"

    # Check virtual environment
    if [[ -z "$VIRTUAL_ENV" ]]; then
        echo -e "${YELLOW}Activating virtual environment...${NC}"
        source "$PROJECT_DIR/venv-proethica/bin/activate"
    fi

    # Set PYTHONPATH
    export PYTHONPATH="/home/chris/onto:$PYTHONPATH"

    # Check if we're in test mode
    export FLASK_ENV=testing

    echo -e "${GREEN}Environment ready${NC}"
}

# Run unit tests
run_unit_tests() {
    echo -e "${YELLOW}Running unit tests...${NC}"
    cd "$PROJECT_DIR"
    pytest tests/unit/ $VERBOSE $FAIL_FAST --tb=short
}

# Run integration tests
run_integration_tests() {
    echo -e "${YELLOW}Running integration tests...${NC}"
    cd "$PROJECT_DIR"

    # Check database connection
    if ! PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm_test -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${RED}Test database not accessible. Creating...${NC}"
        PGPASSWORD=PASS psql -h localhost -U postgres -c "CREATE DATABASE ai_ethical_dm_test;" 2>/dev/null || true
    fi

    pytest tests/integration/ $VERBOSE $FAIL_FAST --tb=short
}

# Run all tests
run_all_tests() {
    echo -e "${YELLOW}Running all tests...${NC}"
    cd "$PROJECT_DIR"
    pytest tests/ $VERBOSE $FAIL_FAST --tb=short
}

# Run tests with coverage
run_coverage() {
    echo -e "${YELLOW}Running tests with coverage...${NC}"
    cd "$PROJECT_DIR"
    pytest tests/ $VERBOSE --cov=app --cov-report=html --cov-report=term-missing --tb=short

    echo ""
    echo -e "${GREEN}Coverage report generated at: htmlcov/index.html${NC}"
}

# Run smoke tests
run_smoke_tests() {
    echo -e "${YELLOW}Running smoke tests...${NC}"

    # Check if server is running
    if ! curl -s http://localhost:5000/ > /dev/null 2>&1; then
        echo -e "${RED}ProEthica server not running. Start it first:${NC}"
        echo "  cd /home/chris/onto/proethica && python run.py"
        exit 1
    fi

    # Check if MCP server is running
    if ! curl -s http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${YELLOW}Warning: OntServe MCP server not running${NC}"
    fi

    cd "$PROJECT_DIR"
    ./tests/smoke_test_phase1.sh
}

# Run new tests only (entity analysis, interactive, synthesizer)
run_new_tests() {
    echo -e "${YELLOW}Running new feature tests...${NC}"
    cd "$PROJECT_DIR"
    pytest tests/unit/test_entity_analysis_pipeline.py \
           tests/unit/test_interactive_scenario_service.py \
           tests/unit/test_case_synthesizer.py \
           $VERBOSE $FAIL_FAST --tb=short
}

# Main execution
main() {
    echo "========================================="
    echo "ProEthica Test Runner"
    echo "========================================="
    echo ""

    check_environment

    case $TEST_TYPE in
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        all)
            run_all_tests
            ;;
        coverage)
            run_coverage
            ;;
        smoke)
            run_smoke_tests
            ;;
        new)
            run_new_tests
            ;;
    esac

    echo ""
    echo -e "${GREEN}Tests completed!${NC}"
}

main
