"""
NSPE Pattern Matcher for the Case URL Processor.

This module provides pattern matching functionality specific to NSPE ethics cases.
"""

import json
import os
import re
import logging
from typing import Dict, List, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

class NSPEPatternMatcher:
    """
    Pattern matcher for NSPE ethics cases.
    """
    
    def __init__(self, config_path=None):
        """
        Initialize the NSPE pattern matcher.
        
        Args:
            config_path: Path to the pattern configuration file (optional)
        """
        # Default config path is in the same directory as this module
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'pattern_config.json')
        
        self.config_path = config_path
        self.patterns = self._load_patterns()
    
    def _load_patterns(self):
        """
        Load patterns from the configuration file.
        
        Returns:
            Dictionary of patterns
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Get the NSPE patterns
            patterns = config.get('nspe', {})
            
            if not patterns:
                logger.warning("No NSPE patterns found in configuration")
            
            return patterns
        except Exception as e:
            logger.error(f"Error loading pattern configuration: {str(e)}")
            return {}
    
    def extract_metadata(self, content, html_content=None, url=None):
        """
        Extract metadata from content using patterns.
        
        Args:
            content: Cleaned text content
            html_content: Raw HTML content (optional)
            url: URL of the content (optional)
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        
        # Add URL if provided
        if url:
            metadata['url'] = url
        
        # Extract single value patterns
        for field, pattern_info in self.patterns.items():
            # Skip fields that are lists of patterns (we'll handle those separately)
            if isinstance(pattern_info, list):
                continue
            
            # Get pattern details
            pattern = pattern_info.get('pattern')
            target_field = pattern_info.get('field', field)
            
            if not pattern:
                continue
            
            # For HTML patterns, use the HTML content if available
            if pattern.startswith("<") and html_content:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            else:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            
            if match:
                metadata[target_field] = match.group(1)
        
        # Extract multi-value patterns (lists)
        for field, pattern_info_list in self.patterns.items():
            if not isinstance(pattern_info_list, list):
                continue
            
            for pattern_info in pattern_info_list:
                pattern = pattern_info.get('pattern')
                value = pattern_info.get('value')
                target_field = pattern_info.get('field', field)
                
                if not pattern:
                    continue
                
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                
                if match:
                    # Initialize field as a list if it doesn't exist
                    if target_field not in metadata:
                        metadata[target_field] = []
                    
                    # Add the value or the matched group
                    if value:
                        if value not in metadata[target_field]:
                            metadata[target_field].append(value)
                    else:
                        matched_value = match.group(1)
                        if matched_value not in metadata[target_field]:
                            metadata[target_field].append(matched_value)
        
        # Special handling for case number
        if 'case_number' in metadata:
            # Ensure it has "Case" prefix
            if not metadata['case_number'].lower().startswith('case'):
                metadata['case_number'] = f"Case {metadata['case_number']}"
        
        # Extract year from date if not already present
        if 'date' in metadata and 'year' not in metadata:
            year_match = re.search(r'(\d{4})', metadata['date'])
            if year_match:
                metadata['year'] = year_match.group(1)
        
        # Extract case title from URL if not already present
        if 'title' not in metadata and url:
            # Extract the last path segment from the URL
            url_path = url.rstrip('/').split('/')[-1]
            
            # Convert kebab-case to title case
            if url_path:
                title = ' '.join(word.capitalize() for word in url_path.split('-'))
                metadata['title'] = title
        
        return metadata
    
    def extract_related_cases(self, content):
        """
        Extract references to related NSPE cases.
        
        Args:
            content: The content to extract related cases from
            
        Returns:
            List of related case numbers
        """
        case_pattern = r'(?:BER\s+)?Case\s+(\d+-\d+(?:-\d+)?)'
        matches = re.finditer(case_pattern, content, re.IGNORECASE)
        
        related_cases = []
        for match in matches:
            case_num = match.group(1)
            case_ref = f"Case {case_num}"
            if case_ref not in related_cases:
                related_cases.append(case_ref)
        
        return related_cases
    
    def extract_outcome(self, content):
        """
        Extract the outcome/decision from the content.
        
        Args:
            content: The content to extract the outcome from
            
        Returns:
            Outcome string or None if not found
        """
        content_lower = content.lower()
        
        if "not ethical" in content_lower or "unethical" in content_lower:
            return "unethical"
        elif "ethical" in content_lower:
            return "ethical"
        elif "mixed finding" in content_lower or "partially ethical" in content_lower:
            return "mixed finding"
        
        return None
    
    def analyze_board_decision(self, content):
        """
        Extract the board's decision and reasoning.
        
        Args:
            content: The content to extract the decision from
            
        Returns:
            Decision text or None if not found
        """
        # Try to find the section containing the board's decision
        decision_sections = [
            "DISCUSSION",
            "CONCLUSION",
            "BOARD DISCUSSION",
            "BOARD'S DISCUSSION",
            "NSPE CODE OF ETHICS REFERENCES",
            "BER DISCUSSION"
        ]
        
        for section in decision_sections:
            pattern = f"{section}[^\n]*\n(.*?)(?=\n\n\n|$)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no specific section found, check for decision keywords in last third of content
        content_lines = content.split('\n')
        last_third_index = len(content_lines) * 2 // 3
        last_third = '\n'.join(content_lines[last_third_index:])
        
        decision_keywords = [
            "board concludes",
            "board believes",
            "board notes",
            "committee concludes",
            "it would be ethical",
            "it would not be ethical",
            "it would be unethical"
        ]
        
        for keyword in decision_keywords:
            pattern = f"({keyword}[^.]*(?:\\.[^.]*)?\\.[^.]*\\.)"
            match = re.search(pattern, last_third, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
