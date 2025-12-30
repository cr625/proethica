# ProEthica Documentation Agent

Help create, update, and maintain the MkDocs documentation for ProEthica.

## Quick Reference

| Item | Location |
|------|----------|
| Documentation | `docs/` |
| Build output | `site/` |
| Screenshots | `docs/assets/images/screenshots/` |
| MkDocs config | `mkdocs.yml` |
| Style guide | `docs-internal/STYLE.md` |

## Commands

```bash
# Build documentation
/home/chris/onto/proethica/venv-proethica/bin/mkdocs build

# Serve locally (preview)
/home/chris/onto/proethica/venv-proethica/bin/mkdocs serve
```

## Navigation Structure (Dec 2025)

| Menu | Type | Contents |
|------|------|----------|
| Home | Link | Home page |
| [Domain] | Dropdown | Current domain, Manage Domains, Create New |
| Cases | Link | Case repository |
| Precedents | Dropdown | Find Precedents, Similarity Network |
| Guidelines | Link | Codes of ethics by domain |
| Docs | Link | This documentation |
| Tools | Dropdown | Academic References, OntServe Web, Browse ProEthica Ontologies |
| [User] | Dropdown | Logout |

## Documentation Structure

```
docs/
├── index.md                      # Home page
├── getting-started/
│   ├── welcome.md               # Quick start
│   └── first-login.md           # Interface overview
├── concepts/
│   └── nine-concepts.md         # Framework reference
├── how-to/
│   ├── upload-cases.md          # Adding cases
│   ├── view-cases.md            # Browsing cases
│   ├── guidelines.md            # Ethical guidelines
│   ├── phase1-extraction.md     # Multi-pass extraction
│   ├── phase2-analysis.md       # Four-phase synthesis
│   ├── phase3-scenario.md       # Interactive scenarios
│   ├── entity-review.md         # Entity validation
│   ├── precedent-discovery.md   # Similarity network
│   ├── pipeline-automation.md   # Batch processing
│   └── settings.md              # Configuration
├── reference/
│   ├── architecture.md          # System architecture (placeholder)
│   ├── ontology-integration.md  # OntServe integration
│   ├── transformation-types.md  # Classification reference
│   └── installation.md          # Deployment
└── faq.md
```

## Writing Style

Follow `docs-internal/STYLE.md` for all documentation.

**Tone**: Formal, technical prose. Not conversational or tutorial-style. Avoid direct address ("you") where possible. Assume professional competence.

**Structure**:
- Main clause first; avoid front-loaded subordinate clauses
- No em dashes or colons in body text
- Avoid starting sentences with -ing phrases

**Word choice**:
- Banned: seamless, nuanced, robust, intriguing, comprehensive, systematic
- No unnecessary intensifiers (critical, key, important)
- Use "of" for inanimate possessives ("capabilities of the system")

**Lists**: Avoid three-item patterns; vary to two or four items

**Formatting**:
- **Bold** for UI elements, `code` for technical terms
- Tables for structured information
- "Related Guides" at end of how-to pages
- No emojis

## Capturing Screenshots

Use Playwright with snap chromium. Login required for most pages.

**Credentials**: `admin@proethica.org` / `Proethica2187`

**Form selectors**:
- Username: `input[name="username"]`
- Password: `input[name="password"]`
- Submit: `input[type="submit"]`

```python
/home/chris/onto/proethica/venv-proethica/bin/python -c "
from playwright.sync_api import sync_playwright
from pathlib import Path
from PIL import Image

BASE_URL = 'http://localhost:5000'
OUTPUT_DIR = Path('/home/chris/onto/proethica/docs/assets/images/screenshots')
NAVBAR_HEIGHT = 56

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/snap/bin/chromium')
    context = browser.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=2)
    page = context.new_page()

    # Login
    page.goto(f'{BASE_URL}/auth/login')
    page.wait_for_load_state('networkidle')
    page.fill('input[name=\"username\"]', 'admin@proethica.org')
    page.fill('input[name=\"password\"]', 'Proethica2187')
    page.click('input[type=\"submit\"]')
    page.wait_for_timeout(2000)

    # Capture page
    page.goto(f'{BASE_URL}/YOUR_URL_HERE')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    full_path = OUTPUT_DIR / 'screenshot-name.png'
    page.screenshot(path=str(full_path), full_page=False)

    # Crop navbar (multiply by device_scale_factor)
    img = Image.open(full_path)
    cropped = img.crop((0, NAVBAR_HEIGHT * 2, img.width, img.height))
    cropped.save(OUTPUT_DIR / 'screenshot-name-content.png')

    browser.close()
"
```

**Naming**: `feature-name.png` (full) and `feature-name-content.png` (cropped)

## Key Screenshots

| File | URL | Description |
|------|-----|-------------|
| `home-page-content.png` | `/` | Home page |
| `cases-list-content.png` | `/cases/` | Case repository |
| `case-detail-content.png` | `/cases/<id>` | Case with step buttons |
| `guidelines-list-content.png` | `/guidelines/` | Guidelines by domain |
| `step4-synthesis-content.png` | `/scenario_pipeline/case/<id>/step4` | Four-phase synthesis |
| `precedent-discovery-content.png` | `/cases/precedents/` | Similarity scores |
| `similarity-network-content.png` | `/cases/precedents/network` | Network graph |
| `pipeline-dashboard-content.png` | `/pipeline/dashboard` | Automation dashboard |

## Step 4: Four-Phase Synthesis

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Entity Foundation | Prepare extracted entities |
| 2 | Analytical Extraction | Provisions, questions, conclusions |
| 3 | Decision Point Synthesis | Identify decision points |
| 4 | Narrative Construction | Build case narrative |

## Similarity Network

| URL | Purpose |
|-----|---------|
| `/cases/precedents/network` | Interactive D3.js graph |
| `/cases/precedents/network?case_id=7` | Focus on specific case |
| `/cases/precedents/api/similarity_network` | JSON graph data |
| `/cases/precedents/api/similarity_matrix` | NxN similarity matrix |

Features: node colors by outcome, edge colors by similarity, entity type filters (R, P, O, S, Rs, A, E, Ca, Cs), subject tag filtering.

## Adding a New Page

1. Create markdown file in appropriate directory
2. Add to `mkdocs.yml` nav section
3. Add to "Related Guides" in related pages
4. Run `mkdocs build` to verify

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Playwright not found | Use proethica venv: `/home/chris/onto/proethica/venv-proethica/bin/python` |
| Chromium not found | Use `/snap/bin/chromium`, not Chrome |
| Login fails | Check selectors: `input[name="username"]`, `input[type="submit"]` |
| Broken links | Use relative paths from page location |
| Wrong navbar crop | Multiply NAVBAR_HEIGHT by device_scale_factor (56 * 2 = 112) |

## Flask Integration

Documentation served at `/docs/` via Flask:
- Route: `app/routes/docs.py`
- Blueprint: `docs_bp`
- Source: `site/` directory

## Placeholder Pages

These pages contain placeholder content and need full documentation:

| Page | Status | Notes |
|------|--------|-------|
| `how-to/phase2-analysis.md` | Placeholder | Created Dec 2025, describes Step 4 synthesis |
| `reference/architecture.md` | Placeholder | Created Dec 2025, basic service overview |
| `how-to/phase3-scenario.md` | Aspirational | Describes Step 5 which is not yet implemented |

Note: `reference/citations.md` is listed in the structure but does not exist. References are served via `/tools/references` route instead.

## References

Academic references are maintained in `/tools/references` (HTML template at `app/templates/tools/references.html`). All documentation links use absolute paths to this in-app page with anchors for specific sections.
