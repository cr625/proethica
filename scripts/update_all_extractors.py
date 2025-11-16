#!/usr/bin/env python3
"""Update all entity extractors to have MCP integration following the Roles extractor pattern."""

import os
import sys
import re
from pathlib import Path

# Add ProEthica to path
sys.path.insert(0, '/home/chris/onto/proethica')

# Define the extractors that need updating
EXTRACTORS_TO_UPDATE = [
    'states',
    'actions', 
    'events',
    'capabilities',
    'constraints'
]

def add_get_prompt_for_preview_method(file_path, entity_type):
    """Add the _get_prompt_for_preview method to an extractor."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if method already exists
    if '_get_prompt_for_preview' in content:
        print(f"✅ {entity_type}: Already has _get_prompt_for_preview method")
        return False
    
    # Find where to insert the method (after concept_type property or after __init__)
    insert_pattern = r'(@property\s+def\s+concept_type.*?return.*?\n)'
    match = re.search(insert_pattern, content, re.DOTALL)
    
    if not match:
        # Try to find after __init__ method
        insert_pattern = r'(def\s+__init__.*?\n(?:\s+.*?\n)*?\s+.*?)\n\s+def'
        match = re.search(insert_pattern, content, re.DOTALL)
    
    if not match:
        print(f"❌ {entity_type}: Could not find insertion point")
        return False
    
    # Create the new method
    new_method = f'''
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_{entity_type}_prompt_with_mcp(text)
'''
    
    # Insert the method
    insert_pos = match.end()
    new_content = content[:insert_pos] + new_method + content[insert_pos:]
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ {entity_type}: Added _get_prompt_for_preview method")
    return True

def add_mcp_prompt_method(file_path, entity_type):
    """Add the _create_XXX_prompt_with_mcp method to an extractor."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if method already exists
    if f'_create_{entity_type}_prompt_with_mcp' in content:
        print(f"✅ {entity_type}: Already has MCP prompt method")
        return False
    
    # Find where to insert (after _extract_with_llm or at end of class)
    class_end_pattern = r'class\s+\w+Extractor.*?(?=\nclass|\Z)'
    class_match = re.search(class_end_pattern, content, re.DOTALL)
    
    if not class_match:
        print(f"❌ {entity_type}: Could not find class definition")
        return False
    
    # Create the MCP prompt method
    entity_type_title = entity_type.title()
    entity_type_upper = entity_type.upper()
    entity_type_plural = entity_type if entity_type.endswith('s') else entity_type + 's'
    
    mcp_method = f'''
    def _create_{entity_type}_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced {entity_type} prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching {entity_type} context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing {entity_type_plural} from ontology
            existing_{entity_type_plural} = external_client.get_all_{entity_type}_entities()
            
            # Build ontology context
            ontology_context = "EXISTING {entity_type_upper} IN ONTOLOGY:\\n"
            if existing_{entity_type_plural}:
                ontology_context += f"Found {{len(existing_{entity_type_plural})}} existing {entity_type} concepts:\\n"
                for item in existing_{entity_type_plural}:  # Show all items
                    label = item.get('label', 'Unknown')
                    description = item.get('description', 'No description')
                    ontology_context += f"- {{label}}: {{description}}\\n"
            else:
                ontology_context += "No existing {entity_type_plural} found in ontology (fresh setup)\\n"
            
            logger.info(f"Retrieved {{len(existing_{entity_type_plural})}} existing {entity_type_plural} from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{{ontology_context}}

You are an ontology-aware extractor analyzing an ethics guideline to extract {entity_type_upper}.

IMPORTANT: Consider the existing {entity_type_plural} above when extracting. For each {entity_type} you extract:
1. Check if it matches an existing {entity_type} (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Extract {entity_type}-related concepts from the professional ethics guideline.

GUIDELINE TEXT:
{{text}}

OUTPUT FORMAT:
Return STRICT JSON with an array under key '{entity_type_plural}':
[
  {{{{
    "label": "{entity_type_title} name",
    "description": "Description of the {entity_type}", 
    "confidence": 0.9,
    "is_existing": false,
    "ontology_match_reasoning": "Reasoning for match or new classification"
  }}}}
]

Focus on accuracy over quantity. Extract only clear, unambiguous {entity_type_plural}.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for {entity_type_plural}: {{e}}")
            logger.info("Falling back to standard {entity_type} prompt")
            return self._create_{entity_type}_prompt(text)
'''
    
    # Insert before the last method or at end of class
    insert_pos = class_match.end() - 1  # Insert just before end of class
    
    # Find a better insertion point - after the last method
    last_method_pattern = r'(\n\s+def\s+\w+.*?(?:\n(?!\s+def).*)*)'
    methods = list(re.finditer(last_method_pattern, class_match.group(), re.MULTILINE))
    if methods:
        last_method_end = methods[-1].end() + class_match.start()
        insert_pos = last_method_end
    
    new_content = content[:insert_pos] + mcp_method + content[insert_pos:]
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ {entity_type}: Added MCP prompt method")
    return True

def update_extract_with_llm(file_path, entity_type):
    """Update _extract_with_llm to always use MCP."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the _extract_with_llm method
    pattern = r'def\s+_extract_with_llm\(self.*?\).*?:\n(.*?)(?=\n\s+def|\nclass|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print(f"⚠️  {entity_type}: No _extract_with_llm method found")
        return False
    
    method_body = match.group(1)
    
    # Check if it's already using MCP unconditionally
    if f'_create_{entity_type}_prompt_with_mcp' in method_body:
        print(f"✅ {entity_type}: Already using MCP in _extract_with_llm")
        return False
    
    # Replace conditional MCP usage with unconditional
    old_pattern = r'use_external_mcp\s*=.*?\n\s+if\s+use_external_mcp:.*?else:.*?prompt\s*=.*?\n'
    if re.search(old_pattern, method_body, re.DOTALL):
        new_line = f'        prompt = self._create_{entity_type}_prompt_with_mcp(text)\n'
        method_body = re.sub(old_pattern, new_line, method_body, flags=re.DOTALL)
    else:
        # Look for simple prompt creation and replace it
        prompt_pattern = rf'prompt\s*=\s*self\._create_{entity_type}_prompt\(text\)'
        if re.search(prompt_pattern, method_body):
            method_body = re.sub(prompt_pattern, f'prompt = self._create_{entity_type}_prompt_with_mcp(text)', method_body)
        else:
            print(f"⚠️  {entity_type}: Could not find prompt creation pattern to update")
            return False
    
    # Reconstruct the content
    new_content = content[:match.start(1)] + method_body + content[match.end(1):]
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ {entity_type}: Updated _extract_with_llm to use MCP")
    return True

def main():
    """Update all extractors."""
    print("ProEthica Entity Extractor MCP Integration Update")
    print("=" * 60)
    
    extraction_dir = Path('/home/chris/onto/proethica/app/services/extraction')
    
    for entity_type in EXTRACTORS_TO_UPDATE:
        print(f"\nUpdating {entity_type.title()} Extractor:")
        print("-" * 40)
        
        file_path = extraction_dir / f"{entity_type}.py"
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue
        
        # Add _get_prompt_for_preview method
        add_get_prompt_for_preview_method(file_path, entity_type)
        
        # Add MCP prompt method
        add_mcp_prompt_method(file_path, entity_type)
        
        # Update _extract_with_llm to use MCP
        update_extract_with_llm(file_path, entity_type)
    
    print("\n" + "=" * 60)
    print("Update Complete!")
    print("\nNext steps:")
    print("1. Update external_mcp_client.py to add missing get_all_XXX_entities methods")
    print("2. Run test_all_extractors.py to verify MCP integration")
    print("3. Add theoretical grounding from Chapter 2 to each prompt")
    print("4. Populate ontology with entities from NSPE Code")

if __name__ == "__main__":
    main()
