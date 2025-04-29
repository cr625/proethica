# Repository Branch Strategy

This document outlines the branch strategy for the ProEthica repository after implementing the unified environment system.

## Branch Structure

### Main Branches

- **`main`**: The primary branch containing stable, tested code.
- **`dev`**: The main development branch where feature branches are merged before going to `main`. This branch includes the unified environment detection system.
- **`production`**: The branch deployed to the production server at proethica.org. This will replace both `production-state` and `agent-ontology-integration` to provide a single, clear production branch.

### Feature Branches

Feature branches should be created for specific features or bug fixes. They should be branched from `dev` and merged back when complete.

Examples of feature branches:
- `feature/new-ui-component`
- `fix/database-connection-issue`

## Release Flow

1. Development happens in `dev` branch and feature branches
2. When ready for testing, merge `dev` into `main`
3. After testing and validation, merge `main` into `production` for deployment
4. The `production` branch should only be updated via approved merges from `main`

## Environment Handling

With the implementation of the unified environment detection system, separate environment-specific branches are no longer needed. The codebase now automatically detects and configures for different environments:

- GitHub Codespaces
- WSL (Windows Subsystem for Linux)
- Regular development environments
- Production environments

## Branch Cleanup Plan

To streamline the repository, we will consolidate production-related branches:

1. The Docker PostgreSQL configuration from `agent-ontology-integration` has been incorporated into `dev`
2. We will create a new `production` branch based on `production-state` but with the Docker deployment configuration
3. After validation, we can eventually deprecate `production-state` and `agent-ontology-integration`

This will simplify our branch structure while preserving all deployment capabilities.

## Working with the Unified Environment System

With the unified system, developers should:

1. Use the `dev` branch for development
2. Create feature branches from `dev` for specific tasks
3. Let the system automatically detect their environment
4. Merge completed feature branches back to `dev`
5. Follow the release flow for deploying to production

The system will automatically adapt to whatever environment it's running in, eliminating the need to switch branches based on environment.
