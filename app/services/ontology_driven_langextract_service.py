"""
Ontology-Driven LangExtract Service for ProEthica

This service extends the existing ProEthica LangExtract functionality by integrating
with the ontology-defined case structures from OntServe via MCP protocol.
It dynamically generates LangExtract prompts based on section types and case templates
defined in the ontologies rather than using hardcoded prompts.
"""

import os
import logging
import requests
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .proethica_langextract_service import ProEthicaLangExtractService

logger = logging.getLogger(__name__)

class OntologyDrivenLangExtractService:
    """
    Ontology-driven LangExtract service that queries case structures and section types
    from ontologies to generate dynamic, contextual LangExtract prompts.
    """
    
    def __init__(self):
        """Initialize the ontology-driven service"""
        self.base_service = ProEthicaLangExtractService()
        self.ontserve_mcp_url = os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
        self.mcp_enabled = os.environ.get('ENABLE_MCP_ONTOLOGY_ACCESS', 'false').lower() == 'true'
        
        # Cache for ontology data to avoid repeated queries
        self.section_type_cache = {}
        self.case_template_cache = {}
        
        logger.info(f"OntologyDrivenLangExtractService initialized - MCP enabled: {self.mcp_enabled}")
    
    def analyze_section_content(self, section_title: str, section_text: str, 
                              case_id: Optional[int] = None, 
                              case_domain: str = 'engineering_ethics') -> Dict[str, Any]:
        """
        Analyze section content using ontology-driven approach
        
        Args:
            section_title: Title of the section (e.g., "Facts", "Discussion", etc.)
            section_text: Content to analyze
            case_id: Optional case ID for context
            case_domain: Professional domain (engineering_ethics, medical_ethics, etc.)
            
        Returns:
            Enhanced analysis results with ontology-guided extraction
        """
        
        if not self.mcp_enabled or not self._test_mcp_connection():
            logger.info("MCP not available, falling back to base service")
            return self.base_service.analyze_section_content(section_title, section_text, case_id)
        
        try:
            # Get section type information from ontology
            section_type_info = self._get_section_type_info(section_title, case_domain)
            
            if section_type_info:
                # Use ontology-guided analysis
                return self._analyze_with_ontology_guidance(
                    section_title, section_text, section_type_info, case_id, case_domain
                )
            else:
                logger.warning(f"No ontology info found for section '{section_title}', using base service")
                return self.base_service.analyze_section_content(section_title, section_text, case_id)
                
        except Exception as e:
            logger.error(f"Ontology-driven analysis failed: {e}")
            return self.base_service.analyze_section_content(section_title, section_text, case_id)
    
    def _test_mcp_connection(self) -> bool:
        """Test if MCP server is available"""
        try:
            response = requests.get(f"{self.ontserve_mcp_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _get_section_type_info(self, section_title: str, case_domain: str) -> Optional[Dict[str, Any]]:
        """
        Query ontology for section type information via MCP
        
        Args:
            section_title: The section title to map to a section type
            case_domain: The professional domain context
            
        Returns:
            Section type information including prompts and extraction targets
        """
        
        # Check cache first
        cache_key = f"{case_domain}:{section_title}"
        if cache_key in self.section_type_cache:
            return self.section_type_cache[cache_key]
        
        try:
            # Map section title to section type URI
            section_type_mapping = self._map_section_title_to_type(section_title, case_domain)
            
            if not section_type_mapping:
                return None
            
            # Query ontology for section type details
            sparql_query = f"""
            PREFIX proeth-cases: <http://proethica.org/ontology/cases#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            
            SELECT ?sectionType ?label ?comment ?definition ?source 
                   ?langExtractPrompt ?extractionTarget ?analysisPriority
            WHERE {{
                <{section_type_mapping['uri']}> a ?sectionType ;
                    rdfs:label ?label ;
                    rdfs:comment ?comment ;
                    skos:definition ?definition .
                
                OPTIONAL {{ <{section_type_mapping['uri']}> dcterms:source ?source . }}
                OPTIONAL {{ <{section_type_mapping['uri']}> proeth-cases:hasLangExtractPrompt ?langExtractPrompt . }}
                OPTIONAL {{ <{section_type_mapping['uri']}> proeth-cases:hasExtractionTarget ?extractionTarget . }}
                OPTIONAL {{ <{section_type_mapping['uri']}> proeth-cases:analysisPriority ?analysisPriority . }}
            }}
            """
            
            mcp_response = requests.post(
                f"{self.ontserve_mcp_url}/sparql",
                json={"query": sparql_query},
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if mcp_response.status_code == 200:
                results = mcp_response.json()
                if results.get('results', {}).get('bindings'):
                    binding = results['results']['bindings'][0]
                    
                    section_info = {
                        'uri': section_type_mapping['uri'],
                        'type': section_type_mapping['type'],
                        'label': binding.get('label', {}).get('value', section_title),
                        'comment': binding.get('comment', {}).get('value', ''),
                        'definition': binding.get('definition', {}).get('value', ''),
                        'sources': binding.get('source', {}).get('value', '').split(',') if binding.get('source') else [],
                        'langextract_prompt': binding.get('langExtractPrompt', {}).get('value', ''),
                        'extraction_targets': binding.get('extractionTarget', {}).get('value', '').split(', ') if binding.get('extractionTarget') else [],
                        'analysis_priority': int(binding.get('analysisPriority', {}).get('value', 5))
                    }
                    
                    # Cache the result
                    self.section_type_cache[cache_key] = section_info
                    return section_info
            
            logger.warning(f"No SPARQL results for section type: {section_title}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to query section type info: {e}")
            return None
    
    def _map_section_title_to_type(self, section_title: str, case_domain: str) -> Optional[Dict[str, str]]:
        """
        Map a section title to its corresponding ontology section type URI
        
        Args:
            section_title: The section title from the case
            case_domain: Professional domain context
            
        Returns:
            Dictionary with URI and type information
        """
        
        # Normalize section title for comparison
        title_normalized = section_title.lower().strip()
        
        # Generic section type mappings (from proethica-cases ontology)
        generic_mappings = {
            'facts': {
                'uri': 'http://proethica.org/ontology/cases#FactualSection',
                'type': 'generic'
            },
            'question': {
                'uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection', 
                'type': 'generic'
            },
            'questions': {
                'uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection',
                'type': 'generic'
            },
            'discussion': {
                'uri': 'http://proethica.org/ontology/cases#AnalysisSection',
                'type': 'generic'
            },
            'analysis': {
                'uri': 'http://proethica.org/ontology/cases#AnalysisSection',
                'type': 'generic'
            },
            'conclusion': {
                'uri': 'http://proethica.org/ontology/cases#ConclusionSection',
                'type': 'generic'
            }
        }
        
        # Domain-specific mappings for engineering ethics
        engineering_mappings = {
            'nspe code of ethics references': {
                'uri': 'http://proethica.org/ontology/cases#CodeReferenceSection',
                'type': 'domain_specific'
            },
            'code references': {
                'uri': 'http://proethica.org/ontology/cases#CodeReferenceSection',
                'type': 'domain_specific'
            },
            'code reference': {
                'uri': 'http://proethica.org/ontology/cases#CodeReferenceSection',
                'type': 'domain_specific'
            },
            'dissenting opinion': {
                'uri': 'http://proethica.org/ontology/cases#DissentingSection',
                'type': 'domain_specific'
            },
            'dissent': {
                'uri': 'http://proethica.org/ontology/cases#DissentingSection',
                'type': 'domain_specific'
            }
        }
        
        # Check domain-specific mappings first
        if case_domain == 'engineering_ethics':
            if title_normalized in engineering_mappings:
                return engineering_mappings[title_normalized]
        
        # Check generic mappings
        if title_normalized in generic_mappings:
            return generic_mappings[title_normalized]
        
        # Try partial matches for flexibility
        for key, mapping in generic_mappings.items():
            if key in title_normalized or title_normalized in key:
                return mapping
        
        if case_domain == 'engineering_ethics':
            for key, mapping in engineering_mappings.items():
                if key in title_normalized or title_normalized in key:
                    return mapping
        
        return None
    
    def _analyze_with_ontology_guidance(self, section_title: str, section_text: str,
                                       section_type_info: Dict[str, Any],
                                       case_id: Optional[int] = None,
                                       case_domain: str = 'engineering_ethics') -> Dict[str, Any]:
        """
        Perform analysis using ontology guidance for enhanced extraction
        
        Args:
            section_title: Section title
            section_text: Content to analyze
            section_type_info: Ontology information about this section type
            case_id: Optional case ID
            case_domain: Professional domain
            
        Returns:
            Enhanced analysis results
        """
        
        if not self.base_service.langextract_available or not self.base_service.service_ready:
            return self.base_service._analyze_with_fallback(section_title, section_text, case_id)
        
        try:
            import langextract as lx
            from langextract import data
            
            # Generate ontology-guided prompt
            ontology_prompt = self._generate_ontology_guided_prompt(section_type_info, case_domain)
            
            # Create domain-specific examples based on section type
            examples = self._create_section_type_examples(section_type_info, case_domain)
            
            logger.info(f"Using ontology-guided analysis for {section_type_info['label']}")
            logger.info(f"Extraction targets: {section_type_info['extraction_targets']}")
            
            # Perform extraction with ontology guidance
            extraction_result = lx.extract(
                text_or_documents=section_text,
                prompt_description=ontology_prompt,
                examples=examples,
                model_id=self.base_service.model_id,
                api_key=self.base_service.google_api_key,
                language_model_type=lx.inference.GeminiLanguageModel,
                temperature=0.3,
                fence_output=False
            )
            
            logger.info("Ontology-guided LangExtract extraction completed")
            
            # Process results with ontology context
            structured_results = self._process_ontology_guided_results(
                extraction_result, section_text, section_type_info
            )
            
            # Format results with ontology metadata
            return self._format_ontology_guided_results(
                section_title, section_text, structured_results, section_type_info, case_domain
            )
            
        except Exception as e:
            logger.error(f"Ontology-guided analysis failed: {e}")
            return self.base_service._analyze_with_fallback(section_title, section_text, case_id, error=str(e))
    
    def _generate_ontology_guided_prompt(self, section_type_info: Dict[str, Any], 
                                        case_domain: str) -> str:
        """
        Generate LangExtract prompt based on ontology section type information
        
        Args:
            section_type_info: Section type information from ontology
            case_domain: Professional domain context
            
        Returns:
            Contextualized prompt for this section type
        """
        
        # Use custom prompt if defined in ontology
        if section_type_info.get('langextract_prompt'):
            base_prompt = section_type_info['langextract_prompt']
        else:
            # Generate prompt from section type definition
            base_prompt = f"""Extract structured information from this {section_type_info['label']} section.
            
{section_type_info['definition']}"""
        
        # Add extraction targets from ontology
        extraction_targets = section_type_info.get('extraction_targets', [])
        if extraction_targets:
            targets_text = ", ".join(extraction_targets)
            base_prompt += f"\n\nSpecific extraction targets: {targets_text}"
        
        # Add domain-specific context
        domain_context = self._get_domain_context(case_domain)
        if domain_context:
            base_prompt += f"\n\nProfessional domain context: {domain_context}"
        
        # Add scholarly grounding from sources
        sources = section_type_info.get('sources', [])
        if sources:
            base_prompt += f"\n\nThis analysis is grounded in established literature and professional standards."
        
        base_prompt += "\n\nProvide clear, structured analysis suitable for professional ethics education and precedent-based reasoning."
        
        return base_prompt
    
    def _get_domain_context(self, case_domain: str) -> str:
        """Get domain-specific context for prompt enhancement"""
        
        domain_contexts = {
            'engineering_ethics': "Engineering professional ethics emphasizing public safety, competence, and NSPE Code compliance",
            'medical_ethics': "Medical professional ethics emphasizing patient autonomy, beneficence, and medical standards",
            'business_ethics': "Business professional ethics emphasizing stakeholder interests and corporate responsibility",
            'legal_ethics': "Legal professional ethics emphasizing advocacy, justice, and professional conduct rules"
        }
        
        return domain_contexts.get(case_domain, "Professional ethics principles and standards")
    
    def _create_section_type_examples(self, section_type_info: Dict[str, Any], 
                                     case_domain: str) -> List[data.ExampleData]:
        """
        Create LangExtract examples tailored to the specific section type
        
        Args:
            section_type_info: Section type information from ontology
            case_domain: Professional domain
            
        Returns:
            List of examples for this section type
        """
        
        section_type = section_type_info['type']
        section_label = section_type_info['label']
        
        # Generate examples based on section type and domain
        if 'factual' in section_label.lower() or 'facts' in section_label.lower():
            return self._create_factual_examples(case_domain)
        elif 'question' in section_label.lower():
            return self._create_question_examples(case_domain)
        elif 'analysis' in section_label.lower() or 'discussion' in section_label.lower():
            return self._create_analysis_examples(case_domain)
        elif 'conclusion' in section_label.lower():
            return self._create_conclusion_examples(case_domain)
        elif 'code' in section_label.lower() and case_domain == 'engineering_ethics':
            return self._create_code_reference_examples()
        elif 'dissent' in section_label.lower() and case_domain == 'engineering_ethics':
            return self._create_dissenting_examples()
        else:
            # Default generic example
            return self._create_generic_examples(case_domain)
    
    def _create_factual_examples(self, case_domain: str) -> List[data.ExampleData]:
        """Create examples for factual sections"""
        return [
            data.ExampleData(
                text="Engineer Smith, a licensed professional engineer with 15 years of experience, was approached by Client Corp to review structural modifications for a 10-story office building constructed in 1985. The proposed changes would remove two load-bearing columns to create an open floor plan. The building currently houses 200 employees daily.",
                extractions=[
                    data.Extraction(
                        extraction_class="factual_analysis",
                        extraction_text="structured_facts",
                        attributes={
                            "key_agents": [
                                {"name": "Engineer Smith", "credentials": "licensed professional engineer", "experience": "15 years"}
                            ],
                            "key_entities": [
                                {"entity": "Client Corp", "role": "client"},
                                {"entity": "10-story office building", "details": "constructed in 1985, houses 200 employees"}
                            ],
                            "technical_details": [
                                {"detail": "structural modifications", "specifics": "remove two load-bearing columns"},
                                {"detail": "purpose", "specifics": "create open floor plan"}
                            ],
                            "contextual_factors": [
                                {"factor": "building_occupancy", "value": "200 employees daily"},
                                {"factor": "building_age", "value": "constructed in 1985"}
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _create_question_examples(self, case_domain: str) -> List[data.ExampleData]:
        """Create examples for ethical question sections"""
        return [
            data.ExampleData(
                text="Was it ethical for Engineer Smith to proceed with the structural analysis without first conducting a thorough site inspection? Should the engineer have disclosed potential conflicts of interest given that Client Corp had previously hired Smith's firm for unrelated projects?",
                extractions=[
                    data.Extraction(
                        extraction_class="ethical_questions",
                        extraction_text="structured_questions",
                        attributes={
                            "primary_questions": [
                                {
                                    "question": "Was it ethical to proceed without thorough site inspection?",
                                    "ethical_dimensions": ["professional_competence", "due_diligence"],
                                    "stakeholders_affected": ["public", "building_occupants", "client"]
                                }
                            ],
                            "secondary_questions": [
                                {
                                    "question": "Should conflicts of interest have been disclosed?",
                                    "ethical_dimensions": ["transparency", "professional_integrity"],
                                    "relevant_standards": ["conflict_disclosure_requirements"]
                                }
                            ],
                            "underlying_dilemmas": [
                                {
                                    "dilemma": "Professional competence vs client efficiency demands",
                                    "tension": "thoroughness vs speed"
                                }
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _create_analysis_examples(self, case_domain: str) -> List[data.ExampleData]:
        """Create examples for analysis/discussion sections"""
        return [
            data.ExampleData(
                text="The NSPE Code requires engineers to hold paramount public safety. In this case, removing load-bearing columns without comprehensive analysis poses significant structural risks. While the client's business needs are important, they cannot supersede fundamental safety obligations. The engineer should have insisted on thorough structural analysis before providing any recommendations.",
                extractions=[
                    data.Extraction(
                        extraction_class="ethical_analysis",
                        extraction_text="structured_analysis",
                        attributes={
                            "principle_applications": [
                                {
                                    "principle": "hold paramount public safety",
                                    "source": "NSPE Code",
                                    "application": "Structural modifications must prioritize safety over business convenience"
                                }
                            ],
                            "reasoning_chains": [
                                {
                                    "premise": "Removing load-bearing columns poses structural risks",
                                    "conclusion": "Comprehensive analysis required before recommendations",
                                    "logical_connection": "safety_precautionary_principle"
                                }
                            ],
                            "value_tensions": [
                                {
                                    "tension": "public safety vs client business needs",
                                    "resolution": "safety takes precedence per professional codes"
                                }
                            ],
                            "professional_obligations": [
                                {
                                    "obligation": "insist on thorough structural analysis",
                                    "basis": "competence and safety requirements"
                                }
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _create_conclusion_examples(self, case_domain: str) -> List[data.ExampleData]:
        """Create examples for conclusion sections"""
        return [
            data.ExampleData(
                text="Engineer Smith should not proceed with recommendations until completing a comprehensive structural analysis including site inspection and load calculations. The engineer must inform the client that structural safety cannot be compromised for aesthetic preferences. This case establishes the precedent that professional engineers must prioritize public safety over client convenience in structural modification projects.",
                extractions=[
                    data.Extraction(
                        extraction_class="professional_conclusions",
                        extraction_text="structured_conclusions",
                        attributes={
                            "required_actions": [
                                {
                                    "action": "complete comprehensive structural analysis",
                                    "components": ["site inspection", "load calculations"],
                                    "timing": "before proceeding with recommendations"
                                },
                                {
                                    "action": "inform client about safety priorities",
                                    "message": "structural safety cannot be compromised for aesthetic preferences"
                                }
                            ],
                            "professional_determinations": [
                                {
                                    "determination": "public safety takes precedence over client convenience",
                                    "scope": "structural modification projects",
                                    "authority": "professional engineering codes"
                                }
                            ],
                            "precedential_value": [
                                {
                                    "precedent": "engineers must prioritize public safety over client convenience",
                                    "domain": "structural modifications",
                                    "application": "establishes standard for similar future cases"
                                }
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _create_code_reference_examples(self) -> List[data.ExampleData]:
        """Create examples for NSPE Code reference sections"""
        return [
            data.ExampleData(
                text="NSPE Code Section I.1 states that engineers must 'hold paramount the safety, health, and welfare of the public.' Section II.2.a requires engineers to 'perform services only in areas of their competence.' The Board of Ethical Review has consistently held that structural modifications require comprehensive analysis (BER Case 76-7, 89-3).",
                extractions=[
                    data.Extraction(
                        extraction_class="code_references",
                        extraction_text="structured_references",
                        attributes={
                            "code_provisions": [
                                {
                                    "reference": "NSPE Code Section I.1",
                                    "text": "hold paramount the safety, health, and welfare of the public",
                                    "relevance": "fundamental duty in structural decisions"
                                },
                                {
                                    "reference": "NSPE Code Section II.2.a", 
                                    "text": "perform services only in areas of their competence",
                                    "relevance": "requires thorough structural analysis capability"
                                }
                            ],
                            "precedent_cases": [
                                {
                                    "citation": "BER Case 76-7",
                                    "principle": "structural modifications require comprehensive analysis",
                                    "authority": "Board of Ethical Review"
                                },
                                {
                                    "citation": "BER Case 89-3",
                                    "principle": "structural modifications require comprehensive analysis",
                                    "authority": "Board of Ethical Review"
                                }
                            ],
                            "interpretive_guidance": [
                                {
                                    "guidance": "Board has consistently required comprehensive analysis for structural modifications",
                                    "basis": "precedent pattern in similar cases"
                                }
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _create_dissenting_examples(self) -> List[data.ExampleData]:
        """Create examples for dissenting opinion sections"""
        return [
            data.ExampleData(
                text="Dissenting Opinion: While public safety is paramount, the majority opinion may be overly conservative. Modern structural analysis software allows for preliminary assessments that could inform initial discussions without full site inspection. The engineer could have provided conditional guidance while emphasizing the need for comprehensive analysis before final recommendations.",
                extractions=[
                    data.Extraction(
                        extraction_class="dissenting_analysis",
                        extraction_text="structured_dissent",
                        attributes={
                            "alternative_interpretations": [
                                {
                                    "interpretation": "preliminary assessments acceptable for initial discussions",
                                    "reasoning": "modern analysis software enables informed conditional guidance",
                                    "limits": "not for final recommendations"
                                }
                            ],
                            "contextual_modifications": [
                                {
                                    "factor": "technological capabilities",
                                    "impact": "enables preliminary assessment without full site inspection",
                                    "limitation": "still requires comprehensive analysis for final decisions"
                                }
                            ],
                            "alternative_obligations": [
                                {
                                    "obligation": "provide conditional guidance with clear limitations",
                                    "justification": "balances client service with professional standards"
                                }
                            ],
                            "minority_position": {
                                "stance": "majority position overly conservative",
                                "rationale": "modern tools enable more nuanced professional responses"
                            }
                        }
                    )
                ]
            )
        ]
    
    def _create_generic_examples(self, case_domain: str) -> List[data.ExampleData]:
        """Create generic examples when specific section type not recognized"""
        return [
            data.ExampleData(
                text="Professional ethics requires careful consideration of competing obligations, stakeholder interests, and established principles within the specific domain context.",
                extractions=[
                    data.Extraction(
                        extraction_class="professional_ethics",
                        extraction_text="structured_content",
                        attributes={
                            "key_concepts": [
                                {"term": "competing obligations", "relevance": "central to professional ethical decisions"}
                            ],
                            "stakeholder_considerations": [
                                {"aspect": "stakeholder interests", "importance": "must be balanced in professional decisions"}
                            ],
                            "principle_grounding": [
                                {"element": "established principles", "context": "domain-specific application required"}
                            ]
                        }
                    )
                ]
            )
        ]
    
    def _process_ontology_guided_results(self, annotated_doc, original_text: str,
                                        section_type_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process LangExtract results with ontology context
        
        Args:
            annotated_doc: LangExtract results
            original_text: Original section text
            section_type_info: Section type information from ontology
            
        Returns:
            Processed results with ontology enhancements
        """
        
        # Start with base processing
        base_results = self.base_service._process_langextract_results(annotated_doc, original_text)
        
        # Enhance with ontology-specific processing
        enhanced_results = base_results.copy()
        
        # Add ontology metadata
        enhanced_results['ontology_metadata'] = {
            'section_type_uri': section_type_info['uri'],
            'section_type_label': section_type_info['label'],
            'analysis_priority': section_type_info.get('analysis_priority', 5),
            'extraction_targets': section_type_info.get('extraction_targets', []),
            'scholarly_sources': section_type_info.get('sources', [])
        }
        
        # Validate extraction targets were addressed
        targets_addressed = self._validate_extraction_targets(
            enhanced_results, section_type_info.get('extraction_targets', [])
        )
        enhanced_results['target_validation'] = targets_addressed
        
        return enhanced_results
    
    def _validate_extraction_targets(self, results: Dict[str, Any], 
                                   extraction_targets: List[str]) -> Dict[str, bool]:
        """
        Validate that extraction targets from ontology were addressed
        
        Args:
            results: Extraction results
            extraction_targets: Target types from ontology
            
        Returns:
            Dictionary showing which targets were addressed
        """
        
        validation = {}
        
        for target in extraction_targets:
            target_found = False
            
            # Check different result categories for target evidence
            if 'factual' in target and results.get('key_concepts'):
                target_found = True
            elif 'stakeholder' in target and results.get('stakeholders'):
                target_found = True
            elif 'principle' in target and results.get('ethical_principles'):
                target_found = True
            elif 'decision' in target and results.get('decision_points'):
                target_found = True
            elif 'temporal' in target and results.get('temporal_markers'):
                target_found = True
            elif 'code' in target and results.get('ethical_principles'):
                # Check if NSPE or code references found
                code_refs = [p for p in results['ethical_principles'] 
                           if isinstance(p, dict) and p.get('nspe_reference')]
                target_found = len(code_refs) > 0
            elif 'precedent' in target and results.get('ethical_principles'):
                # Check for precedent-like references
                precedent_refs = [p for p in results['ethical_principles']
                                if isinstance(p, dict) and ('case' in str(p).lower() or 'precedent' in str(p).lower())]
                target_found = len(precedent_refs) > 0
            
            validation[target] = target_found
        
        return validation
    
    def _format_ontology_guided_results(self, section_title: str, section_text: str,
                                       extraction_result: Dict[str, Any],
                                       section_type_info: Dict[str, Any],
                                       case_domain: str) -> Dict[str, Any]:
        """
        Format results with ontology metadata and enhancements
        
        Args:
            section_title: Section title
            section_text: Original text
            extraction_result: Processed extraction results
            section_type_info: Section type information
            case_domain: Professional domain
            
        Returns:
            Formatted results with ontology enhancements
        """
        
        # Start with base formatting
        base_results = self.base_service._format_langextract_results(
            section_title, section_text, extraction_result, 'ontology_guided_langextract'
        )
        
        # Add ontology-specific enhancements
        base_results['ontology_integration'] = {
            'section_type_uri': section_type_info['uri'],
            'section_type_label': section_type_info['label'],
            'section_definition': section_type_info['definition'],
            'analysis_priority': section_type_info.get('analysis_priority', 5),
            'extraction_targets': section_type_info.get('extraction_targets', []),
            'scholarly_grounding': section_type_info.get('sources', []),
            'domain_context': case_domain,
            'target_validation': extraction_result.get('target_validation', {})
        }
        
        # Update processing info
        base_results['processing_info'].update({
            'method': 'ontology_guided_langextract',
            'mcp_integration': True,
            'ontology_guidance': True,
            'section_type_recognized': True,
            'confidence': 0.9  # Higher confidence due to ontology guidance
        })
        
        # Update ethical context with ontology information
        base_results['ethical_context'].update({
            'ontology_grounded': True,
            'section_type_definition': section_type_info['definition'],
            'scholarly_foundation': len(section_type_info.get('sources', [])) > 0
        })
        
        return base_results
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status including ontology integration"""
        
        base_status = self.base_service.get_service_status()
        
        # Add ontology-specific status information
        ontology_status = {
            'mcp_enabled': self.mcp_enabled,
            'mcp_connection_available': self._test_mcp_connection(),
            'ontserve_mcp_url': self.ontserve_mcp_url,
            'section_types_cached': len(self.section_type_cache),
            'case_templates_cached': len(self.case_template_cache)
        }
        
        # Merge with base status
        enhanced_status = base_status.copy()
        enhanced_status['ontology_integration'] = ontology_status
        enhanced_status['capabilities']['ontology_guided_extraction'] = (
            self.mcp_enabled and self._test_mcp_connection()
        )
        enhanced_status['capabilities']['section_type_recognition'] = (
            self.mcp_enabled and self._test_mcp_connection()
        )
        enhanced_status['implementation'] = 'ontology_driven_proethica'
        
        # Update integration status
        if ontology_status['mcp_connection_available'] and base_status['service_ready']:
            enhanced_status['integration_status'] = 'ontology_guided_ready'
        elif base_status['service_ready']:
            enhanced_status['integration_status'] = 'langextract_ready_no_ontology'
        else:
            enhanced_status['integration_status'] = 'fallback_only'
        
        return enhanced_status
    
    def clear_cache(self):
        """Clear the ontology data cache"""
        self.section_type_cache.clear()
        self.case_template_cache.clear()
        logger.info("Ontology cache cleared")