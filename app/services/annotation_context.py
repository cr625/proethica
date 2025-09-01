"""
Annotation Context Management for Multi-Pass Cascading Annotation

Tracks annotations between passes and provides contextual hints for informed annotation.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class SemanticRegion:
    """Represents a semantically significant region in the text."""
    start: int
    end: int
    concept_uris: Set[str] = field(default_factory=set)
    semantic_field: str = ""
    importance: float = 0.5
    
    def contains(self, position: int) -> bool:
        """Check if a position falls within this region."""
        return self.start <= position <= self.end
    
    def overlaps(self, start: int, end: int) -> bool:
        """Check if a range overlaps with this region."""
        return not (end < self.start or start > self.end)


@dataclass
class ConceptRelationship:
    """Represents a relationship between concepts."""
    source_uri: str
    target_uri: str
    relationship_type: str
    strength: float = 1.0
    bidirectional: bool = False


@dataclass
class AnnotationHint:
    """Hint for the next annotation pass."""
    concept_uri: str
    concept_label: str
    hint_type: str  # 'parent', 'child', 'sibling', 'related', 'co-occurrence'
    confidence_boost: float
    search_keywords: List[str] = field(default_factory=list)
    search_radius: int = 100  # Characters around previous annotation
    source_annotation_uri: Optional[str] = None


class AnnotationContext:
    """
    Manages context between annotation passes for informed cascading annotation.
    """
    
    def __init__(self):
        """Initialize the annotation context."""
        self.current_pass = 0
        self.previous_annotations = []
        self.all_annotations = []
        self.semantic_regions = []
        self.concept_graph = defaultdict(list)  # URI -> list of related URIs
        self.confidence_modifiers = {}
        self.ontology_hierarchy = {}  # Store ontology relationships
        self.co_occurrence_patterns = defaultdict(set)
        self.text_positions = {}  # Track where concepts appear in text
        
        # Configuration
        self.hint_generation_enabled = True
        self.max_search_radius = 200
        self.base_confidence_boost = 0.15
        self.semantic_proximity_boost = 0.2
        self.conflict_penalty = 0.3
        
        logger.info("Annotation context initialized")
    
    def start_new_pass(self, ontology_name: str, priority: int):
        """
        Start a new annotation pass.
        
        Args:
            ontology_name: Name of the ontology for this pass
            priority: Priority level of this ontology
        """
        self.current_pass += 1
        self.previous_annotations = self.all_annotations.copy()
        logger.info(f"Starting pass {self.current_pass} with ontology {ontology_name} (priority {priority})")
    
    def add_annotation(self, annotation: Dict[str, Any]):
        """
        Add an annotation from the current pass.
        
        Args:
            annotation: Annotation data including URI, text, position, etc.
        """
        self.all_annotations.append(annotation)
        
        # Track text position
        uri = annotation.get('concept_uri')
        if uri:
            position = {
                'start': annotation.get('start_offset', 0),
                'end': annotation.get('end_offset', 0),
                'text': annotation.get('text_segment', ''),
                'ontology': annotation.get('ontology_name', 'unknown')
            }
            if uri not in self.text_positions:
                self.text_positions[uri] = []
            self.text_positions[uri].append(position)
        
        # Update semantic regions
        self._update_semantic_regions(annotation)
        
        # Update concept graph
        self._update_concept_graph(annotation)
        
        # Track co-occurrences
        self._track_co_occurrences(annotation)
    
    def _update_semantic_regions(self, annotation: Dict[str, Any]):
        """Update semantic regions based on new annotation."""
        start = annotation.get('start_offset', 0)
        end = annotation.get('end_offset', 0)
        uri = annotation.get('concept_uri', '')
        
        # Check if this overlaps with existing regions
        merged = False
        for region in self.semantic_regions:
            if region.overlaps(start, end):
                # Expand region and add concept
                region.start = min(region.start, start)
                region.end = max(region.end, end)
                region.concept_uris.add(uri)
                merged = True
                break
        
        if not merged:
            # Create new region
            region = SemanticRegion(
                start=start,
                end=end,
                concept_uris={uri},
                semantic_field=annotation.get('concept_type', ''),
                importance=annotation.get('confidence', 0.5)
            )
            self.semantic_regions.append(region)
    
    def _update_concept_graph(self, annotation: Dict[str, Any]):
        """Update the concept relationship graph."""
        uri = annotation.get('concept_uri', '')
        if not uri:
            return
        
        # Find nearby annotations to establish relationships
        start = annotation.get('start_offset', 0)
        
        for other_ann in self.all_annotations:
            if other_ann == annotation:
                continue
            
            other_uri = other_ann.get('concept_uri', '')
            if not other_uri:
                continue
            
            other_start = other_ann.get('start_offset', 0)
            distance = abs(start - other_start)
            
            # If annotations are close, they're likely related
            if distance < self.max_search_radius:
                strength = 1.0 - (distance / self.max_search_radius)
                self.concept_graph[uri].append({
                    'target': other_uri,
                    'strength': strength,
                    'type': 'proximity'
                })
    
    def _track_co_occurrences(self, annotation: Dict[str, Any]):
        """Track which concepts tend to appear together."""
        uri = annotation.get('concept_uri', '')
        if not uri:
            return
        
        # Find concepts in nearby regions
        start = annotation.get('start_offset', 0)
        
        for region in self.semantic_regions:
            if region.contains(start):
                for other_uri in region.concept_uris:
                    if other_uri != uri:
                        self.co_occurrence_patterns[uri].add(other_uri)
                        self.co_occurrence_patterns[other_uri].add(uri)
    
    def generate_hints(self, text_segment: str, position: int) -> List[AnnotationHint]:
        """
        Generate hints for the current position based on previous annotations.
        
        Args:
            text_segment: Text being analyzed
            position: Position in the full text
            
        Returns:
            List of annotation hints
        """
        if not self.hint_generation_enabled or not self.previous_annotations:
            return []
        
        hints = []
        
        # Find nearby previous annotations
        nearby_annotations = self._find_nearby_annotations(position)
        
        for ann in nearby_annotations:
            uri = ann.get('concept_uri', '')
            if not uri:
                continue
            
            # Generate hints based on relationships
            related_hints = self._generate_related_hints(uri, ann)
            hints.extend(related_hints)
            
            # Generate hints based on co-occurrence patterns
            co_occurrence_hints = self._generate_co_occurrence_hints(uri, position)
            hints.extend(co_occurrence_hints)
        
        # Remove duplicates and sort by confidence boost
        unique_hints = self._deduplicate_hints(hints)
        unique_hints.sort(key=lambda h: h.confidence_boost, reverse=True)
        
        return unique_hints[:10]  # Return top 10 hints
    
    def _find_nearby_annotations(self, position: int) -> List[Dict[str, Any]]:
        """Find annotations near the given position."""
        nearby = []
        
        for ann in self.previous_annotations:
            start = ann.get('start_offset', 0)
            distance = abs(position - start)
            
            if distance < self.max_search_radius:
                nearby.append(ann)
        
        return nearby
    
    def _generate_related_hints(self, uri: str, annotation: Dict[str, Any]) -> List[AnnotationHint]:
        """Generate hints based on concept relationships."""
        hints = []
        
        # Get related concepts from the graph
        related = self.concept_graph.get(uri, [])
        
        for rel in related:
            target_uri = rel['target']
            strength = rel['strength']
            
            # Create hint
            hint = AnnotationHint(
                concept_uri=target_uri,
                concept_label=self._get_concept_label(target_uri),
                hint_type='related',
                confidence_boost=self.base_confidence_boost * strength,
                search_keywords=self._extract_keywords(target_uri),
                source_annotation_uri=uri
            )
            hints.append(hint)
        
        return hints
    
    def _generate_co_occurrence_hints(self, uri: str, position: int) -> List[AnnotationHint]:
        """Generate hints based on co-occurrence patterns."""
        hints = []
        
        co_occurring = self.co_occurrence_patterns.get(uri, set())
        
        for co_uri in co_occurring:
            # Check if this concept hasn't been annotated nearby
            if not self._is_already_annotated_nearby(co_uri, position):
                hint = AnnotationHint(
                    concept_uri=co_uri,
                    concept_label=self._get_concept_label(co_uri),
                    hint_type='co-occurrence',
                    confidence_boost=self.base_confidence_boost * 0.8,
                    search_keywords=self._extract_keywords(co_uri),
                    source_annotation_uri=uri
                )
                hints.append(hint)
        
        return hints
    
    def _is_already_annotated_nearby(self, uri: str, position: int) -> bool:
        """Check if a concept is already annotated near this position."""
        positions = self.text_positions.get(uri, [])
        
        for pos in positions:
            distance = abs(pos['start'] - position)
            if distance < self.max_search_radius:
                return True
        
        return False
    
    def _get_concept_label(self, uri: str) -> str:
        """Get the label for a concept URI."""
        # Look through annotations to find the label
        for ann in self.all_annotations:
            if ann.get('concept_uri') == uri:
                return ann.get('concept_label', uri.split('/')[-1])
        
        return uri.split('/')[-1]  # Fallback to last part of URI
    
    def _extract_keywords(self, uri: str) -> List[str]:
        """Extract search keywords from a concept URI and its annotations."""
        keywords = []
        
        # Get label and split into words
        label = self._get_concept_label(uri)
        keywords.extend(label.lower().split())
        
        # Add text segments where this concept appears
        positions = self.text_positions.get(uri, [])
        for pos in positions[:3]:  # Use first 3 occurrences
            text = pos.get('text', '')
            if text:
                keywords.extend(text.lower().split()[:5])  # First 5 words
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen and len(kw) > 2:  # Skip short words
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:10]  # Return top 10 keywords
    
    def _deduplicate_hints(self, hints: List[AnnotationHint]) -> List[AnnotationHint]:
        """Remove duplicate hints, keeping the one with highest confidence boost."""
        unique = {}
        
        for hint in hints:
            key = hint.concept_uri
            if key not in unique or hint.confidence_boost > unique[key].confidence_boost:
                unique[key] = hint
        
        return list(unique.values())
    
    def adjust_confidence(self, candidate: Dict[str, Any]) -> float:
        """
        Adjust confidence score based on context.
        
        Args:
            candidate: Annotation candidate with base confidence
            
        Returns:
            Adjusted confidence score
        """
        base_confidence = candidate.get('confidence', 0.5)
        position = candidate.get('start_offset', 0)
        uri = candidate.get('concept_uri', '')
        
        # Check if in semantic region
        in_semantic_region = False
        for region in self.semantic_regions:
            if region.contains(position):
                in_semantic_region = True
                # Boost based on region importance
                base_confidence *= (1 + self.semantic_proximity_boost * region.importance)
                break
        
        # Check for nearby related concepts
        nearby_related = 0
        for ann in self.previous_annotations:
            ann_uri = ann.get('concept_uri', '')
            if ann_uri in self.co_occurrence_patterns.get(uri, set()):
                ann_pos = ann.get('start_offset', 0)
                distance = abs(position - ann_pos)
                if distance < self.max_search_radius:
                    nearby_related += 1
        
        if nearby_related > 0:
            boost = min(nearby_related * 0.1, 0.3)  # Max 30% boost
            base_confidence *= (1 + boost)
        
        # Check for conflicts
        if self._has_conflicting_concepts(uri, position):
            base_confidence *= (1 - self.conflict_penalty)
        
        return min(base_confidence, 1.0)
    
    def _has_conflicting_concepts(self, uri: str, position: int) -> bool:
        """Check if there are conflicting concepts nearby."""
        # This is a placeholder - implement based on ontology relationships
        # For now, just check if the same position is already annotated
        for ann in self.all_annotations:
            ann_start = ann.get('start_offset', 0)
            ann_end = ann.get('end_offset', 0)
            if ann_start <= position <= ann_end and ann.get('concept_uri') != uri:
                return True
        
        return False
    
    def get_annotated_regions(self) -> List[Tuple[int, int]]:
        """Get list of already annotated regions to avoid re-annotation."""
        regions = []
        
        for ann in self.all_annotations:
            start = ann.get('start_offset', 0)
            end = ann.get('end_offset', 0)
            if start < end:
                regions.append((start, end))
        
        # Merge overlapping regions
        regions.sort()
        merged = []
        
        for start, end in regions:
            if merged and start <= merged[-1][1]:
                # Overlapping or adjacent - merge
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        
        return merged
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get context statistics."""
        return {
            'current_pass': self.current_pass,
            'total_annotations': len(self.all_annotations),
            'semantic_regions': len(self.semantic_regions),
            'concept_relationships': sum(len(v) for v in self.concept_graph.values()),
            'co_occurrence_patterns': len(self.co_occurrence_patterns),
            'unique_concepts': len(self.text_positions)
        }
