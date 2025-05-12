# NSPE Case Processing Pipeline

A unified pipeline for scraping, processing, and semantically tagging NSPE engineering ethics cases directly from URLs.

## Overview

This pipeline provides a streamlined approach to:

1. Scrape engineering ethics case content from NSPE website URLs
2. Process and clean the case content
3. Store cases in the database with proper structure
4. Apply semantic tagging using a dual-layer ontology approach:
   - Case level (McLaren extensional elements aligned with BFO)
   - Scenario level (domain-specific predicates from engineering ethics ontology)
5. Generate meaningful semantic relationships without generic RDF type triples
6. Store all data for use in the ProEthica system

## Directory Structure

```
nspe-pipeline/
├── __init__.py                # Pipeline package definition
├── config.py                  # Configuration settings
├── process_nspe_case.py       # Main entry point script
├── scrapers/                  # Web scrapers for retrieving case content
│   ├── __init__.py
│   └── nspe_case_scraper.py   # NSPE website scraper
├── processors/                # Content processors 
│   ├── __init__.py
│   └── case_content_cleaner.py  # Cleans and structures case content
├── taggers/                   # Semantic taggers
│   ├── __init__.py  
│   └── semantic_tagger.py     # Dual-layer ontology tagging
├── utils/                     # Utility modules
│   ├── __init__.py
│   └── database.py            # Database operations
└── tests/                     # Test cases and fixtures
```

## Requirements

- Python 3.6+
- PostgreSQL database
- Required Python packages:
  - requests
  - beautifulsoup4
  - psycopg2
  - rdflib

## Installation

1. Ensure you have all requirements installed
2. Make sure your database is properly configured in `config.py`
3. Make the main script executable:
   ```
   chmod +x process_nspe_case.py
   ```

## Usage

### Processing a single case from URL

```bash
python process_nspe_case.py https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design
```

### Options

- `--keep-existing`: Keep existing triples instead of clearing them before tagging

## Pipeline Workflow

The pipeline follows these steps:

1. **Scrape Case Content**: The `nspe_case_scraper.py` module extracts case content, including title, case number, year, and structured sections.

2. **Clean Content**: The `case_content_cleaner.py` module processes the raw content:
   - Normalizes whitespace and formatting
   - Identifies and structures case sections (Facts, Question, Discussion, Conclusion, etc.)
   - Extracts key elements like description and decision

3. **Store in Database**: The `database.py` module stores the case:
   - Creates or updates the document in the `documents` table
   - Adds structured content to the `documents_content` table
   - Preserves metadata like case number, year, and sections

4. **Apply Semantic Tagging**: The `semantic_tagger.py` module generates semantic triples:
   - Applies McLaren's extensional definition approach at case level
   - Identifies principle instantiations, conflicts, and operationalization techniques
   - Maps ethical elements to BFO ontology classes
   - Generates domain-specific entity relationships with meaningful predicates
   - Creates semantic links between case entities using engineering ethics ontology

5. **Clean RDF Triples**: Removes generic RDF type triples to maintain clean triple display

6. **Store Entity Triples**: Stores the semantic relationships in the `entity_triples` table

## Example Result

After processing, cases will have semantic relationships like:

- `Case X hasRole EngineeringConsultantRole`
- `Case X involvesResource MunicipalWaterSystem`
- `Case X involvesEvent ProcurementProcess`
- `Case X involvesAction OfferingFreeServices`
- `Case X instantiatesPrinciple ProfessionalIntegrity`
- `Case X hasEthicalVerdict UnethicalAction`

These triple relationships can be viewed in the case detail page in the ProEthica system.
