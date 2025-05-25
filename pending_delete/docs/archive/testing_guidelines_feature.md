# Testing Guidelines Feature

This document provides instructions for testing the new guidelines feature that integrates with the ontology system.

## Prerequisites

- ProEthica server running with updated code
- PostgreSQL database with required tables (run the migration script first)
- Valid API keys for LLM services in `.env` file

## Setup Steps

1. First, apply the database migration to create the necessary tables:

```bash
python scripts/database_migrations/create_guidelines_tables.py
```

2. Start the ProEthica server:

```bash
./start_proethica_updated.sh
```

3. Access the application at http://localhost:3333

## Test Workflow

### 1. Access Engineering World

1. Navigate to http://localhost:3333/worlds
2. Click on the "Engineering World" (or any other available world)

### 2. Add a Guideline Document

There are three ways to add guidelines:

#### Option A: Upload a File

1. Click on "Guidelines" in the world detail page
2. Click "Add New Guideline"
3. In the form, enter a title (e.g., "NSPE Code of Ethics")
4. Select a PDF file to upload (e.g., use `data/23-4-Acknowledging-Errors-in-Design.pdf` or any ethics guideline document)
5. Click "Upload Guideline"

#### Option B: Provide a URL

1. Click on "Guidelines" in the world detail page
2. Click "Add New Guideline"
3. Switch to the "From URL" tab
4. Enter a title (e.g., "IEEE Code of Ethics")
5. Enter a URL (e.g., "https://www.ieee.org/about/corporate/governance/p7-8.html")
6. Click "Import from URL"

#### Option C: Manual Entry

1. Click on "Guidelines" in the world detail page
2. Click "Add New Guideline"
3. Switch to the "Manual Entry" tab
4. Enter a title (e.g., "Sample Ethical Guidelines")
5. Enter text content in the content field. You can use the following sample:

```
ETHICAL GUIDELINES FOR ENGINEERING PRACTICE

1. PRINCIPLE: SAFETY PARAMOUNT
Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.

2. PRINCIPLE: COMPETENCE
Engineers shall perform services only in areas of their competence.

3. PRINCIPLE: TRUTHFULNESS
Engineers shall issue public statements only in an objective and truthful manner.

4. PRINCIPLE: CONFIDENTIALITY
Engineers shall act in professional matters for each employer or client as faithful agents or trustees, and shall avoid conflicts of interest.

5. PRINCIPLE: PROFESSIONAL DEVELOPMENT
Engineers shall continue their professional development throughout their careers and shall provide opportunities for the professional development of those engineers under their supervision.

6. OBLIGATION: ERROR DISCLOSURE
Engineers shall disclose any errors or omissions in their work that could potentially impact safety, functionality, or project outcomes.

7. OBLIGATION: WHISTLEBLOWING
Engineers shall notify proper authorities when professional judgment is overruled under circumstances endangering life or property.

8. VALUE: SUSTAINABILITY
Engineers shall strive to adhere to principles of sustainable development to protect the environment for future generations.

9. VALUE: INCLUSIVITY
Engineers shall treat all persons fairly regardless of race, religion, gender, disability, age, or national origin.
```

6. Click "Save Guideline"

### 3. View Guideline

1. After adding a guideline, you'll be redirected to the guidelines listing page
2. Click on "View" for the guideline you just added
3. Verify the content appears correctly formatted

### 4. Analyze Guideline for Concepts

1. From the guideline view page, click "Analyze Concepts" 
2. Wait for the analysis to complete (this may take 15-30 seconds depending on the LLM service)
3. You should see a list of extracted concepts with:
   - Concept name
   - Type (principle, obligation, value, concept, consideration)
   - Description
   - Ontology match information (if any existing ontology entity matches)

### 5. Review and Select Concepts

1. On the concepts review page, all concepts are pre-selected by default
2. You can uncheck any concepts you don't want to include
3. Use the "Select All" and "Deselect All" buttons to quickly manage selections
4. Click "Save Selected Concepts" to create RDF triples

### 6. View Generated Triples

1. After saving the concepts, you'll be redirected back to the guidelines page
2. Click "View" on your guideline
3. Scroll down to the "RDF Knowledge" section 
4. Click "Show/Hide Triples" to view the generated triples
5. Verify that triples were created for each selected concept

## Testing Edge Cases

### Large Documents

- Try uploading a large ethics document (>20 pages) to test how the system handles longer content
- Verify that concept extraction still works properly

### Malformed Content

- Try adding a guideline with poorly formatted or non-ethical content
- Verify that the system attempts to extract relevant concepts or provides appropriate feedback

### Concept Matching

- If you have access to the engineering-ethics ontology data, try adding a guideline that contains terms exactly matching ontology entities
- Verify that the system correctly identifies these as exact matches with high confidence

## Troubleshooting

### LLM Connection Issues

If concept extraction fails, check:
1. LLM API keys in the `.env` file
2. Network connectivity to the LLM service
3. Logs for any error messages

### Database Issues

If triples aren't saving properly:
1. Verify the migration ran successfully
2. Check database connectivity
3. Look for error messages in the console output

### Content Processing Issues

If guideline content doesn't appear correctly:
1. Check the content type and formatting
2. Verify the file was uploaded successfully
3. For URLs, ensure the URL is accessible and contains actual text content
