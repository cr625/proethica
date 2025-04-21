# Claude API Configuration Guide

This document provides information about Claude API configuration in the ProEthica application.

## API Key Configuration

1. The Claude API key should be set in the `.env` file as:
   ```
   ANTHROPIC_API_KEY=your-key-here
   ```

2. When using the API key in Python scripts, you need to ensure it's properly exported to the environment. Python's `load_dotenv()` alone is not sufficient for the Anthropic SDK.

## Recommended Usage

### Option 1: Using the run_with_env.sh Utility
```bash
./scripts/run_with_env.sh python your_script.py
```
This utility properly exports all environment variables from the .env file, ensuring the API key is accessible.

### Option 2: Using auto_run.sh for the Application
```bash
./auto_run.sh
```
This script handles all environment configuration and starts the application correctly.

### Option 3: Direct Environment Variable Export
```bash
export $(grep -v '^#' .env | xargs) && python your_script.py
```
This manually exports all variables from .env before running your script.

### Option 4: Setting the Key in Code
```python
import os
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
```
This sets the key directly in the Python environment.

## Troubleshooting

If you encounter "invalid x-api-key" errors:
1. Verify your API key is valid and not expired
2. Ensure the key is properly exported to the environment
3. Check that you're using the Anthropic SDK correctly
4. Consider using the `run_with_env.sh` utility

If API access is unavailable, the application can run with mock responses if `USE_MOCK_FALLBACK=true` is set in the .env file.

## Testing Scripts

Several scripts are available to test Claude API connectivity:
- `scripts/check_claude_api.py`: Basic API connectivity check
- `scripts/debug_anthropic.py`: Detailed API diagnostics
- `scripts/simple_claude_test.py`: Minimal test with direct key setting
- `scripts/test_anthropic_auth.py`: Tests different authentication methods
