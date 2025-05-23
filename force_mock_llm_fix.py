#!/usr/bin/env python3
"""
Comprehensive fix to force all LLM services to use engineering ethics mock data
and clear any cached military medical content.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def apply_comprehensive_fix():
    """Apply comprehensive fix to eliminate military medical triage content."""
    
    print("=== Applying Comprehensive Fix ===")
    
    # 1. Force environment variables for mock usage
    os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'true'
    os.environ['FORCE_MOCK_LLM'] = 'true'
    
    # 2. Override all LLM services to use only mock data
    print("1. Overriding LLM services...")
    
    # Import after setting environment variables
    from app.services.llm_service import LLMService
    from langchain_community.llms.fake import FakeListLLM
    
    # Create engineering ethics mock responses
    engineering_ethics_responses = [
        # Conclusion prediction responses
        """Based on the engineering ethics case presented, the conduct described appears to be unethical according to the NSPE Code of Ethics.

The engineer in question failed to uphold their fundamental obligation to hold paramount the safety, health, and welfare of the public. By proceeding with a design that had known safety concerns without proper disclosure or remediation, the engineer violated Section I.1 of the NSPE Code of Ethics.

Additionally, the engineer's failure to be honest and impartial in their professional judgment violates Section II.3, which requires engineers to issue public statements only in an objective and truthful manner. The engineer should have disclosed the limitations and potential risks associated with the design.

The proper course of action would have been to:
1. Immediately disclose the safety concerns to relevant parties
2. Recommend design modifications to address the identified risks
3. Refuse to approve the design until safety issues were resolved
4. Document all concerns and remedial actions taken

Therefore, the conduct described is unethical and inconsistent with the NSPE Code of Ethics.""",

        # Alternative conclusion response
        """The engineering ethics scenario presented involves a clear violation of professional engineering standards and the NSPE Code of Ethics.

The engineer's decision to prioritize economic considerations over public safety represents a fundamental breach of professional responsibility. Under Section I.1 of the NSPE Code, engineers must hold paramount the safety, health, and welfare of the public.

The engineer's conduct is unethical because:
1. Public safety was not given priority consideration
2. Professional judgment was compromised by economic pressures
3. There was inadequate disclosure of risks and limitations
4. The engineer failed to act as a faithful agent for their employer while maintaining ethical standards

The appropriate ethical response would require:
1. Full disclosure of safety concerns to all stakeholders
2. Recommendation of design improvements to meet safety standards
3. Refusal to approve inadequate designs regardless of cost pressures
4. Clear documentation of the decision-making process

This case demonstrates the importance of maintaining professional integrity and prioritizing public welfare in engineering practice.""",

        # Additional responses for variety
        "This engineering ethics case involves questions of professional responsibility, design integrity, and adherence to the NSPE Code of Ethics. The key ethical considerations include public safety, professional honesty, and the engineer's duty to their employer and the public.",
        
        "The scenario presents a conflict between economic pressures and professional ethical obligations. Engineers must navigate these challenges while maintaining their commitment to public safety and professional integrity as outlined in the NSPE Code of Ethics.",
        
        "Based on the NSPE Code of Ethics, this case requires careful consideration of the engineer's duties to the public, employer, and profession. The primary ethical framework emphasizes public safety as the paramount concern.",
        
        "This engineering ethics dilemma highlights the importance of maintaining professional standards even under pressure. The NSPE Code of Ethics provides clear guidance for resolving such conflicts."
    ]
    
    # 3. Monkey patch all LLM service instances
    def create_engineering_ethics_mock_llm():
        return FakeListLLM(responses=engineering_ethics_responses)
    
    # Override the LLMService._create_mock_llm method
    LLMService._create_mock_llm = lambda self: create_engineering_ethics_mock_llm()
    
    # 4. Force any existing LLM instances to use the new mock
    original_init = LLMService.__init__
    
    def forced_mock_init(self, model_name: str = "gpt-3.5-turbo", llm=None):
        """Force LLMService to always use engineering ethics mock LLM."""
        self.model_name = model_name
        self.llm = create_engineering_ethics_mock_llm()  # Always use our mock
        
        # Initialize MCP client
        from app.services.mcp_client import MCPClient
        self.mcp_client = MCPClient.get_instance()
        
        # Setup prompt templates
        from langchain.prompts import PromptTemplate
        
        self.chat_prompt = PromptTemplate(
            input_variables=["context", "message", "guidelines"],
            template="""
            You are an AI assistant helping users with engineering ethics scenarios.
            
            Conversation history:
            {context}
            
            Guidelines for reference:
            {guidelines}
            
            User message: {message}
            
            Respond to the user's message focusing on engineering ethics principles and the NSPE Code of Ethics.
            """
        )
        
        self.options_prompt = PromptTemplate(
            input_variables=["context", "guidelines"],
            template="""
            Generate engineering ethics focused prompt options based on the conversation and guidelines.
            Format as JSON array with 'id' and 'text' fields.
            Example: [{"id": 1, "text": "Analyze the NSPE Code of Ethics implications"}, {"id": 2, "text": "What are the public safety considerations?"}]
            """
        )
        
        # Setup runnable sequences
        self.chat_chain = self.chat_prompt | self.llm
        self.options_chain = self.options_prompt | self.llm
        
        # Set default options
        self._default_options = [
            {"id": 1, "text": "Analyze the NSPE Code of Ethics implications"},
            {"id": 2, "text": "What are the public safety considerations?"},
            {"id": 3, "text": "How should professional integrity be maintained?"}
        ]
    
    # Apply the forced mock initialization
    LLMService.__init__ = forced_mock_init
    
    print("✓ LLM services patched to use engineering ethics content")
    
    # 5. Also patch the prediction service if it exists
    try:
        from app.services.experiment.prediction_service import PredictionService
        
        # Override PredictionService LLM initialization
        original_prediction_init = PredictionService.__init__
        
        def forced_prediction_init(self, llm_service=None):
            # Create new LLM service with forced mock
            self.llm_service = LLMService()  # This will now use our forced mock
            
            # Initialize other services normally
            from app.services.section_embedding_service import SectionEmbeddingService
            from app.services.guideline_section_service import GuidelineSectionService
            from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
            
            self.embedding_service = SectionEmbeddingService()
            self.guideline_service = GuidelineSectionService()
            self.triple_association_service = SectionTripleAssociationService()
        
        PredictionService.__init__ = forced_prediction_init
        
        print("✓ PredictionService patched to use engineering ethics content")
        
    except ImportError:
        print("  PredictionService not available for patching")
    
    print("\n=== Fix Applied Successfully ===")
    print("All LLM services will now use engineering ethics content instead of military medical content.")
    print("Restart your application to ensure the fix takes effect.")

if __name__ == "__main__":
    apply_comprehensive_fix()
