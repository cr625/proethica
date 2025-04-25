# Ontology Editor Improvements

## Current Behavior Analysis

### URL Parameter Handling
- The ontology editor currently accepts two URL parameters:
  - `ontology_id`: Numeric ID for loading an ontology directly (e.g., `/ontology-editor/?ontology_id=1&view=full`)
  - `source`: Alternative identifier for loading an ontology (less commonly used)
- Pros: Direct linking to specific ontologies is possible (e.g., from world detail pages)
- Cons: URL parameters persist during navigation, potentially causing confusion if a user selects a different ontology

### Version Management
- Versions are displayed in a sidebar panel
- Clicking a version loads it into the editor
- Saving creates a new version with a commit message
- The UI doesn't clearly indicate which version is currently active

## Recommended Improvements

### URL Parameter Handling
1. **History API Integration**
   - Use `window.history.pushState()` to update the URL when a user selects a different ontology
   - Example code to add in the `loadOntology()` function:
   ```javascript
   // Update URL without reloading page when ontology is changed
   const newUrl = new URL(window.location.href);
   newUrl.searchParams.set('ontology_id', ontologyId);
   window.history.pushState({ontologyId}, '', newUrl.toString());
   ```

2. **Clear Loading Status**
   - Add visual indicators showing which ontology is being loaded from URL parameters
   - When loading via URL, highlight the corresponding ontology in the sidebar

3. **Parameter Cleanup**
   - Consider removing redundant parameters (e.g., if both `ontology_id` and `source` are present)
   - Handle the `view=full` parameter more explicitly in the UI

### Version Management
1. **Improved Version Display**
   - Add a dropdown in the main editor toolbar to show and select versions
   - Include version number, date, and commit message in a more compact format
   - Example HTML:
   ```html
   <div class="btn-group">
     <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
       <span id="currentVersion">Current Version</span>
     </button>
     <ul class="dropdown-menu" id="versionDropdown">
       <!-- Versions populated here -->
     </ul>
   </div>
   ```

2. **Active Version Indicator**
   - Clearly highlight the currently active version
   - Add "Latest" tag to the most recent version
   - Add visual indicators for modified content (e.g., asterisk or icon)

3. **Version Comparison**
   - Add ability to compare two versions with a diff view
   - Allow restoring previous versions with a new commit

## Implementation Plan

1. **Update `loadOntology` Function**
   - Modify to update URL using History API
   - Add proper active state to sidebar items

2. **Enhance Version UI**
   - Update version list with better visual hierarchy
   - Add secondary version selector in the main toolbar

3. **Improve Navigation**
   - Ensure consistent behavior when switching between ontologies
   - Consider breadcrumb navigation for complex hierarchies

4. **Security Considerations**
   - Validate all URL parameters to prevent injection attacks
   - Ensure CSRF protection for ontology editing operations

## Browser Integration Testing

The browser integration is failing with "Failed to launch the browser process" errors. This likely indicates:

1. Missing dependencies on the server (Chrome/Chromium not installed or misconfigured)
2. Permission issues with the browser executable
3. Resource constraints preventing browser launch

For development and testing, consider:
- Using manual verification steps instead of automated browser testing
- Implementing a simpler preview mechanism that doesn't require a full browser
- Testing browser integration in a more controlled environment
