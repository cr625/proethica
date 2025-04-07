"""
LLM-based extraction for the Case URL Processor.

This module provides functionality for extracting structured data from case content
using LLMs, primarily Claude via LangChain.
"""

import logging
import json
import re
from typing import Dict, Any, Optional

from app.services.langchain_claude import LangChainClaudeService

# Set up logging
logger = logging.getLogger(__name__)

class LlmExtractor:
    """
    Extractor using LLMs to extract structured data from case content.
    """
    
    def __init__(self, provider='claude', fallback_to_local=True):
        """
        Initialize the LLM extractor.
        
        Args:
            provider: LLM provider to use ('claude' or 'local')
            fallback_to_local: Whether to fall back to local models if Claude fails
        """
        self.provider = provider
        self.fallback_to_local = fallback_to_local
        
        # Get LangChain Claude service
        self.langchain_claude = LangChainClaudeService.get_instance()
        
        # Create extraction chain
        # Create two extraction chains: one for standard case files and one for regular engineering articles
        self.case_extraction_chain = self.langchain_claude.create_chain(
            template="""
            You are an expert in engineering ethics cases. Analyze this engineering ethics case content and extract the following information in a structured JSON format:
            
            ```
            {content}
            ```
            
            Extract the following fields:
            - title: A descriptive title for the case
            - case_number: The case number if present (e.g., "Case 93-1")
            - year: The year of the case (integer)
            - ethical_questions: The primary ethical questions posed (array of strings)
            - ethical_principles: Key ethical principles involved (array of strings)
            - involved_parties: Primary stakeholders in the case (array of strings)
            - summary: A brief summary (2-3 sentences)
            - decision: The ethical decision or recommendation
            - engineering_disciplines: Engineering fields involved (array of strings)
            - potential_triples: Identify 3-5 key RDF triples that could be extracted from this case in the format [subject, predicate, object]
            
            Return ONLY a JSON object with these fields - no introduction, explanation, or any text outside the JSON.
            """,
            input_variables=["content"]
        )
        
        self.article_extraction_chain = self.langchain_claude.create_chain(
            template="""
            You are an expert in engineering ethics content analysis. Analyze this engineering ethics article or resource and extract information for a structured JSON format:
            
            ```
            {content}
            ```
            
            Extract the following fields:
            - title: The exact title of this article - DO NOT FABRICATE A TITLE
            - ethical_questions: Primary ethical questions addressed (array of strings)
            - ethical_principles: Key ethical principles involved (array of strings)
            - involved_parties: Relevant stakeholders mentioned (array of strings)
            - summary: A brief factual summary (2-3 sentences)
            - engineering_disciplines: Engineering fields mentioned (array of strings)
            - year: Publication year if clearly indicated (integer, can be null)
            - potential_triples: Identify 3-5 key RDF triples from this article
            
            IMPORTANT INSTRUCTION: DO NOT INVENT A CASE NUMBER FOR THIS ARTICLE. If no clear case number is present in the document, set case_number to null.
            
            Return ONLY a JSON object with these fields - no introduction, explanation, or any text outside the JSON.
            """,
            input_variables=["content"]
        )
    
    def extract_case_data(self, content, pattern_metadata=None, world_id=None):
        """
        Extract structured data from content using LLM.
        
        Args:
            content: The content to extract data from
            pattern_metadata: Metadata already extracted using patterns (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            Dictionary of extracted data
        """
        try:
            # Determine content length and truncate if necessary
            content_length = len(content)
            max_length = 6000  # Reasonable length for context
            
            if content_length > max_length:
                # Try to find a good breaking point
                truncation_point = content.rfind("\n\n", 0, max_length)
                if truncation_point == -1:
                    truncation_point = content.rfind(". ", 0, max_length)
                if truncation_point == -1:
                    truncation_point = max_length
                
                truncated_content = content[:truncation_point] + "\n\n[Content truncated for length...]"
                logger.info(f"Content truncated from {content_length} to {len(truncated_content)} characters")
                content = truncated_content
            
            # Determine if this is likely a case file or a regular article
            is_likely_case = self._is_likely_case_file(content, pattern_metadata)
            
            # Process with appropriate LLM chain
            if is_likely_case:
                logger.info("Processing content as a case file")
                llm_response = self.langchain_claude.run_chain(
                    self.case_extraction_chain,
                    content=content
                )
            else:
                logger.info("Processing content as an article/resource")
                llm_response = self.langchain_claude.run_chain(
                    self.article_extraction_chain,
                    content=content
                )
            
            # Parse the structured data
            structured_data = self._parse_structured_response(llm_response)
            
            # Merge with pattern metadata if provided
            if pattern_metadata:
                # Let LLM extraction override pattern extraction except for URL
                # since the URL isn't part of the content
                url = pattern_metadata.get('url')
                merged_data = {**structured_data}
                if url:
                    merged_data['url'] = url
                
                # Merge arrays (principles, questions, etc.)
                for key in ['ethical_principles', 'ethical_questions', 'related_cases']:
                    if key in pattern_metadata and key in structured_data:
                        # Combine both lists and remove duplicates
                        merged_data[key] = list(set(pattern_metadata[key] + structured_data[key]))
                    elif key in pattern_metadata:
                        merged_data[key] = pattern_metadata[key]
                
                return merged_data
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error in LLM extraction: {str(e)}")
            
            # Fall back to pattern_metadata if available
            if pattern_metadata:
                logger.info("Falling back to pattern-based extraction")
                return pattern_metadata
            else:
                # Return empty dict as fallback
                return {}
    
    def _parse_structured_response(self, response):
        """
        Parse structured data from LLM response.
        
        Args:
            response: Response from LLM
            
        Returns:
            Dictionary of extracted data
        """
        try:
            # Try to find JSON block
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # If no JSON block, try to parse the entire response as JSON
            try:
                return json.loads(response)
            except Exception:
                # Try to find JSON object pattern
                json_obj_match = re.search(r'(\{.*\})', response, re.DOTALL)
                if json_obj_match:
                    return json.loads(json_obj_match.group(1))
            
            # If all parsing fails, do a basic key-value extraction
            return self._fallback_extraction(response)
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.debug(f"Problematic response: {response}")
            return {}
    
    def _is_likely_case_file(self, content, pattern_metadata=None):
        """
        Determine if the content is likely an ethics case file or a regular article.
        
        Args:
            content: The content to analyze
            pattern_metadata: Previously extracted metadata (optional)
            
        Returns:
            Boolean indicating if this is likely a case file
        """
        # Check pattern metadata for case-specific fields
        if pattern_metadata:
            # If case number exists, it's definitely a case
            if pattern_metadata.get('case_number'):
                return True
                
            # Check URL for case-specific patterns
            url = pattern_metadata.get('url', '')
            if url and (
                '/case-' in url.lower() or 
                '/cases/' in url.lower() or
                '/bor-' in url.lower() or
                '/board-of-review/' in url.lower() or
                re.search(r'/\d+-\d+', url)  # Pattern like /93-1
            ):
                return True
        
        # Check content for case-specific keywords and patterns
        case_indicators = [
            r'board of ethical review',
            r'BER case',
            r'Facts:.*?Discussion:.*?Conclusion:',
            r'case\s+\d+[-/]\d+',
            r'complaint against',
            r'board finds that',
            r'ethical issue:',
            r'ethical question:',
            r'ethical violation',
            r'board opinion',
            r'decision:',
            r'findings:',
            r'ethics case study'
        ]
        
        # Count matches for case indicators
        case_indicator_count = 0
        for indicator in case_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                case_indicator_count += 1
                
        # If we find multiple case indicators, it's likely a case
        if case_indicator_count >= 2:
            return True
            
        # Check for section headers common in cases
        section_headers = ['FACTS:', 'REFERENCES:', 'DISCUSSION:', 'CONCLUSION:']
        section_count = 0
        for header in section_headers:
            if header in content.upper():
                section_count += 1
                
        return section_count >= 2
    
    def _fallback_extraction(self, response):
        """
        Fallback method for extracting structured data when JSON parsing fails.
        
        Args:
            response: Response from LLM
            
        Returns:
            Dictionary of extracted data
        """
        extracted_data = {}
        
        # Look for key-value pairs in the format "key: value"
        kvp_pattern = r'([a-zA-Z_]+):\s*(.+?)(?=\n[a-zA-Z_]+:|$)'
        matches = re.finditer(kvp_pattern, response, re.DOTALL)
        
        for match in matches:
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            
            # Handle arrays (look for bullet points or numbered lists)
            if re.search(r'(\n\s*[-*]\s+|\n\s*\d+\.\s+)', value, re.MULTILINE):
                # Extract array items
                items = re.findall(r'(?:[-*]|\d+\.)\s+(.+?)(?=\n\s*(?:[-*]|\d+\.)|$)', value, re.DOTALL)
                extracted_data[key] = [item.strip() for item in items]
            else:
                extracted_data[key] = value
        
        return extracted_data
