# UI Refresh Implementation Guide

## Phase 1: Quick Wins (Can do immediately)

### 1.1 Update Home Page
Replace `/app/templates/index.html` with `/app/templates/index_refreshed.html`:
```python
# In app/routes/index.py, add data collection:
@index_bp.route('/')
def index():
    # Collect stats
    world_count = World.query.count()
    case_count = Case.query.count()
    scenario_count = Scenario.query.count()
    guideline_count = Guideline.query.count()
    
    # Recent activities (mock for now)
    recent_activities = []
    
    # System status checks
    mcp_status = check_mcp_status()  # Implement this
    embedding_status = check_embedding_status()  # Implement this
    
    return render_template('index_refreshed.html',
        world_count=world_count,
        case_count=case_count,
        scenario_count=scenario_count,
        guideline_count=guideline_count,
        recent_activities=recent_activities,
        mcp_status=mcp_status,
        embedding_status=embedding_status,
        last_backup_time=get_last_backup_time()
    )
```

### 1.2 Simplify Navigation (Temporary)
Update existing `base.html` to group Type Management under Ontology:
```html
<!-- Move Type Management under Ontology dropdown -->
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="ontologyDropdown">
        <i class="bi bi-diagram-3"></i> Ontology
    </a>
    <ul class="dropdown-menu">
        <li><a class="dropdown-item" href="/ontology-editor">Ontology Editor</a></li>
        <li><a class="dropdown-item" href="/type-management/">Type Management</a></li>
    </ul>
</li>
```

## Phase 2: Navigation Restructure

### 2.1 Create World Dashboard Route
```python
# app/routes/worlds.py
@worlds_bp.route('/<int:world_id>/dashboard')
def world_dashboard(world_id):
    world = World.query.get_or_404(world_id)
    
    # Get world-specific stats
    case_count = Case.query.filter_by(world_id=world_id).count()
    scenario_count = Scenario.query.filter_by(world_id=world_id).count()
    guideline_count = Guideline.query.filter_by(world_id=world_id).count()
    entity_count = Entity.query.filter_by(world_id=world_id).count()
    
    # Get recent activities for this world
    recent_activities = get_world_activities(world_id)
    
    return render_template('world_dashboard.html',
        world=world,
        case_count=case_count,
        scenario_count=scenario_count,
        guideline_count=guideline_count,
        entity_count=entity_count,
        recent_activities=recent_activities
    )
```

### 2.2 Add World Context Middleware
```python
# app/__init__.py or new middleware file
@app.before_request
def inject_world_context():
    # Check if we're in a world-specific route
    if 'world_id' in request.view_args:
        g.active_world = World.query.get(request.view_args['world_id'])
    else:
        g.active_world = None
```

### 2.3 Update Base Template Gradually
1. First add world context display when available
2. Then reorganize navigation items
3. Finally switch to `base_refreshed.html`

## Phase 3: World-Centric Routes

### 3.1 Route Restructuring
Move routes to be world-scoped:
```
OLD: /cases/<case_id>
NEW: /worlds/<world_id>/cases/<case_id>

OLD: /scenarios/<scenario_id>  
NEW: /worlds/<world_id>/scenarios/<scenario_id>

OLD: /agent
NEW: /worlds/<world_id>/agents
```

### 3.2 Add Redirects for Backward Compatibility
```python
# Keep old routes but redirect
@cases_bp.route('/<int:case_id>')
def legacy_case_detail(case_id):
    case = Case.query.get_or_404(case_id)
    return redirect(url_for('worlds.case_detail', 
                          world_id=case.world_id, 
                          case_id=case_id))
```

## Phase 4: Polish and Refinement

### 4.1 Add Activity Tracking
```python
# app/services/activity_service.py
def log_activity(world_id, activity_type, title, description):
    # Store in database or cache
    activity = Activity(
        world_id=world_id,
        type=activity_type,
        title=title,
        description=description,
        created_at=datetime.utcnow()
    )
    db.session.add(activity)
    db.session.commit()
```

### 4.2 Implement System Status Checks
```python
# app/services/system_status.py
def check_mcp_status():
    try:
        response = requests.get('http://localhost:5001/health')
        return response.status_code == 200
    except:
        return False

def check_embedding_status():
    # Check if embedding service is available
    return hasattr(current_app, 'embedding_service')
```

### 4.3 Add Breadcrumb Support
```python
# app/template_filters.py
@app.template_filter('breadcrumb')
def breadcrumb_filter(path):
    # Convert URL path to breadcrumb items
    parts = path.strip('/').split('/')
    breadcrumbs = []
    for i, part in enumerate(parts):
        breadcrumbs.append({
            'name': part.replace('-', ' ').title(),
            'url': '/' + '/'.join(parts[:i+1])
        })
    return breadcrumbs
```

## Migration Checklist

- [ ] Backup current templates
- [ ] Test new home page with real data
- [ ] Update navigation in stages
- [ ] Create world dashboard
- [ ] Move Type Management under Ontology
- [ ] Add world context to requests
- [ ] Update routes to be world-scoped
- [ ] Add legacy route redirects
- [ ] Implement activity tracking
- [ ] Add system status indicators
- [ ] Test all navigation paths
- [ ] Update documentation

## Benefits of This Approach

1. **Gradual Migration**: Can be done in phases without breaking existing functionality
2. **Better Organization**: World-centric approach matches mental model
3. **Cleaner UI**: Less clutter, more focus on actions
4. **Professional Look**: Removes sales pitch language
5. **Improved UX**: Clear navigation hierarchy

## Next Steps

1. Start with Phase 1 (quick wins) - can be done immediately
2. Test with users to get feedback
3. Proceed with Phase 2-4 based on feedback
4. Consider adding keyboard shortcuts for power users
5. Add user preferences for dashboard customization