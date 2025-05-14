#!/bin/bash
# Test script for the guideline API functionality in the MCP server
# Tests the basic functionality of the guideline analysis tools

echo "=== Testing ProEthica Guideline API ==="
echo ""

# Test the MCP server connection
echo "1. Testing MCP server connection..."
response=$(curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')

echo "$response" | grep -q "extract_guideline_concepts"
if [ $? -eq 0 ]; then
    echo "✓ MCP server is up and running with guideline tools"
else
    echo "❌ MCP server connection failed or guideline tools not found"
    echo "Response: $response"
    exit 1
fi
echo ""

# Test extracting concepts from a guideline
echo "2. Testing extract_guideline_concepts..."
extract_response=$(curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"extract_guideline_concepts","params":{"content":"Engineers shall hold paramount the safety, health, and welfare of the public."},"id":2}')

echo "$extract_response" | grep -q "result"
if [ $? -eq 0 ]; then
    echo "✓ Successfully extracted concepts"
    # Extract just the concepts part for better readability
    echo "Sample response (truncated):"
    echo "$extract_response" | grep -o '"concepts":\[[^]]*\]' | head -n 20
else
    echo "❌ Failed to extract concepts"
    echo "Response: $extract_response"
    exit 1
fi
echo ""

# Test Database Connection via the debug app
echo "3. Testing debug app API..."
status_response=$(curl -s http://localhost:5050/api/status)

echo "$status_response" | grep -q '"connected": true'
if [ $? -eq 0 ]; then
    echo "✓ Debug app API is working and reports successful connections"
else
    echo "❌ Debug app API issues or connection problems"
    echo "Response: $status_response"
    exit 1
fi

echo ""
echo "=== All tests passed! ==="
echo "The ProEthica system is running correctly in codespace environment."
echo "You can access the debug interface at http://localhost:5050/"
