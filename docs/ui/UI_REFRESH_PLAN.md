# ProEthica UI Refresh Plan

## Current Issues
1. **Home page**: Too sales-pitchy, cluttered with conceptual explanations
2. **Navigation**: Flat structure, inconsistent organization
3. **Context confusion**: Cases, Scenarios, and Agents are world-specific but appear global

## Proposed Changes

### 1. Navigation Restructure

#### Current Structure (Flat)
```
Home | Scenarios | Worlds | Cases | Agent | Ontology Editor | Type Management
```

#### Proposed Structure (Hierarchical)
```
Home | Worlds | Ontology | Documentation | About
```

With dropdowns:
- **Worlds**
  - View All Worlds
  - Create New World
  - Engineering Ethics (World 1)
    - Dashboard
    - Cases
    - Scenarios
    - Guidelines
    - Agents

- **Ontology**
  - Ontology Editor
  - Type Management
  - Import/Export
  - Statistics

### 2. Home Page Redesign

#### Current Issues
- Overly enthusiastic language
- Too many conceptual explanations
- Cluttered card layout

#### Proposed Home Page Structure

```
ProEthica
---------
Ethical Decision-Making Platform

[Quick Stats Dashboard]
- X Worlds | Y Cases | Z Scenarios | N Guidelines

[Primary Actions]
- Select a World → 
- Manage Ontology →

[Recent Activity Feed]
- Latest cases added
- Recent guideline updates
- Type mapping improvements

[System Status]
- MCP Server: Online/Offline
- Database: Connected
- Last Backup: Date
```

### 3. World-Centric Navigation

Since Cases, Scenarios, and Agents belong to worlds, we should:

1. **Remove them from main nav**
2. **Add world selector/switcher** in header
3. **Create world dashboard** as landing page after selecting a world

#### World Dashboard Layout
```
Engineering Ethics World
------------------------
[Tab Navigation]
Overview | Cases | Scenarios | Guidelines | Agents | Settings

[World Stats]
- X Cases analyzed
- Y Scenarios created
- Z Guidelines active

[Quick Actions]
- Add New Case
- Create Scenario
- Upload Guideline
```

### 4. Simplified Language

#### Before:
"ProEthica simulates ethical scenarios in customizable worlds using rich domain ontologies, role-based guidelines, and structured reasoning..."

#### After:
"ProEthica helps analyze ethical decisions in professional contexts."

### 5. Implementation Steps

#### Phase 1: Home Page Refresh
1. Simplify index.html content
2. Add statistics dashboard
3. Remove marketing language
4. Add system status indicators

#### Phase 2: Navigation Restructure
1. Update base.html with new nav structure
2. Add world selector component
3. Move Type Management under Ontology
4. Create world dashboard template

#### Phase 3: World-Centric Views
1. Create world dashboard route
2. Move cases/scenarios/agents under world context
3. Add breadcrumb navigation
4. Implement world switching

### 6. Visual Design Guidelines

- **Less is more**: Remove unnecessary explanations
- **Action-oriented**: Focus on what users can do
- **Context-aware**: Always show which world is active
- **Status visible**: Show system health/status
- **Data-driven**: Show actual counts/stats, not concepts

### 7. Specific Page Updates

#### Home Page (index.html)
- Remove jumbotron
- Add stats dashboard
- Simplify to 2 main actions: Select World, Manage Ontology
- Add recent activity feed

#### Base Navigation (base.html)
- Consolidate into 4 main items
- Add world selector/switcher
- Move user menu to right
- Add breadcrumbs below nav

#### World Dashboard (new)
- Central hub for world-specific features
- Tabbed interface for different sections
- Quick stats and actions
- Recent activity in this world

### 8. Benefits

1. **Clearer mental model**: World-centric organization matches how the app works
2. **Less cognitive load**: Simplified navigation and language
3. **Better discoverability**: Related features grouped together
4. **Improved workflow**: World selection → Task completion
5. **Professional feel**: Less marketing, more utility

### 9. Migration Path

To avoid breaking existing bookmarks:
1. Keep old routes but redirect to new structure
2. Add deprecation notices
3. Update documentation
4. Provide URL mapping guide

### 10. Future Considerations

- **Quick world switcher**: Keyboard shortcut or dropdown
- **Favorite worlds**: Pin frequently used worlds
- **Global search**: Search across all worlds
- **Customizable dashboard**: Let users arrange widgets