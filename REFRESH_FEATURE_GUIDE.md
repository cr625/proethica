# Refresh from OntServe - User Guide

## Overview
The new **"Refresh from OntServe"** button addresses synchronization issues between ProEthica and OntServe by allowing you to pull the latest versions of committed entities from OntServe.

## Why This Feature Exists

### The Problem
Previously, ProEthica maintained its own copy of committed entities, which could become out of sync when:
- Entities were edited directly in OntServe
- Multiple users modified the same ontology
- External systems updated OntServe data
- Manual TTL file edits were made

### The Solution
The "Refresh from OntServe" button fetches live data from OntServe and updates ProEthica's records to match, ensuring you always see the current state of your ontology.

## How to Use

1. **Navigate to Entity Review Page**
   - Go to: `http://localhost:5000/scenario_pipeline/case/[CASE_ID]/entities/review`
   - Example: `http://localhost:5000/scenario_pipeline/case/18/entities/review`

2. **Click "Refresh from OntServe" Button**
   - Located in the top toolbar (blue button with refresh icon)
   - Between "Back to Step 1" and "Clear All Entities" buttons

3. **Review Results**
   - A dialog shows what was refreshed:
     - Number of entities checked
     - How many were modified
     - How many remained unchanged
     - Any entities not found in OntServe

4. **Page Automatically Reloads**
   - If changes were detected, the page reloads to show updated data
   - Modified entities now display their current OntServe values

## What Gets Refreshed

### Entities Refreshed
- All entities marked as "Committed" in ProEthica
- Both classes (from proethica-intermediate-extracted)
- And individuals (from proethica-case-N)

### Fields Updated
- **Label**: Entity names and titles
- **Parent URI**: Hierarchical relationships
- **Description/Comment**: Entity descriptions
- **Properties**: Additional metadata

## Example Scenario

1. **Initial State**:
   - ProEthica shows: "Technical Evaluation Report"
   - Someone edits in OntServe to: "Technical Evaluation Report (Revised)"

2. **Without Refresh**:
   - ProEthica still shows old name: "Technical Evaluation Report"
   - Data is out of sync

3. **After Clicking Refresh**:
   - ProEthica fetches from OntServe
   - Updates to show: "Technical Evaluation Report (Revised)"
   - Data is synchronized

## Understanding the Results

### Success Messages

**"Refreshed N entities: X unchanged, Y modified"**
- N = Total entities checked
- X = Entities that matched OntServe (no changes needed)
- Y = Entities that were updated with OntServe data

**"N entities not found in OntServe"**
- These entities exist in ProEthica but were deleted from OntServe
- May need to re-commit or investigate why they're missing

### Change Detection
The system detects changes in:
- Entity labels (names)
- Parent relationships (hierarchy)
- Descriptions and comments
- Any other metadata fields

## Best Practices

1. **Refresh Before Important Work**
   - Always refresh before making new extractions
   - Ensures you're working with current ontology state

2. **Refresh After External Edits**
   - If you or others edit ontologies in OntServe
   - After running scripts that modify TTL files
   - When collaborating with other users

3. **Regular Synchronization**
   - Consider refreshing at the start of each work session
   - Especially in multi-user environments

## Technical Details

### What Happens Behind the Scenes
1. ProEthica queries OntServe database for all committed entities
2. Compares OntServe versions with ProEthica's cached versions
3. Identifies differences in labels, URIs, and metadata
4. Updates ProEthica's database with current OntServe values
5. Maintains commit status and provenance information

### Performance
- Typically completes in 1-2 seconds for ~10 entities
- Scales linearly with number of committed entities
- Only updates entities that have actually changed

## Limitations

1. **One-Way Sync**
   - Only pulls from OntServe to ProEthica
   - Does not push ProEthica changes back to OntServe
   - Use "Commit to OntServe" for that direction

2. **Committed Entities Only**
   - Only refreshes entities already committed
   - Uncommitted entities remain unchanged
   - Draft work is preserved

3. **Requires OntServe Availability**
   - OntServe must be running and accessible
   - Database connection must be working
   - Will show error if OntServe is down

## Future Enhancements (Planned)

1. **Automatic Sync Indicators**
   - Visual badges showing sync status
   - "Out of Sync" warnings
   - Last synced timestamps

2. **Selective Refresh**
   - Choose specific entities to refresh
   - Bulk operations for large ontologies

3. **Conflict Resolution**
   - Handle cases where both systems have changes
   - Merge capabilities for complex edits

4. **Background Sync**
   - Automatic periodic synchronization
   - Real-time change notifications

## Troubleshooting

### "Error refreshing entities"
- Check OntServe is running: `http://localhost:8082`
- Verify database connection
- Check logs for specific error messages

### "0 entities refreshed"
- Ensure entities are marked as committed
- Verify case has committed entities
- Check OntServe has the expected ontologies

### Changes Not Appearing
- Try hard refresh (Ctrl+F5 or Cmd+Shift+R)
- Clear browser cache
- Check browser console for errors

## Summary

The "Refresh from OntServe" button is a critical synchronization tool that:
- Ensures data consistency between ProEthica and OntServe
- Prevents working with outdated ontology information
- Supports collaborative ontology development
- Maintains single source of truth (OntServe)

Use it regularly to keep your ProEthica workspace synchronized with the authoritative ontology storage in OntServe.