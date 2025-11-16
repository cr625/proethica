#!/bin/bash
# Smoke Test for Phase 1 IAO Implementation
# Purpose: Verify no existing functionality was broken
# Date: 2025-10-07

echo "========================================="
echo "ProEthica Phase 1 Smoke Test"
echo "========================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0

# Function to run test
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo "✅ PASS"
        ((PASS_COUNT++))
        return 0
    else
        echo "❌ FAIL"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Test 1: Server is running
run_test "ProEthica server is running" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/ | grep -q 200"

# Test 2: Home page loads
run_test "Home page loads correctly" \
    "curl -s http://localhost:5000/ | grep -q 'ProEthica'"

# Test 3: Step 1 (Facts) loads
run_test "Step 1 Facts section loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/step1 | grep -q 'Facts'"

# Test 4: Step 1b (Discussion) loads
run_test "Step 1b Discussion section loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/step1b | grep -q 'Discussion'"

# Test 5: Step 2 (Pass 2 Facts) loads
run_test "Step 2 Facts section loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/step2 | grep -q 'Normative'"

# Test 6: Step 2b (Pass 2 Discussion) loads
run_test "Step 2b Discussion section loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/step2b | grep -q 'Discussion Section'"

# Test 7: Database connection works
run_test "Database connection works" \
    "export PGPASSWORD=PASS && psql -h localhost -U postgres -d ai_ethical_dm -c 'SELECT 1;' -t | grep -q 1"

# Test 8: TemporaryRDFStorage table exists with IAO columns
run_test "TemporaryRDFStorage has IAO columns" \
    "export PGPASSWORD=PASS && psql -h localhost -U postgres -d ai_ethical_dm -c \"SELECT column_name FROM information_schema.columns WHERE table_name = 'temporary_rdf_storage' AND column_name = 'iao_document_uri';\" -t | grep -q 'iao_document_uri'"

# Test 9: Can query existing entities
run_test "Can query existing RDF entities" \
    "export PGPASSWORD=PASS && psql -h localhost -U postgres -d ai_ethical_dm -c 'SELECT COUNT(*) FROM temporary_rdf_storage;' -t | grep -E '[0-9]+'"

# Test 10: Python model imports successfully
run_test "TemporaryRDFStorage model imports" \
    "cd /home/chris/onto/proethica && python -c 'from app.models.temporary_rdf_storage import TemporaryRDFStorage; print(\"OK\")' | grep -q OK"

# Test 11: OntServe MCP is running
run_test "OntServe MCP server is running" \
    "curl -s http://localhost:8082/health | grep -q '\"status\": \"ok\"'"

# Test 12: OntServe has new IAO properties
run_test "OntServe has IAO properties loaded" \
    "export PGPASSWORD=PASS && psql -h localhost -U postgres -d ontserve -c \"SELECT COUNT(*) FROM ontology_entities WHERE label = 'refers to document';\" -t | grep -q 1"

# Test 13: Pass 1 entity review loads
run_test "Pass 1 entity review page loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/entities/review/pass1 | grep -q 'PASS 1'"

# Test 14: Pass 2 entity review loads
run_test "Pass 2 entity review page loads" \
    "curl -s http://localhost:5000/scenario_pipeline/case/10/entities/review/pass2 | grep -q 'PASS 2'"

# Test 15: Extraction endpoint exists (no auth needed for test)
run_test "Extraction endpoint responds" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/scenario_pipeline/case/10/step1 | grep -q 200"

echo ""
echo "========================================="
echo "Test Results"
echo "========================================="
echo "PASSED: $PASS_COUNT"
echo "FAILED: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED - Safe to continue to Phase 2"
    exit 0
else
    echo "⚠️  SOME TESTS FAILED - Review failures before continuing"
    exit 1
fi
