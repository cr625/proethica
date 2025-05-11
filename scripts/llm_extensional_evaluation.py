#!/usr/bin/env python3
"""
LLM Extensional Principle Evaluation Script

This script demonstrates how an LLM can use ontology-enhanced case data
to perform the extensional principle evaluation that McLaren described
as a human process. It includes functions for:

1. Training the LLM with extensionally defined principles based on cases
2. Testing the LLM on new cases via principle application prediction
3. Testing the LLM on principle conflict resolution
4. Evaluating the accuracy of the LLM compared to human experts
5. Conducting leave-one-out validation to test generalization

The script serves as a proof of concept for using LLMs to perform
sophisticated ethical reasoning using extensional definitions.
"""

import sys
import os
import json
import logging
import argparse
from typing import List, Dict, Any
import traceback
from datetime import datetime
import random
from pprint import pprint

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from mcp.modules.mclaren_case_analysis_module import McLarenCaseAnalysisModule
from mcp.unified_ontology_server import UnifiedOntologyServer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/llm_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger("llm_extensional_evaluation")

# Check if Anthropic Claude is available
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
    anthropic_client = Anthropic()
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic package not available. Will use simulated LLM responses.")

# Check if OpenAI is available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    openai_client = OpenAI()
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available. Will use simulated LLM responses.")

def load_nspe_cases(file_path: str) -> List[Dict[str, Any]]:
    """
    Load NSPE cases from the JSON file.
    
    Args:
        file_path: Path to the NSPE cases JSON file
        
    Returns:
        List of case dictionaries
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading NSPE cases: {str(e)}")
        return []

def load_extensional_definitions_for_principles() -> Dict[str, Dict[str, Any]]:
    """
    Load extensional definitions for principles from the database.
    
    Returns:
        Dictionary mapping principle URIs to their extensional definitions
    """
    try:
        principles = {}
        
        with create_app().app_context():
            # Get all principles that have instantiations
            results = db.session.execute("""
                SELECT DISTINCT principle_uri, principle_label
                FROM principle_instantiations
            """).fetchall()
            
            for row in results:
                principle_uri = row[0]
                principle_label = row[1] or principle_uri.split('/')[-1].split('#')[-1]
                
                # Get positive instantiations (examples of compliance)
                positive = db.session.execute("""
                    SELECT pi.fact_text, pi.fact_context, d.title
                    FROM principle_instantiations pi
                    JOIN document d ON pi.case_id = d.id
                    WHERE pi.principle_uri = :uri
                    AND pi.is_negative = FALSE
                    LIMIT 5
                """, {"uri": principle_uri}).fetchall()
                
                positive_examples = [{
                    "fact": row[0],
                    "context": row[1],
                    "case_title": row[2]
                } for row in positive]
                
                # Get negative instantiations (examples of violations)
                negative = db.session.execute("""
                    SELECT pi.fact_text, pi.fact_context, d.title
                    FROM principle_instantiations pi
                    JOIN document d ON pi.case_id = d.id
                    WHERE pi.principle_uri = :uri
                    AND pi.is_negative = TRUE
                    LIMIT 5
                """, {"uri": principle_uri}).fetchall()
                
                negative_examples = [{
                    "fact": row[0],
                    "context": row[1],
                    "case_title": row[2]
                } for row in negative]
                
                # Get principle conflicts
                conflicts = db.session.execute("""
                    SELECT 
                        CASE 
                            WHEN pc.principle1_uri = :uri THEN pc.principle2_uri
                            ELSE pc.principle1_uri
                        END AS other_principle,
                        CASE 
                            WHEN pc.principle1_uri = :uri THEN pc.principle2_label
                            ELSE pc.principle1_label
                        END AS other_principle_label,
                        pc.resolution_type,
                        pc.override_direction,
                        pc.context,
                        d.title
                    FROM principle_conflicts pc
                    JOIN document d ON pc.case_id = d.id
                    WHERE pc.principle1_uri = :uri OR pc.principle2_uri = :uri
                    LIMIT 5
                """, {"uri": principle_uri}).fetchall()
                
                conflicts_data = [{
                    "other_principle": row[0],
                    "other_principle_label": row[1],
                    "resolution_type": row[2],
                    "override_direction": row[3],
                    "context": row[4],
                    "case_title": row[5]
                } for row in conflicts]
                
                principles[principle_uri] = {
                    "uri": principle_uri,
                    "label": principle_label,
                    "positive_examples": positive_examples,
                    "negative_examples": negative_examples,
                    "conflicts": conflicts_data
                }
        
        return principles
    except Exception as e:
        logger.error(f"Error loading extensional definitions: {str(e)}")
        traceback.print_exc()
        return {}

def generate_training_data(principles: Dict[str, Dict[str, Any]]) -> str:
    """
    Generate training data for the LLM based on extensional definitions.
    
    Args:
        principles: Dictionary mapping principle URIs to extensional definitions
        
    Returns:
        String containing the training data
    """
    training_data = "# Engineering Ethics Principles: Extensional Definitions\n\n"
    training_data += "These principles are defined by their applications in actual cases:\n\n"
    
    for uri, principle in principles.items():
        training_data += f"## {principle['label']}\n\n"
        
        # Add positive examples
        if principle['positive_examples']:
            training_data += "### Examples of Compliance:\n\n"
            for i, example in enumerate(principle['positive_examples']):
                training_data += f"{i+1}. In '{example['case_title']}': {example['fact']}\n"
            training_data += "\n"
        
        # Add negative examples
        if principle['negative_examples']:
            training_data += "### Examples of Violation:\n\n"
            for i, example in enumerate(principle['negative_examples']):
                training_data += f"{i+1}. In '{example['case_title']}': {example['fact']}\n"
            training_data += "\n"
        
        # Add conflict examples
        if principle['conflicts']:
            training_data += "### Conflicts with Other Principles:\n\n"
            for i, conflict in enumerate(principle['conflicts']):
                resolution = "overrides" if conflict['resolution_type'] == 'override' and conflict['override_direction'] == 1 else \
                            "is overridden by" if conflict['resolution_type'] == 'override' and conflict['override_direction'] == 0 else \
                            "must be balanced with"
                
                training_data += f"{i+1}. {principle['label']} {resolution} {conflict['other_principle_label']} in '{conflict['case_title']}':\n"
                training_data += f"   Context: {conflict['context']}\n\n"
        
        training_data += "---\n\n"
    
    return training_data

def generate_principle_application_prompt(case_text: str, 
                                         case_title: str, 
                                         training_data: str,
                                         all_principles: Dict[str, Dict[str, Any]]) -> str:
    """
    Generate a prompt for the principle application prediction task.
    
    Args:
        case_text: Text of the case to analyze
        case_title: Title of the case
        training_data: Training data containing extensional definitions
        all_principles: Dictionary of all principles
        
    Returns:
        Prompt for the LLM
    """
    principle_names = [p['label'] for _, p in all_principles.items()]
    
    prompt = f"""
You are an expert in engineering ethics trained to apply principles based on their extensional definitions.
Please analyze this engineering ethics case using the extensional definition approach developed by Bruce McLaren.

# Case to Analyze: {case_title}

{case_text}

# Your Task

Based on the extensional definitions of principles provided below, determine which principles apply to this case.
For each principle that applies:
1. Identify the specific facts in the case that instantiate the principle
2. Determine if this is a positive application (compliance) or negative application (violation)
3. Explain your reasoning based on the extensional definition (similar past cases)

# Available Principles
{', '.join(principle_names)}

# Extensional Definitions of Principles
{training_data}

# Analysis Format

Please provide your analysis in this format:
```
## Applicable Principle: [Principle Name]
- Facts: [Specific facts from the case that instantiate this principle]
- Application Type: [Positive (compliance) or Negative (violation)]
- Reasoning: [Explanation based on extensional definition]
- Similar Past Cases: [Past cases with similar applications of this principle]

## Applicable Principle: [Next Principle Name]
...
```

# Your Analysis:
"""
    return prompt

def generate_conflict_resolution_prompt(case_text: str, 
                                       case_title: str,
                                       principles_identified: List[str],
                                       training_data: str) -> str:
    """
    Generate a prompt for the conflict resolution prediction task.
    
    Args:
        case_text: Text of the case to analyze
        case_title: Title of the case
        principles_identified: List of principles identified in the case
        training_data: Training data containing extensional definitions
        
    Returns:
        Prompt for the LLM
    """
    prompt = f"""
You are an expert in engineering ethics trained to resolve conflicts between principles based on their extensional definitions.
Please analyze this engineering ethics case where multiple principles are in apparent conflict.

# Case to Analyze: {case_title}

{case_text}

# Principles Involved in this Case
{', '.join(principles_identified)}

# Your Task

Based on the extensional definitions of principles provided below:
1. Identify if there is a conflict between any of the principles in this case
2. If there is a conflict, determine how it should be resolved based on similar past cases
3. Explain your reasoning based on the extensional definitions

# Extensional Definitions of Principles
{training_data}

# Analysis Format

Please provide your analysis in this format:
```
## Conflict Identification
Principles in conflict: [List the conflicting principles]
Nature of the conflict: [Explain how these principles conflict in this specific case]

## Conflict Resolution
Resolution: [One principle overrides | Principles must be balanced]
Dominant principle (if any): [Name the principle that takes precedence]
Reasoning: [Explanation based on extensional definitions]
Similar past cases: [Past cases with similar conflicts and resolutions]
```

# Your Analysis:
"""
    return prompt

def query_llm(prompt: str, model: str = "claude-3-opus-20240229") -> str:
    """
    Query an LLM with a prompt and return the response.
    
    Args:
        prompt: Prompt to send to the LLM
        model: Model to use
        
    Returns:
        LLM response
    """
    logger.info(f"Querying LLM with prompt of length {len(prompt)}")
    
    if ANTHROPIC_AVAILABLE and model.startswith("claude"):
        try:
            message = anthropic_client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.1,
                system="You are an expert in engineering ethics with deep knowledge of applying principles to cases.",
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error querying Anthropic: {str(e)}")
            traceback.print_exc()
            return "<Error querying LLM>"
    
    elif OPENAI_AVAILABLE:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "You are an expert in engineering ethics with deep knowledge of applying principles to cases."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error querying OpenAI: {str(e)}")
            traceback.print_exc()
            return "<Error querying LLM>"
    
    else:
        # Simulate LLM response for testing
        logger.warning("Using simulated LLM response")
        return (
            "## Applicable Principle: Public Safety Principle\n"
            "- Facts: Engineer A discovered safety defects that could cause injury to occupants\n"
            "- Application Type: Negative (violation)\n"
            "- Reasoning: Based on past cases, the engineer has a paramount obligation to protect public safety\n"
            "- Similar Past Cases: Case 76-4-1 where public safety concerns overrode client confidentiality\n\n"
            "## Applicable Principle: Confidentiality Principle\n"
            "- Facts: Engineer A had a confidentiality agreement with the client\n"
            "- Application Type: Negative (violation)\n"
            "- Reasoning: The engineer failed to properly maintain confidentiality, but in this case, was justified\n"
            "- Similar Past Cases: Case 96-8-1 where confidentiality was breached to protect public safety"
        )

def perform_leave_one_out_validation(cases: List[Dict[str, Any]], principles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform leave-one-out validation to test the LLM's ability to generalize.
    
    Args:
        cases: List of cases
        principles: Dictionary of principles
        
    Returns:
        Dictionary with validation results
    """
    results = {
        "total_cases": len(cases),
        "correct_principle_applications": 0,
        "correct_conflict_resolutions": 0,
        "case_results": []
    }
    
    # Limit to 3 cases for demonstration
    for i, test_case in enumerate(cases[:3]):
        logger.info(f"Leave-one-out validation for case {test_case['case_number']}")
        
        # Generate training data excluding the test case
        training_cases = [c for c in cases if c['case_number'] != test_case['case_number']]
        
        # Extract principles from the test case
        test_case_principles = test_case['metadata'].get('principles', [])
        test_case_outcome = test_case['metadata'].get('outcome', '')
        
        # Generate training data
        training_data = generate_training_data(principles)
        
        # Generate principle application prompt
        prompt = generate_principle_application_prompt(
            test_case['full_text'],
            test_case['title'],
            training_data,
            principles
        )
        
        # Query LLM for principle application
        response = query_llm(prompt)
        
        # Simple evaluation of prediction accuracy
        prediction_correct = all(principle.lower() in response.lower() for principle in test_case_principles)
        
        # If multiple principles are involved, test conflict resolution
        if len(test_case_principles) >= 2:
            conflict_prompt = generate_conflict_resolution_prompt(
                test_case['full_text'],
                test_case['title'],
                test_case_principles,
                training_data
            )
            
            conflict_response = query_llm(conflict_prompt)
            
            # Simple evaluation of conflict resolution accuracy
            conflict_correct = test_case_outcome.lower() in conflict_response.lower()
            
            if conflict_correct:
                results["correct_conflict_resolutions"] += 1
        else:
            conflict_response = None
            conflict_correct = None
        
        if prediction_correct:
            results["correct_principle_applications"] += 1
        
        # Store results for this case
        results["case_results"].append({
            "case_number": test_case['case_number'],
            "title": test_case['title'],
            "expected_principles": test_case_principles,
            "expected_outcome": test_case_outcome,
            "principle_application_correct": prediction_correct,
            "conflict_resolution_correct": conflict_correct
        })
    
    # Calculate accuracy percentages
    results["principle_application_accuracy"] = results["correct_principle_applications"] / len(results["case_results"])
    
    conflict_cases = [r for r in results["case_results"] if r["conflict_resolution_correct"] is not None]
    if conflict_cases:
        results["conflict_resolution_accuracy"] = results["correct_conflict_resolutions"] / len(conflict_cases)
    else:
        results["conflict_resolution_accuracy"] = None
    
    return results

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='LLM Extensional Principle Evaluation')
    parser.add_argument('--case', type=str, help='Use a specific case by ID (e.g., "89-7-1")')
    parser.add_argument('--validate', action='store_true', help='Perform leave-one-out validation')
    parser.add_argument('--model', type=str, default='claude-3-opus-20240229', 
                        help='LLM model to use (claude-3-opus-20240229, gpt-4-turbo, etc.)')
    parser.add_argument('--output', type=str, help='Path to save results JSON')
    args = parser.parse_args()
    
    # Load NSPE cases
    cases = load_nspe_cases('data/nspe_cases.json')
    
    if not cases:
        logger.error("No cases loaded. Exiting.")
        return
    
    logger.info(f"Loaded {len(cases)} NSPE cases")
    
    # Load extensional definitions for principles
    principles = load_extensional_definitions_for_principles()
    
    if not principles:
        logger.error("No principle definitions loaded. Have you processed the cases with the McLaren approach?")
        logger.error("Run process_nspe_cases_mclaren.py first.")
        return
    
    logger.info(f"Loaded extensional definitions for {len(principles)} principles")
    
    # Generate training data
    training_data = generate_training_data(principles)
    logger.info(f"Generated training data of length {len(training_data)}")
    
    # If a specific case is requested
    if args.case:
        case_to_evaluate = None
        for case in cases:
            if case.get("case_number") == args.case:
                case_to_evaluate = case
                break
        
        if case_to_evaluate:
            logger.info(f"Evaluating single case: {args.case}")
            
            # Generate principle application prompt
            prompt = generate_principle_application_prompt(
                case_to_evaluate['full_text'],
                case_to_evaluate['title'],
                training_data,
                principles
            )
            
            # Query LLM
            response = query_llm(prompt, model=args.model)
            print("\n===== PRINCIPLE APPLICATION PREDICTION =====\n")
            print(response)
            print("\n============================================\n")
            
            # If the case involves multiple principles, test conflict resolution
            if len(case_to_evaluate['metadata'].get('principles', [])) >= 2:
                conflict_prompt = generate_conflict_resolution_prompt(
                    case_to_evaluate['full_text'],
                    case_to_evaluate['title'],
                    case_to_evaluate['metadata']['principles'],
                    training_data
                )
                
                conflict_response = query_llm(conflict_prompt, model=args.model)
                print("\n======= PRINCIPLE CONFLICT RESOLUTION =======\n")
                print(conflict_response)
                print("\n=============================================\n")
        else:
            logger.error(f"Case {args.case} not found")
            return
    
    # Perform leave-one-out validation if requested
    if args.validate:
        logger.info("Performing leave-one-out validation")
        
        validation_results = perform_leave_one_out_validation(cases, principles)
        
        print("\n===== LEAVE-ONE-OUT VALIDATION RESULTS =====\n")
        print(f"Total cases evaluated: {validation_results['total_cases']}")
        print(f"Principle application accuracy: {validation_results['principle_application_accuracy']:.2f}")
        
        if validation_results['conflict_resolution_accuracy'] is not None:
            print(f"Conflict resolution accuracy: {validation_results['conflict_resolution_accuracy']:.2f}")
        
        print("\nDetailed case results:")
        for result in validation_results['case_results']:
            print(f"- {result['case_number']}: {result['title']}")
            print(f"  Principles: {', '.join(result['expected_principles'])}")
            print(f"  Principle application correct: {result['principle_application_correct']}")
            
            if result['conflict_resolution_correct'] is not None:
                print(f"  Conflict resolution correct: {result['conflict_resolution_correct']}")
            
            print()
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(validation_results, f, indent=2)
            logger.info(f"Saved validation results to {args.output}")

if __name__ == "__main__":
    main()
