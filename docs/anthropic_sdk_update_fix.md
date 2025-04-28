# Anthropic SDK Update Fix

## Overview

This document describes the fixes implemented for the Anthropic SDK authentication issues that occurred after updating the SDK.

## Problem Description

After updating the Anthropic SDK, the application was encountering authentication errors (specifically "invalid x-api-key" errors) when trying to access the agent page at http://localhost:3333/agent/.

## Root Causes

1. **Authentication Method Change**: The Anthropic SDK updated from using the `x-api-key` header to using an `Authorization: Bearer {api_key}` header.
   
2. **Environment Variable Handling**: The `load_dotenv()` function alone was not sufficient for properly setting the environment variables needed by the SDK.

3. **USE_MOCK_FALLBACK Overrides**: The startup scripts (`start_proethica.sh` and `auto_run.sh`) were automatically setting `USE_MOCK_FALLBACK=true` in the .env file, overriding any manual changes.

4. **Submodule Management**: The app/agent_module directory was not properly set up as a git submodule, causing git conflicts.

## Implemented Fixes

### 1. API Authentication Fixes

- Updated the environment variables in .env to use a valid API key
- Set `USE_MOCK_FALLBACK=false` to ensure real API responses
- Fixed all scripts to preserve the `USE_MOCK_FALLBACK` setting in .env instead of overriding it

### 2. Environment Variable Handling

- Modified `start_proethica.sh` and `auto_run.sh` to use `run_with_env.sh`
- Ensured proper environment variable loading for the Anthropic SDK
- Added verification scripts to test proper environment variable handling

### 3. Git Submodule Configuration

- Properly set up app/agent_module as a git submodule
- Created a .gitmodules file pointing to the correct repository
- Created a dedicated `proethica-integration` branch for ProEthica-specific modifications
- Added documentation and customization to make the branch purpose clear

## Test Scripts

Several test scripts were created to verify the API authentication:

1. **verify_anthropic_fix.py**: Verifies that the Anthropic API authentication is working properly
2. **test_claude_with_env.py**: Tests the Claude API with proper environment variable handling
3. **try_anthropic_bearer.py**: Tests different authentication methods
4. **git_protect_keys.sh**: Protects API keys from git commits

## How to Run the Application

Use the standard startup script:

```bash
./start_proethica.sh
```

This will:
1. Keep your `USE_MOCK_FALLBACK=false` setting in .env
2. Properly load environment variables with run_with_env.sh
3. Connect to the real Claude API instead of using mock responses

If you want to manually test the API authentication:

```bash
./scripts/run_with_env.sh python scripts/verify_anthropic_fix.py
```

## Troubleshooting

If you encounter any issues with the Claude API:

1. Check that `USE_MOCK_FALLBACK=false` in your .env file
2. Verify that your API key is valid with `./scripts/run_with_env.sh python scripts/verify_anthropic_fix.py`
3. Ensure you're running the application with `./start_proethica.sh` or `./scripts/run_with_env.sh`
4. Check that you have the correct app/agent_module branch (should be `proethica-integration`)
