# ProEthica Startup Optimization Plan

This document outlines specific implementation steps to address the redundancies identified in the ProEthica startup process. The goal is to eliminate duplicate operations that are currently performed by both `start_proethica_updated.sh` and `auto_run.sh`.

## Current Redundancies Summary

1. PostgreSQL setup is performed twice
2. PGVector extension installation is attempted twice
3. Environment variables and .env file are updated redundantly
4. Environment detection logic is duplicated
5. Database connection verification is repeated

## Implementation Plan

### 1. Create a Shared Configuration Script

Create a new script `scripts/shared_environment_setup.sh` to consolidate common functions:

```bash
#!/bin/bash
#
# Shared environment setup and configuration for ProEthica scripts

# Initialize env variables
export PROETHICA_SETUP_STATE_FILE=".proethica_setup_state"

# Function to detect and initialize environment
function detect_environment() {
    if [ "$CODESPACES" == "true" ]; then
        echo "codespace"
        export POSTGRES_CONTAINER="postgres17-pgvector-codespace"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
        export POSTGRES_CONTAINER="postgres17-pgvector-wsl"
    else
        echo "development"
        export POSTGRES_CONTAINER="postgres17-pgvector"
    fi
}

# Function to save setup state
function save_setup_state() {
    local key=$1
    local value=$2
    echo "${key}=${value}" >> $PROETHICA_SETUP_STATE_FILE
}

# Function to check setup state
function check_setup_state() {
    local key=$1
    if [ -f "$PROETHICA_SETUP_STATE_FILE" ]; then
        grep -q "^${key}=true$" $PROETHICA_SETUP_STATE_FILE
        return $?
    else
        return 1
    fi
}

# Initialize setup state file if requested
function init_setup_state() {
    if [ -f "$PROETHICA_SETUP_STATE_FILE" ]; then
        rm $PROETHICA_SETUP_STATE_FILE
    fi
    touch $PROETHICA_SETUP_STATE_FILE
}
```

### 2. Modify `start_proethica_updated.sh`

Update the script to use the shared environment setup and track completed operations:

```bash
# Near the start of the script
source ./scripts/shared_environment_setup.sh
init_setup_state  # Start with fresh state tracking

# After environment detection
ENV=$(detect_environment)
echo -e "${BLUE}Using environment: ${ENV} with container: ${POSTGRES_CONTAINER}${NC}"
save_setup_state "ENVIRONMENT_DETECTED" "true"
save_setup_state "ENVIRONMENT_TYPE" "$ENV"
save_setup_state "POSTGRES_CONTAINER" "$POSTGRES_CONTAINER"

# After PostgreSQL setup
./scripts/setup_codespace_db.sh
save_setup_state "POSTGRES_CONFIGURED" "true"

# After .env file is updated with correct settings
save_setup_state "ENV_FILE_UPDATED" "true"

# Before launching auto_run.sh
# Pass information via environment variables
export POSTGRES_ALREADY_CONFIGURED=true
export ENV_FILE_ALREADY_UPDATED=true
```

### 3. Modify `auto_run.sh`

Update the script to check for previous setup operations:

```bash
# Near the start of the script
source ./scripts/shared_environment_setup.sh

# Replace environment detection with
if check_setup_state "ENVIRONMENT_DETECTED"; then
    # Use already detected environment
    ENV=$(grep "^ENVIRONMENT_TYPE=" $PROETHICA_SETUP_STATE_FILE | cut -d= -f2)
    POSTGRES_CONTAINER=$(grep "^POSTGRES_CONTAINER=" $PROETHICA_SETUP_STATE_FILE | cut -d= -f2)
    echo "Using previously detected environment: $ENV"
else
    # Do environment detection as before
    ENV=$(detect_environment)
    echo "Detecting environment: $ENV"
fi

# Before PostgreSQL setup
if [ "$POSTGRES_ALREADY_CONFIGURED" == "true" ] || check_setup_state "POSTGRES_CONFIGURED"; then
    echo "PostgreSQL already configured, skipping setup..."
else
    # Do PostgreSQL setup as before
    ./scripts/setup_codespace_db.sh
fi

# Before .env file updates
if [ "$ENV_FILE_ALREADY_UPDATED" == "true" ] || check_setup_state "ENV_FILE_UPDATED"; then
    echo "Environment file already updated, skipping..."
else
    # Update .env file as before
fi
```

### 4. Implement a More Robust Flag System

Extend the existing `MCP_SERVER_ALREADY_RUNNING` approach to other components:

```bash
# Add these to start_proethica_updated.sh before calling auto_run.sh
export POSTGRES_ALREADY_CONFIGURED=true
export ENV_FILE_ALREADY_UPDATED=true
export SCHEMA_ALREADY_VERIFIED=true
export PGVECTOR_ALREADY_INITIALIZED=true
```

Then in `auto_run.sh`, check these flags:

```bash
# PostgreSQL setup section
if [ "$POSTGRES_ALREADY_CONFIGURED" == "true" ]; then
    echo "PostgreSQL already configured. Skipping setup."
else
    # Regular PostgreSQL setup
fi

# pgvector initialization section
if [ "$PGVECTOR_ALREADY_INITIALIZED" == "true" ]; then
    echo "pgvector extension already initialized. Skipping."
else
    # Regular pgvector initialization
fi
```

## Expected Outcome

Implementing these changes will yield several benefits:

1. **Reduced Startup Time**: Eliminating redundant operations could save 10-20 seconds
2. **Cleaner Logs**: Less repetitive output makes logs easier to read and analyze
3. **More Reliable Startup**: Reduced chance of race conditions or conflicting settings
4. **Better Resource Utilization**: Less CPU and memory usage during startup

## Testing Strategy

1. Add logging before and after each major step to measure execution time
2. Run comparative tests with and without the optimizations
3. Verify that all components start correctly and maintain proper state
4. Test in all environments (Codespace, WSL, development)

## Implementation Priority

1. Shared environment setup script
2. Flag system for skipping redundant operations
3. State tracking for completed tasks
4. Sequential modifications to start_proethica_updated.sh and auto_run.sh
