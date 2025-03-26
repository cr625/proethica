# Agent-Based Architecture for Ethical Decision-Making

This document describes the agent-based architecture implemented for the AI Ethical Decision-Making Simulator. The architecture uses specialized agents to analyze decisions from different perspectives, providing a more comprehensive ethical evaluation.

## Overview

The agent-based architecture consists of:

1. **Base Agent**: A foundation class that defines the common interface for all agents
2. **Specialized Agents**: Agents that focus on specific aspects of ethical decision-making
3. **Agent Orchestrator**: A coordinator that manages the flow of information between agents

The current implementation includes a Guidelines Agent that analyzes decisions based on relevant guidelines. The architecture is designed to be extensible, allowing for additional agents to be added in the future.

## Components

### BaseAgent

The `BaseAgent` class provides a common interface for all specialized agents. It defines:

- A standard `analyze` method that takes scenario data, decision text, and options
- Helper methods for formatting options and extracting scenario data
- Logging and error handling

### GuidelinesAgent

The `GuidelinesAgent` specializes in retrieving and analyzing guidelines for ethical decision-making. It:

1. Uses vector similarity search to find relevant guidelines
2. Formats the guidelines for LLM input
3. Analyzes how each decision option aligns with the guidelines
4. Provides alignment scores, reasoning, and key principles

### AgentOrchestrator

The `AgentOrchestrator` coordinates between specialized agents and synthesizes their analyses. It:

1. Initializes and manages specialized agents
2. Processes decisions through each agent
3. Synthesizes the results into a comprehensive evaluation
4. Provides a final response with ethical scores and recommendations

## Integration with Simulation Controller

The agent-based architecture is integrated with the `SimulationController` through a configuration parameter:

```python
controller = SimulationController(
    scenario_id=scenario_id,
    use_agent_orchestrator=True  # Enable agent-based processing
)
```

When enabled, the `SimulationController` will use the `AgentOrchestrator` to process decisions, providing more comprehensive ethical analyses.

## Running with Agent Orchestrator

There are two ways to enable the agent orchestrator:

1. **Environment Variable**: Set `USE_AGENT_ORCHESTRATOR=true` before running the application
2. **Run Script**: Use the `scripts/run_with_agents.py` script to run the application with the agent orchestrator enabled

Example:

```bash
# Method 1: Environment variable
export USE_AGENT_ORCHESTRATOR=true
python run.py

# Method 2: Run script
./scripts/run_with_agents.py
```

## Testing the Agent Orchestrator

You can test the agent orchestrator using:

1. **Test Script**: Run `scripts/test_guidelines_agent.py` to test the Guidelines Agent directly
2. **Web Interface**: Visit `/simulation/api/test_agents/<scenario_id>` to test the agent orchestrator through the web interface

Example:

```bash
# Test script
./scripts/test_guidelines_agent.py

# Web interface
# Visit http://localhost:5000/simulation/api/test_agents/1
```

## Future Extensions

The agent-based architecture is designed to be extensible. Future agents could include:

1. **Ontology Agent**: Analyzes decisions based on the ontology of the world
2. **Cases Agent**: Analyzes decisions based on similar cases
3. **Ruleset Agent**: Analyzes decisions based on specific rules or laws
4. **References Agent**: Analyzes decisions based on academic or professional references

To add a new agent:

1. Create a new agent class that inherits from `BaseAgent`
2. Implement the `analyze` method
3. Add the agent to the `AgentOrchestrator`

## Benefits

The agent-based architecture provides several benefits:

1. **Modular Analysis**: Each agent focuses on a specific aspect of ethical decision-making
2. **Comprehensive Evaluation**: The combined analyses provide a more thorough evaluation
3. **Transparent Reasoning**: Each agent provides its reasoning, making the evaluation process transparent
4. **Extensible Framework**: New agents can be added to cover additional aspects of ethical decision-making
5. **Improved Decision Quality**: The multi-agent approach leads to more nuanced and balanced ethical evaluations
