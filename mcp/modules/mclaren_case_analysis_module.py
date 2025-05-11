#!/usr/bin/env python3
"""
McLaren Case Analysis Module for Unified Ontology Server

This module extends the base case analysis module to implement Bruce McLaren's
extensional definition approach for engineering ethics cases.

Implementation based on "Extensionally Defining Principles and Cases in Ethics: an AI Model" (2003)
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Union
import traceback

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from mcp.modules.case_analysis_module import CaseAnalysisModule
from mcp.modules.base_module import BaseModule

# Set up logging
logger = logging.getLogger("McLarenCaseAnalysisModule")


class McLarenCaseAnalysisModule(CaseAnalysisModule):
    """
    Enhanced case analysis module implementing McLaren's extensional definition approach.
    
    Adds support for the nine operationalization techniques identified by McLaren:
    1. Principle Instantiation: Linking abstract principles to specific facts
    2. Fact Hypotheses: Hypothesizing facts that affect principle application
    3. Principle Revision: Evolving principle interpretation over time
    4. Conflicting Principles Resolution: Resolving conflicts between principles
    5. Principle Grouping: Grouping related principles to strengthen an argument
    6. Case Instantiation: Using past cases as precedent
    7. Principle Elaboration: Elaborating principles from past cases
    8. Case Grouping: Grouping related cases to support an argument
    9. Operationalization Reuse: Reusing previous applications
    """
    
    @property
    def name(self) -> str:
        """Get the name of this module."""
        return "mclaren_case_analysis"
    
    @property
    def description(self) -> str:
        """Get the description of this module."""
        return "Case analysis using McLaren's extensional definition approach"
    
    def _register_tools(self) -> None:
        """Register the tools provided by this module."""
        # Include base tools from parent class
        super()._register_tools()
        
        # Add McLaren-specific tools
        self.tools.update({
            "identify_operationalization_techniques": self.identify_operationalization_techniques,
            "extract_principle_instantiations": self.extract_principle_instantiations,
            "identify_principle_conflicts": self.identify_principle_conflicts,
            "generate_extensional_definitions": self.generate_extensional_definitions,
        })
    
    def identify_operationalization_techniques(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify operationalization techniques used in a case according to McLaren's framework.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case to analyze
                - case_text: Optional text of the case (if not stored in DB)
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with identified techniques and their instances
        """
        case_id = arguments.get("case_id")
        case_text = arguments.get("case_text")
        ontology_source = arguments.get("ontology_source")
        
        if not case_id and not case_text:
            return {"error": "Missing case_id or case_text parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Get case text either from parameter or database
            if not case_text:
                if not self.server.app:
                    return {"error": "Flask app context not available"}
                
                with self.server.app.app_context():
                    try:
                        # Look up case by ID (adapt based on your model structure)
                        from app.models.document import Document
                        case_doc = Document.query.get(case_id)
                        if not case_doc:
                            return {"error": f"Case not found: {case_id}"}
                        
                        case_text = case_doc.content
                        case_title = case_doc.title
                        case_metadata = json.loads(case_doc.doc_metadata) if case_doc.doc_metadata else {}
                    except Exception as e:
                        return {"error": f"Error retrieving case: {str(e)}"}
            else:
                case_title = f"Case {case_id}" if case_id else "Provided case text"
                case_metadata = {}
            
            # Define patterns for each operationalization technique
            technique_patterns = {
                "principle_instantiation": [
                    r"(code|principle|canon|ethic).*\b(applied|applies|application)\b",
                    r"(violate[sd]?|breach(ed)?|contravene[sd]?).*\b(code|principle|canon|ethic)\b",
                    r"(code|principle|canon|ethic).*\b(require[sd]?|mandate[sd]?|dictate[sd]?)\b"
                ],
                "fact_hypotheses": [
                    r"(what\s+if|suppose|assuming|hypothetical|scenario|consider)",
                    r"(could\s+have|might\s+have|if\s+the\s+engineer\s+had)"
                ],
                "principle_revision": [
                    r"(evolving|evolution|develop(ing|ed|ment)|chang(ing|ed)|revision|update[sd]?)\s+.*\b(interpretation|meaning|understanding)\b",
                    r"(previous|prior|past|earlier|former)\s+.*\b(interpretation|meaning|understanding)\b"
                ],
                "conflicting_principles_resolution": [
                    r"(conflict|tension|trade.?off|balance|weigh|competing|versus|vs\.)",
                    r"(override[sd]?|outweigh[sd]?|supersede[sd]?|take[s]?\s+precedence)",
                    r"(more\s+important|greater|higher|paramount)"
                ],
                "principle_grouping": [
                    r"(both|several|multiple|many|various|different)\s+.*\b(principles|codes|canons|ethics)\b",
                    r"(principle|code|canon).{1,50}(and|as\s+well\s+as|along\s+with|together\s+with).{1,50}(principle|code|canon)"
                ],
                "case_instantiation": [
                    r"(similar|analogous|previous|past|earlier|former)\s+.*\b(case|situation|scenario)\b",
                    r"(like|as\s+in|comparable\s+to)\s+.*\b(case|situation|scenario)\b"
                ],
                "principle_elaboration": [
                    r"(expand|elaborate|clarify|explain|elucidate|define)\s+.*\b(principle|code|canon)\b",
                    r"(meaning|interpretation|understanding|definition)\s+of\s+.*\b(principle|code|canon)\b"
                ],
                "case_grouping": [
                    r"(several|multiple|many|various|different)\s+.*\b(cases|situations|scenarios)\b",
                    r"(case|situation|scenario).{1,50}(and|as\s+well\s+as|along\s+with|together\s+with).{1,50}(case|situation|scenario)"
                ],
                "operationalization_reuse": [
                    r"(reuse|reapply|reapplication|again|previously\s+used|earlier\s+used)",
                    r"(similar|same)\s+.*\b(approach|method|technique|reasoning|argument)\b"
                ]
            }
            
            # For each technique, find matches in the text
            technique_matches = {}
            
            for technique, patterns in technique_patterns.items():
                matches = []
                
                for pattern in patterns:
                    for match in re.finditer(pattern, case_text, re.IGNORECASE):
                        start, end = match.span()
                        context_start = max(0, start - 50)
                        context_end = min(len(case_text), end + 50)
                        
                        matches.append({
                            "match": match.group(0),
                            "start": start,
                            "end": end,
                            "context": case_text[context_start:context_end]
                        })
                
                if matches:
                    technique_matches[technique] = matches
            
            # Use metadata to enhance technique detection if available
            if case_metadata.get("operationalization_techniques"):
                metadata_techniques = case_metadata["operationalization_techniques"]
                for technique in metadata_techniques:
                    technique_key = technique.lower().replace(" ", "_")
                    if technique_key not in technique_matches:
                        technique_matches[technique_key] = [{"match": "From metadata", "source": "metadata"}]
            
            # Build the result
            result = {
                "case_id": case_id,
                "title": case_title,
                "techniques": technique_matches,
                "technique_count": len(technique_matches),
                "dominant_techniques": sorted(technique_matches.keys(), 
                                            key=lambda k: len(technique_matches[k]), 
                                            reverse=True)[:3]
            }
            
            return result
        except Exception as e:
            logger.error(f"Error identifying operationalization techniques: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error identifying operationalization techniques: {str(e)}"}
    
    def extract_principle_instantiations(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract principle instantiations from a case (linking abstract principles to concrete facts).
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case to analyze
                - case_text: Optional text of the case (if not stored in DB)
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with principle instantiations
        """
        case_id = arguments.get("case_id")
        case_text = arguments.get("case_text")
        ontology_source = arguments.get("ontology_source")
        
        if not case_id and not case_text:
            return {"error": "Missing case_id or case_text parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Get case text and metadata either from parameter or database
            if not case_text:
                if not self.server.app:
                    return {"error": "Flask app context not available"}
                
                with self.server.app.app_context():
                    try:
                        from app.models.document import Document
                        case_doc = Document.query.get(case_id)
                        if not case_doc:
                            return {"error": f"Case not found: {case_id}"}
                        
                        case_text = case_doc.content
                        case_title = case_doc.title
                        case_metadata = json.loads(case_doc.doc_metadata) if case_doc.doc_metadata else {}
                    except Exception as e:
                        return {"error": f"Error retrieving case: {str(e)}"}
            else:
                case_title = f"Case {case_id}" if case_id else "Provided case text"
                case_metadata = {}
            
            # Get principle entities from the ontology
            g = self.server._load_graph_from_file(ontology_source)
            
            principles = []
            
            # Look for classes with "Principle" or "Code" in their label or superclass
            for cls in g.subjects(RDF.type, OWL.Class):
                if isinstance(cls, URIRef):
                    labels = list(g.objects(cls, RDFS.label))
                    
                    is_principle = False
                    principle_label = ""
                    
                    # Check labels for principle indicators
                    for label in labels:
                        label_str = str(label).lower()
                        if "principle" in label_str or "code" in label_str or "canon" in label_str or "ethic" in label_str:
                            is_principle = True
                            principle_label = str(label)
                            break
                    
                    # If no label match, check superclasses
                    if not is_principle:
                        for parent in g.objects(cls, RDFS.subClassOf):
                            parent_labels = list(g.objects(parent, RDFS.label))
                            for parent_label in parent_labels:
                                parent_label_str = str(parent_label).lower()
                                if "principle" in parent_label_str or "code" in parent_label_str:
                                    is_principle = True
                                    principle_label = str(labels[0]) if labels else str(cls).split("/")[-1].split("#")[-1]
                                    break
                    
                    if is_principle:
                        principles.append({
                            "uri": str(cls),
                            "label": principle_label or str(cls).split("/")[-1].split("#")[-1],
                        })
            
            # Use regex patterns to find potential instantiations
            instantiation_patterns = [
                # Principle cited in relation to specific actions
                r"(principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)(?:requires|mandates|dictates|states|says|applies)\s+(?:that)?\s*([^.;:]+)[.;:]",
                # Actions described as violating principles
                r"([^.;:]+)(?:violates|breaches|contravenes|fails to comply with|does not follow)\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)[.;:]",
                # Actions in accordance with principles
                r"([^.;:]+)(?:follows|complies with|adheres to|is in accordance with)\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)[.;:]"
            ]
            
            # Find matches for each pattern
            instantiations = []
            
            for pattern in instantiation_patterns:
                for match in re.finditer(pattern, case_text, re.IGNORECASE):
                    # Extract the components based on the pattern
                    if "violates" in match.group(0) or "breaches" in match.group(0) or "contravenes" in match.group(0):
                        fact = match.group(1).strip()
                        principle_text = match.group(2).strip()
                    elif "follows" in match.group(0) or "complies" in match.group(0) or "adheres" in match.group(0):
                        fact = match.group(1).strip()
                        principle_text = match.group(2).strip()                        
                    else:
                        principle_text = match.group(2).strip()
                        fact = match.group(3).strip()
                    
                    # Find the best matching principle from the ontology
                    best_match = None
                    best_score = 0
                    
                    for principle in principles:
                        principle_label = principle["label"].lower()
                        score = 0
                        
                        # Simple word overlap scoring
                        for word in principle_text.lower().split():
                            if word in principle_label:
                                score += 1
                        
                        if score > best_score:
                            best_score = score
                            best_match = principle
                    
                    instantiations.append({
                        "principle_text": principle_text,
                        "fact": fact,
                        "principle_uri": best_match["uri"] if best_match else None,
                        "principle_label": best_match["label"] if best_match else None,
                        "match_confidence": best_score / len(principle_text.split()) if best_match else 0,
                        "context": match.group(0)
                    })
            
            # Use metadata to enhance instantiation detection if available
            if case_metadata.get("principles") and case_metadata.get("board_analysis"):
                metadata_principles = case_metadata["principles"]
                board_analysis = case_metadata["board_analysis"]
                
                # Look for principle-fact connections in the board analysis
                for principle in metadata_principles:
                    principle_text = principle.lower()
                    
                    # Find a matching ontology principle
                    best_match = None
                    best_score = 0
                    
                    for ont_principle in principles:
                        ont_label = ont_principle["label"].lower()
                        score = 0
                        
                        # Simple word overlap scoring
                        for word in principle_text.split():
                            if word in ont_label:
                                score += 1
                        
                        if score > best_score:
                            best_score = score
                            best_match = ont_principle
                    
                    # Look for sentences with this principle in the board analysis
                    analysis_sentences = re.split(r'[.!?]', board_analysis)
                    for sentence in analysis_sentences:
                        if principle_text in sentence.lower():
                            # This sentence likely contains a fact related to the principle
                            instantiations.append({
                                "principle_text": principle,
                                "fact": sentence.strip(),
                                "principle_uri": best_match["uri"] if best_match else None,
                                "principle_label": best_match["label"] if best_match else None,
                                "match_confidence": 0.7,  # Metadata-based instantiations have high confidence
                                "source": "metadata"
                            })
            
            # Build the result
            result = {
                "case_id": case_id,
                "title": case_title,
                "instantiations": instantiations,
                "instantiation_count": len(instantiations),
                "principles_instantiated": list(set([i["principle_label"] for i in instantiations if i["principle_label"]]))
            }
            
            return result
        except Exception as e:
            logger.error(f"Error extracting principle instantiations: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error extracting principle instantiations: {str(e)}"}
    
    def identify_principle_conflicts(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify conflicts between principles in a case and how they are resolved.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case to analyze
                - case_text: Optional text of the case (if not stored in DB)
                - ontology_source: Source identifier for ontology
                
        Returns:
            Dict with identified principle conflicts and resolutions
        """
        case_id = arguments.get("case_id")
        case_text = arguments.get("case_text")
        ontology_source = arguments.get("ontology_source")
        
        if not case_id and not case_text:
            return {"error": "Missing case_id or case_text parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Get case text and metadata either from parameter or database
            if not case_text:
                if not self.server.app:
                    return {"error": "Flask app context not available"}
                
                with self.server.app.app_context():
                    try:
                        from app.models.document import Document
                        case_doc = Document.query.get(case_id)
                        if not case_doc:
                            return {"error": f"Case not found: {case_id}"}
                        
                        case_text = case_doc.content
                        case_title = case_doc.title
                        case_metadata = json.loads(case_doc.doc_metadata) if case_doc.doc_metadata else {}
                    except Exception as e:
                        return {"error": f"Error retrieving case: {str(e)}"}
            else:
                case_title = f"Case {case_id}" if case_id else "Provided case text"
                case_metadata = {}
            
            # Get principle entities from the ontology
            g = self.server._load_graph_from_file(ontology_source)
            
            principles = []
            
            # Look for classes with "Principle" or "Code" in their label
            for cls in g.subjects(RDF.type, OWL.Class):
                if isinstance(cls, URIRef):
                    labels = list(g.objects(cls, RDFS.label))
                    
                    is_principle = False
                    principle_label = ""
                    
                    # Check labels for principle indicators
                    for label in labels:
                        label_str = str(label).lower()
                        if "principle" in label_str or "code" in label_str or "canon" in label_str or "ethic" in label_str:
                            is_principle = True
                            principle_label = str(label)
                            break
                    
                    # If no label match, check superclasses
                    if not is_principle:
                        for parent in g.objects(cls, RDFS.subClassOf):
                            parent_labels = list(g.objects(parent, RDFS.label))
                            for parent_label in parent_labels:
                                parent_label_str = str(parent_label).lower()
                                if "principle" in parent_label_str or "code" in parent_label_str:
                                    is_principle = True
                                    principle_label = str(labels[0]) if labels else str(cls).split("/")[-1].split("#")[-1]
                                    break
                    
                    if is_principle:
                        principles.append({
                            "uri": str(cls),
                            "label": principle_label or str(cls).split("/")[-1].split("#")[-1],
                        })
            
            # Use regex patterns to find potential conflicts
            conflict_patterns = [
                # Direct conflict statements
                r"(principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)(?:conflicts|clashes|contradicts|is at odds)\s+with\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)[.;:]",
                # Override statements
                r"(principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)(?:overrides|outweighs|supersedes|takes precedence over)\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)[.;:]",
                # Balancing or weighing statements
                r"(?:balancing|weighing|considering)\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)(?:against|versus|vs\.)\s+(?:the)?\s*(?:principle|code|canon|ethic)s?\s+(?:of|that|which)?\s*([^.;:]+)[.;:]"
            ]
            
            # Find matches for each pattern
            conflicts = []
            
            for pattern in conflict_patterns:
                for match in re.finditer(pattern, case_text, re.IGNORECASE):
                    # Extract the components based on the pattern
                    if "conflicts" in match.group(0) or "clashes" in match.group(0) or "contradicts" in match.group(0):
                        principle1_text = match.group(2).strip()
                        principle2_text = match.group(3).strip()
                        resolution_type = "conflict"
                    elif "overrides" in match.group(0) or "outweighs" in match.group(0) or "supersedes" in match.group(0):
                        principle1_text = match.group(2).strip()
                        principle2_text = match.group(3).strip()
                        resolution_type = "override"
                    elif "balancing" in match.group(0) or "weighing" in match.group(0) or "considering" in match.group(0):
                        principle1_text = match.group(1).strip()
                        principle2_text = match.group(2).strip()
                        resolution_type = "balancing"
                    else:
                        continue  # Skip if we can't determine the relationship
                    
                    # Find the best matching principles from the ontology
                    best_match1 = None
                    best_score1 = 0
                    best_match2 = None
                    best_score2 = 0
                    
                    for principle in principles:
                        principle_label = principle["label"].lower()
                        
                        # Match for principle1
                        score1 = 0
                        for word in principle1_text.lower().split():
                            if word in principle_label:
                                score1 += 1
                        if score1 > best_score1:
                            best_score1 = score1
                            best_match1 = principle
                        
                        # Match for principle2
                        score2 = 0
                        for word in principle2_text.lower().split():
                            if word in principle_label:
                                score2 += 1
                        if score2 > best_score2:
                            best_score2 = score2
                            best_match2 = principle
                    
                    conflicts.append({
                        "principle1_text": principle1_text,
                        "principle2_text": principle2_text,
                        "principle1_uri": best_match1["uri"] if best_match1 else None,
                        "principle2_uri": best_match2["uri"] if best_match2 else None,
                        "principle1_label": best_match1["label"] if best_match1 else None,
                        "principle2_label": best_match2["label"] if best_match2 else None,
                        "resolution_type": resolution_type,
                        "context": match.group(0)
                    })
            
            # Use metadata to enhance conflict detection if available
            if case_metadata.get("principles") and len(case_metadata.get("principles", [])) > 1:
                metadata_principles = case_metadata["principles"]
                
                # If multiple principles are mentioned in metadata, they may be in conflict
                if len(metadata_principles) >= 2 and case_metadata.get("board_analysis"):
                    board_analysis = case_metadata["board_analysis"]
                    
                    # Look for override patterns in the board analysis
                    override_patterns = [
                        r"(override[sd]?|outweigh[sd]?|supersede[sd]?|take[s]?\s+precedence|more\s+important)",
                        r"(paramount|higher|greater)"
                    ]
                    
                    has_override = False
                    for pattern in override_patterns:
                        if re.search(pattern, board_analysis, re.IGNORECASE):
                            has_override = True
                            break
                    
                    if has_override:
                        # There appears to be a conflict resolution
                        
                        # Find matching ontology principles
                        matches = []
                        for principle in metadata_principles:
                            principle_text = principle.lower()
                            
                            # Find a matching ontology principle
                            best_match = None
                            best_score = 0
                            
                            for ont_principle in principles:
                                ont_label = ont_principle["label"].lower()
                                score = 0
                                
                                # Simple word overlap scoring
                                for word in principle_text.split():
                                    if word in ont_label:
                                        score += 1
                                
                                if score > best_score:
                                    best_score = score
                                    best_match = ont_principle
                            
                            if best_match:
                                matches.append({
                                    "text": principle,
                                    "uri": best_match["uri"],
                                    "label": best_match["label"],
                                    "score": best_score
                                })
                        
                        # If we found at least two matching principles, record the conflict
                        if len(matches) >= 2:
                            # The first two principles from metadata
                            conflicts.append({
                                "principle1_text": matches[0]["text"],
                                "principle2_text": matches[1]["text"],
                                "principle1_uri": matches[0]["uri"],
                                "principle2_uri": matches[1]["uri"],
                                "principle1_label": matches[0]["label"],
                                "principle2_label": matches[1]["label"],
                                "resolution_type": "override" if "override" in board_analysis.lower() else "conflict",
                                "source": "metadata",
                                "context": board_analysis
                            })
            
            # Build the result
            result = {
                "case_id": case_id,
                "title": case_title,
                "conflicts": conflicts,
                "conflict_count": len(conflicts),
                "principles_in_conflict": list(set([c["principle1_label"] for c in conflicts if c["principle1_label"]] + 
                                              [c["principle2_label"] for c in conflicts if c["principle2_label"]]))
            }
            
            return result
        except Exception as e:
            logger.error(f"Error identifying principle conflicts: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error identifying principle conflicts: {str(e)}"}

    def generate_extensional_definitions(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate extensional definitions of principles based on their applications in cases.
        
        Args:
            arguments: Dict with keys:
                - principle_uri: URI of the principle to define extensionally
                - ontology_source: Source identifier for ontology
                - case_limit: Maximum number of cases to include (default: 5)
                
        Returns:
            Dict with extensional definition of the principle
        """
        principle_uri = arguments.get("principle_uri")
        ontology_source = arguments.get("ontology_source")
        case_limit = int(arguments.get("case_limit", 5))
        
        if not principle_uri:
            return {"error": "Missing principle_uri parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Load the ontology
            g = self.server._load_graph_from_file(ontology_source)
            
            # Get principle information
            principle_node = URIRef(principle_uri)
            
            # Check if principle exists in the ontology
            if (principle_node, RDF.type, OWL.Class) not in g:
                return {"error": f"Principle not found in ontology: {principle_uri}"}
            
            labels = list(g.objects(principle_node, RDFS.label))
            comments = list(g.objects(principle_node, RDFS.comment))
            
            principle_info = {
                "uri": principle_uri,
                "label": str(labels[0]) if labels else principle_uri.split("/")[-1].split("#")[-1],
                "description": str(comments[0]) if comments else "No description available"
            }
            
            # Search for cases where this principle is applied
            # This requires access to the database
            if not self.server.app:
                return {"error": "Flask app context not available"}
            
            with self.server.app.app_context():
                try:
                    # Try to find cases that reference this principle
                    from app.models.document import Document
                    from app.models.triple import Triple
                    
                    # First, check if there are any triples referencing this principle
                    principle_cases = []
                    
                    # Query for triples that reference this principle
                    triples = Triple.query.filter(
                        (Triple.subject == principle_uri) | 
                        (Triple.object == principle_uri)
                    ).limit(case_limit * 2).all()
                    
                    # Get unique cases from triples
                    case_ids = set()
                    for triple in triples:
                        if triple.context and triple.context.startswith("case:"):
                            case_id = triple.context.split(":")[-1]
                            try:
                                case_ids.add(int(case_id))
                            except ValueError:
                                pass
                    
                    # Get case documents
                    for case_id in list(case_ids)[:case_limit]:
                        case_doc = Document.query.get(case_id)
                        if case_doc:
                            case_metadata = json.loads(case_doc.doc_metadata) if case_doc.doc_metadata else {}
                            
                            # Check if case mentions this principle either explicitly or in metadata
                            is_relevant = False
                            
                            # Check metadata principles
                            if case_metadata.get("principles"):
                                principle_label = principle_info["label"].lower()
                                for p in case_metadata["principles"]:
                                    if principle_label in p.lower():
                                        is_relevant = True
                                        break
                            
                            # Or directly check content
                            if not is_relevant and principle_info["label"].lower() in case_doc.content.lower():
                                is_relevant = True
                            
                            if is_relevant:
                                # Get instantiations for this case
                                instantiations = self.extract_principle_instantiations({
                                    "case_id": case_id,
                                    "ontology_source": ontology_source
                                })
                                
                                # Check if any instantiations match this principle
                                matching_instantiations = []
                                for inst in instantiations.get("instantiations", []):
                                    if inst.get("principle_uri") == principle_uri:
                                        matching_instantiations.append(inst)
                                
                                if matching_instantiations:
                                    principle_cases.append({
                                        "case_id": case_id,
                                        "title": case_doc.title,
                                        "instantiations": matching_instantiations
                                    })
                    
                    # If we don't have enough cases yet, try searching for the principle name in all cases
                    if len(principle_cases) < case_limit:
                        # Search for cases that mention the principle name
                        principle_label = principle_info["label"]
                        additional_cases_needed = case_limit - len(principle_cases)
                        
                        # Get cases that contain the principle name
                        additional_cases = Document.query.filter(
                            Document.content.ilike(f"%{principle_label}%")
                        ).limit(additional_cases_needed * 2).all()
                        
                        for case_doc in additional_cases:
                            case_id = case_doc.id
                            
                            # Skip if already included
                            if any(pc["case_id"] == case_id for pc in principle_cases):
                                continue
                            
                            # Get instantiations for this case
                            instantiations = self.extract_principle_instantiations({
                                "case_id": case_id,
                                "ontology_source": ontology_source
                            })
                            
                            # Check if any instantiations match this principle
                            matching_instantiations = []
                            for inst in instantiations.get("instantiations", []):
                                if inst.get("principle_uri") == principle_uri:
                                    matching_instantiations.append(inst)
                            
                            if matching_instantiations:
                                principle_cases.append({
                                    "case_id": case_id,
                                    "title": case_doc.title,
                                    "instantiations": matching_instantiations
                                })
                            
                            if len(principle_cases) >= case_limit:
                                break
                    
                    # Build the extensional definition
                    positive_examples = []
                    negative_examples = []
                    
                    for case in principle_cases:
                        for inst in case["instantiations"]:
                            example = {
                                "case_id": case["case_id"],
                                "case_title": case["title"],
                                "fact": inst["fact"],
                                "context": inst.get("context", "")
                            }
                            
                            # Determine if this is a positive or negative example
                            # (e.g., if the fact describes compliance or violation)
                            context = inst.get("context", "").lower()
                            if "violate" in context or "breach" in context or "contravene" in context:
                                negative_examples.append(example)
                            else:
                                positive_examples.append(example)
                    
                    # Generate a textual definition based on examples
                    extensional_definition = f"The principle '{principle_info['label']}' is extensionally defined through its application in {len(principle_cases)} cases:"
                    
                    if positive_examples:
                        extensional_definition += "\n\nPositive applications (examples of compliance):"
                        for i, example in enumerate(positive_examples[:3]):
                            extensional_definition += f"\n{i+1}. In case '{example['case_title']}': {example['fact']}"
                    
                    if negative_examples:
                        extensional_definition += "\n\nNegative applications (examples of violations):"
                        for i, example in enumerate(negative_examples[:3]):
                            extensional_definition += f"\n{i+1}. In case '{example['case_title']}': {example['fact']}"
                    
                    return {
                        "principle": principle_info,
                        "extensional_definition": extensional_definition,
                        "cases": principle_cases,
                        "positive_examples": positive_examples,
                        "negative_examples": negative_examples,
                        "case_count": len(principle_cases)
                    }
                    
                except Exception as e:
                    logger.error(f"Error retrieving case data: {str(e)}")
                    traceback.print_exc()
                    return {"error": f"Error retrieving case data: {str(e)}"}
        except Exception as e:
            logger.error(f"Error generating extensional definition: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error generating extensional definition: {str(e)}"}
    
    def convert_to_triples(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert principle instantiations, conflicts, and operationalization techniques to RDF triples.
        
        Args:
            arguments: Dict with keys:
                - case_id: ID of the case to analyze
                - case_text: Optional text of the case (if not stored in DB)
                - ontology_source: Source identifier for ontology
                - output_format: Format for returned triples (turtle, ntriples, etc.)
                
        Returns:
            Dict with generated triples
        """
        case_id = arguments.get("case_id")
        case_text = arguments.get("case_text")
        ontology_source = arguments.get("ontology_source")
        output_format = arguments.get("output_format", "turtle")
        
        if not case_id and not case_text:
            return {"error": "Missing case_id or case_text parameter"}
        
        if not ontology_source:
            return {"error": "Missing ontology_source parameter"}
        
        try:
            # Create a new RDF graph
            from rdflib import Graph, Namespace, URIRef, Literal, BNode
            from rdflib.namespace import RDF, RDFS, XSD
            
            g = Graph()
            
            # Define namespaces
            MCEXT = Namespace("http://proethica.org/ontology/mclaren-extensional#")
            ENETH = Namespace("http://proethica.org/ontology/engineering-ethics#")
            PROETH = Namespace("http://proethica.org/ontology/intermediate#")
            CASE = Namespace(f"http://proethica.org/cases#")
            
            # Bind namespaces
            g.bind("mcext", MCEXT)
            g.bind("eneth", ENETH)
            g.bind("proeth", PROETH)
            g.bind("case", CASE)
            
            # Get case URI
            case_uri = CASE[f"Case-{case_id}" if case_id else "AnonymousCase"]
            
            # Add basic case type information
            g.add((case_uri, RDF.type, PROETH.Case))
            
            # 1. Extract instantiations
            instantiations = self.extract_principle_instantiations({
                "case_id": case_id,
                "case_text": case_text,
                "ontology_source": ontology_source
            })
            
            if "error" not in instantiations:
                # Process each instantiation
                for i, inst in enumerate(instantiations.get("instantiations", [])):
                    # Create unique ID for this instantiation
                    inst_id = f"instantiation_{i}"
                    inst_uri = CASE[inst_id]
                    
                    # Add basic type information
                    g.add((inst_uri, RDF.type, MCEXT.PrincipleInstantiation))
                    g.add((case_uri, MCEXT.hasInstantiation, inst_uri))
                    
                    # Add principle relationship
                    if inst.get("principle_uri"):
                        principle_uri = URIRef(inst["principle_uri"])
                        g.add((inst_uri, MCEXT.appliesPrinciple, principle_uri))
                        g.add((principle_uri, MCEXT.hasInstantiation, inst_uri))
                    
                    # Add fact text
                    if inst.get("fact"):
                        g.add((inst_uri, MCEXT.toFact, Literal(inst["fact"])))
                    
                    # Add context if available
                    if inst.get("context"):
                        g.add((inst_uri, MCEXT.hasContext, Literal(inst["context"])))
                    
                    # Add confidence score
                    if "match_confidence" in inst:
                        g.add((inst_uri, MCEXT.hasConfidence, Literal(inst["match_confidence"], datatype=XSD.float)))
                    
                    # Determine if this is a negative example (e.g., violation of principle)
                    is_negative = False
                    if inst.get("context"):
                        context = inst["context"].lower()
                        if "violate" in context or "breach" in context or "contravene" in context:
                            is_negative = True
                    
                    g.add((inst_uri, MCEXT.isNegativeExample, Literal(is_negative, datatype=XSD.boolean)))
            
            # 2. Extract conflicts
            conflicts = self.identify_principle_conflicts({
                "case_id": case_id,
                "case_text": case_text,
                "ontology_source": ontology_source
            })
            
            if "error" not in conflicts:
                # Process each conflict
                for i, conflict in enumerate(conflicts.get("conflicts", [])):
                    # Create unique ID for this conflict
                    conflict_id = f"conflict_{i}"
                    conflict_uri = CASE[conflict_id]
                    
                    # Add basic type information
                    g.add((conflict_uri, RDF.type, MCEXT.PrincipleConflict))
                    g.add((case_uri, MCEXT.hasConflict, conflict_uri))
                    
                    # Add principles
                    if conflict.get("principle1_uri"):
                        principle1_uri = URIRef(conflict["principle1_uri"])
                        g.add((conflict_uri, MCEXT.hasPrinciple1, principle1_uri))
                    
                    if conflict.get("principle2_uri"):
                        principle2_uri = URIRef(conflict["principle2_uri"])
                        g.add((conflict_uri, MCEXT.hasPrinciple2, principle2_uri))
                    
                    # Add resolution type
                    resolution_type = conflict.get("resolution_type", "").lower()
                    if resolution_type == "override":
                        g.add((conflict_uri, MCEXT.hasResolution, MCEXT.OverrideResolution))
                        
                        # If one principle overrides another, add that relationship
                        if conflict.get("principle1_uri") and conflict.get("principle2_uri"):
                            principle1_uri = URIRef(conflict["principle1_uri"])
                            principle2_uri = URIRef(conflict["principle2_uri"])
                            g.add((principle1_uri, MCEXT.overrides, principle2_uri))
                            g.add((conflict_uri, MCEXT.dominantPrinciple, principle1_uri))
                    
                    elif resolution_type == "balancing":
                        g.add((conflict_uri, MCEXT.hasResolution, MCEXT.BalancingResolution))
                    
                    # Add context
                    if conflict.get("context"):
                        g.add((conflict_uri, MCEXT.hasResolutionContext, Literal(conflict["context"])))
            
            # 3. Extract operationalization techniques
            techniques = self.identify_operationalization_techniques({
                "case_id": case_id,
                "case_text": case_text,
                "ontology_source": ontology_source
            })
            
            if "error" not in techniques:
                # Process each technique
                for technique, matches in techniques.get("techniques", {}).items():
                    # Map technique name to ontology class
                    technique_class_mapping = {
                        "principle_instantiation": MCEXT.PrincipleInstantiationTechnique,
                        "fact_hypotheses": MCEXT.FactHypothesesTechnique,
                        "principle_revision": MCEXT.PrincipleRevisionTechnique,
                        "conflicting_principles_resolution": MCEXT.ConflictingPrinciplesResolutionTechnique,
                        "principle_grouping": MCEXT.PrincipleGroupingTechnique,
                        "case_instantiation": MCEXT.CaseInstantiationTechnique,
                        "principle_elaboration": MCEXT.PrincipleElaborationTechnique,
                        "case_grouping": MCEXT.CaseGroupingTechnique,
                        "operationalization_reuse": MCEXT.OperationalizationReuseTechnique
                    }
                    
                    # Get the technique class URI
                    technique_class = technique_class_mapping.get(technique)
                    if technique_class:
                        # Create unique ID for this technique use
                        technique_id = f"technique_{technique}"
                        technique_uri = CASE[technique_id]
                        
                        # Add basic type information
                        g.add((technique_uri, RDF.type, technique_class))
                        g.add((case_uri, MCEXT.usesTechnique, technique_uri))
                        g.add((technique_uri, MCEXT.usedInCase, case_uri))
                        
                        # Add confidence based on number of matches
                        confidence = min(1.0, len(matches) / 10.0)  # Normalize to 0-1 range
                        g.add((technique_uri, MCEXT.hasConfidence, Literal(confidence, datatype=XSD.float)))
                        
                        # Add some example contexts
                        for i, match in enumerate(matches[:3]):  # Just add up to 3 examples
                            if match.get("context"):
                                context_id = f"{technique_id}_context_{i}"
                                context_uri = CASE[context_id]
                                g.add((technique_uri, MCEXT.hasContext, Literal(match["context"])))
            
            # Convert to requested format
            result = {
                "case_id": case_id,
                "triple_count": len(g),
                "triples_format": output_format,
                "triples": g.serialize(format=output_format)
            }
            
            return result
        except Exception as e:
            logger.error(f"Error converting to triples: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error converting to triples: {str(e)}"}
