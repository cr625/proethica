ere is # Simulation Decision Text Fix

## Current Status
- Analyzing the issue with the simulation decision text display
- Planning to implement a fix to correctly display decision text in the UI

## Issue Description
When a user reaches a decision point in the simulation:
1. The timeline correctly shows that a decision is required
2. The decision options are displayed correctly
3. However, the text displayed in the "Current Event" section is showing the previous event's description instead of the decision's name and description

For example, in scenario 2:
- The event before the decision shows: "Alex Rodriguez faces an ethical dilemma about whether to formally report the design deficiency..."
- When the user clicks next, the same text is shown instead of the decision's text: "Decide Whether to Report Design Deficiency" and its description

## Implementation Plan
1. Modify the `updateCurrentEvent` function in `simulate_scenario.html` to:
   - Check if the current event is a decision point
   - If it is, display the action name and description instead of the event description
   - Keep the existing decision options functionality intact

## Progress
- [x] Analyzed the code to understand the current implementation
- [x] Created a plan for the UI fix
- [x] Implemented the changes in `app/templates/simulate_scenario.html`
- [x] Tested the changes to ensure they work as expected

## Implementation Details
The following changes were made to fix the decision text display issue:

1. Modified the `updateCurrentEvent` function in `simulate_scenario.html` to:
   - Check if the current event is a decision point using the `isDecisionPoint` function
   - For decision points, display the action name and description instead of the event description
   - Keep the existing functionality for non-decision events

```javascript
// Check if this is a decision point
const isDecisionEvent = isDecisionPoint(currentEvent);

// For decision points, display the action name and description instead of the event description
if (isDecisionEvent && currentEvent.action) {
    currentEventDisplay.innerHTML = `
        <h4>${formatTime(currentEvent.event_time)}</h4>
        <h5>${currentEvent.action.name || 'Decision Required'}</h5>
        <p>${currentEvent.action.description || currentEvent.description}</p>
        ${characterName ? `<p><strong>Character:</strong> ${characterName}</p>` : ''}
    `;
} else {
    currentEventDisplay.innerHTML = `
        <h4>${formatTime(currentEvent.event_time)}</h4>
        <p>${currentEvent.description}</p>
        ${characterName ? `<p><strong>Character:</strong> ${characterName}</p>` : ''}
    `;
}
```

## Results
The changes have been successfully implemented and tested. Now when a user reaches a decision point in the simulation:

1. The timeline correctly shows that a decision is required
2. The decision options are displayed correctly
3. The "Current Event" section now displays the correct action name and description for the decision, rather than showing the previous event's description

For example, in scenario 2, when reaching the decision point about reporting the design deficiency, the UI now shows:
- The action name: "Decide Whether to Report Design Deficiency"
- The action description: "Alex Rodriguez must decide whether to formally report the design deficiency to Dr. Jordan Patel and Sam Washington. This decision represents the central ethical dilemma of the scenario, balancing professional responsibility against project constraints and team loyalty."

This provides users with the proper context for making their decision, rather than showing the previous event's description.
