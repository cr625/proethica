#!/usr/bin/env python3
"""
Test script to verify LLM connection outside the Flask application context.
This script attempts to connect to the LLM using the same method as in the guideline_analysis_service.py file,
but as a standalone script that can be run from the command line.
"""

import os
import sys
import json
import logging
import traceback
import re
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("llm_connection_test")

def get_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an environment variable value.
    
    Args:
        name: The name of the environment variable
        default: Default value if variable is not set
        
    Returns:
        The value of the environment variable or default
    """
    return os.environ.get(name, default)

def get_llm_client():
    """
    Get an LLM client based on environment variables.
    This is a simplified version of the get_llm_client function in app.utils.llm_utils.
    
    Returns:
        An LLM client (Anthropic or OpenAI)
    """
    # First check for Anthropic
    try:
        import anthropic
        api_key = get_env_var('ANTHROPIC_API_KEY')
        if api_key:
            # Determine Anthropic API version
            import pkg_resources
            anthropic_version = pkg_resources.get_distribution("anthropic").version
            client = anthropic.Anthropic(api_key=api_key)
            
            # Add version info to client for easier compatibility checks
            if anthropic_version.startswith('0.') or anthropic_version.startswith('1.'):
                client.api_version = "v1"
            else:
                client.api_version = "v2"
                
            # Detect available models
            try:
                if client.api_version == "v2" and hasattr(client, 'models'):
                    models = client.models.list()
                    available_models = [model.id for model in models.data]
                    client.available_models = available_models
                else:
                    # Default models for v1
                    client.available_models = ["claude-2.0", "claude-2.1", "claude-instant-1.2"]
            except Exception:
                # Fallback if models check fails
                client.available_models = ["claude-3-opus-20240229", "claude-3-haiku-20240307"]
                
            logger.info(f"Initialized Anthropic client version {anthropic_version} ({client.api_version}) with models: {client.available_models}")
            return client
    except (ImportError, Exception) as e:
        logger.error(f"Failed to initialize Anthropic: {str(e)}")
    
    # If Anthropic failed, try OpenAI
    try:
        import openai
        api_key = get_env_var('OPENAI_API_KEY')
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            # Test with a simple request to make sure it's configured correctly
            models = client.models.list()
            logger.info(f"Initialized OpenAI client with models available")
            return client
    except (ImportError, Exception) as e:
        logger.error(f"Failed to initialize OpenAI: {str(e)}")
    
    # If both failed, raise an exception
    raise RuntimeError("No LLM client available. Please set up Anthropic or OpenAI API keys.")

def test_llm_completion(client, prompt="Hello, world!"):
    """
    Test LLM completion with a simple prompt.
    
    Args:
        client: The LLM client to use
        prompt: The prompt to send to the LLM
    """
    logger.info("Testing LLM completion...")
    
    system_prompt = "You are a helpful assistant. Keep your response very short and concise."
    user_prompt = prompt
    
    try:
        # Get the client type
        client_type = type(client).__name__
        logger.info(f"LLM client type: {client_type}")
        
        # Try newer Anthropic API format (v2.0+)
        if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            logger.info("Using Anthropic v2+ API format")
            model_name = "claude-3-7-sonnet-latest" if hasattr(client, 'available_models') and "claude-3-7-sonnet-latest" in client.available_models else "claude-3-7-sonnet-20250219"
            logger.info(f"Using model: {model_name}")
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=model_name,
                max_tokens=100,
                temperature=0.2
            )
            response_text = response.choices[0].message.content
            logger.info(f"Response: {response_text}")
            return response_text
            
        # Try OpenAI format
        elif hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            logger.info("Using OpenAI API format")
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="gpt-4-turbo",
                max_tokens=100,
                temperature=0.2
            )
            response_text = response.choices[0].message.content
            logger.info(f"Response: {response_text}")
            return response_text
            
        # Try older Anthropic API format (v1.x)
        elif hasattr(client, 'completion'):
            logger.info("Using Anthropic v1 completion API format")
            prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
            response = client.completion(
                prompt=prompt,
                model="claude-2.0",
                max_tokens_to_sample=100,
                temperature=0.2
            )
            response_text = response.completion
            logger.info(f"Response: {response_text}")
            return response_text
            
        # Try older Anthropic API format (v1.x, messages version)
        elif hasattr(client, 'messages'):
            logger.info("Using Anthropic v1 messages API format")
            response = client.messages.create(
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                model="claude-3-7-sonnet-latest",
                max_tokens=100,
                temperature=0.2
            )
            response_text = response.content[0].text
            logger.info(f"Response: {response_text}")
            return response_text
            
        else:
            logger.error("Unsupported LLM client type")
            raise ValueError(f"Unsupported LLM client type: {client_type}. Cannot generate response.")
            
    except Exception as e:
        logger.error(f"Error testing LLM completion: {str(e)}")
        traceback.print_exc()
        return None

def test_concept_extraction(client, content):
    """
    Test concept extraction using the LLM - similar to the guideline_analysis_service.py implementation.
    
    Args:
        client: The LLM client to use
        content: The content to extract concepts from
    """
    logger.info("Testing concept extraction...")
    
    system_prompt = """
    You are an expert in ethical engineering and ontology analysis. Your task is to extract key ethical concepts
    from engineering guidelines and standards. Focus on identifying specific types of entities:
    
    1. Roles (e.g., professional positions like Engineer, Manager)
    2. Principles (e.g., core ethical principles like Honesty, Integrity)
    3. Obligations (e.g., professional duties like Public Safety, Confidentiality)
    4. Conditions (e.g., contextual factors like Budget Constraints, Time Pressure)
    5. Resources (e.g., tools or standards like Technical Specifications)
    6. Actions (e.g., professional activities like Report Safety Concern)
    7. Events (e.g., occurrences like Project Milestone, Safety Incident)
    8. Capabilities (e.g., skills like Technical Design, Leadership)
    
    For each concept, provide:
    - A label (short name for the concept)
    - A description (brief explanation of what it means in this context)
    - Type (one of the categories above)
    - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
    """
    
    user_prompt = f"""
    Please extract key ethical and engineering concepts from the following guidelines:
    
    ---
    {content[:10000]}  # Limit to first 10k chars as many LLMs have context limits
    ---
    
    Respond with a JSON array of concept objects in the following format:
    ```json
    [
        {{
            "label": "Concept Name",
            "description": "Explanation of the concept",
            "type": "role|principle|obligation|condition|resource|action|event|capability",
            "confidence": 0.9  # A number between 0-1 indicating how clearly this concept appears in the text
        }}
    ]
    ```
    
    Only include concepts that are directly referenced or implied in the guidelines. Focus on quality over quantity.
    """
    
    try:
        # First log the LLM client type and available methods for debugging
        client_type = type(client).__name__
        logger.info(f"LLM client type: {client_type}")
        
        # Try newer Anthropic API format (v2.0+)
        if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            logger.info("Using Anthropic v2+ API format")
            model_name = "claude-3-7-sonnet-latest" if hasattr(client, 'available_models') and "claude-3-7-sonnet-latest" in client.available_models else "claude-3-7-sonnet-20250219"
            logger.info(f"Using model: {model_name}")
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=model_name,
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2
            )
            response_text = response.choices[0].message.content
        
        # Try OpenAI format
        elif hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            logger.info("Using OpenAI API format")
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="gpt-4-turbo",
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2
            )
            response_text = response.choices[0].message.content
        
        # Try older Anthropic API format (v1.x)
        elif hasattr(client, 'completion'):
            logger.info("Using Anthropic v1 completion API format")
            prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
            response = client.completion(
                prompt=prompt,
                model="claude-2.0",
                max_tokens_to_sample=4000,
                temperature=0.2
            )
            response_text = response.completion
        
        # Try older Anthropic API format (v1.x, messages version)
        elif hasattr(client, 'messages'):
            logger.info("Using Anthropic v1 messages API format")
            response = client.messages.create(
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                model="claude-3-7-sonnet-latest",
                max_tokens=4000,
                temperature=0.2
            )
            response_text = response.content[0].text
        
        else:
            logger.error("Unsupported LLM client type")
            raise ValueError(f"Unsupported LLM client type: {client_type}. Cannot generate concepts.")

        # Process and clean up the response
        cleaned_text = response_text
        logger.info(f"Received LLM response with {len(response_text)} characters")
        
        # Remove markdown code blocks if present
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        code_block_match = re.search(code_block_pattern, cleaned_text)
        if code_block_match:
            cleaned_text = code_block_match.group(1)
            logger.info("Successfully extracted JSON from markdown code block")
        
        # Parse the JSON response
        response_json = json.loads(cleaned_text)
        
        # Check if response is array or has concepts key
        if isinstance(response_json, list):
            concepts = response_json
        elif isinstance(response_json, dict) and "concepts" in response_json:
            concepts = response_json["concepts"]
        else:
            concepts = []
        
        # Add IDs to concepts
        for i, concept in enumerate(concepts):
            concept["id"] = i
        
        logger.info(f"Successfully extracted {len(concepts)} concepts")
        
        # Print the first few concepts
        for i, concept in enumerate(concepts[:3]):
            logger.info(f"Concept {i+1}: {concept['label']} ({concept['type']}) - {concept['confidence']}")
        
        return concepts
        
    except Exception as e:
        logger.error(f"Error extracting concepts: {str(e)}")
        traceback.print_exc()
        return None

def generate_sample_guideline_content():
    """Generate a sample guideline for testing"""
    return """
    # Professional Code of Ethics for Engineers

    ## Introduction
    
    This code of ethics establishes the fundamental principles and standards that should guide engineers in the fulfillment of their professional duties.
    
    ## Fundamental Principles
    
    1. **Public Safety**: Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.
    
    2. **Competence**: Engineers shall perform services only in areas of their competence.
    
    3. **Honesty and Integrity**: Engineers shall issue public statements only in an objective and truthful manner.
    
    4. **Professional Development**: Engineers shall continue their professional development throughout their careers.
    
    ## Professional Obligations
    
    1. Engineers shall be objective and truthful in professional reports, statements, or testimony.
    
    2. Engineers shall not reveal confidential information without consent.
    
    3. Engineers shall disclose all known or potential conflicts of interest.
    
    4. Engineers shall not accept compensation from more than one party for the same service without disclosure.
    
    5. Engineers shall uphold the honor and dignity of the profession.
    """

def main():
    """Main function to run the test script"""
    logger.info("Starting LLM connection test...")
    
    try:
        # Try to get the LLM client
        client = get_llm_client()
        logger.info("Successfully connected to LLM!")
        
        # Test simple completion
        logger.info("\n=== Testing simple completion ===")
        test_llm_completion(client, "What is engineering ethics in one sentence?")
        
        # Test concept extraction
        logger.info("\n=== Testing concept extraction ===")
        sample_content = generate_sample_guideline_content()
        concepts = test_concept_extraction(client, sample_content)
        
        if concepts:
            # Write concepts to a file for inspection
            with open('test_concepts_output.json', 'w') as f:
                json.dump(concepts, f, indent=2)
            logger.info(f"Wrote {len(concepts)} concepts to test_concepts_output.json")
        
        logger.info("All tests completed successfully!")
        return 0
    
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
