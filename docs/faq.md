# Frequently Asked Questions

## General Questions

### What is ProEthica?

ProEthica is a professional role-based ethical analysis tool that combines case-based reasoning with ontology-supported validation, orchestrated by large language models (LLMs), to help professional ethics committees analyze ethical scenarios against established standards and precedents.

### What domains does ProEthica support?

The current implementation processes engineering ethics cases from the National Society of Professional Engineers (NSPE) Board of Ethical Review. The framework supports extension to other professional domains with established codes and precedent systems, including medical and legal ethics.

### What is the Nine-Concept Framework?

ProEthica uses a formal framework D = (R, P, O, S, Rs, A, E, Ca, Cs) consisting of:

- **R**oles - Professional positions
- **P**rinciples - Abstract ethical standards
- **O**bligations - Concrete duties
- **S**tates - Situational context
- **R**esources - Available knowledge
- **A**ctions - Professional behaviors
- **E**vents - Precipitating occurrences
- **Ca**pabilities - Permissions
- **Cs**onstraints - Prohibitions

See [Nine-Concept Framework](concepts/nine-concepts.md) for details.

### What are the three phases?

1. **Phase 1 (Extraction)**: Multi-pass extraction of 9 concepts
2. **Phase 2 (Analysis)**: Case synthesis, rule analysis, transformation classification
3. **Phase 3 (Scenario)**: Interactive visualization with timeline and participants

## Installation

### What are the system requirements?

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Redis (for pipeline automation)
- 8GB+ RAM recommended
- API key for Claude (Anthropic)

### Why do I need OntServe?

OntServe provides ontology management and validation. It serves concept definitions that constrain LLM output to match formal specifications, ensuring consistency across extraction.

### Can I run without OntServe?

Yes, but with limited functionality. The "Available Classes" section will be empty, and entities won't validate against the ontology. Extraction still works, storing entities locally.

### How do I install pgvector?

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Required for semantic similarity matching in precedent discovery.

## Extraction

### How long does extraction take?

Typical extraction times per pass:

| Pass | Time | Notes |
|------|------|-------|
| Pass 1 | 30-60 seconds | Roles, States, Resources |
| Pass 2 | 60-90 seconds | Principles, Obligations, etc. |
| Pass 3 | 30-60 seconds | Events, Actions |

Times vary with case length and LLM response time.

### What if extraction fails?

Common solutions:

1. Check LLM API key is valid and has credits
2. Verify OntServe MCP is running
3. Use "Clear and Re-run" to restart
4. Check network connectivity

### Can I edit extracted entities?

Yes. During Entity Review you can:

- Edit labels and definitions
- Change class assignments
- Delete irrelevant entities
- Approve new ontology classes

### What happens when I commit entities?

Entities are saved to `temporary_rdf_storage` linked by `extraction_session_id`. They remain in temporary storage until explicitly pushed to the OntServe ontology.

## Analysis

### What is transformation classification?

Phase 2 classifies how ethical situations evolve using four patterns:

- **Transfer**: Clear state change (A → B)
- **Stalemate**: Competing forces deadlock (A ↔ B)
- **Oscillation**: Cyclic alternation (A → B → A)
- **Phase Lag**: Delayed response (A ... → B)

### How are conflicts identified?

The system identifies:

- **Principle tensions**: Abstract conflicts (efficiency vs. competence)
- **Obligation conflicts**: Concrete duty conflicts (timely delivery vs. verification)

These are detected through LLM analysis of extracted obligations and case context.

### Can I modify analysis results?

Yes. All analysis results can be edited:

- Tension characterizations
- Action mappings
- Transformation classification

Changes are saved when you commit the analysis.

## Scenarios

### What does Phase 3 generate?

Phase 3 creates an interactive scenario including:

- Timeline with decision points
- Participant profiles with LLM enhancement
- Relationship networks
- Causal chain visualization
- Links to code provisions

### How are participants enhanced?

The LLM generates:

- 2-3 sentence analytical profiles
- Ethically-relevant background details
- Additional motivations illuminating tensions
- Analytical notes on key principles and conflicts

## Precedent Discovery

### How does similarity matching work?

Cases are compared using 384-dimensional embeddings generated from:

- Facts section text
- Discussion section text

Cosine similarity measures how semantically similar cases are.

### Why are my similarity scores zero?

Embeddings may need syncing. Check:

1. Generate embeddings in Structure page
2. Verify `case_precedent_features` table has embeddings
3. Re-sync if needed

### What similarity score is significant?

| Score | Interpretation |
|-------|----------------|
| 0.8+ | Very similar cases |
| 0.5-0.8 | Moderately similar |
| < 0.5 | Limited similarity |

## Pipeline Automation

### What is Celery used for?

Celery handles background task processing for:

- Batch extraction across multiple cases
- Long-running LLM operations
- Queue management for bulk processing

### Do I need Celery?

No. Celery is optional for pipeline automation. You can perform extraction manually through the web interface without Celery.

### How do I monitor pipeline progress?

The Pipeline Dashboard (`/pipeline/dashboard`) shows:

- Service status
- Active pipeline runs
- Queue depth
- Progress for each case

## LLM Configuration

### Which LLM models are supported?

Primary: Claude (Anthropic)
- claude-sonnet-4-* (default extraction)
- claude-opus-4-* (complex analysis)

Fallback: OpenAI, Google Gemini (optional)

### How do I change the model?

Edit environment variables:

```bash
CLAUDE_DEFAULT_MODEL=claude-sonnet-4-20250514
```

Or configure via Admin interface.

### What about API costs?

Typical costs per case:

| Phase | Approximate Tokens | Cost* |
|-------|-------------------|-------|
| Phase 1 | 10,000-20,000 | $0.03-0.06 |
| Phase 2 | 5,000-10,000 | $0.02-0.03 |
| Phase 3 | 5,000-10,000 | $0.02-0.03 |

*Estimates based on Claude Sonnet pricing

## Troubleshooting

### OntServe connection failed

1. Verify OntServe MCP is running on port 8082
2. Check URL in `.env` matches actual server
3. Test with curl:
   ```bash
   curl -X POST http://localhost:8082 \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","id":1}'
   ```

### Database connection failed

1. Verify PostgreSQL is running
2. Check credentials in `.env`
3. Test connection:
   ```bash
   PGPASSWORD=PASS psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT 1"
   ```

### LLM API errors

1. Check API key is valid
2. Verify account has credits
3. Check rate limits
4. Review error message for specifics

### Pipeline step locked

Steps require prerequisites:

1. Step 1b requires Step 1 complete
2. Step 2 requires Step 1b complete
3. And so on...

Complete prior steps to unlock.

## Data Management

### How do I backup data?

```bash
pg_dump -h localhost -U postgres ai_ethical_dm > backup.sql
```

Or use provided scripts:
```bash
./scripts/backup_demo_database.sh
```

### How do I clear a case for re-extraction?

```bash
python scripts/clear_case_extractions.py <case_id>
```

Add `--include-runs` to also clear pipeline run records.

### How do I remove orphaned entities?

```bash
python scripts/cleanup_orphaned_entities.py --delete
```

Run without `--delete` first to preview what will be removed.

## Getting Help

### Where can I report issues?

- GitHub Issues: https://github.com/cr625/proethica/issues
- Demo site: https://proethica.org

### Where is the academic paper?

Rauch, C. B., & Weber, R. O. (2026). ProEthica: A Professional Role-Based Ethical Analysis Tool Using LLM-Orchestrated, Ontology Supported Case-Based Reasoning. *AAAI Conference on Artificial Intelligence*. Singapore.

### How do I cite ProEthica?

```bibtex
@inproceedings{rauch2026proethica,
  title={ProEthica: A Professional Role-Based Ethical Analysis Tool Using LLM-Orchestrated, Ontology Supported Case-Based Reasoning},
  author={Rauch, Christopher B. and Weber, Rosina O.},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence},
  year={2026},
  organization={AAAI Press}
}
```
