# Repository Branch Strategy

This document outlines the branch strategy for the ProEthica repository after implementing the unified environment system.

## Branch Structure

### Main Branches

- **`main`**: The primary branch containing stable, production-ready code.
- **`dev`**: The main development branch where all feature branches are merged before going to `main`. This branch now includes the unified environment detection system.

### Feature Branches

Feature branches should be created for specific features or bug fixes. They should be branched from `dev` and merged back when complete.

Examples of feature branches:
- `feature/new-ui-component`
- `fix/database-connection-issue`

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

## Working with the Unified Environment System

With the unified system, developers should:

1. Use the `dev` branch for development
2. Create feature branches from `dev` for specific tasks
3. Let the system automatically detect their environment
4. Merge completed feature branches back to `dev`

The system will automatically adapt to whatever environment it's running in, eliminating the need to switch branches based on environment.
