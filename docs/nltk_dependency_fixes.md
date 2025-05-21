# NLTK Dependency Fixes

## Issue Overview

The application's document processing pipeline was encountering issues when running on a fresh environment because it was trying to automatically download NLTK resources during runtime. Specifically:

1. The application would attempt to download `punkt` tokenizer if not found
2. The application would attempt to download `stopwords` dataset if not found
3. These downloads would sometimes fail, especially in containerized or restricted network environments
4. The application would silently continue with missing resources, leading to failures during document processing

## Solution Implementation

We've implemented a comprehensive solution that uses a "fail fast" approach to dependency management:

1. **Separated Resource Setup**: Created a dedicated script (`scripts/setup_nltk_resources.py`) to download and verify NLTK resources during the setup phase, rather than at runtime.

2. **Resource Verification**: Implemented a verification utility (`app/utils/nltk_verification.py`) that checks for required NLTK resources at application startup.

3. **Early Failure**: Modified the application initialization to verify NLTK resources early and fail with a clear error message if resources are missing.

4. **Documentation**: Added comprehensive documentation (`docs/nltk_setup.md`) explaining the NLTK setup process and troubleshooting steps.

5. **Added punkt_tab Resource**: Updated setup script and verification utility to include the `punkt_tab` resource which is needed for language-specific tokenization features. This fixed the error: `LookupError: Resource punkt_tab not found`.

## Code Changes

### 1. Created setup script: `scripts/setup_nltk_resources.py`
This script downloads and verifies the required NLTK resources in a controlled way.

### 2. Created verification utility: `app/utils/nltk_verification.py`
This utility provides a function to verify that required NLTK resources are available.

### 3. Modified application initialization: `app/__init__.py`
Added code to verify NLTK resources during application startup.

### 4. Updated service code: `app/services/guideline_section_service.py`
Removed automatic NLTK resource downloading from the service code and replaced it with an import from the verification utility.

## Benefits

1. **Improved Reliability**: By separating resource setup from runtime operations, we've made the application more reliable and predictable.

2. **Better Error Handling**: The application now fails fast with clear error messages if resources are missing, rather than failing in unpredictable ways later.

3. **Deployment Simplicity**: The setup script can be easily incorporated into deployment scripts and containerization processes.

4. **Documented Process**: The NLTK setup process is now clearly documented, making it easier for developers to set up the environment correctly.

## Testing Results

The setup script was tested and successfully downloaded both the `punkt` tokenizer and `stopwords` corpus:

```
Setting up NLTK resources...
Checking/downloading NLTK resource: punkt
[nltk_data] Downloading package punkt to /home/chris/nltk_data...
[nltk_data]   Package punkt is already up-to-date!
✓ Successfully set up punkt
Checking/downloading NLTK resource: stopwords
[nltk_data] Downloading package stopwords to /home/chris/nltk_data...
[nltk_data]   Package stopwords is already up-to-date!
✓ Successfully set up stopwords
Checking/downloading NLTK resource: punkt_tab
[nltk_data] Downloading package punkt_tab to /home/chris/nltk_data...
[nltk_data]   Unzipping tokenizers/punkt_tab.zip.
✓ Successfully set up punkt_tab

All NLTK resources successfully installed!
```

The application now correctly checks for these resources at startup, ensuring they are available before the application begins processing documents.
