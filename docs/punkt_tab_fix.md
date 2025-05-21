# NLTK punkt_tab Resource Fix

## Issue Overview

The application was encountering a specific error with NLTK's tokenization functionality:

```
LookupError: 
**********************************************************************
  Resource punkt_tab not found.
  Please use the NLTK Downloader to obtain the resource:

  >>> import nltk
  >>> nltk.download('punkt_tab')
  
  For more information see: https://www.nltk.org/data.html
```

This error occurred in the `_calculate_term_overlap` method of `app/services/guideline_section_service.py` during tokenization, despite having the `punkt` and `stopwords` resources already installed.

## Root Cause Analysis

While our setup process was correctly installing and verifying the `punkt` tokenizer and `stopwords` corpus, the NLTK library was specifically looking for a language-specific tokenizer resource called `punkt_tab`. 

The error trace shows that when `word_tokenize()` was called, it triggered `sent_tokenize()` internally, which then attempted to access a particular language-specific resource path:
```python
find(f"tokenizers/punkt_tab/{lang}/")
```

Our initial setup and verification was only checking for the main `punkt` resource at `tokenizers/punkt` but not the language-specific `punkt_tab` resource.

## Solution Implementation

We implemented a comprehensive fix with the following changes:

1. **Updated Setup Script**: Modified `scripts/setup_nltk_resources.py` to include the `punkt_tab` resource in the list of required resources to download:
   ```python
   # Define resources needed
   resources = ['punkt', 'stopwords', 'punkt_tab']
   ```

2. **Enhanced Verification**: Updated the verification utility in `app/utils/nltk_verification.py` to also check for the `punkt_tab` resource:
   ```python
   required_resources = {
       'punkt': 'tokenizers/punkt',
       'stopwords': 'corpora/stopwords',
       'punkt_tab': 'tokenizers/punkt_tab/english/'
   }
   ```

3. **Updated Documentation**: Added references to the `punkt_tab` resource in `docs/nltk_setup.md` and `docs/nltk_dependency_fixes.md` to ensure future developers are aware of this requirement.

## Testing Results

The setup script was tested and successfully downloaded the `punkt_tab` resource:

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

The GuidelineSectionService test was successfully executed without the previous error, confirming that the issue has been resolved.

## Key Insights

1. **Complete Resource Verification**: It's important to verify all specific resources that a library might require, not just the main packages.

2. **Language-Specific Resources**: NLTK has both general resources (like `punkt`) and language-specific variants (like `punkt_tab/english/`) that may be required depending on how the library functions are called.

3. **Error Tracing**: Carefully examining error traces helped identify the exact resource path being requested, allowing for a targeted fix.
