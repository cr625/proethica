# Git Workflow Guide

This guide outlines the recommended workflow for managing development, testing, and deployment in the ProEthica project. It explains how to use multiple branches effectively and deploy changes to production.

## Overview

The workflow is based on a standard GitHub Flow with some customizations:

1. **Development Branch** (`dev`): All active development happens here
2. **Main Branch** (`main`): Stable code that is ready for production 
3. **Production Server**: Running code deployed from the `main` branch

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│             │    │             │    │             │
│  Dev Branch │ → │ Main Branch │ → │ Production  │
│             │    │             │    │   Server    │
└─────────────┘    └─────────────┘    └─────────────┘
  (Development)       (Stable)         (Deployed)
```

## Workflow Tools

We've created several tools to assist with this workflow:

- **`scripts/git_workflow.sh`**: Manages the full Git workflow
- **`scripts/direct_sync.sh`**: Deploys code to production
- **`scripts/sync_from_production.sh`**: Syncs production changes back to development

## Recommended Workflow

### 1. Development Phase

```bash
# Switch to (or create) the dev branch
git checkout dev   # or ./scripts/git_workflow.sh (option 2)

# Make your changes...
# ...

# Commit your changes
git add .
git commit -m "Your descriptive commit message"

# Push to GitHub (optional but recommended)
git push origin dev
```

### 2. Merge to Main

Once your changes are ready to go to production:

```bash
# Using the workflow script (recommended)
./scripts/git_workflow.sh   # Select option 4 to merge dev into main

# Or manually:
git checkout main
git merge dev
git push origin main
```

### 3. Deploy to Production

After merging to main, deploy the changes:

```bash
# Using the workflow script (recommended)
./scripts/git_workflow.sh   # Select option 5 to deploy main to production

# Or directly:
./scripts/direct_sync.sh
```

### 4. Full Workflow in One Step

For convenience, you can do the entire workflow in one step:

```bash
./scripts/git_workflow.sh   # Select option 6 for the full workflow
```

## Handling Production Changes

Sometimes changes might be made directly on the production server. To bring those changes back to your development environment:

```bash
# Sync from production
./scripts/sync_from_production.sh

# Review changes
git status
git diff

# Commit changes if appropriate
git add .
git commit -m "Sync changes from production"
```

## Setting Up a Dev Branch

If you don't already have a dev branch:

```bash
# Create a dev branch from main
git checkout main
git checkout -b dev

# Or use the workflow script
./scripts/git_workflow.sh   # Select option 2 to switch to dev branch
```

## Handling Merge Conflicts

If you encounter merge conflicts:

1. The merge operation will show which files have conflicts
2. Edit those files to resolve conflicts (look for `<<<<<<<`, `=======`, and `>>>>>>>` markers)
3. Add the resolved files: `git add <filename>`
4. Complete the merge: `git commit`

## Continuous Integration

For a more automated approach, consider:

1. **GitHub Actions**: Set up workflows in `.github/workflows/` to automatically:
   - Run tests when changes are pushed to dev or main
   - Deploy to production when changes are pushed to main

2. **Deployment Hooks**: Configure the production server to pull changes automatically:
   ```bash
   # On the server (in a cron job):
   cd /home/chris/proethica && git pull origin main
   ```

## Troubleshooting

- If you encounter Git conflicts on the server, use:
  ```bash
  ./scripts/resolve_git_conflicts.sh
  ```

- If Git authentication fails during deployment, use direct sync:
  ```bash
  ./scripts/direct_sync.sh
  ```

- For Git authentication setup, use:
  ```bash
  ./scripts/setup_git_auth.sh
  ```
