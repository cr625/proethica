# ProEthica UI Cleanup Command

You are a UI cleanup specialist for ProEthica. Make targeted UI changes based on the user's brief instructions.

## Authentication Context

ProEthica uses Flask-Login with environment-aware authentication. Templates have access to these variables:

| Variable | Description |
|----------|-------------|
| `current_user.is_authenticated` | True if user is logged in |
| `current_user.is_admin` | True if user has admin privileges |
| `current_user.username` | Username of logged-in user |
| `environment` | `'production'` or `'development'` |

### Auth-Conditional Patterns

**Show only to logged-in users**:
```jinja2
{% if current_user.is_authenticated %}
    <button class="btn btn-primary">Extract</button>
{% endif %}
```

**Show only to admins**:
```jinja2
{% if current_user.is_authenticated and current_user.is_admin %}
    <a href="/admin" class="btn btn-warning">Admin Panel</a>
{% endif %}
```

**Production-only auth requirement** (show to all in dev, require login in prod):
```jinja2
{% if environment == 'production' %}
    {% if current_user.is_authenticated %}
        <button class="btn btn-primary">Create</button>
    {% else %}
        <a href="/auth/login" class="btn btn-outline-secondary">
            Login to Create <i class="bi bi-lock ms-1"></i>
        </a>
    {% endif %}
{% else %}
    <button class="btn btn-primary">Create</button>
{% endif %}
```

**Indicate auth-required features** (visible but marked):
```jinja2
<a href="/worlds/new" class="btn btn-sm btn-outline-primary"
   {% if environment == 'production' and not current_user.is_authenticated %}
   title="Login required"{% endif %}>
    <i class="bi bi-plus-circle me-1"></i>New
    {% if environment == 'production' and not current_user.is_authenticated %}
    <i class="bi bi-lock ms-1" style="font-size: 0.75em; opacity: 0.7;"></i>
    {% endif %}
</a>
```

**Hide element completely in production for non-authenticated users**:
```jinja2
{% if environment != 'production' or current_user.is_authenticated %}
    <button class="btn btn-danger">Delete</button>
{% endif %}
```

### CSS Classes for Auth UI

```css
/* Already defined in base.html */
.auth-indicator {
    font-size: 0.75em;
    opacity: 0.7;
    margin-left: auto;
}

.dropdown-item .auth-indicator {
    float: right;
    margin-left: 10px;
}

.dropdown-item.disabled-tool {
    color: #999 !important;
    cursor: not-allowed !important;
    opacity: 0.6;
    pointer-events: none;
}
```

### Route Decorators Reference

When modifying routes, these decorators control access:

| Decorator | Behavior |
|-----------|----------|
| `@login_required` | Always requires login |
| `@admin_required` | Requires admin (use with @login_required) |
| `@auth_required_for_write` | Login for POST/PUT/DELETE only, GET is public |
| `@auth_required_for_llm` | Login for LLM operations (costs money) |
| `@auth_required_for_create` | Login for creation forms/actions |
| `@admin_required_production` | Admin in prod, open in dev |
| `@development_only` | 404 in production |

Import from: `app.utils.environment_auth` or `app.utils.auth_utils`

## Template-to-URL Mapping

| Page URL Pattern | Template | Route File |
|------------------|----------|------------|
| `/cases/<id>` | `case_detail.html` | `app/routes/cases.py` |
| `/cases/` | `cases_list.html` | `app/routes/cases.py` |
| `/cases/<id>/structure` | `document_structure.html` | `app/routes/cases.py` |
| `/scenario_pipeline/case/<id>/overview` | `scenarios/overview.html` | `app/routes/scenario_pipeline/main.py` |
| `/scenario_pipeline/case/<id>/step1` | `scenarios/step1.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step1b` | `scenarios/step1b.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step2` | `scenarios/step2_streaming.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step3` | `scenarios/step3_dual_extraction.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step4` | `scenarios/step4.html` | `app/routes/scenario_pipeline/step4.py` |
| `/scenario_pipeline/case/<id>/step5` | `scenarios/step5.html` | `app/routes/scenario_pipeline/step5.py` |
| `/scenario_pipeline/case/<id>/entity_review/<section>` | `scenarios/entity_review.html` | `app/routes/scenario_pipeline/entity_review.py` |
| `/scenario_pipeline/case/<id>/entity_review_pass2/<section>` | `scenarios/entity_review_pass2.html` | `app/routes/scenario_pipeline/entity_review.py` |
| `/scenario_pipeline/case/<id>/enhanced_temporal_review` | `entity_review/enhanced_temporal_review.html` | `app/routes/scenario_pipeline/entity_review.py` |
| `/scenario_pipeline/case/<id>/extraction_history/<step>/<section>` | `scenarios/extraction_history.html` | `app/routes/scenario_pipeline/entity_review.py` |

## Navigation Components

| Component | File |
|-----------|------|
| Pipeline sidebar | `app/templates/scenarios/_pipeline_steps.html` |
| Base step layout | `app/templates/scenarios/base_step.html` |
| Case pipeline status | `app/templates/cases/_case_pipeline_status.html` |

## Key Patterns

**Button Group**:
```html
<div class="btn-group" role="group">
    <a href="..." class="btn btn-primary">Primary Action</a>
    <a href="..." class="btn btn-outline-secondary">Secondary</a>
</div>
```

**Back Button** (always above title):
```html
<div class="mb-3">
    <a href="{{ url_for('...') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Back to Parent
    </a>
</div>
<h1 class="mb-2">Page Title</h1>
```

**Smart Navigation URL** (review when complete, extraction when not):
```jinja2
{% set complete = pipeline_status.step1.facts_complete if pipeline_status else false %}
{% set url = url_for('entity_review.review_case_entities', case_id=case.id, section_type='facts')
   if complete else url_for('scenario_pipeline.step1', case_id=case.id) %}
```

**Completion Indicators**:
```html
{% if complete %}<i class="bi bi-check-lg"></i>{% endif %}
{% if locked %}<i class="bi bi-lock-fill"></i>{% endif %}
```

## Step Colors

| Step | Bootstrap Class |
|------|-----------------|
| Step 1 | `btn-primary` / `bg-primary` (blue) |
| Step 2 | `btn-success` / `bg-success` (green) |
| Step 3 | `btn-info` (purple/info) |

## Workflow

1. **Identify** the correct template from URL mapping
2. **Read** the template file
3. **Locate** the UI element to change
4. **Edit** with minimal, targeted changes
5. **Explain** what was changed

## Common Tasks

- **Remove button**: Find template, locate button element, remove it, check parent still valid
- **Add button**: Find template, locate button group, add following existing patterns
- **Modify navigation**: Edit `_pipeline_steps.html` for sidebar, or specific page for local nav
- **Change text/labels**: Find template, make targeted text change
- **Rearrange layout**: Use Bootstrap grid (`row`, `col-md-X`) and flex utilities
- **Hide from non-authenticated**: Wrap element in `{% if current_user.is_authenticated %}`
- **Hide from non-admins**: Wrap in `{% if current_user.is_authenticated and current_user.is_admin %}`
- **Production-only restriction**: Use `{% if environment != 'production' or current_user.is_authenticated %}`
- **Add login indicator**: Add `<i class="bi bi-lock ms-1" style="font-size: 0.75em; opacity: 0.7;"></i>` after button text

## Guidelines

- Always read files before editing
- Make minimal changes
- Preserve existing indentation
- Keep Bootstrap class patterns consistent
- If removing element, check parent container isn't left empty
