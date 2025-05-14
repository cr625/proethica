# Template URL Routing Fix

## Issue Overview

When attempting to access the `/worlds/1/guidelines` route, the application was returning a 500 Internal Server Error with the following error message:

```
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'index'. Did you mean 'index.index' instead?
```

This error occurred because the application had been updated to use Flask blueprints for better code organization, but some template files still referenced routes using their old names without blueprint prefixes.

## Root Cause

In Flask, when using blueprints, URL endpoints get prefixed with the blueprint name. For example, if you have:

```python
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    ...
```

The endpoint for this route becomes `'index.index'` (blueprint_name.function_name) rather than just `'index'`.

The templates were still using the old style:

```jinja
<a href="{{ url_for('index') }}">Home</a>
```

Instead of the new blueprint-style:

```jinja
<a href="{{ url_for('index.index') }}">Home</a>
```

## Files Fixed

The following files contained incorrect references to `url_for('index')` that were updated to `url_for('index.index')`:

1. `app/templates/guidelines.html`
2. `app/templates/guideline_concepts_review.html`
3. `app/templates/guideline_content.html`
4. `app/routes/auth.py` (multiple occurrences)

## Solution Implementation

The `url_for()` calls were updated in all affected files to use the correct blueprint-prefixed endpoint format.

For example, in templates:

```diff
- <a href="{{ url_for('index') }}">Home</a>
+ <a href="{{ url_for('index.index') }}">Home</a>
```

And in Python code:

```diff
- return redirect(url_for('index'))
+ return redirect(url_for('index.index'))
```

## Verification

After implementing these changes:
1. The `/worlds/1/guidelines` route is now accessible
2. Navigation between pages works correctly
3. No more 500 errors occur due to URL routing issues

## Preventative Measures

To prevent similar issues in the future:

1. When refactoring routes to use blueprints, use grep or search functionality to find all instances of `url_for('route_name')` and update them accordingly.

2. Consider implementing a template context processor that could make these references more resilient to structural changes:

```python
@app.context_processor
def utility_processor():
    def safe_url_for(endpoint, **kwargs):
        # Handle both blueprint-style and non-blueprint-style endpoints
        try:
            return url_for(endpoint, **kwargs)
        except BuildError:
            # Try adding blueprint prefix if simple endpoint fails
            parts = endpoint.split('.')
            if len(parts) == 1:
                try:
                    return url_for(f"{endpoint}.{endpoint}", **kwargs)
                except:
                    pass
            raise
    return dict(safe_url_for=safe_url_for)
```

3. Use automated testing that renders templates to catch these issues before they reach production.
