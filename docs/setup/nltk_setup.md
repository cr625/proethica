# NLTK Resource Setup Guide

## Overview

The ProEthica application requires certain NLTK (Natural Language Toolkit) resources to function properly. Specifically, the application needs:

- `punkt`: Used for tokenization of text
- `stopwords`: Used for filtering common words from text analysis
- `punkt_tab`: Used for language-specific tokenization features

## Setup Process

1. Run the provided setup script:

```bash
python scripts/setup_nltk_resources.py
```

This script will:
- Check if the required NLTK resources are available
- Download any missing resources
- Verify that the resources were downloaded successfully

## Application Verification

The application has been configured to verify the availability of these resources at startup. If any required resources are missing, the application will fail to start with a clear error message directing you to run the setup script.

This verification happens in `app/__init__.py` during application initialization.

## Manual Download (Alternative Approach)

If the setup script isn't working for some reason, you can manually download the NLTK resources using a Python shell:

```python
import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('punkt_tab')
```

## Troubleshooting

If you encounter issues with NLTK resource downloads:

1. Ensure you have an active internet connection
2. Check that Python has sufficient permissions to write to the NLTK data directory
3. If behind a proxy, configure your proxy settings appropriately
4. Try the manual download approach as described above

## Why This Approach?

The application uses a "fail fast" approach for dependencies rather than attempting to download resources at runtime. This ensures that all required resources are available before the application starts, preventing cryptic failures during operation.
