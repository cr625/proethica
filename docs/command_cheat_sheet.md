# Command Cheat Sheet

## Force Delete World ID 18

To fix the integrity error when deleting world ID 18, use one of these approaches:

### Option 1: Use the Force Delete World Script

The `force_delete_world.py` script handles deletion of a world and all related data, including handling the simulation_states issue:

```bash
# To delete world 18 with confirmation
python scripts/force_delete_world.py 18

# To force delete without confirmation
python scripts/force_delete_world.py 18 --force
```

This script:
1. Identifies all related data (scenarios, characters, events, resources, etc.)
2. Handles the null scenario_id issue in simulation_states by using direct SQL 
3. Deletes everything in the proper order to avoid constraint violations
4. Shows detailed information about what is being deleted

### Option 2: Direct SQL Approach

If the Python script doesn't work, you can use direct SQL to bypass the constraint error:

```bash
# Connect to PostgreSQL
psql ai_ethical_dm

# Delete the problematic simulation states directly
DELETE FROM simulation_states WHERE metadata->>'world_id' = '18';

# Then delete the world and rely on cascading deletes
DELETE FROM worlds WHERE id = 18;
```

### Option 3: Temporarily Disable Constraint

```bash
# Connect to PostgreSQL
psql ai_ethical_dm

# Temporarily disable the constraint
ALTER TABLE simulation_states ALTER COLUMN scenario_id DROP NOT NULL;

# Delete the world through the app interface or API
# After deletion, re-enable the constraint
ALTER TABLE simulation_states ALTER COLUMN scenario_id SET NOT NULL;
```

## Phase 1 RDF Implementation Commands

### Run the Complete Implementation

```bash
# Run with backup and interaction
python scripts/implement_phase1_fixed.py --with-backup

# Run without interaction
python scripts/implement_phase1_fixed.py --with-backup --force
```

### Test Individual Components

```bash
# Test entity triple creation
python scripts/test_entity_triples_creation.py

# Test entity triple service
python scripts/test_entity_triple_service.py

# Test RDF serialization
python scripts/test_rdf_serialization.py

# Test temporal features
python scripts/add_temporal_fields_to_triples.py
