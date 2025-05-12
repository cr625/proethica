"""
Script to test JSON parsing logic from the guideline analysis service.
This helps identify why we might be getting "No principles found" despite valid responses.
"""

import json
import re
import sys

# Sample responses to test with
SAMPLE_RESPONSES = [
    # Response 1: Standard JSON array
    """
    [
      {
        "concept_name": "Public Safety",
        "concept_type": "principle",
        "description": "Engineers must prioritize the safety of the public above all other considerations."
      },
      {
        "concept_name": "Professional Competence",
        "concept_type": "obligation",
        "description": "Engineers must only work within their areas of professional expertise."
      }
    ]
    """,
    
    # Response 2: JSON wrapped in markdown code blocks
    """
    ```json
    [
      {
        "concept_name": "Public Safety",
        "concept_type": "principle",
        "description": "Engineers must prioritize the safety of the public above all other considerations."
      }
    ]
    ```
    """,
    
    # Response 3: JSON wrapped in a JSON object
    """
    {
      "concepts": [
        {
          "concept_name": "Public Safety",
          "concept_type": "principle",
          "description": "Engineers must prioritize the safety of the public above all other considerations."
        }
      ]
    }
    """,
    
    # Response 4: Problematic JSON that might cause issues
    """
    [
      {
        "concept_name": "Public Safety",
        "concept_type": "principle",
        "description": "Engineers must prioritize the safety of the public above all other considerations."
      },
    ]
    """,
    
    # Response 5: Empty array
    """
    []
    """,
    
    # Response 6: Text with JSON embedded
    """
    Here are the key concepts I've identified:

    ```json
    [
      {
        "concept_name": "Public Safety",
        "concept_type": "principle",
        "description": "Engineers must prioritize the safety of the public above all other considerations."
      }
    ]
    ```

    These concepts represent the core ethical principles in the guidelines.
    """
]

def parse_json_response(result_text):
    """
    Parse LLM response text into JSON, exactly mimicking the logic in the GuidelineAnalysisService.
    Returns a tuple of (concepts, success, error_message).
    """
    print(f"Input text length: {len(result_text)} characters")
    print(f"Input text snippet: {result_text[:100]}...")
    
    # 1. Clean up the response
    result_text = result_text.strip()
    
    # 2. Extract JSON from code blocks if present
    if "```" in result_text:
        print("Detected code block markers ```")
        try:
            import re
            json_content = re.search(r'```(?:json)?(.*?)```', result_text, re.DOTALL)
            if json_content:
                extracted_text = json_content.group(1).strip()
                print(f"Extracted content from code block: {len(extracted_text)} chars")
                result_text = extracted_text
        except Exception as e:
            print(f"Error extracting from code block: {str(e)}")
    
    # 3. Try to parse the JSON
    try:
        result = json.loads(result_text)
        print(f"Successfully parsed JSON of type: {type(result).__name__}")
        
        # 4. Extract concepts based on structure
        concepts = []
        
        if isinstance(result, list):
            print(f"Result is a list with {len(result)} items")
            concepts = result
        elif isinstance(result, dict):
            print(f"Result is a dict with keys: {', '.join(result.keys())}")
            if "concepts" in result:
                print(f"Found 'concepts' key with {len(result['concepts'])} items")
                concepts = result["concepts"]
            else:
                # Try to find any array in the result
                for key, value in result.items():
                    if isinstance(value, list) and len(value) > 0:
                        print(f"Found list in key '{key}' with {len(value)} items")
                        concepts = value
                        break
        
        # 5. Check if we got any concepts
        if not concepts:
            print("WARNING: No concepts found in the parsed JSON")
            return [], False, "No concepts found in the response"
            
        print(f"Final extraction: {len(concepts)} concepts")
        for i, concept in enumerate(concepts):
            if i < 3:  # Just show the first few
                print(f"  Concept {i+1}: {concept.get('concept_name', 'Unknown')}")
        
        return concepts, True, None
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        return [], False, f"JSON parsing error: {str(e)}"
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return [], False, f"Unexpected error: {str(e)}"

def main():
    print("Testing JSON parsing logic from guideline analysis service\n")
    
    # Test with example file if provided
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                print(f"Testing with file: {sys.argv[1]}")
                test_response = f.read()
                print("\n" + "="*50)
                print(f"TEST CASE: File {sys.argv[1]}")
                print("="*50)
                concepts, success, error = parse_json_response(test_response)
                print(f"Success: {success}, Concepts found: {len(concepts)}")
                print("="*50 + "\n")
                return
        except Exception as e:
            print(f"Error reading file: {str(e)}")
    
    # Test with our sample responses
    for i, response in enumerate(SAMPLE_RESPONSES):
        print("\n" + "="*50)
        print(f"TEST CASE {i+1}: {response[:50]}...")
        print("="*50)
        concepts, success, error = parse_json_response(response)
        print(f"Success: {success}, Concepts found: {len(concepts)}")
        print("="*50 + "\n")

if __name__ == "__main__":
    main()
