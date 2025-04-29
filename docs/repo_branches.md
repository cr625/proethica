# Repository Branch Strategy

This document outlines the branch strategy for the ProEthica repository after implementing the unified environment system.

## Branch Structure

### Main Branches

- **`main`**: The primary branch containing stable, production-ready code.
- **`dev`**: The main development branch where all feature branches are merged before going to `main`.

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

## Legacy Branches

The following branches were previously used for environment-specific code but are now deprecated:

- **`codespace-environment`**: Previously contained GitHub Codespaces specific configuration
- **`agent-ontology-dev`**: Previously contained WSL-specific development configuration

These branches have been consolidated into the unified environment system. All functionality from these branches has been preserved in the main codebase with automatic environment detection.

## Branch Cleanup

After confirming that all necessary changes have been incorporated into the unified environment system, the deprecated environment-specific branches should be deleted to maintain a clean repository.

Local cleanup:
```bash
git branch -d codespace-environment
```

Remote cleanup (requires appropriate permissions):
```bash
git push origin --delete codespace-environment
```

## Working with the Unified Environment System

With the unified system, developers should:

1. Use the `dev` branch for development
2. Create feature branches from `dev` for specific tasks
3. Let the system automatically detect their environment
4. Merge completed feature branches back to `dev`

The system will automatically adapt to whatever environment it's running in, eliminating the need to switch branches based on environment.
