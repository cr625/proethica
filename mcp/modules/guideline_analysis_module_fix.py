"""
This is a fix for the Anthropic API calls in extract_guideline_concepts method.
The issue is with the tool_choice parameter that's causing a 400 error:
'tool_choice: Input should be a valid dictionary or object to extract fields from'

This file contains only the corrected extract_guideline_concepts method that should be applied
to the GuidelineAnalysisModule class in guideline_analysis_module.py.
"""

async def extract_guideline_concepts(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract concepts from guideline content.
    
    Args:
        arguments: Dictionary with the following keys:
            - content: The guideline content to analyze
            - ontology_source: Optional ontology source ID
        
    Returns:
        Dictionary with extracted concepts
    """
    # DEBUGGING BREAKPOINT - This line is for manual debugging
    import inspect
    current_frame = inspect.currentframe()
    frame_info = inspect.getframeinfo(current_frame)
    logger.debug(f"BREAKPOINT: Hit extract_guideline_concepts at {frame_info.filename}:{frame_info.lineno}")
    logger.debug(f"BREAKPOINT: Arguments: {arguments}")
    logger.info(f"Extract guideline concepts - USE_MOCK_RESPONSES: {self.use_mock_responses}")
    
    try:
        content = arguments.get("content", "")
        ontology_source = arguments.get("ontology_source")
        
        if not content:
            return {"error": "No content provided"}
            
        # Check if we should use mock responses for faster development
        if self.use_mock_responses:
            logger.info("Using mock concepts response (development mode)")
            # Clone the mock concepts data to avoid modifying the original
            if self.mock_concepts:
                return self.mock_concepts.copy()
            else:
                # Generate simple mock concepts if no mock data is available
                return {
                    "concepts": [
                        {
                            "id": 0,
                            "label": "Public Safety",
                            "description": "The paramount obligation of engineers to prioritize public safety",
                            "category": "principle",
                            "related_concepts": ["Ethical Responsibility", "Risk Management"],
                            "text_references": ["Engineers shall hold paramount the safety of the public"]
                        },
                        {
                            "id": 1,
                            "label": "Professional Competence",
                            "description": "The obligation to only perform work within one's area of competence",
                            "category": "obligation",
                            "related_concepts": ["Professional Development", "Technical Expertise"],
                            "text_references": ["Engineers shall perform services only in areas of their competence"]
                        }
                    ],
                    "mock": True
                }
            
        # If not using mock mode, check if LLM client is available
        if not self.llm_client:
            return {"error": "LLM client not available"}
        
        # Get ontology context for tool use
        ontology_context = {"structure": {}, "entity_count": 0}
        if ontology_source:
            try:
                # Load a summary of the ontology structure to provide as context
                ontology_context = await self.handle_get_ontology_structure({"entity_type": "all", "include_relationships": True})
            except Exception as e:
                logger.warning(f"Error getting ontology context: {str(e)}")
        
        # Create system prompt for Claude with tool use
        system_prompt = """
        You are an expert in ethical analysis, ontology engineering, and knowledge extraction. 
        Your task is to analyze a set of ethical guidelines and extract key concepts, principles, and entities.
        
        Focus on identifying:
        1. Ethical principles (e.g., honesty, integrity, responsibility)
        2. Professional obligations
        3. Stakeholders mentioned
        4. Actions and behaviors described
        5. Values emphasized
        6. Constraints or limitations
        7. Context-specific considerations
        
        For each concept you identify, provide:
        - A short label or name for the concept
        - A more detailed description of the concept
        - The type it falls under (one of: "principle", "obligation", "role", "action", "resource", "capability", "event")
        - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
        
        First use the available tools to understand the ontology structure and find similar concepts that may already exist.
        Then use this knowledge to extract and categorize concepts from the guidelines in a way that aligns with the existing ontology.
        """
        
        # Create user message with the guideline content
        user_message = f"""
        Please analyze the following guidelines and extract key ethical concepts:
        
        {content[:10000]}  # Limit to first 10k chars to avoid token limits
        
        Use the available tools to check if similar concepts already exist in the ontology, then extract concepts that align with the ontology structure.
        """
        
        # Call Anthropic API with tool use
        try:
            logger.info("Making LIVE LLM call to extract guideline concepts")
            start_time = time.time()
            
            # Use Claude 3 Sonnet model with updated version
            # FIX: Fixed tool_choice parameter - changed from "auto" to None
            response = await self.llm_client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=self.claude_tools,
                max_tokens=4000,
                temperature=0.2
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"LLM API call completed in {elapsed_time:.2f} seconds")
            
            # Process the response
            result_text = None
            tool_calls = []
            
            # Process tool calls if present
            for content_item in response.content:
                if content_item.type == "text":
                    result_text = content_item.text
                elif content_item.type == "tool_use":
                    tool_calls.append({
                        "name": content_item.tool_use.name,
                        "arguments": content_item.tool_use.arguments
                    })
            
            # Process all tool calls
            tool_results = []
            for tool_call in tool_calls:
                try:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]
                    
                    # Execute the tool
                    if tool_name == "query_ontology":
                        result = await self.handle_query_ontology(tool_args)
                    elif tool_name == "search_similar_concepts":
                        result = await self.handle_search_similar_concepts(tool_args)
                    elif tool_name == "get_ontology_structure":
                        result = await self.handle_get_ontology_structure(tool_args)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    
                    tool_results.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": result
                    })
                    
                except Exception as e:
                    logger.error(f"Error executing tool call '{tool_call}': {str(e)}")
                    tool_results.append({
                        "tool": tool_call["name"],
                        "arguments": tool_call["arguments"],
                        "error": str(e)
                    })
            
            # Process the final response text
            concepts_data = {"concepts": []}
            if result_text:
                try:
                    # Extract and parse JSON
                    json_text = result_text
                    if "```json" in result_text:
                        json_parts = result_text.split("```json")
                        if len(json_parts) > 1:
                            json_text = json_parts[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_parts = result_text.split("```")
                        if len(json_parts) > 1:
                            json_text = json_parts[1].strip()
                    
                    # Clean the JSON text to handle potential inconsistencies
                    json_text = self._clean_json_text(json_text)
                    
                    # Parse the JSON
                    try:
                        parsed_data = json.loads(json_text)
                        
                        # Make sure it has a concepts array
                        if "concepts" in parsed_data and isinstance(parsed_data["concepts"], list):
                            concepts_data = parsed_data
                            
                            # Add unique IDs to each concept if they don't have them
                            for i, concept in enumerate(concepts_data["concepts"]):
                                if "id" not in concept:
                                    concept["id"] = i
                                    
                            logger.info(f"Successfully extracted {len(concepts_data['concepts'])} concepts")
                        else:
                            # Wrap the data in a concepts array if it's not already
                            if isinstance(parsed_data, list):
                                concepts_data = {"concepts": parsed_data}
                                
                                # Add unique IDs to each concept
                                for i, concept in enumerate(concepts_data["concepts"]):
                                    if "id" not in concept:
                                        concept["id"] = i
                            else:
                                logger.warning("Expected concepts array in response, but none found")
                                concepts_data = {"concepts": [], "error": "Expected concepts array in response"}
                    except json.JSONDecodeError as je:
                        logger.error(f"Error parsing JSON: {str(je)}")
                        logger.error(f"JSON text: {json_text}")
                        concepts_data = {"concepts": [], "error": f"Error parsing JSON: {str(je)}"}
                except Exception as e:
                    logger.error(f"Error processing LLM response: {str(e)}")
                    concepts_data = {"concepts": [], "error": f"Error processing LLM response: {str(e)}"}
            
            # Add tool results to the response
            concepts_data["tool_results"] = tool_results
            
            # Add debug information
            concepts_data["debug"] = {
                "model": "claude-3-sonnet-20240229",
                "prompt_length": len(user_message),
                "response_length": len(result_text) if result_text else 0,
                "tool_calls_count": len(tool_calls),
                "elapsed_time": elapsed_time
            }
            
            # Add flag to indicate this is NOT a mock response
            concepts_data["mock"] = False
            
            return concepts_data
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            return {"concepts": [], "error": f"Error calling Anthropic API: {str(e)}"}
    except Exception as e:
        logger.error(f"Error in extract_guideline_concepts: {str(e)}")
        return {"concepts": [], "error": str(e)}
