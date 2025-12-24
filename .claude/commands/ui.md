# ProEthica UI Cleanup Command

You are a UI cleanup specialist for ProEthica. Make targeted UI changes based on the user's brief instructions.

## Template-to-URL Mapping

| Page URL Pattern | Template | Route File |
|------------------|----------|------------|
| `/cases/<id>` | `case_detail.html` | `app/routes/cases.py` |
| `/cases/` | `cases_list.html` | `app/routes/cases.py` |
| `/cases/<id>/structure` | `document_structure.html` | `app/routes/cases.py` |
| `/scenario_pipeline/case/<id>/step1` | `scenarios/step1.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step2` | `scenarios/step2_streaming.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step3` | `scenarios/step3_dual_extraction.html` | `app/routes/scenario_pipeline/interactive_builder.py` |
| `/scenario_pipeline/case/<id>/step4` | `scenario_pipeline/step4.html` | `app/routes/scenario_pipeline/step4.py` |
| `/scenario_pipeline/case/<id>/step4/review` | `scenario_pipeline/step4_review.html` | `app/routes/scenario_pipeline/step4.py` |
| `/scenario_pipeline/case/<id>/entity_review/<section>` | `scenarios/entity_review.html` | `app/routes/scenario_pipeline/entity_review.py` |
| `/scenario_pipeline/case/<id>/entity_review_pass2/<section>` | `scenarios/entity_review_pass2.html` | `app/routes/scenario_pipeline/entity_review.py` |
| `/scenario_pipeline/case/<id>/enhanced_temporal_review` | `entity_review/enhanced_temporal_review.html` | `app/routes/scenario_pipeline/entity_review.py` |

## Navigation Components

| Component | File |
|-----------|------|
| Pipeline status bar (case detail) | `app/templates/cases/_case_pipeline_status.html` |
| Pipeline sidebar | `app/templates/scenarios/_pipeline_steps.html` |

## Ontology Label Popovers

For displaying entity URIs with rich hover popovers showing metadata, use inline macro pattern (see `step4_review.html` for full implementation):

**Macro Definition** (at top of template):
```jinja2
{% macro ontology_label(uri, entity_lookup) %}
{%- set label = uri.split('#')[-1] if uri is string and '#' in uri else (uri.split('/')[-1] if uri is string and '/' in uri else uri) -%}
{%- set entity = entity_lookup.get(uri) if entity_lookup and uri is string else none -%}
{%- if entity -%}
<span class="onto-label"
      tabindex="0"
      data-bs-toggle="popover"
      data-bs-trigger="hover focus"
      data-bs-html="true"
      data-bs-placement="top"
      data-entity-type="{{ entity.entity_type or entity.extraction_type }}"
      data-entity-pass="{{ entity.source_pass }}"
      data-entity-definition="{{ entity.definition|e }}"
      data-entity-uri="{{ uri|e }}"
      title="{{ entity.label or label }}">{{ entity.label or label }}</span>
{%- elif uri is string and ('http' in uri or '#' in uri) -%}
<span class="onto-label onto-label-unknown" ...>{{ label }}</span>
{%- else -%}
<span>{{ uri }}</span>
{%- endif -%}
{% endmacro %}
```

**Usage**:
```jinja2
{{ ontology_label(obligation_uri, entity_lookup) }}
```

**Required Route Context**:
```python
entity_lookup = _build_entity_lookup_dict(case_id)
context = {'entity_lookup': entity_lookup, ...}
```

**Required JavaScript** (initialize Bootstrap popovers from data attributes):
```javascript
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (typeof bootstrap === 'undefined') return;
        document.querySelectorAll('.onto-label[data-bs-toggle="popover"]').forEach(function(el) {
            var content = buildPopoverContent(el.dataset);
            new bootstrap.Popover(el, {container: 'body', sanitize: false, content: content, html: true});
        });
    }, 100);
});
```

## Entity Type Colors

| Type | CSS Class | Color |
|------|-----------|-------|
| Role | `.onto-type-roles` | Blue (#0d6efd) |
| State | `.onto-type-states` | Purple (#6f42c1) |
| Resource | `.onto-type-resources` | Teal (#20c997) |
| Principle | `.onto-type-principles` | Orange (#fd7e14) |
| Obligation | `.onto-type-obligations` | Red (#dc3545) |
| Constraint | `.onto-type-constraints` | Gray (#6c757d) |
| Capability | `.onto-type-capabilities` | Cyan (#0dcaf0) |
| Action | `.onto-type-actions` | Green (#198754) |
| Event | `.onto-type-events` | Yellow (#ffc107) |

## Pass Badge Colors

| Pass | Bootstrap Class |
|------|-----------------|
| Pass 1 | `bg-primary` (blue) |
| Pass 2 | `bg-success` (green) |
| Pass 3 | `bg-warning text-dark` (yellow) |
| Pass 4 | `bg-danger` (red) |

## Authentication Context

Templates have access to:

| Variable | Description |
|----------|-------------|
| `current_user.is_authenticated` | True if user is logged in |
| `current_user.is_admin` | True if user has admin privileges |
| `environment` | `'production'` or `'development'` |

**Common Auth Patterns**:
```jinja2
{# Show only to logged-in users #}
{% if current_user.is_authenticated %}...{% endif %}

{# Show only to admins #}
{% if current_user.is_authenticated and current_user.is_admin %}...{% endif %}

{# Production-only restriction #}
{% if environment != 'production' or current_user.is_authenticated %}...{% endif %}
```

**Route Decorators** (from `app.utils.environment_auth`):

| Decorator | Behavior |
|-----------|----------|
| `@auth_required_for_write` | Login for POST/PUT/DELETE only |
| `@auth_required_for_llm` | Login for LLM operations |
| `@admin_required_production` | Admin in prod, open in dev |

## Common Layout Patterns

**Colored Background Sections** (for Fulfills/Violates):
```html
<div class="p-2 rounded" style="background-color: rgba(25, 135, 84, 0.08);">
    <!-- green tint for positive -->
</div>
<div class="p-2 rounded" style="background-color: rgba(220, 53, 69, 0.08);">
    <!-- red tint for negative -->
</div>
```

**Competing Pairs** (with bidirectional arrow):
```html
<span class="d-flex align-items-center flex-wrap gap-1">
    {{ ontology_label(pair[0], entity_lookup) }}
    <i class="bi bi-arrow-left-right text-warning mx-1"></i>
    {{ ontology_label(pair[1], entity_lookup) }}
</span>
```

**Accordion for Expandable Content**:
```html
<div class="accordion" id="myAccordion">
    {% for item in items %}
    <div class="accordion-item">
        <h2 class="accordion-header">
            <button class="accordion-button collapsed py-2" type="button"
                    data-bs-toggle="collapse" data-bs-target="#item-{{ loop.index }}">
                {{ item.title }}
            </button>
        </h2>
        <div id="item-{{ loop.index }}" class="accordion-collapse collapse">
            <div class="accordion-body">{{ item.content }}</div>
        </div>
    </div>
    {% endfor %}
</div>
```

## Workflow

1. **Identify** the correct template from URL mapping
2. **Read** the template file before editing
3. **Locate** the UI element to change
4. **Edit** with minimal, targeted changes
5. **Test** by refreshing the page

## Guidelines

- Always read files before editing
- Make minimal changes
- Preserve existing indentation
- Use Bootstrap 5 classes consistently
- Check browser console for JavaScript errors after changes
- Add null checks when accessing DOM elements that may not exist
