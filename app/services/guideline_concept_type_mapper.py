"""
Intelligent type mapping service for guideline concepts.

This service maps LLM-suggested concept types to ontology types, preserving
semantic insights while maintaining ontology consistency. Instead of forcing
all invalid types to "state", it uses a multi-level mapping strategy.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TypeMappingResult:
    """Result of type mapping operation."""
    mapped_type: str              # Final type to use
    confidence: float             # Mapping confidence (0-1)
    is_new_type: bool            # Whether this suggests a new ontology type
    suggested_parent: Optional[str]  # Suggested parent class if new
    justification: str           # Why this mapping was chosen
    needs_review: bool           # Whether human review is needed
    original_type: str           # Original LLM-suggested type


class GuidelineConceptTypeMapper:
    """
    Intelligent type mapping that preserves LLM insights and enables ontology expansion.
    
    Uses a four-level mapping strategy:
    1. Exact match to core types
    2. Semantic similarity mapping  
    3. Description-based inference
    4. New type proposal with parent suggestion
    """
    
    def __init__(self):
        self.core_types = {
            "role", "principle", "obligation", "state", 
            "resource", "action", "event", "capability"
        }
        
        # Comprehensive semantic mapping dictionary
        self.semantic_mapping = self._build_semantic_mapping()
        
        # Keywords for description-based inference
        self.description_keywords = self._build_description_keywords()
        
        # Parent type suggestions for new types
        self.parent_suggestions = self._build_parent_suggestions()
        
        logger.info("GuidelineConceptTypeMapper initialized with comprehensive mappings")
    
    def map_concept_type(self, llm_type: str, concept_description: str = "", 
                        concept_name: str = "") -> TypeMappingResult:
        """
        Map LLM-suggested type to ontology type or propose new type.
        
        Args:
            llm_type: Type suggested by LLM
            concept_description: Description of the concept
            concept_name: Name/label of the concept
            
        Returns:
            TypeMappingResult with mapping decision and metadata
        """
        if not llm_type:
            return self._create_result("state", 0.3, False, None, 
                                     "No type provided, defaulting to state", True, "")
        
        llm_type_clean = llm_type.strip().lower()
        
        # Level 1: Exact match to core types
        if llm_type_clean in self.core_types:
            return self._create_result(llm_type_clean, 1.0, False, None,
                                     f"Exact match to core type '{llm_type_clean}'", False, llm_type)
        
        # Level 2: Semantic similarity mapping
        semantic_result = self._find_semantic_match(llm_type)
        if semantic_result.confidence > 0.8:
            return semantic_result
        
        # Level 3: Description-based inference
        desc_result = self._analyze_description(concept_description, concept_name)
        if desc_result.confidence > 0.5:
            return self._create_result(
                desc_result.mapped_type,
                desc_result.confidence,
                desc_result.is_new_type,
                desc_result.suggested_parent,
                f"Description analysis: {desc_result.justification}",
                desc_result.needs_review,
                llm_type
            )
        
        # Level 4: Propose new type
        return self._propose_new_type(llm_type, concept_description)
    
    def _build_semantic_mapping(self) -> Dict[str, Tuple[str, float, str]]:
        """
        Build comprehensive semantic mapping dictionary.
        
        Returns:
            Dict mapping LLM types to (core_type, confidence, justification)
        """
        return {
            # Principle mappings
            "fundamental principle": ("principle", 0.95, "Core ethical principle"),
            "core principle": ("principle", 0.95, "Core ethical principle"),
            "ethical principle": ("principle", 0.95, "Ethical principle"),
            "guiding principle": ("principle", 0.9, "Guiding principle"),
            "professional standard": ("principle", 0.85, "Professional standard as principle"),
            "core value": ("principle", 0.85, "Core value as principle"),
            "ethical value": ("principle", 0.85, "Ethical value as principle"),
            "standard": ("principle", 0.8, "Standard as principle"),
            "value": ("principle", 0.75, "Value as principle"),
            
            # Obligation mappings
            "professional duty": ("obligation", 0.95, "Professional duty"),
            "professional obligation": ("obligation", 0.95, "Professional obligation"),
            "ethical duty": ("obligation", 0.95, "Ethical duty"),
            "responsibility": ("obligation", 0.9, "Responsibility as obligation"),
            "professional responsibility": ("obligation", 0.9, "Professional responsibility"),
            "social responsibility": ("obligation", 0.85, "Social responsibility"),
            "environmental responsibility": ("obligation", 0.85, "Environmental responsibility"),
            "legal obligation": ("obligation", 0.9, "Legal obligation"),
            "duty": ("obligation", 0.85, "Duty as obligation"),
            "requirement": ("obligation", 0.8, "Requirement as obligation"),
            "ethical prohibition": ("obligation", 0.85, "Prohibition as negative obligation"),
            
            # Role mappings
            "professional role": ("role", 0.95, "Professional role"),
            "stakeholder": ("role", 0.9, "Stakeholder as role"),
            "professional relationship": ("role", 0.85, "Professional relationship as role"),
            "position": ("role", 0.8, "Position as role"),
            "agent": ("role", 0.75, "Agent as role"),
            
            # State mappings
            "condition": ("state", 0.9, "Condition as state"),
            "situation": ("state", 0.9, "Situation as state"),
            "context": ("state", 0.85, "Context as state"),
            "constraint": ("state", 0.85, "Constraint as state"),
            "risk": ("state", 0.8, "Risk as state"),
            "ethical risk": ("state", 0.85, "Ethical risk as state"),
            "hazard": ("state", 0.8, "Hazard as state"),
            "environmental condition": ("state", 0.85, "Environmental condition"),
            "organizational state": ("state", 0.85, "Organizational state"),
            
            # Action mappings
            "activity": ("action", 0.9, "Activity as action"),
            "practice": ("action", 0.85, "Practice as action"),
            "procedure": ("action", 0.85, "Procedure as action"),
            "process": ("action", 0.8, "Process as action"),
            "intervention": ("action", 0.8, "Intervention as action"),
            "communication": ("action", 0.75, "Communication as action"),
            "professional development": ("action", 0.8, "Professional development as action"),
            
            # Capability mappings
            "competency": ("capability", 0.95, "Competency as capability"),
            "skill": ("capability", 0.9, "Skill as capability"),
            "ability": ("capability", 0.9, "Ability as capability"),
            "expertise": ("capability", 0.85, "Expertise as capability"),
            "qualification": ("capability", 0.85, "Qualification as capability"),
            "professional competence": ("capability", 0.9, "Professional competence"),
            
            # Resource mappings
            "document": ("resource", 0.9, "Document as resource"),
            "information": ("resource", 0.85, "Information as resource"),
            "data": ("resource", 0.85, "Data as resource"),
            "specification": ("resource", 0.85, "Specification as resource"),
            "guideline": ("resource", 0.8, "Guideline as resource"),
            "tool": ("resource", 0.8, "Tool as resource"),
            "equipment": ("resource", 0.85, "Equipment as resource"),
            
            # Event mappings
            "incident": ("event", 0.9, "Incident as event"),
            "occurrence": ("event", 0.9, "Occurrence as event"),
            "meeting": ("event", 0.85, "Meeting as event"),
            "review": ("event", 0.8, "Review as event"),
            "audit": ("event", 0.8, "Audit as event"),
            "assessment": ("event", 0.8, "Assessment as event"),
        }
    
    def _build_description_keywords(self) -> Dict[str, List[Tuple[str, float]]]:
        """
        Build keyword patterns for description-based inference.
        
        Returns:
            Dict mapping core types to list of (keyword_pattern, confidence_boost)
        """
        return {
            "principle": [
                (r"\b(fundamental|core|basic|essential)\b", 0.8),
                (r"\b(value|belief|ethic)\b", 0.7),
                (r"\b(guide|govern|direct)\b", 0.6),
                (r"\b(principle|standard)\b", 0.8),
            ],
            "obligation": [
                (r"\b(must|shall|required|mandatory)\b", 0.8),
                (r"\b(duty|responsibility|obligation)\b", 0.8),
                (r"\b(prohibit|forbidden|not allow)\b", 0.7),
                (r"\b(comply|follow|adhere)\b", 0.6),
            ],
            "role": [
                (r"\b(role|position|function)\b", 0.8),
                (r"\b(actor|agent|stakeholder)\b", 0.7),
                (r"\b(person|individual|party)\b", 0.6),
                (r"\b(professional|expert|specialist)\b", 0.6),
                (r"\b(responsible|decision)\b", 0.5),
                (r"\b(who|entity|organization)\b", 0.4),
            ],
            "capability": [
                (r"\b(skill|ability|competenc)\b", 0.8),
                (r"\b(qualified|capable|expert)\b", 0.7),
                (r"\b(knowledge|understanding|expertise)\b", 0.6),
                (r"\b(train|educate|develop)\b", 0.5),
                (r"\b(technical|engineering)\b", 0.4),
            ],
            "action": [
                (r"\b(perform|conduct|execute|carry out)\b", 0.7),
                (r"\b(process|procedure|method)\b", 0.6),
                (r"\b(implement|apply|practice)\b", 0.6),
                (r"\b(communicate|report|disclose)\b", 0.6),
            ],
            "state": [
                (r"\b(condition|situation|circumstance)\b", 0.8),
                (r"\b(constraint|limitation|restriction)\b", 0.7),
                (r"\b(context|environment|setting)\b", 0.6),
                (r"\b(pressure|stress|conflict)\b", 0.6),
            ],
            "resource": [
                (r"\b(document|specification|standard)\b", 0.8),
                (r"\b(information|data|knowledge)\b", 0.7),
                (r"\b(tool|equipment|material)\b", 0.7),
                (r"\b(budget|funding|resource)\b", 0.7),
            ],
            "event": [
                (r"\b(event|incident|occurrence)\b", 0.8),
                (r"\b(meeting|review|audit)\b", 0.7),
                (r"\b(milestone|deadline|schedule)\b", 0.6),
                (r"\b(happen|occur|take place)\b", 0.6),
                (r"\b(construction|project)\b", 0.4),
            ],
        }
    
    def _build_parent_suggestions(self) -> Dict[str, str]:
        """
        Build suggestions for parent types of new concept types.
        
        Returns:
            Dict mapping type patterns to suggested parent types
        """
        return {
            # Order matters - more specific terms first
            "professional development": "action",
            "professional growth": "action",
            "professional courtesy": "obligation",
            "development": "action",
            "growth": "action",
            "standard": "principle",
            "value": "principle", 
            "ethic": "principle",
            "justice": "principle",
            "duty": "obligation",
            "responsibility": "obligation",
            "requirement": "obligation",
            "courtesy": "obligation",
            "stakeholder": "role",
            "professional": "role",
            "competency": "capability",
            "skill": "capability",
            "process": "action",
            "activity": "action",
            "condition": "state",
            "constraint": "state",
            "document": "resource",
            "tool": "resource",
            "incident": "event",
            "meeting": "event",
        }
    
    def _find_semantic_match(self, llm_type: str) -> TypeMappingResult:
        """Find best semantic match using similarity and exact mappings."""
        llm_type_clean = llm_type.strip().lower()
        
        # Check exact mappings first
        if llm_type_clean in self.semantic_mapping:
            core_type, confidence, justification = self.semantic_mapping[llm_type_clean]
            return self._create_result(core_type, confidence, False, None,
                                     f"Semantic mapping: {justification}", False, llm_type)
        
        # Check fuzzy string matching
        best_match = None
        best_score = 0.0
        
        for semantic_type, (core_type, base_confidence, justification) in self.semantic_mapping.items():
            similarity = SequenceMatcher(None, llm_type_clean, semantic_type).ratio()
            if similarity > 0.7 and similarity > best_score:
                best_score = similarity
                best_match = (core_type, base_confidence * similarity, justification)
        
        if best_match:
            core_type, confidence, justification = best_match
            return self._create_result(core_type, confidence, False, None,
                                     f"Fuzzy match: {justification} (similarity: {best_score:.2f})", 
                                     confidence < 0.8, llm_type)
        
        return self._create_result("state", 0.3, False, None,
                                 "No semantic match found", True, llm_type)
    
    def _analyze_description(self, description: str, concept_name: str = "") -> TypeMappingResult:
        """Analyze concept description and name for type hints."""
        if not description and not concept_name:
            return self._create_result("state", 0.3, False, None,
                                     "No description available for analysis", True, "")
        
        text_to_analyze = f"{concept_name} {description}".lower()
        
        type_scores = {}
        
        for core_type, patterns in self.description_keywords.items():
            score = 0.0
            matched_patterns = []
            
            for pattern, confidence_boost in patterns:
                if re.search(pattern, text_to_analyze):
                    score += confidence_boost
                    matched_patterns.append(pattern)
            
            if score > 0:
                # Normalize score and cap at 0.9
                normalized_score = min(score / 2.0, 0.9)
                type_scores[core_type] = (normalized_score, matched_patterns)
        
        if not type_scores:
            return self._create_result("state", 0.3, False, None,
                                     "No keywords matched in description", True, "")
        
        # Get best scoring type
        best_type = max(type_scores.keys(), key=lambda t: type_scores[t][0])
        best_score, matched_patterns = type_scores[best_type]
        
        justification = f"Keywords matched for {best_type}: {', '.join(matched_patterns[:3])}"
        
        return self._create_result(best_type, best_score, False, None,
                                 justification, best_score < 0.7, "")
    
    def _propose_new_type(self, llm_type: str, description: str = "") -> TypeMappingResult:
        """Propose a new type for ontology expansion."""
        # Suggest parent type based on keywords
        suggested_parent = "state"  # Default fallback
        
        llm_type_lower = llm_type.lower()
        # Find all matching patterns and prefer more specific ones
        matches = []
        for pattern, parent in self.parent_suggestions.items():
            if pattern in llm_type_lower:
                matches.append((len(pattern), parent))  # Prefer longer, more specific matches
        
        if matches:
            # Sort by pattern length (descending) to prefer more specific matches
            matches.sort(reverse=True)
            suggested_parent = matches[0][1]
        
        # Check description for better parent suggestion
        if description:
            desc_result = self._analyze_description(description)
            if desc_result.confidence > 0.4:
                suggested_parent = desc_result.mapped_type
        
        justification = f"New type proposal: '{llm_type}' could be added as subclass of '{suggested_parent}'"
        
        return self._create_result(suggested_parent, 0.6, True, suggested_parent,
                                 justification, True, llm_type)
    
    def _create_result(self, mapped_type: str, confidence: float, is_new_type: bool,
                      suggested_parent: Optional[str], justification: str, 
                      needs_review: bool, original_type: str) -> TypeMappingResult:
        """Create a TypeMappingResult with consistent formatting."""
        return TypeMappingResult(
            mapped_type=mapped_type,
            confidence=round(confidence, 3),
            is_new_type=is_new_type,
            suggested_parent=suggested_parent,
            justification=justification,
            needs_review=needs_review,
            original_type=original_type
        )
    
    def get_mapping_statistics(self) -> Dict[str, int]:
        """Get statistics about available mappings."""
        stats = {
            "total_semantic_mappings": len(self.semantic_mapping),
            "core_types": len(self.core_types),
            "description_patterns": sum(len(patterns) for patterns in self.description_keywords.values()),
            "parent_suggestions": len(self.parent_suggestions)
        }
        
        # Count mappings by target type
        for target_type in self.core_types:
            count = sum(1 for _, (mapped_type, _, _) in self.semantic_mapping.items() 
                       if mapped_type == target_type)
            stats[f"{target_type}_mappings"] = count
        
        return stats