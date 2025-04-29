# Repository Branch Strategy

This document outlines the branch strategy for the ProEthica repository after implementing the unified environment system.

## Branch Structure

### Main Branches

- **`main`**: The primary branch containing stable, production-ready code.
- **`production-state`**: The branch deployed to the production server at proethica.org.
- **`dev`**: The main development branch where all feature branches are merged before going to `main`. This branch now includes the unified environment detection system.

### Feature Branches

Feature branches should be created for specific features or bug fixes. They should be branched from `dev` and merged back when complete.

Examples of feature branches:
- `feature/new-ui-component`
- `fix/database-connection-issue`

## Release Flow

1. Development happens in `dev` branch and feature branches
2. When ready for testing, merge `dev` into `main`
3. After testing and validation, merge `main` into `production-state` for deployment
4. The `production-state` branch should only be updated via approved merges from `main`

## Environment Handling

With the implementation of the unified environment detection system, separate environment-specific branches are no longer needed. The codebase now automatically detects and configures for different environments:

- GitHub Codespaces
- WSL (Windows Subsystem for Linux)
- Regular development environments
- Production environments

## Branch Cleanup Actions

The following actions have been taken to streamline the repository:

1. The former `agent-ontology-dev` branch, which contained the unified environment system implementation, has been renamed to `dev`.
2. The deprecated `codespace-environment` branch has been deleted as its functionality is now part of the unified system.
3. The remote `dev` branch has been updated to match the current branch structure.
4. We maintain `main` and `production-state` branches for stable code and production deployment respectively.

## Working with the Unified Environment System

With the unified system, developers should:

1. Use the `dev` branch for development
2. Create feature branches from `dev` for specific tasks
3. Let the system automatically detect their environment
4. Merge completed feature branches back to `dev`
5. Follow the release flow for deploying to production

The system will automatically adapt to whatever environment it's running in, eliminating the need to switch branches based on environment.
