"""
Service for converting agent conversations to NSPE-format engineering ethics cases.

This service takes a complete agent conversation and generates a structured
engineering ethics case following the NSPE Board of Ethical Review format.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from app.services.llm.manager import LLMManager
from app.models import Document
from app.models.world import World
from app.models.agent_conversation import AgentConversation
from app import db

logger = logging.getLogger(__name__)


class ConversationToCaseService:
    """Service for converting agent conversations to NSPE-format cases."""
    
    def __init__(self):
        """Initialize the service."""
        self.llm_manager = LLMManager()
    
    def generate_case_from_conversation(self, conversation: AgentConversation, 
                                     user_title: Optional[str] = None) -> Optional[Document]:
        """
        Generate a complete NSPE-format case from an agent conversation.
        
        Args:
            conversation: AgentConversation instance with complete thread
            user_title: Optional user-provided title override
            
        Returns:
            Document instance with generated case, or None if generation fails
        """
        try:
            logger.info(f"Generating case from conversation {conversation.id}")
            
            # Extract conversation context
            context = self._extract_conversation_context(conversation)
            
            # Generate NSPE-format case content
            case_content = self._generate_nspe_case_content(context)
            
            if not case_content:
                logger.error(f"Failed to generate case content for conversation {conversation.id}")
                return None
            
            # Create Document record
            document = self._create_case_document(
                conversation=conversation,
                case_content=case_content,
                user_title=user_title
            )
            
            # Update conversation with generated case
            conversation.generated_case_id = document.id
            conversation.case_generation_status = 'generated'
            conversation.mark_completed()
            
            db.session.commit()
            
            logger.info(f"Successfully generated case {document.id} from conversation {conversation.id}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating case from conversation {conversation.id}: {e}")
            if conversation:
                conversation.case_generation_status = 'failed'
                db.session.commit()
            return None
    
    def _extract_conversation_context(self, conversation: AgentConversation) -> Dict:
        """Extract key context from conversation for case generation."""
        context = {
            'conversation_id': conversation.id,
            'world_id': conversation.world_id,
            'ontology_selections': conversation.ontology_selections or {},
            'total_messages': len(conversation.messages) if conversation.messages else 0,
            'user_messages': [],
            'assistant_messages': [],
            'key_themes': [],
            'selected_concepts_summary': conversation.get_selected_concepts_summary()
        }
        
        # Extract messages by role
        if conversation.messages:
            for msg in conversation.messages:
                msg_data = {
                    'content': msg.get('content', ''),
                    'timestamp': msg.get('timestamp'),
                    'metadata': msg.get('metadata', {})
                }
                
                if msg.get('role') == 'user':
                    context['user_messages'].append(msg_data)
                elif msg.get('role') == 'assistant':
                    context['assistant_messages'].append(msg_data)
        
        # Extract key themes from ontology selections
        if conversation.ontology_selections:
            for category, concepts in conversation.ontology_selections.items():
                if concepts:
                    context['key_themes'].extend([f"{category}: {concept}" for concept in concepts])
        
        return context
    
    def _generate_nspe_case_content(self, context: Dict) -> Optional[Dict]:
        """Generate NSPE-format case content using LLM."""
        
        # Build comprehensive prompt for case generation
        prompt = self._create_case_generation_prompt(context)
        
        try:
            # Generate case content using LLMManager
            llm_response = self.llm_manager.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )

            case_text = llm_response.text
            
            if not case_text:
                logger.error("LLM returned empty case content")
                return None
            
            # Parse the generated content into sections
            case_sections = self._parse_case_sections(case_text, context)
            
            return case_sections
            
        except Exception as e:
            logger.error(f"Error generating case content with LLM: {e}")
            return None
    
    def _create_case_generation_prompt(self, context: Dict) -> str:
        """Create detailed prompt for LLM case generation."""
        
        # Build conversation summary
        conversation_summary = self._summarize_conversation(context)
        
        # Build ontology context
        ontology_context = self._build_ontology_context(context)
        
        prompt = f"""You are an expert in engineering ethics who writes cases for the NSPE Board of Ethical Review.

Based on the following agent-assisted conversation about engineering ethics, generate a complete NSPE-format case study.

CONVERSATION SUMMARY:
{conversation_summary}

ONTOLOGY CONCEPTS USED:
{ontology_context}

INSTRUCTIONS:
Generate a complete NSPE Board of Ethical Review case with the following sections:

**FACTS:**
Write 3-4 factual statements describing the engineering situation, stakeholders, and context. Use past tense and objective language.

**QUESTION(S):**
Write 1-2 clear ethical questions that an engineer would face in this situation. Questions should focus on professional conduct and ethical decision-making.

**NSPE CODE OF ETHICS REFERENCES:**
List 2-3 relevant NSPE Code of Ethics principles that apply to this case. Use the format:
- Section [number]: [principle title]

**DISCUSSION:**
Write a detailed ethical analysis (200-300 words) that:
- Analyzes the ethical considerations
- References the NSPE Code sections
- Considers professional obligations and public welfare
- Discusses potential consequences of different choices

**CONCLUSION:**
Provide a clear conclusion about the ethical course of action, typically 50-100 words.

FORMAT:
Use clear section headers and professional language appropriate for engineering ethics education.

The case should incorporate the selected ontological concepts naturally into the scenario while maintaining realistic engineering context."""
        
        return prompt
    
    def _summarize_conversation(self, context: Dict) -> str:
        """Create a summary of the conversation content."""
        if not context['user_messages']:
            return "No user messages found."
        
        # Get key user inputs
        user_inputs = [msg['content'] for msg in context['user_messages'][:5]]  # First 5 messages
        
        # Get key assistant responses
        assistant_responses = [msg['content'][:200] + "..." for msg in context['assistant_messages'][:3]]
        
        summary = f"User discussed: {'; '.join(user_inputs[:3])}\n"
        if assistant_responses:
            summary += f"Agent provided guidance on: {'; '.join(assistant_responses[:2])}"
        
        return summary
    
    def _build_ontology_context(self, context: Dict) -> str:
        """Build readable ontology context for the prompt."""
        if not context['ontology_selections']:
            return "No specific ontology concepts selected."
        
        context_lines = []
        for category, concepts in context['ontology_selections'].items():
            if concepts:
                context_lines.append(f"• {category}: {', '.join(concepts)}")
        
        if not context_lines:
            return "No specific ontology concepts selected."
        
        return "\n".join(context_lines)
    
    def _parse_case_sections(self, case_text: str, context: Dict) -> Dict:
        """Parse generated case text into structured sections."""
        sections = {
            'facts': '',
            'questions': '',
            'references': '',
            'discussion': '',
            'conclusion': '',
            'raw_content': case_text,
            'generation_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'conversation_id': context['conversation_id'],
                'ontology_selections': context['ontology_selections'],
                'llm_service': 'claude' if self.llm_service.use_claude else 'openai'
            }
        }
        
        # Simple section parsing based on headers
        current_section = None
        lines = case_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Detect section headers
            if any(keyword in line.lower() for keyword in ['facts:', 'fact:']):
                current_section = 'facts'
                continue
            elif any(keyword in line.lower() for keyword in ['question', 'questions:']):
                current_section = 'questions'
                continue
            elif any(keyword in line.lower() for keyword in ['reference', 'nspe code', 'code of ethics']):
                current_section = 'references'
                continue
            elif any(keyword in line.lower() for keyword in ['discussion:', 'analysis:']):
                current_section = 'discussion'
                continue
            elif any(keyword in line.lower() for keyword in ['conclusion:', 'finding:']):
                current_section = 'conclusion'
                continue
            
            # Add content to current section
            if current_section and line:
                if sections[current_section]:
                    sections[current_section] += '\n'
                sections[current_section] += line
        
        return sections
    
    def _create_case_document(self, conversation: AgentConversation, 
                            case_content: Dict, user_title: Optional[str] = None) -> Document:
        """Create Document record with generated case content."""
        
        # Generate title
        title = user_title or self._generate_case_title(case_content, conversation)
        
        # Build document metadata
        doc_metadata = {
            'source': 'agent_generated',
            'generation_method': 'language_model_assisted',
            'source_conversation_id': conversation.id,
            'ontology_selections': conversation.ontology_selections,
            'generation_timestamp': datetime.utcnow().isoformat(),
            'selected_concepts_summary': conversation.get_selected_concepts_summary(),
            
            # NSPE-format sections
            'sections': {
                'facts': case_content.get('facts', ''),
                'questions': case_content.get('questions', ''),
                'nspe_references': case_content.get('references', ''),
                'discussion': case_content.get('discussion', ''),
                'conclusion': case_content.get('conclusion', '')
            },
            
            # Generation metadata
            'generation_metadata': case_content.get('generation_metadata', {}),
            
            # Full conversation thread for reference
            'conversation_thread': conversation.messages if conversation.messages else []
        }
        
        # Create document
        document = Document(
            title=title,
            content=case_content.get('raw_content', ''),
            document_type='case_study',
            world_id=conversation.world_id,
            source='Generated with Language Model assistance',
            doc_metadata=doc_metadata,
            processing_status='COMPLETED',
            processing_progress=100
        )
        
        db.session.add(document)
        db.session.flush()  # Get ID without committing
        
        return document
    
    def _generate_case_title(self, case_content: Dict, conversation: AgentConversation) -> str:
        """Generate an appropriate title for the case."""
        
        # Try to extract from facts or first user message
        if case_content.get('facts'):
            # Simple title extraction from facts
            facts = case_content['facts'][:100]
            if 'structural' in facts.lower():
                return "Structural Engineering Ethics Case"
            elif 'safety' in facts.lower():
                return "Engineering Safety Ethics Case"
        
        # Fallback based on ontology selections
        if conversation.ontology_selections:
            categories = list(conversation.ontology_selections.keys())
            if categories:
                return f"Engineering Ethics Case - {categories[0]} Focus"
        
        # Final fallback
        return f"Language Model Generated Ethics Case"
    
    def preview_case_generation(self, conversation: AgentConversation) -> Dict:
        """
        Generate a preview of what the case would look like without saving it.
        
        Args:
            conversation: AgentConversation to preview
            
        Returns:
            Dictionary with preview data
        """
        try:
            context = self._extract_conversation_context(conversation)
            preview = {
                'can_generate': conversation.can_generate_case(),
                'context_summary': {
                    'message_count': context['total_messages'],
                    'ontology_concepts': context['selected_concepts_summary'],
                    'key_themes': context['key_themes'][:5],  # First 5 themes
                    'estimated_sections': self._estimate_case_sections(context)
                },
                'preview_title': self._generate_case_title({}, conversation)
            }
            
            return preview
            
        except Exception as e:
            logger.error(f"Error generating case preview: {e}")
            return {'can_generate': False, 'error': str(e)}
    
    def _estimate_case_sections(self, context: Dict) -> List[str]:
        """Estimate what sections will be generated based on context."""
        sections = ['Facts', 'Questions', 'NSPE Code References']
        
        if context['total_messages'] >= 3:
            sections.append('Discussion')
        
        if context['total_messages'] >= 4:
            sections.append('Conclusion')
        
        return sections