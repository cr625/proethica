"""
ProEthica LangExtract Service

Standalone implementation of LangExtract-style document analysis specifically
for ProEthica's ethical content analysis needs. Does not depend on OntExtract.
"""

import os
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ProEthicaLangExtractService:
    """
    Standalone LangExtract-style service for ProEthica ethical content analysis
    """
    
    def __init__(self):
        """Initialize the service"""
        self.google_api_key = os.environ.get('GOOGLE_GEMINI_API_KEY')
        self.service_ready = bool(self.google_api_key)
        
        if self.service_ready:
            try:
                # Try to import langextract if available
                import langextract as lx
                self.langextract_available = True
                self.model_id = "gemini-1.5-flash"
                logger.info("ProEthica LangExtract service initialized with Gemini support")
            except ImportError:
                self.langextract_available = False
                logger.warning("langextract library not available - using fallback analysis")
        else:
            self.langextract_available = False
            logger.warning("GOOGLE_GEMINI_API_KEY not available - using fallback analysis only")
    
    def analyze_section_content(self, section_title: str, section_text: str, 
                              case_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze a section's content for ethical insights
        
        Args:
            section_title: Title of the section being analyzed
            section_text: Clean text content of the section
            case_id: Optional case ID for context
            
        Returns:
            Analysis results formatted for ProEthica display
        """
        
        if self.langextract_available and self.service_ready:
            return self._analyze_with_langextract(section_title, section_text, case_id)
        else:
            return self._analyze_with_fallback(section_title, section_text, case_id)
    
    def _analyze_with_langextract(self, section_title: str, section_text: str, 
                                 case_id: Optional[int] = None) -> Dict[str, Any]:
        """Analyze using actual LangExtract library"""
        
        try:
            import langextract as lx
            from langextract import data
            
            logger.info(f"Starting LangExtract API call for section: {section_title}")
            logger.info(f"API Key available: {bool(self.google_api_key)}")
            logger.info(f"Text length: {len(section_text)} characters")
            
            # Create examples to guide extraction
            examples = [
                data.ExampleData(
                    text="Engineer Smith, a licensed professional engineer, faces an ethical dilemma regarding public safety when Client Corp requests modifications that may compromise structural integrity.",
                    extractions=[
                        data.Extraction(
                            extraction_class="ethics_analysis",
                            extraction_text="structured_ethical_analysis",
                            attributes={
                                "key_concepts": [
                                    {"term": "professional engineer", "ethical_relevance": "professional_identity"},
                                    {"term": "ethical dilemma", "ethical_relevance": "decision_framework"},
                                    {"term": "public safety", "ethical_relevance": "fundamental_principle"}
                                ],
                                "stakeholders": [
                                    {"name": "Engineer Smith", "role": "Professional Engineer", "responsibilities": "Uphold public safety"},
                                    {"name": "Client Corp", "role": "Client", "responsibilities": "Project requirements"}
                                ],
                                "ethical_principles": [
                                    {"principle": "Hold paramount the safety, health, and welfare of the public", "nspe_reference": "I.1", "relevance": "Fundamental duty"}
                                ],
                                "decision_points": [
                                    {"decision": "Whether to compromise structural integrity per client request", "ethical_considerations": "Public safety vs client satisfaction"}
                                ]
                            }
                        )
                    ]
                )
            ]
            
            # Perform extraction using correct API
            extraction_result = lx.extract(
                text_or_documents=section_text,
                prompt_description=f"""Extract structured information from this professional ethics case section: {section_title}
                
Focus on extracting:
1. Key ethical concepts, principles, and terms
2. Stakeholders and their roles 
3. Professional ethics principles (especially NSPE-related)
4. Decision points and ethical dilemmas
5. Temporal markers and sequence indicators

Provide clear, structured analysis suitable for professional ethics education.""",
                examples=examples,
                model_id=self.model_id,
                api_key=self.google_api_key,
                language_model_type=lx.inference.GeminiLanguageModel,
                temperature=0.3,
                fence_output=False
            )
            
            logger.info("LangExtract API call completed successfully")
            
            # Process LangExtract results into structured format
            logger.info(f"Raw LangExtract result type: {type(extraction_result)}")
            if hasattr(extraction_result, 'extractions'):
                logger.info(f"Number of extractions: {len(extraction_result.extractions)}")
            structured_results = self._process_langextract_results(extraction_result, section_text)
            logger.info(f"Processed results keys: {list(structured_results.keys())}")
            
            # Format results for ProEthica
            return self._format_langextract_results(
                section_title, section_text, structured_results, 'langextract_gemini'
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"LangExtract analysis failed for section '{section_title}': {e}")
            logger.error(f"Full traceback: {error_details}")
            return self._analyze_with_fallback(section_title, section_text, case_id, error=str(e))
    
    def _process_langextract_results(self, annotated_doc, original_text: str) -> Dict[str, Any]:
        """Process LangExtract API results into structured format for ProEthica"""
        
        result = {
            'key_concepts': [],
            'stakeholders': [],
            'ethical_principles': [],
            'decision_points': [],
            'temporal_markers': []
        }
        
        try:
            if annotated_doc and hasattr(annotated_doc, 'extractions'):
                for extraction in annotated_doc.extractions:
                    # Handle different LangExtract data structure formats
                    extraction_data = None
                    if hasattr(extraction, 'data') and extraction.data:
                        extraction_data = extraction.data
                    elif hasattr(extraction, 'attributes') and extraction.attributes:
                        extraction_data = extraction.attributes
                    elif hasattr(extraction, 'extraction_text'):
                        # Try to parse JSON from extraction text
                        try:
                            import json
                            extraction_data = json.loads(extraction.extraction_text)
                        except:
                            # If not JSON, create basic structure from raw text
                            extraction_data = {
                                'key_concepts': [{'term': extraction.extraction_text, 'ethical_relevance': 'general'}]
                            }
                    
                    if extraction_data:
                        # Merge structured data from extraction
                        for key in result.keys():
                            if key in extraction_data and extraction_data[key]:
                                if isinstance(extraction_data[key], list):
                                    result[key].extend(extraction_data[key])
                                else:
                                    # Convert non-list values to list format
                                    result[key].append({
                                        'term': str(extraction_data[key]),
                                        'context': 'extracted_content'
                                    })
            
            # If no extractions found, create basic analysis from the extraction response
            if not any(result.values()):
                result = self._create_basic_analysis_from_response(annotated_doc, original_text)
                
        except Exception as e:
            logger.warning(f"Error processing LangExtract results: {e}")
            # Return basic structure if processing fails
            result = {
                'key_concepts': [{'term': 'professional_ethics', 'ethical_relevance': 'general'}],
                'stakeholders': [],
                'ethical_principles': [],
                'decision_points': [],
                'temporal_markers': []
            }
        
        return result
    
    def _create_basic_analysis_from_response(self, annotated_doc, text: str) -> Dict[str, Any]:
        """Create basic analysis when structured extraction is not available"""
        
        # Use fallback analysis as base
        fallback_result = {
            'key_concepts': self._extract_key_concepts_fallback(text),
            'stakeholders': self._extract_stakeholders_fallback(text),
            'ethical_principles': self._extract_ethical_principles_fallback(text),
            'decision_points': self._extract_decision_points_fallback(text),
            'temporal_markers': self._extract_temporal_markers_fallback(text)
        }
        
        return fallback_result
    
    def _analyze_with_fallback(self, section_title: str, section_text: str, 
                              case_id: Optional[int] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """Fallback analysis using rule-based methods"""
        
        logger.info(f"Using fallback analysis for section: {section_title}")
        
        # Extract key concepts using simple patterns
        key_concepts = self._extract_key_concepts_fallback(section_text)
        
        # Extract stakeholders using patterns
        stakeholders = self._extract_stakeholders_fallback(section_text)
        
        # Extract ethical principles
        ethical_principles = self._extract_ethical_principles_fallback(section_text)
        
        # Extract decision points
        decision_points = self._extract_decision_points_fallback(section_text)
        
        # Extract temporal markers
        temporal_markers = self._extract_temporal_markers_fallback(section_text)
        
        # Create structured result
        extraction_result = {
            'key_concepts': key_concepts,
            'stakeholders': stakeholders,
            'ethical_principles': ethical_principles,
            'decision_points': decision_points,
            'temporal_markers': temporal_markers
        }
        
        return self._format_langextract_results(
            section_title, section_text, extraction_result, 'fallback_analysis', error=error
        )
    
    def _extract_key_concepts_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Extract key concepts using pattern matching"""
        
        concepts = []
        
        # Common ethical/professional terms
        ethical_terms = [
            'professional', 'ethics', 'ethical', 'responsibility', 'duty', 'obligation',
            'safety', 'public welfare', 'competence', 'integrity', 'honesty', 'disclosure',
            'conflict of interest', 'confidentiality', 'client', 'employer', 'engineer'
        ]
        
        for term in ethical_terms:
            if term.lower() in text.lower():
                # Find context around the term
                pattern = rf'.{{0,50}}{re.escape(term)}.{{0,50}}'
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    concepts.append({
                        'term': term,
                        'definition': '',
                        'ethical_relevance': 'professional_ethics',
                        'context': match.group().strip()
                    })
                    break  # Only add each term once
        
        return concepts[:10]  # Limit to top 10
    
    def _extract_stakeholders_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Extract stakeholders using pattern matching"""
        
        stakeholders = []
        
        # Common stakeholder patterns
        stakeholder_patterns = [
            r'Engineer\s+[A-Z]',
            r'Client\s+[A-Z]',
            r'Manager\s+[A-Z]', 
            r'the\s+client',
            r'the\s+engineer',
            r'the\s+employer',
            r'the\s+public',
            r'regulatory\s+authority',
            r'professional\s+board'
        ]
        
        for pattern in stakeholder_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                stakeholder_text = match.group().strip()
                stakeholders.append({
                    'name': stakeholder_text,
                    'role': self._infer_role(stakeholder_text),
                    'responsibilities': 'To be determined from context'
                })
                if len(stakeholders) >= 8:  # Limit results
                    break
            if len(stakeholders) >= 8:
                break
        
        return stakeholders
    
    def _infer_role(self, stakeholder_text: str) -> str:
        """Infer role from stakeholder text"""
        text_lower = stakeholder_text.lower()
        
        if 'engineer' in text_lower:
            return 'Professional Engineer'
        elif 'client' in text_lower:
            return 'Client/Customer'
        elif 'manager' in text_lower:
            return 'Management'
        elif 'employer' in text_lower:
            return 'Employer'
        elif 'public' in text_lower:
            return 'Public Interest'
        elif 'regulatory' in text_lower or 'authority' in text_lower:
            return 'Regulatory Body'
        else:
            return 'Stakeholder'
    
    def _extract_ethical_principles_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Extract ethical principles using NSPE-based patterns"""
        
        principles = []
        
        # NSPE-related principles
        nspe_principles = [
            ('public safety', 'Hold paramount the safety, health, and welfare of the public', 'I.1'),
            ('competence', 'Perform services only in areas of their competence', 'II.2.a'),
            ('honesty', 'Be honest and impartial', 'III.3'),
            ('disclosure', 'Avoid conflicts of interest and disclose them when they exist', 'III.4'),
            ('confidential', 'Keep information confidential', 'III.6'),
            ('professional development', 'Continue professional development', 'II.2.h')
        ]
        
        for keyword, principle, reference in nspe_principles:
            if keyword.lower() in text.lower():
                principles.append({
                    'principle': principle,
                    'relevance': f'Mentioned in context: "{keyword}"',
                    'nspe_reference': reference
                })
        
        return principles[:6]  # Limit results
    
    def _extract_decision_points_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Extract decision points using pattern matching"""
        
        decisions = []
        
        # Look for decision-indicating phrases
        decision_patterns = [
            r'should\s+[A-Za-z\s]{10,50}\?',
            r'whether\s+to\s+[A-Za-z\s]{10,50}',
            r'decision\s+to\s+[A-Za-z\s]{10,50}',
            r'chose\s+to\s+[A-Za-z\s]{10,50}',
            r'must\s+decide\s+[A-Za-z\s]{10,50}'
        ]
        
        for pattern in decision_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                decision_text = match.group().strip()
                decisions.append({
                    'decision': decision_text,
                    'ethical_considerations': 'Professional ethics principles apply'
                })
                if len(decisions) >= 5:
                    break
            if len(decisions) >= 5:
                break
        
        return decisions
    
    def _extract_temporal_markers_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Extract temporal markers using pattern matching"""
        
        markers = []
        
        # Temporal patterns
        temporal_patterns = [
            r'\b(before|after|during|when|while|then|next|later|initially|finally)\b',
            r'\b(first|second|third|last)\b',
            r'\b\d{4}\b',  # Years
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b'
        ]
        
        for pattern in temporal_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                marker_text = match.group().strip()
                # Get surrounding context
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                
                markers.append({
                    'marker': marker_text,
                    'context': context
                })
                if len(markers) >= 8:
                    break
            if len(markers) >= 8:
                break
        
        return markers
    
    def _format_langextract_results(self, section_title: str, section_text: str, 
                                  extraction_result: Dict[str, Any], method: str,
                                  error: Optional[str] = None) -> Dict[str, Any]:
        """Format extraction results for ProEthica display"""
        
        return {
            'success': True,
            'analysis_method': method,
            'section_title': section_title,
            'original_text_length': len(section_text),
            'analysis_timestamp': datetime.utcnow().isoformat(),
            
            # Core Analysis Results
            'structured_analysis': {
                'key_concepts': extraction_result.get('key_concepts', []),
                'stakeholders': extraction_result.get('stakeholders', []),
                'ethical_principles': extraction_result.get('ethical_principles', []),
                'decision_points': extraction_result.get('decision_points', []),
                'temporal_markers': extraction_result.get('temporal_markers', [])
            },
            
            # ProEthica-Specific Context
            'ethical_context': {
                'professional_domain': 'engineering_ethics',
                'analysis_suitability': 'high' if method == 'langextract_gemini' else 'medium',
                'nspe_relevance': len([p for p in extraction_result.get('ethical_principles', []) 
                                    if isinstance(p, dict) and p.get('nspe_reference')])
            },
            
            # Processing Information
            'processing_info': {
                'method': method,
                'langextract_available': self.langextract_available,
                'service_ready': self.service_ready,
                'error': error,
                'confidence': 0.8 if method == 'langextract_gemini' else 0.6
            },
            
            # Analysis Summary
            'summary': {
                'key_concepts_found': len(extraction_result.get('key_concepts', [])),
                'stakeholders_identified': len(extraction_result.get('stakeholders', [])),
                'ethical_principles_referenced': len(extraction_result.get('ethical_principles', [])),
                'decision_points_detected': len(extraction_result.get('decision_points', [])),
                'temporal_markers_found': len(extraction_result.get('temporal_markers', []))
            }
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get the current status of the service"""
        
        return {
            'service_ready': self.service_ready,
            'langextract_available': self.langextract_available,
            'langextract_service_ready': self.service_ready,  # Template compatibility
            'ontextract_available': False,  # This is ProEthica standalone, not OntExtract
            'google_api_key_available': bool(self.google_api_key),
            'integration_status': 'ready' if (self.langextract_available and self.service_ready) else 'fallback_only',
            'capabilities': {
                'structured_extraction': self.langextract_available and self.service_ready,
                'ethical_context_analysis': True,  # Always available
                'stakeholder_identification': True,
                'principle_mapping': True,
                'fallback_analysis': True
            },
            'implementation': 'standalone_proethica'
        }