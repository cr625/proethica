"""
Script to test LLM API calls directly from the command line.
This helps debug issues with the guideline analysis service.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_anthropic_api(test_content, model_name=None):
    """Test Anthropic API with the specified content."""
    try:
        import anthropic
        
        # Get API key from environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not found in environment variables")
            return False
            
        client = anthropic.Anthropic(api_key=api_key)
        
        # Prepare a simple prompt
        prompt = f"""
        You are an expert in ethics and ontology analysis. Your task is to analyze the following ethical guidelines 
        and identify key concepts that can be represented in our ontology.

        The guideline content is:
        ```
        {test_content}
        ```
        
        Extract key concepts from the guidelines and categorize them.
        For each concept, provide:
        
        1. concept_name: A concise name for the concept
        2. concept_type: The type (principle, obligation, role, action, resource, or condition)
        3. description: A clear description of the concept
        
        Return the results as a JSON array.
        """
        
        print(f"Testing Anthropic API with model: {model_name or 'default'}")
        
        # List of models to try if none specified
        model_names = [model_name] if model_name else [
            "claude-3-7-sonnet-latest",
            "claude-3-7-sonnet-20250219",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229", 
            "claude-3-sonnet",
            "claude-3-opus",
            "claude-3-haiku"
        ]
        
        for model in model_names:
            try:
                print(f"Attempting with model: {model}")
                response = client.messages.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2000
                )
                
                print(f"SUCCESS with model {model}!")
                print("Response content:")
                print("=" * 40)
                print(response.content[0].text)
                print("=" * 40)
                
                # Try to parse as JSON to verify format
                try:
                    result_text = response.content[0].text.strip()
                    if "```" in result_text:
                        import re
                        json_content = re.search(r'```(?:json)?(.*?)```', result_text, re.DOTALL)
                        if json_content:
                            result_text = json_content.group(1).strip()
                    
                    parsed_json = json.loads(result_text)
                    print("\nSuccessfully parsed as JSON:")
                    print(json.dumps(parsed_json, indent=2))
                except Exception as e:
                    print(f"\nWarning: Could not parse response as JSON: {str(e)}")
                
                return True
            except Exception as e:
                print(f"Error with model {model}: {str(e)}")
                continue
        
        print("All models failed")
        return False
    
    except ImportError:
        print("Error: Anthropic package not installed. Install with: pip install anthropic")
        return False
    except Exception as e:
        print(f"Error testing Anthropic API: {str(e)}")
        return False

def test_openai_api(test_content):
    """Test OpenAI API with the specified content."""
    try:
        import openai
        
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not found in environment variables")
            return False
            
        client = openai.OpenAI(api_key=api_key)
        
        # Prepare a simple prompt
        prompt = f"""
        You are an expert in ethics and ontology analysis. Your task is to analyze the following ethical guidelines 
        and identify key concepts that can be represented in our ontology.

        The guideline content is:
        ```
        {test_content}
        ```
        
        Extract key concepts from the guidelines and categorize them.
        For each concept, provide:
        
        1. concept_name: A concise name for the concept
        2. concept_type: The type (principle, obligation, role, action, resource, or condition)
        3. description: A clear description of the concept
        
        Return the results as a JSON array.
        """
        
        print("Testing OpenAI API")
        response = client.chat.completions.create(
            model="gpt-4", # Or use the model specified in your config
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        print("SUCCESS with OpenAI API!")
        print("Response content:")
        print("=" * 40)
        result = response.choices[0].message.content
        print(result)
        print("=" * 40)
        
        # Try to parse as JSON
        try:
            parsed_json = json.loads(result)
            print("\nSuccessfully parsed as JSON:")
            print(json.dumps(parsed_json, indent=2))
        except Exception as e:
            print(f"\nWarning: Could not parse response as JSON: {str(e)}")
        
        return True
    
    except ImportError:
        print("Error: OpenAI package not installed. Install with: pip install openai")
        return False
    except Exception as e:
        print(f"Error testing OpenAI API: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test LLM API calls")
    parser.add_argument("--model", help="Specific model name to test", default=None)
    parser.add_argument("--file", help="File containing text to analyze", default=None)
    parser.add_argument("--text", help="Direct text to analyze", default=None)
    parser.add_argument("--provider", help="Provider to test (anthropic or openai)", default="anthropic")
    
    args = parser.parse_args()
    
    # Get content to test
    test_content = ""
    if args.file:
        try:
            with open(args.file, 'r') as f:
                test_content = f.read()
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return
    elif args.text:
        test_content = args.text
    else:
        test_content = """
        Ethics Guidelines for Engineers:
        
        1. Engineers shall hold paramount the safety, health, and welfare of the public.
        2. Engineers shall perform services only in areas of their competence.
        3. Engineers shall issue public statements only in an objective and truthful manner.
        4. Engineers shall act for each employer or client as faithful agents or trustees.
        5. Engineers shall avoid deceptive acts.
        6. Engineers shall conduct themselves honorably, responsibly, ethically, and lawfully.
        """
    
    print(f"Testing with content ({len(test_content)} chars):\n{test_content[:200]}...")
    
    # Test the specified provider
    if args.provider.lower() == "openai":
        test_openai_api(test_content)
    else:  # Default to Anthropic
        test_anthropic_api(test_content, args.model)

if __name__ == "__main__":
    main()
