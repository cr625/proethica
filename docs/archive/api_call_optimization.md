# API Call Optimization for AI Ethical Decision-Making Simulator

## Overview

This document outlines strategies to minimize Anthropic API calls while maintaining the quality of ethical reasoning in the AI Ethical Decision-Making Simulator. Given the limited budget for API calls, these optimization techniques are crucial for cost-effective operation.

## Optimization Strategies

### 1. Caching Layer

```python
import hashlib
import json
from functools import lru_cache
from typing import Dict, Any

class CachedLLMService:
    def __init__(self, llm_service, cache_size=1000):
        self.llm_service = llm_service
        self.llm = llm_service.get_llm()
        self.query_cache = {}
        self.get_cached_response = lru_cache(maxsize=cache_size)(self._get_response)
    
    def _get_response(self, query_hash):
        """Get response from cache using query hash."""
        if query_hash in self.query_cache:
            return self.query_cache[query_hash]
        return None
    
    def _hash_query(self, query):
        """Generate a hash for a query."""
        if isinstance(query, dict):
            query_str = json.dumps(query, sort_keys=True)
        else:
            query_str = str(query)
        return hashlib.md5(query_str.encode()).hexdigest()
    
    def query(self, prompt, **kwargs):
        """Query the LLM with caching."""
        # Create a hash of the prompt and kwargs
        query_data = {"prompt": prompt, "kwargs": kwargs}
        query_hash = self._hash_query(query_data)
        
        # Check cache
        cached_response = self.get_cached_response(query_hash)
        if cached_response:
            return cached_response
        
        # Get response from LLM
        response = self.llm(prompt, **kwargs)
        
        # Cache the response
        self.query_cache[query_hash] = response
        
        return response
    
    def clear_cache(self):
        """Clear the cache."""
        self.query_cache.clear()
        self.get_cached_response.cache_clear()
```

### 2. Prompt Engineering

#### Structured Output Format

```python
def get_structured_prompt(scenario, decision, character):
    """Generate a prompt that requests structured output."""
    prompt = f"""
    Evaluate the following ethical decision:
    
    Scenario: {scenario.description}
    Decision: {decision.description}
    Character: {character.name} ({character.role})
    
    Provide your evaluation in the following JSON format:
    
    {{
        "ethical_framework": "virtue_ethics",
        "analysis": {{
            "character_virtues": [
                {{
                    "virtue": "string",
                    "demonstrated": true|false,
                    "explanation": "string"
                }}
            ],
            "role_obligations": [
                {{
                    "obligation": "string",
                    "fulfilled": true|false,
                    "explanation": "string"
                }}
            ]
        }},
        "overall_assessment": "string",
        "score": integer (1-10)
    }}
    
    Focus on the character virtues relevant to the professional role and how well the decision aligns with those virtues.
    """
    
    return prompt
```

#### Efficient Prompting Techniques

```python
def get_efficient_prompt(scenario, decision, character):
    """Generate a prompt that maximizes information per token."""
    prompt = f"""
    SCENARIO: {scenario.description}
    DECISION: {decision.description}
    CHARACTER: {character.name} ({character.role})
    
    TASK: Evaluate this decision from a virtue ethics perspective.
    
    FORMAT:
    1. Virtues demonstrated/violated (list)
    2. Role obligations fulfilled/neglected (list)
    3. Overall ethical assessment (1-2 sentences)
    4. Score (1-10)
    
    BE CONCISE.
    """
    
    return prompt
```

### 3. Batching and Pooling

```python
class BatchProcessor:
    def __init__(self, llm_service, batch_size=5):
        self.llm_service = llm_service
        self.llm = llm_service.get_llm()
        self.batch_size = batch_size
        self.query_queue = []
        self.results = {}
    
    def add_query(self, query_id, prompt, **kwargs):
        """Add a query to the queue."""
        self.query_queue.append({
            "id": query_id,
            "prompt": prompt,
            "kwargs": kwargs
        })
        
        # Process batch if queue is full
        if len(self.query_queue) >= self.batch_size:
            self.process_batch()
    
    def process_batch(self):
        """Process a batch of queries."""
        if not self.query_queue:
            return
        
        # Combine prompts
        combined_prompt = self._combine_prompts(self.query_queue)
        
        # Send to LLM
        combined_response = self.llm(combined_prompt)
        
        # Parse responses
        parsed_responses = self._parse_responses(combined_response)
        
        # Store results
        for query_id, response in parsed_responses.items():
            self.results[query_id] = response
        
        # Clear queue
        self.query_queue = []
    
    def _combine_prompts(self, queries):
        """Combine multiple prompts into a single prompt."""
        combined = "Answer the following questions. Provide your answer after each question, starting with 'ANSWER:'.\n\n"
        
        for i, query in enumerate(queries):
            combined += f"QUESTION {i+1}: {query['prompt']}\n\n"
        
        return combined
    
    def _parse_responses(self, combined_response):
        """Parse the combined response into individual responses."""
        parsed = {}
        
        # Split by "QUESTION" markers
        parts = combined_response.split("QUESTION ")
        
        # Skip the first part (it's the instruction)
        for i, part in enumerate(parts[1:], 1):
            # Extract the answer
            answer_parts = part.split("ANSWER:", 1)
            if len(answer_parts) > 1:
                answer = answer_parts[1].strip()
                query_id = self.query_queue[i-1]["id"]
                parsed[query_id] = answer
        
        return parsed
    
    def get_result(self, query_id):
        """Get the result for a specific query."""
        # Process any remaining queries
        if self.query_queue:
            self.process_batch()
        
        return self.results.get(query_id)
```

### 4. Hybrid Approach

```python
from sentence_transformers import SentenceTransformer, util

class HybridEthicalReasoner:
    def __init__(self, llm_service, embedding_model="all-MiniLM-L6-v2", threshold=0.85):
        self.llm_service = llm_service
        self.llm = llm_service.get_llm()
        self.embedding_model = SentenceTransformer(embedding_model)
        self.threshold = threshold
        self.case_library = {}
    
    def add_to_library(self, case_id, scenario, decision, character, evaluation):
        """Add a case to the library."""
        case = {
            "scenario": scenario.description,
            "decision": decision.description,
            "character": f"{character.name} ({character.role})",
            "evaluation": evaluation
        }
        
        # Generate embedding for the case
        case_text = f"{scenario.description} {decision.description} {character.name} {character.role}"
        case_embedding = self.embedding_model.encode(case_text)
        
        # Store in library
        self.case_library[case_id] = {
            "case": case,
            "embedding": case_embedding
        }
    
    def evaluate_decision(self, scenario, decision, character):
        """Evaluate a decision using a hybrid approach."""
        # Generate query embedding
        query_text = f"{scenario.description} {decision.description} {character.name} {character.role}"
        query_embedding = self.embedding_model.encode(query_text)
        
        # Find similar cases
        similar_case = self._find_similar_case(query_embedding)
        
        if similar_case:
            # Use the similar case's evaluation
            return similar_case["case"]["evaluation"]
        else:
            # Use LLM for evaluation
            evaluation = self._evaluate_with_llm(scenario, decision, character)
            
            # Add to library for future use
            case_id = len(self.case_library) + 1
            self.add_to_library(case_id, scenario, decision, character, evaluation)
            
            return evaluation
    
    def _find_similar_case(self, query_embedding):
        """Find a similar case in the library."""
        if not self.case_library:
            return None
        
        max_similarity = 0
        most_similar_case = None
        
        for case_id, case_data in self.case_library.items():
            similarity = util.cos_sim(query_embedding, case_data["embedding"]).item()
            
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_case = case_data
        
        # Return the most similar case if it's above the threshold
        if max_similarity > self.threshold:
            return most_similar_case
        
        return None
    
    def _evaluate_with_llm(self, scenario, decision, character):
        """Evaluate a decision using the LLM."""
        prompt = f"""
        Evaluate the following ethical decision:
        
        Scenario: {scenario.description}
        Decision: {decision.description}
        Character: {character.name} ({character.role})
        
        Provide an ethical evaluation from a virtue ethics perspective,
        focusing on the character virtues relevant to the professional role.
        """
        
        return self.llm(prompt)
```

### 5. Decision Tree for Model Selection

```python
class ModelSelector:
    def __init__(self, llm_service, embedding_model="all-MiniLM-L6-v2"):
        self.llm_service = llm_service
        self.llm = llm_service.get_llm()
        self.embedding_model = SentenceTransformer(embedding_model)
        self.complexity_threshold = 0.7
        self.importance_threshold = 0.8
    
    def select_model(self, scenario, decision, character):
        """Select the appropriate model based on decision characteristics."""
        # Assess complexity
        complexity = self._assess_complexity(scenario, decision)
        
        # Assess importance
        importance = self._assess_importance(scenario, decision, character)
        
        # Select model based on complexity and importance
        if complexity > self.complexity_threshold and importance > self.importance_threshold:
            # High complexity, high importance: Use Claude
            return "claude"
        elif complexity > self.complexity_threshold:
            # High complexity, lower importance: Use Claude with caching
            return "claude_cached"
        elif importance > self.importance_threshold:
            # Lower complexity, high importance: Use hybrid approach
            return "hybrid"
        else:
            # Lower complexity, lower importance: Use embedding similarity
            return "embedding"
    
    def _assess_complexity(self, scenario, decision):
        """Assess the complexity of a decision."""
        # Factors that indicate complexity:
        # - Length of scenario and decision descriptions
        # - Number of entities involved
        # - Presence of conflicting values or principles
        
        # Simple heuristic based on length
        combined_text = f"{scenario.description} {decision.description}"
        length_score = min(len(combined_text) / 1000, 1.0)
        
        # Count entities (characters, resources)
        entity_count = len(scenario.characters) + len(scenario.resources)
        entity_score = min(entity_count / 10, 1.0)
        
        # Combine scores (could be more sophisticated)
        complexity = (length_score + entity_score) / 2
        
        return complexity
    
    def _assess_importance(self, scenario, decision, character):
        """Assess the importance of a decision."""
        # Factors that indicate importance:
        # - Character's role tier
        # - Severity of conditions
        # - Potential consequences
        
        # Role tier (assuming higher tier = more important)
        role_score = character.role.tier / 5 if hasattr(character.role, 'tier') else 0.5
        
        # Condition severity
        severity_sum = sum(c.severity for c in character.conditions) if hasattr(character, 'conditions') else 0
        severity_score = min(severity_sum / 20, 1.0)
        
        # Combine scores
        importance = (role_score + severity_score) / 2
        
        return importance
    
    def evaluate_decision(self, scenario, decision, character):
        """Evaluate a decision using the selected model."""
        model = self.select_model(scenario, decision, character)
        
        if model == "claude":
            # Use Claude directly
            return self._evaluate_with_claude(scenario, decision, character)
        elif model == "claude_cached":
            # Use Claude with caching
            return self._evaluate_with_claude_cached(scenario, decision, character)
        elif model == "hybrid":
            # Use hybrid approach
            return self._evaluate_with_hybrid(scenario, decision, character)
        else:
            # Use embedding similarity
            return self._evaluate_with_embedding(scenario, decision, character)
    
    def _evaluate_with_claude(self, scenario, decision, character):
        """Evaluate using Claude directly."""
        prompt = f"""
        Evaluate the following ethical decision:
        
        Scenario: {scenario.description}
        Decision: {decision.description}
        Character: {character.name} ({character.role})
        
        Provide a comprehensive ethical evaluation from a virtue ethics perspective.
        """
        
        return self.llm(prompt)
    
    def _evaluate_with_claude_cached(self, scenario, decision, character):
        """Evaluate using Claude with caching."""
        # Implementation would use the CachedLLMService
        pass
    
    def _evaluate_with_hybrid(self, scenario, decision, character):
        """Evaluate using hybrid approach."""
        # Implementation would use the HybridEthicalReasoner
        pass
    
    def _evaluate_with_embedding(self, scenario, decision, character):
        """Evaluate using embedding similarity only."""
        # Implementation would use only embedding similarity to find similar cases
        pass
```

## Implementation Plan

### Phase 1: Basic Caching (Week 1)
1. Implement the CachedLLMService
2. Add caching to the DecisionEngine and EventEngine
3. Test with existing scenarios to measure API call reduction

### Phase 2: Prompt Optimization (Week 2)
1. Redesign prompts for efficiency
2. Implement structured output formats
3. Test and measure token usage reduction

### Phase 3: Advanced Techniques (Week 3)
1. Implement batching for similar queries
2. Develop the hybrid reasoning approach
3. Create the model selection decision tree

### Phase 4: Integration and Testing (Week 4)
1. Integrate all optimization techniques
2. Develop monitoring for API usage
3. Conduct comprehensive testing with various scenarios
4. Measure and report on cost savings

## Expected Outcomes

With these optimization strategies, we expect to achieve:

1. **50-70% reduction** in Anthropic API calls through caching alone
2. **20-30% reduction** in tokens per call through prompt optimization
3. **40-60% offloading** of queries to embedding similarity for simple cases
4. Overall **70-80% cost reduction** while maintaining ethical reasoning quality

## Monitoring and Continuous Improvement

To ensure ongoing optimization:

1. Implement API call tracking and analytics
2. Regularly review cache hit rates and adjust cache size
3. Analyze which types of queries benefit most from which optimization techniques
4. Continuously refine the decision tree for model selection
5. Periodically evaluate the quality of ethical reasoning to ensure it meets standards

## Conclusion

By implementing these API call optimization strategies, the AI Ethical Decision-Making Simulator can operate within budget constraints while maintaining high-quality ethical reasoning. The hybrid approach, combining Claude's sophisticated reasoning with efficient embedding-based similarity search, provides an optimal balance of cost and quality.
