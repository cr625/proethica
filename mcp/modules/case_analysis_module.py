#!/usr/bin/env python3
"""
Case Analysis Module for Unified Ontology Server

This module provides functionality for analyzing cases using ontology data,
including entity extraction, case structure analysis, and entity matching.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Union
import traceback

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL

from mcp.modules.base_module import BaseModule

# Set up logging
logger = logging.getLogger("CaseAnalysisModule")


class CaseAnalysisModule(BaseModule):
    """
    Case analysis module for working with case data using ontologies.
    
    Provides tools for extracting entities from cases, analyzing case structure,
    matching case elements to ontology entities, and generating ontology-based summaries.
    """
    
    @property
    def name(self) -> str:
        """Get the name of this module."""
        return "case_analysis"
    
    @property
    def description(self) -> str:
        """Get the description of this module."""
        return "Case analysis using ontology data"
    
    def _register_tools(self) -> None:
        """Register the tools provided by this module."""
        self.tools = {
            "extract_entities": self.extract_entities_from_text,
            "analyze_case_structure": self.analyze_case_structure,
            "match_entities": self.match_case_elements,
            "generate_summary": self.generate_ontology_summary
        }
    
    def extract_entities_from_text(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract entities from text using ontology classes.
        
        Args:
            arguments: Dict with keys:
                - text: Text to extract entities from
                - ontology_source: Source identifier for ontology
                - entity_types: Optional list of entity types to extract
                
        Returns:
            Dict with extracted entities
        """
        text = arguments.get("text")
        ontology_source = arguments.get("ontology_source")
        entity_types = arguments.get("entity_types", [])
        
        if not text:
            return {"error": "Missing text parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Load the ontology
            g = self.server._load_graph_from_file(ontology_source)
            
            # Get all class labels
            class_dict = {}
            for cls in g.subjects(RDF.type, OWL.Class):
                if isinstance(cls, URIRef):
                    # Get labels
                    labels = list(g.objects(cls, RDFS.label))
                    if labels:
                        for label in labels:
                            class_dict[str(label).lower()] = {
                                "id": str(cls),
                                "label": str(label),
                                "type": "class"
                            }
                    
                    # Use fragment identifier if no label
                    else:
                        name = str(cls).split("/")[-1].split("#")[-1]
                        class_dict[name.lower()] = {
                            "id": str(cls),
                            "label": name,
                            "type": "class"
                        }
            
            # Get all individual labels
            individual_dict = {}
            for ind, cls in g.subject_objects(RDF.type):
                if isinstance(ind, URIRef) and isinstance(cls, URIRef) and cls != OWL.Class:
                    # Get labels
                    labels = list(g.objects(ind, RDFS.label))
                    if labels:
                        for label in labels:
                            individual_dict[str(label).lower()] = {
                                "id": str(ind),
                                "label": str(label),
                                "class": str(cls),
                                "type": "individual"
                            }
                    
                    # Use fragment identifier if no label
                    else:
                        name = str(ind).split("/")[-1].split("#")[-1]
                        individual_dict[name.lower()] = {
                            "id": str(ind),
                            "label": name,
                            "class": str(cls),
                            "type": "individual"
                        }
            
            # Extract entities from text
            found_entities = []
            
            # Process classes
            for class_label, class_info in class_dict.items():
                # Skip if entity_types specified and this type is not in the list
                if entity_types and "class" not in entity_types:
                    continue
                
                # Look for label in text (case-insensitive)
                pattern = r'\b' + re.escape(class_label) + r'\b'
                matches = list(re.finditer(pattern, text.lower()))
                
                for match in matches:
                    start, end = match.span()
                    found_entities.append({
                        **class_info,
                        "start": start,
                        "end": end,
                        "text": text[start:end]
                    })
            
            # Process individuals
            for ind_label, ind_info in individual_dict.items():
                # Skip if entity_types specified and this type is not in the list
                if entity_types and "individual" not in entity_types:
                    continue
                
                # Look for label in text (case-insensitive)
                pattern = r'\b' + re.escape(ind_label) + r'\b'
                matches = list(re.finditer(pattern, text.lower()))
                
                for match in matches:
                    start, end = match.span()
                    found_entities.append({
                        **ind_info,
                        "start": start,
                        "end": end,
                        "text": text[start:end]
                    })
            
            # Sort by position in text
            found_entities.sort(key=lambda e: e["start"])
            
            return {
                "entities": found_entities,
                "count": len(found_entities),
                "text_length": len(text)
            }
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error extracting entities: {str(e)}"}
    
    def analyze_case_structure(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the structure of a case using ontology concepts.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case to analyze
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with case structure analysis
        """
        case_id = arguments.get("case_id")
        ontology_source = arguments.get("ontology_source")
        
        if not case_id:
            return {"error": "Missing case_id parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Try to load the case from the database
            if not self.server.app:
                return {"error": "Flask app context not available"}
            
            with self.server.app.app_context():
                try:
                    # Look up case by ID
                    # This is a placeholder - adjust based on your actual model names
                    from app.models.case import Case
                    
                    case = Case.query.get(case_id)
                    if not case:
                        return {"error": f"Case not found: {case_id}"}
                    
                    # Extract case text
                    case_text = case.content if hasattr(case, 'content') and case.content else ""
                    
                    if not case_text:
                        return {"error": f"No content found for case: {case_id}"}
                    
                    # Extract entities from case text
                    entities_result = self.extract_entities_from_text({
                        "text": case_text,
                        "ontology_source": ontology_source
                    })
                    
                    if "error" in entities_result:
                        return entities_result
                    
                    # Group entities by type
                    entities_by_type = {}
                    for entity in entities_result.get("entities", []):
                        entity_type = entity["type"]
                        if entity_type not in entities_by_type:
                            entities_by_type[entity_type] = []
                        entities_by_type[entity_type].append(entity)
                    
                    # Load ontology for further analysis
                    g = self.server._load_graph_from_file(ontology_source)
                    
                    # Find key ethical concepts (simplified approach)
                    # Here we could use more sophisticated methods like looking for
                    # instances of specific ethical concept classes
                    ethical_concepts = []
                    
                    # Look for classes with "Ethics" or "Ethical" in their label
                    for cls in g.subjects(RDF.type, OWL.Class):
                        if isinstance(cls, URIRef):
                            labels = list(g.objects(cls, RDFS.label))
                            for label in labels:
                                label_str = str(label).lower()
                                if "ethic" in label_str:
                                    ethical_concepts.append({
                                        "id": str(cls),
                                        "label": str(label),
                                        "type": "ethical_concept"
                                    })
                    
                    # Build the case structure
                    case_structure = {
                        "case_id": case_id,
                        "title": case.title if hasattr(case, 'title') else f"Case {case_id}",
                        "entities": entities_result.get("entities", []),
                        "entities_by_type": entities_by_type,
                        "ethical_concepts": ethical_concepts,
                        "entity_count": entities_result.get("count", 0)
                    }
                    
                    return case_structure
                
                except ImportError:
                    return {"error": "Case model not available"}
                except Exception as e:
                    logger.error(f"Error analyzing case: {str(e)}")
                    traceback.print_exc()
                    return {"error": f"Error analyzing case: {str(e)}"}
        except Exception as e:
            logger.error(f"Error analyzing case structure: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error analyzing case structure: {str(e)}"}
    
    def match_case_elements(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match case elements to ontology entities.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case
                - ontology_source: Source identifier for ontology
                - entity_type: Optional type of entity to match
                
        Returns:
            Dict with matched entities
        """
        case_id = arguments.get("case_id")
        ontology_source = arguments.get("ontology_source")
        entity_type = arguments.get("entity_type")
        
        if not case_id:
            return {"error": "Missing case_id parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Analyze case structure first
            case_structure = self.analyze_case_structure({
                "case_id": case_id,
                "ontology_source": ontology_source
            })
            
            if "error" in case_structure:
                return case_structure
            
            # Filter by entity type if specified
            if entity_type:
                entities = case_structure.get("entities_by_type", {}).get(entity_type, [])
            else:
                entities = case_structure.get("entities", [])
            
            # Load ontology
            g = self.server._load_graph_from_file(ontology_source)
            
            # Enhance entity information with additional ontology data
            enhanced_entities = []
            
            for entity in entities:
                try:
                    entity_id = entity.get("id")
                    entity_uri = URIRef(entity_id)
                    
                    # Get additional information
                    comments = list(g.objects(entity_uri, RDFS.comment))
                    
                    # Get relationships
                    outgoing = []
                    for p, o in g.predicate_objects(entity_uri):
                        if p != RDF.type and p != RDFS.label and p != RDFS.comment:
                            # Get predicate and object labels
                            pred_labels = list(g.objects(p, RDFS.label))
                            pred_label = str(pred_labels[0]) if pred_labels else str(p).split("/")[-1].split("#")[-1]
                            
                            obj_label = str(o)
                            if isinstance(o, URIRef):
                                obj_labels = list(g.objects(o, RDFS.label))
                                if obj_labels:
                                    obj_label = str(obj_labels[0])
                                else:
                                    obj_label = str(o).split("/")[-1].split("#")[-1]
                            
                            outgoing.append({
                                "predicate": str(p),
                                "predicate_label": pred_label,
                                "object": str(o),
                                "object_label": obj_label
                            })
                    
                    # Add enhanced data
                    enhanced_entity = {
                        **entity,
                        "description": str(comments[0]) if comments else "",
                        "relationships": outgoing
                    }
                    
                    enhanced_entities.append(enhanced_entity)
                except Exception as e:
                    # If enhancement fails, include the original entity
                    logger.warning(f"Error enhancing entity {entity.get('id')}: {str(e)}")
                    enhanced_entities.append(entity)
            
            return {
                "case_id": case_id,
                "matched_entities": enhanced_entities,
                "count": len(enhanced_entities),
                "entity_type": entity_type or "all"
            }
        except Exception as e:
            logger.error(f"Error matching case elements: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error matching case elements: {str(e)}"}
    
    def generate_ontology_summary(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an ontology-based summary of a case.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with case summary
        """
        case_id = arguments.get("case_id")
        ontology_source = arguments.get("ontology_source")
        
        if not case_id:
            return {"error": "Missing case_id parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # First get matched entities
            match_result = self.match_case_elements({
                "case_id": case_id,
                "ontology_source": ontology_source
            })
            
            if "error" in match_result:
                return match_result
            
            # Try to load the case from the database
            if not self.server.app:
                return {"error": "Flask app context not available"}
            
            with self.server.app.app_context():
                try:
                    # Look up case by ID
                    from app.models.case import Case
                    
                    case = Case.query.get(case_id)
                    if not case:
                        return {"error": f"Case not found: {case_id}"}
                    
                    # Get case metadata
                    title = case.title if hasattr(case, 'title') else f"Case {case_id}"
                    description = case.description if hasattr(case, 'description') else ""
                    
                    # Categorize entities by type
                    entities_by_type = {}
                    for entity in match_result.get("matched_entities", []):
                        entity_type = entity["type"]
                        if entity_type not in entities_by_type:
                            entities_by_type[entity_type] = []
                        entities_by_type[entity_type].append(entity)
                    
                    # Generate summary sections
                    summary_sections = []
                    
                    # Add case overview
                    summary_sections.append({
                        "title": "Case Overview",
                        "content": description or f"This is case {case_id}: {title}"
                    })
                    
                    # Add entity summary for each type
                    for entity_type, entities in entities_by_type.items():
                        entity_names = [e.get("label", "unnamed") for e in entities]
                        
                        # Format as readable text with commas and "and"
                        if len(entity_names) == 1:
                            entity_text = entity_names[0]
                        elif len(entity_names) == 2:
                            entity_text = f"{entity_names[0]} and {entity_names[1]}"
                        else:
                            entity_text = ", ".join(entity_names[:-1]) + f", and {entity_names[-1]}"
                        
                        # Generate section content
                        section_content = f"The case involves {entity_text}."
                        
                        # Add section
                        summary_sections.append({
                            "title": f"{entity_type.title()} Entities",
                            "content": section_content
                        })
                    
                    # Generate ethical analysis section if available
                    ethical_concepts = entities_by_type.get("ethical_concept", [])
                    if ethical_concepts:
                        ethical_names = [e.get("label", "unnamed") for e in ethical_concepts]
                        ethical_text = ", ".join(ethical_names)
                        
                        summary_sections.append({
                            "title": "Ethical Analysis",
                            "content": f"This case involves ethical concepts related to: {ethical_text}."
                        })
                    
                    # Assemble complete summary
                    full_summary = "\n\n".join([
                        f"# {section['title']}\n{section['content']}"
                        for section in summary_sections
                    ])
                    
                    return {
                        "case_id": case_id,
                        "title": title,
                        "summary_sections": summary_sections,
                        "full_summary": full_summary,
                        "entity_count": match_result.get("count", 0)
                    }
                    
                except ImportError:
                    return {"error": "Case model not available"}
                except Exception as e:
                    logger.error(f"Error generating summary: {str(e)}")
                    traceback.print_exc()
                    return {"error": f"Error generating summary: {str(e)}"}
        except Exception as e:
            logger.error(f"Error generating ontology summary: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error generating ontology summary: {str(e)}"}
