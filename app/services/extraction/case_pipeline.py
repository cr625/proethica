"""
Core Case Extraction Pipeline
Modular infrastructure for analyzing all case sections across the 3-pass system
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class SectionType(Enum):
    """Case section types with processing priorities"""
    FACTS = "facts"
    DISCUSSION = "discussion" 
    QUESTIONS = "questions"
    NSPE_REFERENCES = "nspe_references"
    CONCLUSION = "conclusion"


@dataclass
class SectionConfig:
    """Configuration for section processing"""
    name: str
    priority: int
    extraction_focus: List[str]
    depends_on: List[str] = None
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


class CaseExtractionPipeline:
    """
    Orchestrates extraction across all sections and passes
    Implements modular, reusable architecture for case analysis
    """
    
    def __init__(self):
        self.section_configs = {
            SectionType.FACTS: SectionConfig(
                name="facts",
                priority=1,
                extraction_focus=["states", "roles", "events", "resources"],
                depends_on=[]
            ),
            SectionType.DISCUSSION: SectionConfig(
                name="discussion", 
                priority=2,
                extraction_focus=["obligations", "principles", "constraints", "roles"],
                depends_on=["facts"]
            ),
            SectionType.QUESTIONS: SectionConfig(
                name="questions",
                priority=3, 
                extraction_focus=["capabilities", "actions", "constraints"],
                depends_on=["facts", "discussion"]
            ),
            SectionType.NSPE_REFERENCES: SectionConfig(
                name="nspe_references",
                priority=4,
                extraction_focus=["resources", "principles"],
                depends_on=[]
            ),
            SectionType.CONCLUSION: SectionConfig(
                name="conclusion",
                priority=5,
                extraction_focus=["actions", "events", "obligations"],
                depends_on=["facts", "discussion", "questions"]
            )
        }
        
        self.section_processors = {}
        self.pass_orchestrator = PassOrchestrator()
        self.consolidator = EntityConsolidator()
        
    def process_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for complete case analysis
        
        Args:
            case_data: Dict containing case sections and metadata
            
        Returns:
            Complete analysis results with entity extractions and relationships
        """
        logger.info("Starting case extraction pipeline")
        
        # Extract section texts from case data
        sections = self._extract_sections(case_data)
        
        # Step 1: Section-level extraction with dependencies
        section_results = self._process_sections_by_priority(sections)
        
        # Step 2: Cross-section integration and consolidation
        integrated_results = self._integrate_across_sections(section_results)
        
        # Step 3: Three-pass analysis on integrated data
        final_results = self.pass_orchestrator.execute_all_passes(
            integrated_results,
            section_context=section_results
        )
        
        logger.info("Case extraction pipeline completed")
        return final_results
        
    def _extract_sections(self, case_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract section texts from case data structure"""
        sections = {}
        
        # Handle both flat content and structured sections
        if 'sections' in case_data.get('doc_metadata', {}):
            sections = case_data['doc_metadata']['sections']
        else:
            # Parse from content field for legacy cases
            content = case_data.get('content', '')
            sections = self._parse_content_sections(content)
            
        return sections
        
    def _parse_content_sections(self, content: str) -> Dict[str, str]:
        """Parse sections from structured content text"""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**') and line.endswith('**'):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                    
                # Start new section
                section_name = line[2:-2].lower().replace(' ', '_').replace(':', '')
                current_section = section_name
                current_content = []
            elif current_section and line:
                current_content.append(line)
                
        # Save final section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
        
    def _process_sections_by_priority(self, sections: Dict[str, str]) -> Dict[str, Any]:
        """Process sections in priority order with dependency awareness"""
        results = {}
        processed_sections = set()
        
        # Sort sections by priority
        section_order = sorted(
            self.section_configs.values(),
            key=lambda x: x.priority
        )
        
        for config in section_order:
            section_name = config.name
            
            if section_name not in sections:
                logger.warning(f"Section {section_name} not found in case")
                continue
                
            # Check dependencies
            if not all(dep in processed_sections for dep in config.depends_on):
                logger.warning(f"Dependencies not met for section {section_name}")
                continue
                
            # Get processor for this section
            processor = self._get_section_processor(section_name)
            
            # Build context from processed sections
            context = {
                dep: results.get(dep, {}) 
                for dep in config.depends_on
            }
            
            # Process section
            logger.info(f"Processing section: {section_name}")
            section_result = processor.process(
                sections[section_name],
                context=context,
                extraction_focus=config.extraction_focus
            )
            
            results[section_name] = section_result
            processed_sections.add(section_name)
            
        return results
        
    def _get_section_processor(self, section_name: str):
        """Get or create processor for section type"""
        if section_name not in self.section_processors:
            # Import processor classes dynamically
            from .section_processors import get_processor_classes
            processor_classes = get_processor_classes()
            
            # Get appropriate processor class
            if section_name in processor_classes:
                processor_class = processor_classes[section_name]
            else:
                # Default to generic processor
                processor_class = processor_classes['generic']
                
            # Instantiate processor
            self.section_processors[section_name] = processor_class()
                
        return self.section_processors[section_name]
        
    def _integrate_across_sections(self, section_results: Dict[str, Any]) -> Dict[str, Any]:
        """Integrate and consolidate entities across all sections"""
        return self.consolidator.consolidate_sections(section_results)


class PassOrchestrator:
    """Manages 3-pass extraction with section awareness"""
    
    def __init__(self):
        # Import extraction modules
        from app.services.extraction import (
            enhanced_prompts_roles_resources,
            enhanced_prompts_states_capabilities,
            enhanced_prompts_principles,
            enhanced_prompts_obligations,
            enhanced_prompts_constraints,
            enhanced_prompts_actions,
            enhanced_prompts_events
        )
        
        self.extractors = {
            'roles': enhanced_prompts_roles_resources.create_enhanced_roles_prompt,
            'resources': enhanced_prompts_roles_resources.create_enhanced_resources_prompt,
            'states': enhanced_prompts_states_capabilities.create_enhanced_states_prompt,
            'capabilities': enhanced_prompts_states_capabilities.create_enhanced_capabilities_prompt,
            'principles': enhanced_prompts_principles.create_enhanced_principles_prompt,
            'obligations': enhanced_prompts_obligations.create_enhanced_obligations_prompt,
            'constraints': enhanced_prompts_constraints.create_enhanced_constraints_prompt,
            'actions': enhanced_prompts_actions.create_enhanced_actions_prompt,
            'events': enhanced_prompts_events.create_enhanced_events_prompt
        }
        
    def execute_all_passes(self, integrated_data: Dict[str, Any], 
                          section_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all 3 passes with section-aware context"""
        results = {}
        
        # Pass 1: Contextual Framework (WHO, WHERE, WHAT)
        logger.info("Executing Pass 1: Contextual Framework")
        results['pass1'] = self._execute_pass1(integrated_data, section_context)
        
        # Pass 2: Normative Requirements (SHOULD/MUST) 
        logger.info("Executing Pass 2: Normative Requirements")
        results['pass2'] = self._execute_pass2(
            integrated_data,
            section_context,
            pass1_context=results['pass1']
        )
        
        # Pass 3: Temporal Dynamics (WHEN/HOW)
        logger.info("Executing Pass 3: Temporal Dynamics") 
        results['pass3'] = self._execute_pass3(
            integrated_data,
            section_context,
            pass1_context=results['pass1'],
            pass2_context=results['pass2']
        )
        
        return results
        
    def _execute_pass1(self, data: Dict[str, Any], section_context: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 1: Roles, States, Resources"""
        pass1_results = {}
        
        # Combine all section texts weighted by relevance
        combined_text = self._build_weighted_text(data, {
            'facts': 0.4,      # Primary source for states
            'discussion': 0.3,  # Reveals role relationships 
            'questions': 0.2,   # Highlights key actors
            'nspe_references': 0.1  # Resources primarily
        })
        
        # Extract Pass 1 entities
        for entity_type in ['roles', 'states', 'resources']:
            if entity_type in self.extractors:
                pass1_results[entity_type] = self._extract_entities(
                    entity_type,
                    combined_text,
                    section_context=section_context
                )
                
        return pass1_results
        
    def _execute_pass2(self, data: Dict[str, Any], section_context: Dict[str, Any],
                      pass1_context: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 2: Principles, Obligations, Constraints, Capabilities"""
        pass2_results = {}
        
        # Weight sections for normative analysis
        combined_text = self._build_weighted_text(data, {
            'discussion': 0.4,     # Primary normative reasoning
            'nspe_references': 0.3, # Code-based obligations
            'questions': 0.2,      # Capability requirements
            'conclusion': 0.1      # Final normative judgments
        })
        
        # Build pass context
        pass_context = {
            'pass1': pass1_context,
            'section_context': section_context
        }
        
        # Extract Pass 2 entities
        for entity_type in ['principles', 'obligations', 'constraints', 'capabilities']:
            if entity_type in self.extractors:
                pass2_results[entity_type] = self._extract_entities(
                    entity_type,
                    combined_text,
                    section_context=section_context,
                    pass_context=pass_context
                )
                
        return pass2_results
        
    def _execute_pass3(self, data: Dict[str, Any], section_context: Dict[str, Any],
                      pass1_context: Dict[str, Any], pass2_context: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 3: Actions, Events"""
        pass3_results = {}
        
        # Weight sections for temporal analysis
        combined_text = self._build_weighted_text(data, {
            'facts': 0.3,        # Temporal sequence of events
            'discussion': 0.3,   # Analysis of actions taken
            'conclusion': 0.3,   # Recommended actions
            'questions': 0.1     # Action-oriented questions
        })
        
        # Build full pass context
        pass_context = {
            'pass1': pass1_context,
            'pass2': pass2_context,
            'section_context': section_context
        }
        
        # Extract Pass 3 entities
        for entity_type in ['actions', 'events']:
            if entity_type in self.extractors:
                pass3_results[entity_type] = self._extract_entities(
                    entity_type,
                    combined_text,
                    section_context=section_context,
                    pass_context=pass_context
                )
                
        return pass3_results
        
    def _build_weighted_text(self, data: Dict[str, Any], weights: Dict[str, float]) -> str:
        """Combine section texts with specified weights"""
        weighted_parts = []
        
        for section, weight in weights.items():
            if section in data and data[section]:
                text = data[section]
                if isinstance(text, dict):
                    text = str(text)
                weighted_parts.append(f"[{section.upper()} - Weight: {weight}]\n{text}\n")
                
        return "\n".join(weighted_parts)
        
    def _extract_entities(self, entity_type: str, text: str, 
                         section_context: Dict[str, Any] = None,
                         pass_context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Extract entities using appropriate extractor"""
        try:
            extractor_func = self.extractors[entity_type]
            
            # Build extractor arguments
            kwargs = {
                'include_mcp_context': True,
                'pass_context': pass_context
            }
            
            # Get extraction prompt
            prompt = extractor_func(text, **kwargs)
            
            # For now, return prompt - in full implementation would call LLM
            return {
                'entity_type': entity_type,
                'prompt': prompt,
                'section_context': section_context,
                'pass_context': pass_context
            }
            
        except Exception as e:
            logger.error(f"Error extracting {entity_type}: {e}")
            return []


class EntityConsolidator:
    """Resolves and merges entities across sections and passes"""
    
    def consolidate_sections(self, section_results: Dict[str, Any]) -> Dict[str, Any]:
        """Consolidate entities across all sections"""
        consolidated = {
            'entities': {},
            'section_mapping': {},
            'conflicts': []
        }
        
        # Process each section's results
        for section_name, section_data in section_results.items():
            self._process_section_entities(
                section_name,
                section_data,
                consolidated
            )
            
        return consolidated
        
    def _process_section_entities(self, section_name: str, section_data: Dict[str, Any],
                                 consolidated: Dict[str, Any]) -> None:
        """Process entities from a single section"""
        if not isinstance(section_data, dict) or 'entities' not in section_data:
            return
            
        for entity in section_data['entities']:
            entity_key = self._generate_entity_key(entity)
            
            if entity_key in consolidated['entities']:
                # Merge with existing entity
                existing = consolidated['entities'][entity_key]
                merged = self._merge_entities(existing, entity, section_name)
                consolidated['entities'][entity_key] = merged
            else:
                # Add new entity
                entity['source_sections'] = [section_name]
                consolidated['entities'][entity_key] = entity
                
            # Track section mapping
            if section_name not in consolidated['section_mapping']:
                consolidated['section_mapping'][section_name] = []
            consolidated['section_mapping'][section_name].append(entity_key)
            
    def _generate_entity_key(self, entity: Dict[str, Any]) -> str:
        """Generate unique key for entity"""
        entity_type = entity.get('type', 'unknown')
        label = entity.get('label', 'unknown')
        return f"{entity_type}:{label}".lower().replace(' ', '_')
        
    def _merge_entities(self, existing: Dict[str, Any], new: Dict[str, Any], 
                       source_section: str) -> Dict[str, Any]:
        """Merge two entities with conflict detection"""
        merged = existing.copy()
        
        # Add source section
        merged['source_sections'].append(source_section)
        
        # Merge descriptions and context
        if 'description' in new:
            existing_desc = merged.get('description', '')
            new_desc = new['description']
            if new_desc not in existing_desc:
                merged['description'] = f"{existing_desc}\n[{source_section}] {new_desc}"
                
        # Merge confidence (average)
        if 'confidence' in new:
            existing_conf = merged.get('confidence', 0.5)
            new_conf = new['confidence']
            merged['confidence'] = (existing_conf + new_conf) / 2
            
        # Detect conflicts in key fields
        conflict_fields = ['subtype', 'category']
        for field in conflict_fields:
            if field in existing and field in new and existing[field] != new[field]:
                if 'conflicts' not in merged:
                    merged['conflicts'] = []
                merged['conflicts'].append({
                    'field': field,
                    'existing_value': existing[field],
                    'new_value': new[field],
                    'source_section': source_section
                })
                
        return merged


# Base classes for section processors
class BaseSectionProcessor:
    """Base class for all section processors"""
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process section text with optional context"""
        raise NotImplementedError
        
    def _get_relevant_entities(self, extraction_focus: List[str]) -> List[str]:
        """Filter entity types based on extraction focus"""
        if not extraction_focus:
            return []
        return extraction_focus
