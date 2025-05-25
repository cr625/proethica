"""
Service for formatting structure triples in a user-friendly way.
Provides both formatted and raw views of RDF triples.
"""

import re
from typing import Dict, List, Tuple, Any
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class StructureTripleFormatter:
    """Formats RDF structure triples for user-friendly display."""
    
    # Define ProEthica namespace
    PROETHICA = "http://proethica.org/ontology/intermediate#"
    
    # Map ProEthica types to friendly names
    TYPE_LABELS = {
        'CaseNumber': 'Case Number',
        'CaseTitle': 'Case Title',
        'CaseYear': 'Year',
        'FactsSection': 'Facts',
        'DiscussionSection': 'Discussion',
        'QuestionsSection': 'Questions',
        'ConclusionSection': 'Conclusion',
        'ReferencesSection': 'References',
        'QuestionItem': 'Question',
        'ConclusionItem': 'Conclusion Item',
        'CodeReferenceItem': 'Code Reference',
        'DocumentElement': 'Document'
    }
    
    # Predicates to include in formatted view
    RELEVANT_PREDICATES = {
        'hasTextContent': 'Content',
        'hasPart': 'Contains',
        'isPartOf': 'Part of',
        'precedesInDocument': 'Precedes',
        'followsInDocument': 'Follows'
    }
    
    def __init__(self):
        self.graph = None
        
    def parse_triples(self, turtle_string: str) -> Dict[str, Any]:
        """Parse turtle string and return structured data."""
        try:
            # Parse the turtle string
            self.graph = Graph()
            self.graph.parse(data=turtle_string, format='turtle')
            
            # Extract structured information
            result = {
                'document_info': self._extract_document_info(),
                'sections': self._extract_sections(),
                'section_items': self._extract_all_section_items(),
                'statistics': self._calculate_statistics(),
                'raw_triples': turtle_string
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing triples: {str(e)}")
            return {
                'error': str(e),
                'raw_triples': turtle_string
            }
    
    def _extract_document_info(self) -> Dict[str, str]:
        """Extract basic document information."""
        info = {}
        
        # Find case number
        for s, p, o in self.graph.triples((None, RDF.type, URIRef(f"{self.PROETHICA}CaseNumber"))):
            for _, _, content in self.graph.triples((s, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                info['case_number'] = str(content)
                
        # Find case title
        for s, p, o in self.graph.triples((None, RDF.type, URIRef(f"{self.PROETHICA}CaseTitle"))):
            for _, _, content in self.graph.triples((s, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                info['title'] = str(content)
                
        # Find year
        for s, p, o in self.graph.triples((None, RDF.type, URIRef(f"{self.PROETHICA}CaseYear"))):
            for _, _, content in self.graph.triples((s, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                info['year'] = str(content)
                
        return info
    
    def _extract_sections(self) -> Dict[str, Dict[str, Any]]:
        """Extract section information organized by type."""
        sections = {}
        
        # Define section types to extract
        section_types = [
            'FactsSection', 'DiscussionSection', 'QuestionsSection', 
            'ConclusionSection', 'ReferencesSection'
        ]
        
        for section_type in section_types:
            # Find section of this type
            for section_uri, _, _ in self.graph.triples((None, RDF.type, URIRef(f"{self.PROETHICA}{section_type}"))):
                section_data = {
                    'uri': str(section_uri),
                    'type': section_type,
                    'label': self.TYPE_LABELS.get(section_type, section_type),
                    'content': None,
                    'items': []
                }
                
                # Get section content
                for _, _, content in self.graph.triples((section_uri, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                    # Truncate long content for display
                    content_str = str(content)
                    if len(content_str) > 200:
                        section_data['content'] = content_str[:200] + "..."
                    else:
                        section_data['content'] = content_str
                    section_data['full_content_length'] = len(content_str)
                
                # Extract items within this section
                section_data['items'] = self._extract_section_items(section_uri)
                
                sections[section_type] = section_data
                
        return sections
    
    def _extract_section_items(self, section_uri: URIRef) -> List[Dict[str, str]]:
        """Extract items that belong to a section."""
        items = []
        
        # Find all items that are part of this section
        for item_uri, _, _ in self.graph.triples((None, URIRef(f"{self.PROETHICA}isPartOf"), section_uri)):
            item_data = {'uri': str(item_uri)}
            
            # Get item type
            for _, _, item_type in self.graph.triples((item_uri, RDF.type, None)):
                type_str = str(item_type)
                if type_str.startswith(self.PROETHICA):
                    type_name = type_str.replace(self.PROETHICA, '')
                    if type_name in self.TYPE_LABELS:
                        item_data['type'] = self.TYPE_LABELS[type_name]
                    else:
                        item_data['type'] = type_name
                elif 'NamedIndividual' in type_str:
                    # Skip OWL NamedIndividual type, look for the actual type
                    continue
                else:
                    item_data['type'] = type_str
                    
            # Get item content
            for _, _, content in self.graph.triples((item_uri, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                content_str = str(content)
                if len(content_str) > 150:
                    item_data['content'] = content_str[:150] + "..."
                else:
                    item_data['content'] = content_str
                    
            if 'type' in item_data:  # Only add if we found a type
                items.append(item_data)
                
        return items
    
    def _calculate_statistics(self) -> Dict[str, int]:
        """Calculate statistics about the triples."""
        stats = {
            'total_triples': len(self.graph),
            'entities': 0,
            'sections': 0,
            'items': 0
        }
        
        # Count entities by type
        entity_counts = defaultdict(int)
        for s, p, o in self.graph.triples((None, RDF.type, None)):
            if str(o).startswith(self.PROETHICA):
                entity_type = str(o).replace(self.PROETHICA, '')
                entity_counts[entity_type] += 1
                
        stats['entities'] = sum(entity_counts.values())
        stats['sections'] = sum(1 for t in entity_counts if 'Section' in t)
        stats['items'] = entity_counts.get('QuestionItem', 0) + \
                        entity_counts.get('ConclusionItem', 0) + \
                        entity_counts.get('CodeReferenceItem', 0)
        
        # Add detailed counts
        stats['entity_breakdown'] = dict(entity_counts)
        
        return stats
    
    def format_for_llm(self, structured_data: Dict[str, Any]) -> str:
        """Format the structured data for LLM consumption."""
        if 'error' in structured_data:
            return f"Error parsing structure: {structured_data['error']}"
            
        lines = []
        
        # Document info
        doc_info = structured_data.get('document_info', {})
        if doc_info:
            lines.append(f"Case {doc_info.get('case_number', 'Unknown')} ({doc_info.get('year', 'Unknown')})")
            if 'title' in doc_info:
                lines.append(f"Title: {doc_info['title']}")
            lines.append("")
        
        # Sections summary
        sections = structured_data.get('sections', {})
        if sections:
            lines.append("Document Structure:")
            for section_type, section_data in sections.items():
                lines.append(f"\n{section_data['label']}:")
                if section_data.get('content'):
                    lines.append(f"  Content preview: {section_data['content']}")
                if section_data.get('full_content_length'):
                    lines.append(f"  (Full content: {section_data['full_content_length']} characters)")
                if section_data.get('items'):
                    lines.append(f"  Contains {len(section_data['items'])} items:")
                    for item in section_data['items'][:3]:  # Show first 3 items
                        lines.append(f"    - {item.get('type', 'Unknown')}: {item.get('content', 'No content')}")
                    if len(section_data['items']) > 3:
                        lines.append(f"    ... and {len(section_data['items']) - 3} more items")
        
        return "\n".join(lines)
    
    def get_similarity_optimized_triples(self, structured_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract triples optimized for similarity search and LLM reasoning.
        Returns a dictionary with section keys and their semantic content.
        """
        if 'error' in structured_data:
            return {}
            
        optimized = {}
        
        # Document metadata
        doc_info = structured_data.get('document_info', {})
        if doc_info:
            metadata_parts = []
            if 'case_number' in doc_info:
                metadata_parts.append(f"Case {doc_info['case_number']}")
            if 'year' in doc_info:
                metadata_parts.append(f"Year {doc_info['year']}")
            if 'title' in doc_info:
                metadata_parts.append(f"Title: {doc_info['title']}")
            
            if metadata_parts:
                optimized['metadata'] = " | ".join(metadata_parts)
        
        # Sections
        sections = structured_data.get('sections', {})
        for section_type, section_data in sections.items():
            section_key = section_data['label'].lower().replace(' ', '_')
            
            # Include section content if available
            if section_data.get('content'):
                # Use full content for similarity, not the truncated preview
                # Note: In real implementation, we'd fetch the full content
                optimized[section_key] = section_data['content']
            
            # Add items as structured text
            if section_data.get('items'):
                items_text = []
                for item in section_data['items']:
                    item_type = item.get('type', 'Item')
                    content = item.get('content', '')
                    if content:
                        items_text.append(f"{item_type}: {content}")
                
                if items_text:
                    if section_key in optimized:
                        optimized[section_key] += "\n\n" + "\n".join(items_text)
                    else:
                        optimized[section_key] = "\n".join(items_text)
        
        return optimized
    
    def _extract_all_section_items(self) -> Dict[str, Dict[str, Any]]:
        """Extract all section items with their full content and metadata."""
        items = {}
        
        # Find all items that have content
        for item_uri, _, _ in self.graph.triples((None, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
            item_id = str(item_uri).split('/')[-1]
            
            # Skip main sections and document-level items
            if any(x in item_id for x in ['facts', 'discussion', 'questions', 'conclusion', 'references', 
                                          'case_number', 'case_title', 'case_year']):
                if not any(x in item_id for x in ['_item_', 'question_', 'conclusion_item_']):
                    continue
            
            item_data = {
                'uri': str(item_uri),
                'id': item_id,
                'content': None,
                'type': None,
                'parent_section': None
            }
            
            # Get item type
            for _, _, item_type in self.graph.triples((item_uri, RDF.type, None)):
                type_str = str(item_type)
                if type_str.startswith(self.PROETHICA):
                    type_name = type_str.replace(self.PROETHICA, '')
                    if type_name in self.TYPE_LABELS:
                        item_data['type'] = self.TYPE_LABELS[type_name]
                    else:
                        item_data['type'] = type_name
                elif 'NamedIndividual' not in type_str:
                    item_data['type'] = type_str
            
            # Get full content
            for _, _, content in self.graph.triples((item_uri, URIRef(f"{self.PROETHICA}hasTextContent"), None)):
                item_data['content'] = str(content)
            
            # Find parent section
            for _, _, parent in self.graph.triples((item_uri, URIRef(f"{self.PROETHICA}isPartOf"), None)):
                parent_str = str(parent)
                if 'questions' in parent_str:
                    item_data['parent_section'] = 'questions'
                elif 'conclusion' in parent_str:
                    item_data['parent_section'] = 'conclusion'
                elif 'references' in parent_str:
                    item_data['parent_section'] = 'references'
                elif 'facts' in parent_str:
                    item_data['parent_section'] = 'facts'
                elif 'discussion' in parent_str:
                    item_data['parent_section'] = 'discussion'
            
            if item_data['content']:  # Only add items with content
                items[item_id] = item_data
        
        return items