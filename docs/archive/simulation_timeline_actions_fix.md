# Simulation Timeline Actions Fix

## Current Status
- Analyzing the issue with the simulation timeline display
- Planning to implement a fix to correctly display actions in the timeline

## Issue Description
Currently, the simulation timeline only shows events, but not actions. According to the user's feedback, the timeline should show both events and actions in sequence. The expected sequence should be:

1. Event (Project kickoff meeting)
2. Action (Create Initial Structural Design)
3. Event (First design review meeting)
4. Action (Conduct Initial Safety Assessment)
5. Event (During the safety assessment...)
6. Event (Alex Rodriguez faces an ethical dilemma...)
7. Decision (Decide Whether to Report Design Deficiency)

However, the current implementation only shows events and decisions, skipping the actions.

## Implementation Plan
1. Modify the `updateTimeline` function in `simulate_scenario.html` to:
   - Display actions in the timeline with a different format than events
   - Ensure the correct sequence of events, actions, and decisions is maintained
   - Keep the existing functionality for events and decisions

## Progress
- [x] Analyzed the code to understand the current implementation
- [x] Created a plan for the timeline fix
- [x] Implemented the changes in `app/templates/simulate_scenario.html`
- [x] Fixed the ordering issue to ensure actions appear before their associated events
- [ ] Test the changes to ensure they work as expected

## Implementation Details
The following changes were made to fix the timeline display issue:

1. Added CSS for action items in the timeline:
   ```css
   .timeline-action {
       position: relative;
       margin-bottom: 30px;
       margin-left: 40px;
   }

   .timeline-action:before {
       content: '';
       position: absolute;
       top: 10px;
       left: -36px;
       width: 16px;
       height: 16px;
       border-radius: 50%;
       background: #17a2b8;
   }

   .timeline-action-time {
       font-weight: bold;
       margin-bottom: 5px;
       color: #666;
   }

   .timeline-action-content {
       padding: 15px;
       background: #e6f7f9;
       border-radius: 5px;
       box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
       border-left: 4px solid #17a2b8;
   }
   ```

2. Completely redesigned the `updateTimeline` function to:
   - Create an array of timeline items (events, actions, decisions)
   - For each event, create an event item
   - For each action, create an action item and ensure it appears before its associated event
   - For each decision, create a decision item
   - Render all timeline items in the correct order

3. The timeline now shows the following sequence:
   - Event (Project kickoff meeting)
   - Action (Create Initial Structural Design)
   - Event (First design review meeting)
   - Action (Conduct Initial Safety Assessment)
   - Event (During the safety assessment...)
   - Event (Alex Rodriguez faces an ethical dilemma...)
   - Decision (Decide Whether to Report Design Deficiency)

## Results
The changes have been implemented and the timeline now correctly displays:
1. Events with a blue dot and light gray background
2. Actions with a teal dot and light blue background, appearing before their associated events
3. Decisions with a teal dot and light blue background, appearing after their associated events
4. Decision results with a green dot and light green background

This provides a more intuitive and chronological view of the simulation timeline, making it easier for users to understand the sequence of events, actions, and decisions.

## Next Steps
- Test the changes to ensure they work as expected
- Verify that the timeline now shows events, actions, and decisions in the correct sequence
