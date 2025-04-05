# Simulation Decision Options and Evaluation Fix

## Problem

The simulation timeline had two issues:
1. Decision options were not displaying properly, showing up as "Option undefined" instead of the actual decision options.
2. The LLM evaluation functionality was broken, showing an error: "Error evaluating decision: 'LLMService' object has no attribute 'get_llm'".

## Investigation

After examining the code, we found:
1. In the `showDecisionPoint` function in `simulate_scenario.html`, it was trying to call `toLowerCase()` on `optionText` without checking if it was defined first.
2. The decision options in the database were not properly formatted.
3. In the `_evaluate_decision` method of the `SimulationController` class, it was trying to call `self.llm_service.get_llm()`, but the `LLMService` class doesn't have a `get_llm` method. Instead, it has an `llm` attribute that can be used directly.

## Solution

We implemented a three-part solution:

1. Fixed the `showDecisionPoint` function in `simulate_scenario.html` to handle undefined option text:
   - Added a fallback value for `optionText` if it's undefined
   - Added a type check before calling `toLowerCase()`

```javascript
// Extract the option number and description for better formatting
let optionText = option.description || `Option ${option.id}`;
let optionClass = 'btn-outline-primary';

// Apply different styling based on the option content
if (typeof optionText === 'string') {
    if (optionText.toLowerCase().includes('ethical') ||
        optionText.toLowerCase().includes('integrity') ||
        optionText.toLowerCase().includes('welfare') ||
        optionText.toLowerCase().includes('safety')) {
        optionClass = 'btn-outline-success';
    } else if (optionText.toLowerCase().includes('compromise') ||
        optionText.toLowerCase().includes('balance')) {
        optionClass = 'btn-outline-info';
    } else if (optionText.toLowerCase().includes('efficiency') ||
        optionText.toLowerCase().includes('prioritize')) {
        optionClass = 'btn-outline-warning';
    }
}
```

2. Created a script to update the decision options in the database with scenario-specific options:
   - Created `scripts/update_decision_options.py` to update the options for specific actions
   - Added scenario-specific decision options for the "Report or Not" decision (Action ID 17)
   - Added scenario-specific decision options for the budget meeting decision (Action ID 18)

```python
# Specific options for action ID 17 (Report or Not decision)
action_17.options = [
    {
        'id': 1,
        'description': 'Report the deficiency immediately, prioritizing safety and professional integrity'
    },
    {
        'id': 2,
        'description': 'Conduct additional tests to confirm the deficiency before reporting'
    },
    {
        'id': 3,
        'description': 'Address the issue internally without formal reporting to avoid delays'
    },
    {
        'id': 4,
        'description': 'Consult with senior engineers before making a decision'
    }
]
```

3. Created a script to fix the LLM evaluation functionality:
   - Created `scripts/fix_llm_evaluation.py` to monkey patch the `_evaluate_decision` method
   - Modified the method to use `self.llm_service.llm` directly instead of calling `get_llm()`

```python
# Get evaluation from LLM
try:
    # Use the llm attribute directly instead of calling get_llm()
    evaluation_text = self.llm_service.llm(prompt)
    
    # For now, return a simple evaluation
    # In the future, we'll parse the LLM output to extract structured data
    evaluation = {
        'raw_evaluation': evaluation_text,
        'structured_evaluation': {
            'alignment_score': 7,  # Placeholder
            'virtues_demonstrated': ['integrity', 'compassion'],  # Placeholder
            'virtues_violated': [],  # Placeholder
            'character_reflection': 'The decision reflects positively on the character as a professional',  # Placeholder
            'recommendations': 'A virtuous professional would consider...'  # Placeholder
        }
    }
    
    return evaluation
except Exception as e:
    logger.error(f"Error evaluating decision: {str(e)}")
    return {
        'raw_evaluation': f"Error evaluating decision: {str(e)}",
        'structured_evaluation': None
    }
```

## Results

After implementing these fixes:
1. The decision options now display correctly in the simulation timeline
2. The options are scenario-specific and relevant to the ethical dilemmas presented
3. Users can now make meaningful choices at decision points in the simulation
4. The LLM evaluation functionality should now work correctly, providing ethical analysis for each decision

## Future Improvements

1. Implement the branching timeline functionality mentioned in the "Future Implementation" note
2. Add more detailed ethical analysis for each decision by parsing the LLM output
3. Improve the styling and presentation of the decision options
4. Add more decision points and options to the simulation
