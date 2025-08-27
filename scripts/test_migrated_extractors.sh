#!/bin/bash

# Test script for migrated extractors with selective controls
# This allows testing only the fully migrated extractors

echo "🧪 Testing Migrated Extractors with Selective Controls"
echo "======================================================="

# Enable atomic concept splitting
export ENABLE_CONCEPT_SPLITTING=true

# Enable only fully migrated extractors
export ENABLE_OBLIGATION_EXTRACTION=true
export ENABLE_PRINCIPLE_EXTRACTION=true  
export ENABLE_ROLE_EXTRACTION=true
export ENABLE_RESOURCE_EXTRACTION=true

# Disable extractors that haven't been migrated yet
export ENABLE_ACTION_EXTRACTION=false
export ENABLE_STATE_EXTRACTION=false
export ENABLE_EVENT_EXTRACTION=false
export ENABLE_CAPABILITY_EXTRACTION=false
export ENABLE_CONSTRAINT_EXTRACTION=false

echo "✅ Environment configured for migrated extractors only:"
echo "  - Obligations: ENABLED"
echo "  - Principles: ENABLED" 
echo "  - Roles: ENABLED"
echo "  - Resources: ENABLED"
echo ""
echo "  - Actions: DISABLED"
echo "  - States: DISABLED"
echo "  - Events: DISABLED"
echo "  - Capabilities: DISABLED" 
echo "  - Constraints: DISABLED"
echo ""

echo "🎯 Ready for testing at: http://localhost:3333/worlds/1/guidelines/43#associated-concepts"
echo ""
echo "Expected behavior:"
echo "  ✅ Clean, normalized concept labels"
echo "  ✅ Atomic concepts (no compound statements)"
echo "  ✅ Proper capitalization and formatting"
echo "  ✅ No leading dashes, bullets, or trailing punctuation"
echo "  ✅ Only migrated concept types extracted"