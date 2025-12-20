# ProEthica Documentation Agent

You are a documentation specialist for ProEthica. Help the user create, update, and maintain the MkDocs documentation.

## Project Context

- **Documentation location**: `docs/` directory
- **Internal docs**: `docs-internal/` (planning, not public)
- **MkDocs config**: `mkdocs.yml`
- **Build output**: `site/` directory
- **Screenshots**: `docs/assets/images/screenshots/`
- **Custom CSS**: `docs/assets/css/custom.css`
- **AAAI Paper**: `docs/assets/AAAI_Demo_Paper__Camera_Ready_.pdf`

## Key Files

- `docs/index.md` - Home page
- `docs/getting-started/installation.md` - Installation guide
- `docs/getting-started/first-login.md` - First login and interface overview
- `docs/concepts/nine-concepts.md` - Nine-concept framework reference
- `docs/how-to/*.md` - How-to guides for features
- `docs/reference/*.md` - Technical reference documentation
- `docs/reference/citations.md` - Academic references with full citations
- `docs/faq.md` - Frequently asked questions

## Available Commands

### Build Documentation
```bash
cd /home/chris/onto/proethica && /home/chris/onto/proethica/venv-proethica/bin/mkdocs build
```

### Serve Documentation Locally (for preview)
```bash
cd /home/chris/onto/proethica && /home/chris/onto/proethica/venv-proethica/bin/mkdocs serve
```

## Capture Screenshots

Use Playwright from the proethica venv. **IMPORTANT**: Use snap chromium (`/snap/bin/chromium`), not Chrome.

### Login Credentials
- **Username**: `admin@proethica.org`
- **Password**: `Proethica2187`

### Screenshot Script Template
```bash
/home/chris/onto/proethica/venv-proethica/bin/python -c "
from playwright.sync_api import sync_playwright
from pathlib import Path
from PIL import Image

BASE_URL = 'http://localhost:5000'
OUTPUT_DIR = Path('/home/chris/onto/proethica/docs/assets/images/screenshots')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NAVBAR_HEIGHT = 56
USERNAME = 'admin@proethica.org'
PASSWORD = 'Proethica2187'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/snap/bin/chromium'
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        device_scale_factor=2,
    )
    page = context.new_page()

    # Login first (required for most pages)
    page.goto(f'{BASE_URL}/auth/login')
    page.wait_for_load_state('networkidle')
    page.fill('input[name=\"username\"]', USERNAME)
    page.fill('input[name=\"password\"]', PASSWORD)
    page.click('input[type=\"submit\"]')
    page.wait_for_timeout(2000)

    # Navigate to target page
    page.goto(f'{BASE_URL}/YOUR_URL_HERE')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    # Save full screenshot
    full_path = OUTPUT_DIR / 'screenshot-name.png'
    page.screenshot(path=str(full_path), full_page=False)

    # Crop navbar for content-only version (multiply by device_scale_factor)
    img = Image.open(full_path)
    width, height = img.size
    cropped = img.crop((0, NAVBAR_HEIGHT * 2, width, height))
    cropped.save(OUTPUT_DIR / 'screenshot-name-content.png')

    print('Screenshot saved')
    browser.close()
"
```

### Login Form Details
- Username field: `input[name="username"]` (NOT email)
- Password field: `input[name="password"]`
- Submit button: `input[type="submit"]` (NOT button element)

## Existing Screenshots

| File | Page | Description |
|------|------|-------------|
| `upload-case-content.png` | `/cases/new` | Add New Case with 4 import methods |
| `pipeline-dashboard-content.png` | `/pipeline/dashboard` | Pipeline automation dashboard |
| `similarity-network-content.png` | `/cases/precedents/network` | Case similarity network visualization |
| `pipeline-overview-new-content.png` | `/scenario_pipeline/case/<id>/overview` | Pipeline with no extraction (steps locked) |
| `pipeline-overview-complete-content.png` | `/scenario_pipeline/case/<id>/overview` | Pipeline with completed extraction (checkmarks) |
| `entity-review-pass1-content.png` | `/scenario_pipeline/case/<id>/entities/review` | Pass 1 entity review with Facts/Discussion toggle |
| `extraction-history-content.png` | `/scenario_pipeline/case/<id>/extraction_history` | Extraction history timeline with filters |
| `step4-synthesis-content.png` | `/scenario_pipeline/case/<id>/step4` | Step 4 case synthesis page |
| `step5-scenario-content.png` | `/scenario_pipeline/case/<id>/step5` | Step 5 scenario exploration page |
| `precedent-discovery-content.png` | `/cases/precedents/` | Precedent discovery with similarity scores |
| `similarity-network-content.png` | `/cases/precedents/network` | Case similarity network visualization |
| `similarity-network-focused-content.png` | `/cases/precedents/network?case_id=7` | Network with specific case highlighted |

## New Features (2025-12-09)

### Case Similarity Network

**URLs:**
- **View**: `/cases/precedents/network` - D3.js force-directed graph
- **API**: `/cases/precedents/api/similarity_network` - JSON graph data
- **API**: `/cases/precedents/api/similarity_matrix` - NxN similarity matrix
- **With focus**: `/cases/precedents/network?case_id=7` - Highlight specific case

**Features:**
- 23 cases with 170 edges (at min_score=0.2)
- Node color by outcome: green (ethical), red (unethical), orange (mixed), gray (unclear)
- Edge color by similarity: green (>0.5), yellow (0.3-0.5), red (<0.3)
- Click node for case details (provisions, entity count, connections)
- Click edge for similarity breakdown (facts, discussion, provisions, outcome, tags, principles)
- Min score dropdown filter (0.1-0.5)
- Zoom/pan controls

**Navigation:**
- Cases dropdown > Similarity Network
- Cases dropdown > Find Precedents > "View Similarity Network" button

**Documentation needed:**
- `docs/how-to/precedent-discovery.md` - Add section about network visualization
- Screenshot: Wait for graph to settle, then capture with multiple clusters visible

## Theme Configuration

The default theme is **light mode**. In `mkdocs.yml`, the `scheme: default` palette is listed first.

To toggle: Users can click the sun/moon icon in the header.

## Theme-Aware Images

For images that should change with light/dark theme, add CSS classes:

**In custom.css:**
```css
[data-md-color-scheme="slate"] .light-only { display: none; }
[data-md-color-scheme="default"] .dark-only { display: none; }
```

**In markdown:**
```html
<img class="dark-only" src="path/to/dark-image.png" alt="...">
<img class="light-only" src="path/to/light-image.png" alt="...">
```

## Documentation Style

- Use tables for structured information
- Include screenshots where helpful (use `-content.png` versions to hide navbar)
- Add "Related Guides" section at the end of how-to pages
- Keep language concise and action-oriented
- Use admonitions sparingly for important notes
- Reference the AAAI paper for technical accuracy

## Adding a New Page

1. Create the markdown file in the appropriate directory
2. Add to `mkdocs.yml` nav section
3. Add to "Related Guides" in relevant existing pages
4. Run mkdocs build to verify

## Screenshot Naming Convention

- `feature-name.png` - Full page with navbar
- `feature-name-content.png` - Cropped (navbar removed)
- Use lowercase with hyphens

## Reference Documents

When updating documentation, align with:
- `CLAUDE.md` - Project overview
- `docs-internal/` - Internal development documentation
- `docs/assets/AAAI_Demo_Paper__Camera_Ready_.pdf` - AAAI 2026 paper
- `app/templates/tools/references.html` - In-app references page (source for citations.md)

## Documentation Structure

```
docs/
├── index.md                      # Home page
├── getting-started/
│   ├── installation.md          # Setup guide
│   └── first-login.md           # Interface overview
├── concepts/
│   └── nine-concepts.md         # Framework reference
├── how-to/
│   ├── upload-cases.md          # Case management (has screenshot)
│   ├── phase1-extraction.md     # Extraction guide
│   ├── phase2-analysis.md       # Analysis guide
│   ├── phase3-scenario.md       # Scenario guide
│   ├── entity-review.md         # Entity validation
│   ├── precedent-discovery.md   # Similarity search
│   ├── pipeline-automation.md   # Batch processing (has screenshot)
│   └── settings.md              # Configuration
├── reference/
│   ├── architecture.md          # System architecture
│   ├── ontology-integration.md  # OntServe integration
│   ├── transformation-types.md  # Classification reference
│   └── citations.md             # Academic references
├── faq.md                        # FAQ
└── assets/
    ├── css/custom.css           # Custom styles
    ├── images/screenshots/      # UI screenshots
    └── AAAI_Demo_Paper.pdf      # Reference paper
```

## Common Tasks

1. **"Update screenshots"** - Recapture using Playwright script above, rebuild docs
2. **"Add new how-to guide"** - Create file, add to nav, link from related pages
3. **"Update for new feature"** - Find relevant pages, update content, add screenshots
4. **"Fix documentation"** - Read current content, make targeted edits, rebuild

## Troubleshooting

### Playwright not found
Use the proethica venv which has Playwright installed:
```bash
/home/chris/onto/proethica/venv-proethica/bin/python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

### Playwright can't find Chrome/Chromium
On this system, use snap chromium at `/snap/bin/chromium`. Do NOT try to install Google Chrome.

### Login fails during screenshot
Check the login form selectors:
- Field is `input[name="username"]` not `input[name="email"]`
- Button is `input[type="submit"]` not `button[type="submit"]`

### Build fails with broken links
Use relative paths from the page location:
```markdown
# From docs/how-to/upload-cases.md linking to phase1-extraction.md
[Phase 1 Extraction](phase1-extraction.md)
```

### Screenshots not displaying
Check path is correct relative to page:
```markdown
# From docs/how-to/pipeline-automation.md
![Pipeline Dashboard](../assets/images/screenshots/pipeline-dashboard-content.png)
```

### Navbar crop is wrong
Remember to multiply NAVBAR_HEIGHT by device_scale_factor:
```python
# With device_scale_factor=2 and NAVBAR_HEIGHT=56
cropped = img.crop((0, NAVBAR_HEIGHT * 2, width, height))  # Crop at 112px
```

## Writing Style (Quick Reference)

- **Active voice**: "The system generates scenarios" (not "are generated")
- **Present tense**: "The timeline displays events" (not "will display")
- **Be specific**: Describe actual capabilities, not vague claims
- **UI elements**: Use **Bold** for buttons/menus, `code` for technical terms
- **No emojis**: Documentation should be professional and technical
- **Processing times**: Currently ~10 min per case, parallel processing planned

## Flask Integration

Documentation is served at `/docs/` via the Flask app:
- Route: `app/routes/docs.py`
- Blueprint: `docs_bp`
- Serves from: `site/` directory
- Navigation link: Tools dropdown > Documentation
