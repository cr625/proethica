# NSPE Engineering Ethics Case Import Guide

This guide explains how to properly import NSPE engineering ethics cases into the ProEthica system.

## Importing Process

The system provides several scripts to handle the import process:

1. `improved_fetch_nspe_cases.py` - Fetches and parses case content from NSPE URLs
2. `update_engineering_ontology.py` - Updates the engineering ethics ontology with new concepts
3. `create_nspe_ethics_cases.py` - Converts cases to RDF triples for semantic representation
4. `import_nspe_cases_to_world.py` - Imports the cases to an engineering world
5. `cleanup_header_links_cases.py` - Cleanup tool to remove incorrectly imported cases
6. `reimport_nspe_cases.py` - Master script that runs all steps in sequence

## Quick Start

To import NSPE cases in one step:

```bash
python reimport_nspe_cases.py
```

This will handle the entire process from cleanup to import.

## Important Notes

1. **Source URLs** - The system preserves the exact URLs provided in the input list. This is critical since these URLs serve as unique identifiers for the cases and are used throughout the system.

2. **Fallback Content** - If a URL is unreachable or doesn't contain proper content, the system will generate fallback content based on the URL path.

3. **Case Titles** - The system extracts meaningful titles from the case content, falling back to URL-based titles if needed.

4. **Case Numbers** - NSPE case numbers (e.g., "Case 98-5") are extracted from the content where available.

## Troubleshooting Common Issues

### "Pre Header Utility Links" Cases

These incorrectly imported cases occur when the content extraction fails to find the main article content and instead captures navigation elements. They can be fixed by:

1. Running the cleanup script: `python cleanup_header_links_cases.py`
2. Using the improved scraper for imports: `python improved_fetch_nspe_cases.py`

### Missing Case Content

If case content is missing or incomplete:

1. Check that the URL is accessible
2. Verify that the site structure hasn't changed
3. Run the improved scraper with a longer delay: `python improved_fetch_nspe_cases.py --delay 2`

## Adding New Cases

To add new NSPE case URLs:

1. Edit `improved_fetch_nspe_cases.py` and add the URLs to the `NSPE_CASE_URLS` list
2. Add corresponding fallback titles to the `FALLBACK_TITLES` dictionary if needed
3. Run the full import process: `python reimport_nspe_cases.py`

## Keeping the Original Source URLs

It's essential to maintain the exact source URLs as provided in the original input. The improved scripts now ensure that:

1. The original URL is stored at the case/document level
2. The URL is preserved throughout the import pipeline
3. Entity triples and RDF representations maintain the original source URL

This prevents URL normalization issues where different URL forms (with/without trailing slashes, etc.) might be treated as different cases.
