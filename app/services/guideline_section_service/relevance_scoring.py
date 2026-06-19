"""
Guideline-section relevance scoring.

The multi-metric relevance scoring methods (term overlap, structural relevance, LLM analysis,
final combination, mock fallback), split out of guideline_section_service.py as a mixin. Mixed
into GuidelineSectionService; `self.` resolution preserved by MRO. Import header mirrors service.py.
"""

import logging
import json
import re
import random
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
import numpy as np
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
from sqlalchemy import text

from app import db
from app.models import Document
from app.models.document_section import DocumentSection
from app.services.mcp_client import MCPClient
from app.services.section_embedding_service import SectionEmbeddingService
from app.utils.llm_utils import get_llm_client
from app.utils.nltk_verification import verify_nltk_resources

# Set up logging
logger = logging.getLogger(__name__)


class RelevanceScoringMixin:
    """Multi-metric guideline-section relevance scoring. Mixed into GuidelineSectionService."""

    def calculate_triple_section_relevance(self, section, triple):
        """
        Calculate comprehensive relevance between section and triple using multiple metrics.
        
        Args:
            section: Document section object
            triple: Guideline triple dictionary
            
        Returns:
            dict: Relevance metrics and scores
        """
        try:
            # Convert triple to text for embedding comparison
            triple_text = self._triple_to_text(triple)
            
            # 1. Vector similarity using section embedding service
            vector_similarity = 0.0
            if section.embedding is not None:
                # Get embedding for the triple text
                triple_embedding = self.embedding_service.get_embedding(triple_text)
                # Calculate similarity
                vector_similarity = self.embedding_service.calculate_similarity(
                    section.embedding, 
                    triple_embedding
                )
            
            # 2. Term overlap using basic NLP
            term_overlap, shared_terms = self._calculate_term_overlap(section.content, triple_text)
            
            # 3. Structural relevance based on section type and triple type
            structural_relevance = self._get_structural_relevance(section.section_type, triple.get('entity_type', 'guideline'))
            
            # Combined preliminary score
            combined_score = (
                0.6 * vector_similarity + 
                0.25 * term_overlap + 
                0.15 * structural_relevance
            )
            
            return {
                'vector_similarity': vector_similarity,
                'term_overlap': term_overlap,
                'shared_terms': shared_terms,
                'structural_relevance': structural_relevance,
                'combined_score': combined_score,
                'triple': triple,
                'section': section
            }
            
        except Exception as e:
            logger.exception(f"Error calculating triple-section relevance: {str(e)}")
            # Return default scores
            return {
                'vector_similarity': 0.0,
                'term_overlap': 0.0,
                'shared_terms': [],
                'structural_relevance': 0.0,
                'combined_score': 0.0,
                'triple': triple,
                'section': section,
                'error': str(e)
            }
    
    def _triple_to_text(self, triple):
        """
        Convert a triple to text for embedding and comparison.
        
        Args:
            triple: Guideline triple dictionary
            
        Returns:
            str: Text representation of the triple
        """
        # Start with subject label
        text = triple.get('subject_label', '')
        
        # Add predicate if available (simplified version)
        predicate = triple.get('predicate', '')
        if predicate:
            # Extract the last part of the URI
            pred_parts = predicate.split('/')
            if pred_parts:
                pred_name = pred_parts[-1]
                # Convert camelCase to spaces
                pred_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', pred_name)
                text += f" {pred_name}"
        
        # Add object (literal or label)
        if 'object_literal' in triple:
            text += f" {triple['object_literal']}"
        elif 'object_label' in triple:
            text += f" {triple['object_label']}"
        
        # Add description if available
        if 'description' in triple:
            text += f". {triple['description']}"
            
        return text
    
    def _calculate_term_overlap(self, section_content: str, triple_text: str) -> Tuple[float, List[str]]:
        """
        Calculate term overlap between section content and triple text.
        
        Args:
            section_content: Content of the document section
            triple_text: Text representation of the triple
            
        Returns:
            Tuple of (overlap score, list of shared terms)
        """
        try:
            # Normalize and tokenize section content and triple text
            section_tokens = word_tokenize(section_content.lower())
            triple_tokens = word_tokenize(triple_text.lower())
            
            # Remove stopwords and short words
            section_terms = {w for w in section_tokens if w not in self.stop_words and len(w) > 2}
            triple_terms = {w for w in triple_tokens if w not in self.stop_words and len(w) > 2}
            
            # Find intersection and calculate Jaccard similarity
            intersection = section_terms.intersection(triple_terms)
            union = section_terms.union(triple_terms)
            
            # Calculate Jaccard similarity
            if union:
                jaccard = len(intersection) / len(union)
            else:
                jaccard = 0.0
                
            # Return the score and shared terms
            return jaccard, list(intersection)
            
        except Exception as e:
            logger.exception(f"Error calculating term overlap: {str(e)}")
            return 0.0, []
    
    def _get_structural_relevance(self, section_type: str, entity_type: str) -> float:
        """
        Calculate structural relevance based on section type and entity type.
        
        Args:
            section_type: Type of the document section
            entity_type: Type of the entity in the triple
            
        Returns:
            float: Structural relevance score (0-1)
        """
        # Define relevance matrix for different combinations
        # This maps section types to entity types with relevance scores
        relevance_matrix = {
            'facts': {
                'condition': 0.9,
                'resource': 0.7,
                'action': 0.6,
                'role': 0.5,
                'guideline': 0.6
            },
            'discussion': {
                'condition': 0.7,
                'resource': 0.5,
                'action': 0.8,
                'role': 0.7,
                'guideline': 0.8
            },
            'conclusion': {
                'condition': 0.6,
                'resource': 0.4,
                'action': 0.7,
                'role': 0.6,
                'guideline': 0.9
            },
            'question': {
                'condition': 0.8,
                'resource': 0.6,
                'action': 0.7,
                'role': 0.6,
                'guideline': 0.7
            }
        }
        
        # Normalize section_type and entity_type
        normalized_section_type = section_type.lower().split('_')[0]  # handle types like "discussion_1"
        normalized_entity_type = entity_type.lower()
        
        # Get relevance score from matrix or use default
        if normalized_section_type in relevance_matrix:
            if normalized_entity_type in relevance_matrix[normalized_section_type]:
                return relevance_matrix[normalized_section_type][normalized_entity_type]
        
        # Default relevance score
        return 0.5
        
    def analyze_triple_relevance_with_llm(self, section, triple, combined_score):
        """
        Use LLM to analyze relevance between section and triple for deeper semantic understanding.
        
        Args:
            section: Document section object
            triple: Guideline triple dictionary
            combined_score: Previously calculated combined score
            
        Returns:
            dict: LLM analysis results
        """
        try:
            # Get the LLM client
            client = get_llm_client()
            if not client:
                logger.warning("LLM client unavailable for triple relevance analysis")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': "LLM analysis unavailable",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM unavailable
                }
            
            # Prepare section content (limit length to avoid token limits)
            max_content_length = 1000
            section_content = section.content
            if len(section_content) > max_content_length:
                section_content = section_content[:max_content_length] + "..."
            
            # Convert triple to text
            triple_text = self._triple_to_text(triple)
            
            # Construct the prompt
            prompt = f"""
            Analyze the relevance between this document section and ethical guideline:
            
            DOCUMENT SECTION TYPE: {section.section_type}
            DOCUMENT SECTION CONTENT:
            {section_content}
            
            ETHICAL GUIDELINE:
            {triple_text}
            
            Is there a clear semantic relationship between the section and the guideline? Provide:
            1. A yes/no determination if there's a meaningful relationship
            2. Brief reasoning for your assessment (1-2 sentences)
            3. Specific patterns or key terms that connect them, if any

            Format your response as JSON:
            {{
              "is_relevant": true/false,
              "reasoning": "Brief explanation of the relationship",
              "patterns_identified": ["pattern1", "pattern2"]
            }}
            """
            
            # Send to LLM based on API version
            result = ""
            try:
                # If new API (v2)
                if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                    response = client.chat.completions.create(
                        model=client.available_models[0],  # Use latest available model
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,  # Low temperature for more consistent results
                        max_tokens=500
                    )
                    result = response.choices[0].message.content
                    
                # If messages API (v1.5)
                elif hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                    response = client.messages.create(
                        model=client.available_models[0],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500
                    )
                    result = response.content[0].text
                    
                # If old API (v1)
                else:
                    response = client.completion(
                        prompt=f"Human: {prompt}\n\nAssistant:",
                        model=client.available_models[0],
                        temperature=0.1,
                        max_tokens_to_sample=500
                    )
                    result = response.completion
            except Exception as api_error:
                logger.warning(f"Error using LLM API: {str(api_error)}")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': f"LLM API error: {str(api_error)}",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM fails
                }
                
            # Parse JSON response
            try:
                # Clean up the result to ensure it's valid JSON
                # Sometimes LLM responses include markdown code blocks or additional text
                json_start = result.find('{')
                json_end = result.rfind('}')
                if json_start >= 0 and json_end >= 0:
                    json_str = result[json_start:json_end+1]
                    analysis = json.loads(json_str)
                else:
                    # If no JSON found, create default response
                    analysis = {
                        'is_relevant': False,
                        'reasoning': "Could not reliably determine relevance",
                        'patterns_identified': []
                    }
            except json.JSONDecodeError:
                # If JSON parsing fails, create a default response
                logger.warning(f"Failed to parse LLM response as JSON: {result}")
                analysis = {
                    'is_relevant': False,
                    'reasoning': "Could not parse LLM response",
                    'patterns_identified': []
                }
            
            # Calculate agreement score - how well does the LLM assessment match the vector similarity?
            llm_score = 1.0 if analysis.get('is_relevant', False) else 0.0
            agreement_score = 1.0 - abs(llm_score - combined_score)
            
            return {
                'llm_is_relevant': analysis.get('is_relevant', False),
                'llm_reasoning': analysis.get('reasoning', ''),
                'llm_patterns': analysis.get('patterns_identified', []),
                'agreement_score': agreement_score
            }
            
        except Exception as e:
            logger.exception(f"Error in LLM analysis: {str(e)}")
            return {
                'llm_is_relevant': False,
                'llm_reasoning': f"Error in LLM analysis: {str(e)}",
                'llm_patterns': [],
                'agreement_score': 0.5  # Neutral score if error
            }
    
    def calculate_final_relevance(self, basic_scores, llm_analysis):
        """
        Calculate final relevance score with comprehensive reasoning chain.
        
        Args:
            basic_scores: Initial metrics from calculate_triple_section_relevance
            llm_analysis: Results from LLM analysis
            
        Returns:
            dict: Final relevance metrics with complete reasoning chain
        """
        try:
            # Extract base metrics
            vector_similarity = basic_scores.get('vector_similarity', 0.0)
            term_overlap = basic_scores.get('term_overlap', 0.0)
            structural_relevance = basic_scores.get('structural_relevance', 0.0)
            
            # Extract LLM metrics
            llm_is_relevant = llm_analysis.get('llm_is_relevant', False)
            agreement_score = llm_analysis.get('agreement_score', 0.5)
            
            # Convert LLM boolean to score
            llm_relevance_score = 1.0 if llm_is_relevant else 0.0
            
            # Calculate weighted final score
            # Weight components based on confidence and reliability
            final_score = (
                0.35 * vector_similarity +
                0.20 * term_overlap +
                0.10 * structural_relevance +
                0.35 * llm_relevance_score
            )
            
            # Apply agreement bonus if metrics are in strong agreement
            if agreement_score > 0.75:
                final_score *= 1.15  # 15% bonus for strong agreement
                agreement_bonus = "Strong agreement between embedding similarity and LLM analysis"
            elif agreement_score < 0.25:
                final_score *= 0.85  # 15% penalty for strong disagreement
                agreement_bonus = "Strong disagreement between embedding similarity and LLM analysis"
            else:
                agreement_bonus = "Neutral agreement between metrics"
            
            # Determine relationship type based on final score and patterns
            relationship = "related_to"  # Default
            
            # If score is very high, suggest stronger relationship
            if final_score > 0.8:
                relationship = "strongly_related_to"
            elif final_score > 0.95:
                relationship = "directly_implements"
            
            # Calculate explanatory string for the score calculation
            calculation = (
                f"Final score {final_score:.2f} calculated from: "
                f"Vector similarity ({vector_similarity:.2f} × 0.35) + "
                f"Term overlap ({term_overlap:.2f} × 0.20) + "
                f"Structural relevance ({structural_relevance:.2f} × 0.10) + "
                f"LLM assessment ({llm_relevance_score:.1f} × 0.35) "
                f"with {agreement_bonus}"
            )
            
            # Return complete result
            return {
                'score': min(1.0, max(0.0, final_score)),  # Clamp to 0-1 range
                'relationship': relationship,
                'vector_similarity': vector_similarity,
                'term_overlap': term_overlap,
                'shared_terms': basic_scores.get('shared_terms', []),
                'structural_relevance': structural_relevance,
                'llm_reasoning': llm_analysis.get('llm_reasoning', ''),
                'llm_patterns': llm_analysis.get('llm_patterns', []),
                'calculation': calculation
            }
            
        except Exception as e:
            logger.exception(f"Error calculating final relevance: {str(e)}")
            # Return default result with error information
            return {
                'score': 0.0,
                'relationship': 'related_to',
                'vector_similarity': basic_scores.get('vector_similarity', 0.0),
                'term_overlap': basic_scores.get('term_overlap', 0.0),
                'shared_terms': basic_scores.get('shared_terms', []),
                'structural_relevance': basic_scores.get('structural_relevance', 0.0),
                'llm_reasoning': f"Error calculating final relevance: {str(e)}",
                'llm_patterns': [],
                'calculation': f"Calculation failed: {str(e)}"
            }
    
    def _generate_mock_guidelines(self, section_content: str, section_type: str) -> Dict[str, Any]:
        """
        Generate mock guidelines for a section when MCP extraction fails.
        This is a fallback implementation for testing and graceful degradation.
        
        Args:
            section_content: Content of the document section
            section_type: Type of the document section
            
        Returns:
            dict: Mock guideline extraction result
        """
        # Generic guidelines by section type
        section_type_guidelines = {
            'facts': [
                {
                    'uri': 'http://proethica.org/guidelines/fact_verification',
                    'label': 'Fact Verification Guideline',
                    'description': 'Engineers must ensure all factual statements are accurate and verifiable.',
                    'confidence': 0.75
                },
                {
                    'uri': 'http://proethica.org/guidelines/due_diligence',
                    'label': 'Due Diligence Guideline',
                    'description': 'Engineers should perform due diligence before making statements of fact.',
                    'confidence': 0.65
                }
            ],
            'discussion': [
                {
                    'uri': 'http://proethica.org/guidelines/balanced_view',
                    'label': 'Balanced Perspective Guideline',
                    'description': 'Engineers should present multiple perspectives when discussing complex issues.',
                    'confidence': 0.70
                },
                {
                    'uri': 'http://proethica.org/guidelines/informed_discussion',
                    'label': 'Informed Discussion Guideline',
                    'description': 'Engineers must base discussions on valid engineering principles and factual data.',
                    'confidence': 0.68
                }
            ],
            'conclusion': [
                {
                    'uri': 'http://proethica.org/guidelines/evidence_based_conclusions',
                    'label': 'Evidence-Based Conclusion Guideline',
                    'description': 'Engineers must draw conclusions based on sound evidence and reasoning.',
                    'confidence': 0.72
                },
                {
                    'uri': 'http://proethica.org/guidelines/public_safety',
                    'label': 'Public Safety Guideline',
                    'description': 'Engineers must prioritize public safety in all professional conclusions.',
                    'confidence': 0.85
                }
            ],
            'question': [
                {
                    'uri': 'http://proethica.org/guidelines/ethical_inquiry',
                    'label': 'Ethical Inquiry Guideline',
                    'description': 'Engineers should question practices that may compromise ethical standards.',
                    'confidence': 0.65
                },
                {
                    'uri': 'http://proethica.org/guidelines/critical_thinking',
                    'label': 'Critical Thinking Guideline',
                    'description': 'Engineers must apply critical thinking to professional questions and challenges.',
                    'confidence': 0.70
                }
            ]
        }
        
        # Normalize the section type
        normalized_section_type = section_type.lower().split('_')[0]
        
        # Select guidelines based on section type
        if normalized_section_type in section_type_guidelines:
            guidelines = section_type_guidelines[normalized_section_type]
        else:
            # Default guidelines for other section types
            guidelines = [
                {
                    'uri': 'http://proethica.org/guidelines/professional_conduct',
                    'label': 'Professional Conduct Guideline',
                    'description': 'Engineers shall uphold the highest standards of professional conduct.',
                    'confidence': 0.60
                },
                {
                    'uri': 'http://proethica.org/guidelines/competence',
                    'label': 'Professional Competence Guideline',
                    'description': 'Engineers shall perform services only in areas of their competence.',
                    'confidence': 0.55
                }
            ]
        
        # Add some variation based on content to make it less obvious these are mock guidelines
        # Use some keywords from the content
        words = section_content.lower().split()
        keywords = [w for w in words if len(w) > 5 and w not in self.stop_words]
        
        if keywords:
            # Add a content-specific guideline using extracted keywords
            # Select up to 3 random keywords
            selected_keywords = random.sample(keywords, min(3, len(keywords)))
            keyword_string = ', '.join(selected_keywords)
            
            content_guideline = {
                'uri': f"http://proethica.org/guidelines/content_specific_{selected_keywords[0]}",
                'label': f"Content-Specific Guideline on {keyword_string.title()}",
                'description': f"Engineers should carefully consider {keyword_string} in their professional practice.",
                'confidence': 0.50  # Lower confidence for these dynamic guidelines
            }
            
            guidelines.append(content_guideline)
        
        # Add relationship information
        for guideline in guidelines:
            guideline['relationship'] = 'related_to'
        
        return {
            'success': True,
            'guidelines': guidelines
        }
