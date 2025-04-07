# URL Processor for Case Import

The URL Processor module provides functionality for importing engineering ethics cases from URLs, automatically extracting metadata, content, and generating RDF triples.

## Overview

The Case URL Processor is a modular system designed to:

1. Validate and process URLs to engineering ethics case studies
2. Extract and clean content from web pages
3. Detect and extract metadata such as case numbers, dates, and ethical principles
4. Use LLM-based extraction for more complex metadata
5. Generate RDF triples from extracted data
6. Support caching and user corrections

## Architecture

The processor is composed of several components:

![URL Processor Architecture](../app/static/img/diagrams/url_processor_architecture.png)

- **URL Validator**: Validates URL format and checks reachability
- **Content Extractor**: Extracts and cleans HTML content
- **Pattern Matchers**: Extracts metadata using regex patterns (e.g., NSPE pattern matcher)
- **LLM Extractor**: Uses Claude to extract structured data
- **Triple Generator**: Converts extracted data to RDF triples
- **Caching**: Stores processed URL results to avoid redundant processing
- **Correction Handler**: Manages user corrections to automatically processed content

## Usage

### Basic Usage

```python
from app.services.case_url_processor import CaseUrlProcessor

# Create processor instance
processor = CaseUrlProcessor()

# Process a URL
result = processor.process_url(
    url="https://www.nspe.org/resources/ethics/ethics-resources/board-of-ethical-review-cases/competitive-bidding-vs-quality",
    world_id=1,  # Engineering ethics world ID
    user_id=current_user.id  # Optional
)

# Result contains metadata, content, and triples
print(f"Title: {result.get('title')}")
print(f"Triples: {len(result.get('triples', []))} generated")
```

### Applying Corrections

```python
# Apply corrections to processed result
corrections = {
    'metadata': {
        'title': 'Corrected Title',
        'year': '2023'
    },
    'triples': [
        # Updated triples
    ]
}

corrected_result = processor.apply_correction(
    url="https://example.com/case",
    corrections=corrections,
    user_id=current_user.id
)
```

## Components

### URL Validator

The URL validator checks if a URL is properly formatted and reachable. It also has special handling for known engineering ethics domains like NSPE.

```python
from app.services.case_url_processor.url_validator import UrlValidator

validator = UrlValidator()
is_valid = validator.validate("https://www.nspe.org/resources/ethics/case/93-1")
```

### Content Extractor

Extracts and cleans HTML content from URLs, focusing on the main content and removing navigation, ads, and other irrelevant sections.

```python
from app.services.case_url_processor.content_extractor import ContentExtractor

extractor = ContentExtractor()
html_content = extractor.extract_html(url)
cleaned_content = extractor.clean_content(html_content)
```

### Pattern Matchers

Pattern matchers use regex and heuristics to extract structured data from case content. The NSPE pattern matcher is specialized for NSPE ethics cases.

```python
from app.services.case_url_processor.patterns.nspe_patterns import NSPEPatternMatcher

matcher = NSPEPatternMatcher()
metadata = matcher.extract_metadata(content, html_content, url)
```

### LLM Extractor

Uses Claude to extract structured data from case content. This is especially useful for complex metadata that can't be easily extracted with regex.

```python
from app.services.case_url_processor.llm_extractor import LlmExtractor

extractor = LlmExtractor()
structured_data = extractor.extract_case_data(content, pattern_metadata)
```

### Triple Generator

Converts extracted data to RDF triples that can be stored in the database.

```python
from app.services.case_url_processor.triple_generator import TripleGenerator

generator = TripleGenerator()
triples = generator.generate_triples(case_data, world_id)
```

## Customization

### Adding New Pattern Matchers

To add support for new sources of engineering ethics cases:

1. Create a new pattern matcher class in `app/services/case_url_processor/patterns/`
2. Add pattern configuration in `pattern_config.json` or create a new config file
3. Update the `CaseUrlProcessor` to use the new pattern matcher for appropriate URLs

### LLM Prompt Customization

The LLM extractor uses a set of prompt templates that can be customized in `llm_extractor.py` to improve extraction for specific types of cases.

## Error Handling

The URL processor has comprehensive error handling for:

- Invalid or unreachable URLs
- Content extraction failures
- Pattern matching issues
- LLM extraction errors
- Triple generation problems

Errors are logged and returned in the result dictionary with a `status` field set to `error`.

## Performance Considerations

- **Caching**: Processed URLs are cached to avoid redundant processing
- **LLM Usage**: LLM extraction is only used when needed to minimize API usage
- **Validation**: URLs are validated before processing to avoid unnecessary work
