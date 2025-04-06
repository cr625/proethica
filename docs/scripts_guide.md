# Scripts Guide

This document provides an overview of the utility scripts available in the `scripts/` directory, organized by functional categories. Use this guide to quickly find scripts for specific tasks within the ProEthica system.

## Table of Contents

- [RDF and Triple Management](#rdf-and-triple-management)
- [Database Management](#database-management)
- [Temporal Functionality](#temporal-functionality)
- [Entity and Character Management](#entity-and-character-management)
- [Case and World Management](#case-and-world-management)
- [Scenario Management](#scenario-management)
- [Testing and Verification](#testing-and-verification)
- [Ontology Management](#ontology-management)
- [Embedding and Search](#embedding-and-search)
- [System Maintenance](#system-maintenance)

## RDF and Triple Management

- **add_triples_to_cases.py**: Adds relevant triples to cases based on their content.
- **check_case_triples_namespaces.py**: Checks if cases have proper namespace associations and triple templates.
- **fix_all_cases_namespaces_and_triples.py**: Fixes namespaces and triples for all cases to ensure proper display in the edit interface.
- **fix_namespaces_and_triples_for_case_123.py**: Test script fixing namespaces and triples for a single case.
- **fix_triples_in_metadata.py**: Updates doc_metadata with triples from the entity_triples table.
- **fix_triples_in_metadata_and_entity_type.py**: Fixes both doc_metadata and entity_type in entity_triples.
- **view_case_triples.py**: Displays triples associated with a specific case.
- **test_rdf_serialization.py**: Tests RDF serialization functionality.
- **test_rdf_embeddings.py**: Tests embedding generation for RDF triples.
- **test_ontology.py**: Tests basic ontology loading and querying.
- **test_ontology_extraction.py**: Tests extraction of ontology elements.
- **test_ontology_mcp.py**: Tests the ontology MCP server functionality.
- **test_intermediate_ontology.py**: Tests the intermediate ontology format.
- **check_namespaces.py**: Checks namespace declarations across the system.

## Database Management

- **manage_test_db.py**: Manages test database creation and teardown.
- **run_tests_with_pg.py**: Runs tests with a PostgreSQL database.
- **check_db.py**: Performs database health checks and displays status.
- **create_entity_triples_table.sql**: SQL script to create the entity_triples table.
- **enhance_entity_triples_temporal.sql**: SQL script to add temporal fields to entity_triples.
- **test_db.py**: Tests database connection and basic operations.
- **test_postgres.py**: Tests PostgreSQL-specific functionality.
- **migrate_to_pgvector.py**: Migrates database to use pgvector for embeddings.
- **enable_pgvector.sql**: SQL script to enable pgvector extension.

## Temporal Functionality

- **add_temporal_fields_to_triples.py**: Adds temporal fields to entity triples.
- **setup_temporal_enhancements.sh**: Sets up temporal functionality enhancements.
- **test_temporal_functionality.py**: Tests temporal context and timeline functionality.
- **verify_temporal_fields.py**: Verifies temporal fields in the database.

## Entity and Character Management

- **check_entity_details.py**: Displays detailed information about entities.
- **demo_entity_triple_queries.py**: Demonstrates queries against the entity_triples table.
- **implement_entity_triples.py**: Implements entity-triple relationships.
- **populate_entities.py**: Populates entities from the ontology.
- **setup_character_triples.py**: Sets up triples for characters.
- **test_character_rdf_triples.py**: Tests RDF triple management for characters.
- **test_character_role_api.py**: Tests the character role API.
- **test_character_role_direct.py**: Tests direct character role operations.
- **test_character_role_update.py**: Tests character role update operations.
- **test_entity_triple_service.py**: Tests the entity triple service.
- **test_entity_triples_creation.py**: Tests creation of entity triples.
- **init_character_rdf.py**: Initializes RDF for characters.
- **integrate_character_rdf.py**: Integrates character data with RDF.
- **test_rdf_character_sync.py**: Tests synchronization of characters with RDF.

## Case and World Management

- **check_worlds.py**: Checks world configuration and status.
- **check_worlds_and_scenarios.py**: Checks relationships between worlds and scenarios.
- **check_world_ontology.py**: Checks world ontology sources.
- **create_nspe_ethics_cases.py**: Creates NSPE ethics cases.
- **direct_delete_world.py**: Directly deletes a world from the database.
- **direct_update_world.py**: Directly updates world properties.
- **extend_engineering_ethics_ontology.py**: Extends the engineering ethics ontology.
- **extend_nspe_engineering_ontology.py**: Extends NSPE engineering ontology.
- **import_case_triples_to_db.py**: Imports case triples to the database.
- **import_missing_nspe_cases.py**: Imports missing NSPE cases.
- **import_nspe_cases.py**: Imports NSPE cases into the system.
- **import_nspe_cases_to_world.py**: Imports NSPE cases into a specific world.
- **list_nspe_ethics_cases.py**: Lists NSPE ethics cases.
- **list_nspe_world_cases.py**: Lists cases in the NSPE world.
- **list_worlds.py**: Lists all worlds in the system.
- **remove_engineering_world_cases.py**: Removes cases from the Engineering world.
- **remove_incorrect_nspe_cases.py**: Removes incorrectly imported NSPE cases.

## Scenario Management

- **add_characters_to_scenario6.py**: Adds characters to scenario 6.
- **add_resources_to_scenario6.py**: Adds resources to scenario 6.
- **add_timeline_to_scenario6.py**: Adds timeline to scenario 6.
- **get_scenario_info.py**: Retrieves information about a scenario.
- **get_scenario_timeline.py**: Retrieves timeline information for a scenario.
- **get_scenario_with_resources.py**: Retrieves scenario with associated resources.
- **list_scenarios.py**: Lists all scenarios in the system.
- **delete_all_scenarios.py**: Deletes all scenarios from the system.

## Testing and Verification

- **simple_check.py**: Performs a simple system check.
- **test_application_context.py**: Tests the application context service.
- **test_claude_api.py**: Tests the Claude API integration.
- **test_document_search.py**: Tests document search functionality.
- **test_embedding_providers.py**: Tests different embedding providers.
- **test_embedding_service.py**: Tests the embedding service.
- **test_guidelines_agent.py**: Tests the guidelines agent functionality.
- **test_mcp_server.py**: Tests the MCP server.
- **test_mcp_singleton.py**: Tests the MCP singleton pattern.
- **test_simulation.py**: Tests simulation functionality.

## Ontology Management

- **bfo_ethics_demo.py**: Demonstrates BFO ethics integration.
- **check_mcp_roles.py**: Checks MCP roles in the ontology.
- **fix_ontology_syntax.py**: Fixes syntax issues in ontology files.
- **revised_engineering_ethics_world.py**: Revises the Engineering Ethics world ontology.
- **revised_nj_legal_ethics_world.py**: Revises the NJ Legal Ethics world ontology.
- **revised_tccc_world.py**: Revises the TCCC world ontology.
- **update_engineering_ontology.py**: Updates the engineering ontology.

## Embedding and Search

- **simple_pgvector_test.py**: Tests pgvector functionality.
- **setup_embedding_environment.sh**: Sets up the embedding environment.

## System Maintenance

- **create_admin_user.py**: Creates an admin user in the system.
- **create_condition_types_table.py**: Creates the condition_types table.
- **create_specific_revision.py**: Creates a specific revision for testing.
- **create_uploads_directory.py**: Creates the uploads directory structure.
- **fix_all_json_fields.py**: Fixes all JSON fields in the database.
- **initialize_migrations.py**: Initializes database migrations.
- **run_action_migration.py**: Runs action-related database migrations.
- **run_entity_triples_migration.py**: Runs entity triples migration.
- **run_with_agents.py**: Runs the system with agent functionality enabled.
- **restart_http_mcp_server.sh**: Restarts the HTTP MCP server.
- **restart_mcp_server.sh**: Restarts the MCP server.
- **restart_mcp_server_gunicorn.sh**: Restarts the MCP server with Gunicorn.
- **restart_mcp_server_gunicorn.fixed.sh**: Restarts the MCP server with a fixed Gunicorn configuration.
- **setup_agent_architecture.sh**: Sets up the agent architecture.
- **setup_condition_types.py**: Sets up condition types in the system.
- **setup_document_status_cron.sh**: Sets up a cron job for document status updates.
- **check_claude_api.py**: Checks Claude API functionality and credentials.
