# Repository Branch Management Guide

This document explains how to manage branches in the ProEthica project, including how to handle the directly cloned repositories in the project structure.

## Project Repository Structure

The ProEthica project uses directly cloned repositories rather than Git submodules:

1. **app/agent_module/**: Agent module system (directly cloned repository)
2. **app/yamz_o/**: Another directly cloned repository component

These repositories are maintained as separate codebases but are incorporated directly into the project structure.

## Creating a New Branch

When you create a new branch, you'll need to consider these cloned repositories:

```bash
# Create and switch to a new branch in the main repository
git checkout -b new-feature-branch
```

### What Happens to Cloned Repositories?

Since these repositories are directly cloned and not linked as Git submodules:

1. The cloned repositories' files are tracked by the main repository **as regular files**
2. Any changes to these files will be included in the main repository's commits
3. These repositories maintain their internal Git history separate from the main repository

## Branch Creation and Repository Management

When creating a new branch, **you do not need to re-clone** the repositories. The files are already present in your working directory and will be tracked by Git just like any other files.

```bash
# Create new branch
git checkout -b feature-branch

# The cloned repositories will remain unchanged in your working directory
```

## Making Changes in Cloned Repositories

When you make changes within these repositories, you have two options:

### 1. Treat as Regular Files in Main Repository

```bash
# Make changes in app/agent_module/
# Then commit those changes in the main repository
git add app/agent_module/changed_file.py
git commit -m "Updated agent module file"
```

### 2. Manage the Repository's Internal Version Control

```bash
# Navigate to the repository directory
cd app/agent_module/

# Use git commands here to manage this repo separately
git checkout -b agent-feature
git add .
git commit -m "Made changes in agent module"
git push origin agent-feature

# Return to main project
cd ../..
```

## Best Practices for Branch Management

1. **Document Repository States**: When creating important branches, document which version of each cloned repository is being used.

2. **Coordinate Changes**: If making significant changes to cloned repositories, coordinate with other developers to ensure compatibility.

3. **Release Management**: For releases, record the exact commit hash of each cloned repository to enable reproducing the exact configuration.

4. **Consider Using Script**: For complex setups, use a script to ensure cloned repositories are in the correct state:

```bash
#!/bin/bash
# Example script to ensure repositories are in correct state

# Main repo branch
git checkout specific-branch

# Agent module state
cd app/agent_module/
git checkout specific-agent-branch
cd ../..

# Other repos...
```

## Troubleshooting

### Repository State Issues

If you're experiencing issues with the state of a cloned repository:

```bash
# Check the repository's status
cd app/agent_module/
git status

# Reset to a known good state if needed
git checkout main
git pull
```

### Working with Multiple Branches

When working with multiple branches that depend on different versions of the cloned repositories, you may need to manually update the cloned repositories when switching branches:

```bash
# After switching branches
git checkout another-feature-branch

# Update cloned repositories as needed
cd app/agent_module/
git checkout required-agent-branch
cd ../..
```

This direct cloning approach gives you more flexibility but requires more manual management than using Git submodules.
