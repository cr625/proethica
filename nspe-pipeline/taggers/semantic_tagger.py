"""
Semantic Tagger
--------------
Applies dual-layer ontology tagging to engineering ethics cases:
1. Case level (McLaren extensional elements aligned with BFO)
2. Scenario level (domain-specific predicates from engineering ethics ontology)

This approach generates semantic relationships that meaningfully categorize ethical elements:
- Principle instantiations (ProfessionalIntegrity, Fairness, etc.)
- Entity roles (EngineeringConsultantRole, ClientRole, etc.)
- Resources (MunicipalWaterSystem, RequestForQualifications, etc.)
- Events (RegulatoryNotification, ProcurementProcess, etc.)
- Actions (OfferingFreeServices, IssuingProcurementDocument, etc.)
- Conditions (RegulatoryNonCompliance, FairCompetitiveSelectionRequirement, etc.)
- Ethical issues (UnfairCompetitiveAdvantage, etc.)
- Ethical verdicts (UnethicalAction, EthicalAction, etc.)
"""

import os
import sys
import json
import logging
from datetime import datetime
import traceback

# Add parent directory to path to import config and utils
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import NAMESPACE_URIS, RDF_TYPE_PREDICATE
from utils.database import store_entity_triples, clear_entity_triples, remove_rdf_type_triples

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("semantic_tagger")

class SemanticTagger:
    """Applies dual-layer ontology tagging to engineering ethics cases."""
    
    def __init__(self):
        """Initialize the tagger with necessary namespaces."""
        self.namespaces = NAMESPACE_URIS
        
    def tag_case(self, case_data, clear_existing=True):
        """
        Apply semantic tagging to a case.
        
        Args:
            case_data: Dictionary containing case information
            clear_existing: Whether to clear existing triples for this case
            
        Returns:
            dict: A dictionary with the following keys:
                - success: Whether the tagging was successful
                - message: A message indicating the result
                - case_id: The ID of the case
                - triple_count: The number of triples generated
        """
        try:
            case_id = case_data.get('id')
            if not case_id:
                return {
                    'success': False,
                    'message': 'Case ID is required'
                }
                
            logger.info(f"Applying semantic tagging to case ID {case_id}")
            
            # Clear existing triples if requested
            if clear_existing:
                removed_count = clear_entity_triples(case_id)
                logger.info(f"Cleared {removed_count} existing triples for case ID {case_id}")
                
            # Generate triples using the dual-layer approach
            mclaren_triples = self._generate_mclaren_triples(case_data)
            scenario_triples = self._generate_scenario_triples(case_data)
            
            # Combine triples and store in database
            all_triples = mclaren_triples + scenario_triples
            
            if store_entity_triples(case_id, all_triples):
                # Remove any RDF type triples to maintain clean triple display
                removed_count = remove_rdf_type_triples(case_id)
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} generic RDF type triples")
                    
                return {
                    'success': True,
                    'message': f"Successfully generated {len(all_triples)} semantic triples",
                    'case_id': case_id,
                    'triple_count': len(all_triples)
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to store triples in database",
                    'case_id': case_id
                }
                
        except Exception as e:
            logger.error(f"Error in semantic tagging: {str(e)}")
            traceback.print_exc()
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'case_id': case_id if 'case_id' in locals() else None
            }
    
    def _generate_mclaren_triples(self, case_data):
        """
        Generate triples based on McLaren's extensional definition approach.
        
        Args:
            case_data: Dictionary containing case information
            
        Returns:
            list: List of triple dictionaries
        """
        case_id = case_data.get('id')
        triples = []
        
        # Determine case type and content for analysis
        case_title = case_data.get('title', '')
        case_number = case_data.get('doc_metadata', {}).get('case_number', '')
        
        if not case_number and isinstance(case_data.get('doc_metadata'), str):
            # Handle case where doc_metadata is a JSON string
            try:
                metadata = json.loads(case_data.get('doc_metadata', '{}'))
                case_number = metadata.get('case_number', '')
            except:
                pass
                
        description = case_data.get('description', '')
        decision = case_data.get('decision', '')
        
        # Content to analyze
        content_to_analyze = description
        if decision:
            content_to_analyze += "\n\n" + decision
            
        # Fallback to full content if needed
        if not content_to_analyze and case_data.get('content'):
            content_to_analyze = case_data.get('content')
            
        # Skip if no content to analyze
        if not content_to_analyze:
            logger.warning(f"No content to analyze for case ID {case_id}")
            return []
            
        # 1. Principle Instantiations
        # Extracted from this case's content - normally we would use NLP or LLM to identify these
        # Here we'll use a simple approach based on common patterns in NSPE cases
        
        # Check for common principles in engineering ethics
        principles = {
            "PublicSafetyFirst": {
                "keywords": ["public safety", "protect the public", "safety of the public", "welfare of the public"],
                "code": "I.1",
                "text": "Engineers shall hold paramount the safety, health, and welfare of the public"
            },
            "ProfessionalIntegrity": {
                "keywords": ["integrity", "honest", "impartial", "faithful", "ethical conduct"],
                "code": "II.5.B",
                "text": "Engineers shall not offer any gift or valuable consideration in order to secure work"
            },
            "Fairness": {
                "keywords": ["fair", "fairness", "equitable", "justice", "impartial"],
                "code": "III.1.F",
                "text": "Engineers shall treat all persons with fairness"
            },
            "Confidentiality": {
                "keywords": ["confidential", "proprietary", "secret", "nondisclosure"],
                "code": "III.4",
                "text": "Engineers shall not disclose, without consent, confidential information"
            },
            "HonestyInReporting": {
                "keywords": ["honest", "truthful", "report", "disclose", "acknowledge errors"],
                "code": "II.3.A",
                "text": "Engineers shall be objective and truthful in professional reports, statements, or testimony"
            }
        }
        
        # Look for principles in the content
        for principle_name, principle_info in principles.items():
            for keyword in principle_info["keywords"]:
                if keyword.lower() in content_to_analyze.lower():
                    # Add principle instantiation triple
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}instantiatesPrinciple",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{principle_name}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}case-analysis",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000015",  # Process
                            "principle_code": principle_info["code"],
                            "principle_text": principle_info["text"]
                        }
                    })
                    break  # Only add once per principle
                    
        # 2. Principle Conflicts - only if we found more than one principle
        if len([t for t in triples if "instantiatesPrinciple" in t["predicate"]]) > 1:
            # Add a potential conflict
            triples.append({
                "subject": f"Case {case_id}",
                "predicate": f"{self.namespaces['engineering-ethics']}hasPrincipleConflict",
                "object_literal": "Contains potential principle conflicts",
                "is_literal": True,
                "graph": f"{self.namespaces['proethica']}case-analysis",
                "triple_metadata": {
                    "bfo_classification": f"{self.namespaces['bfo']}BFO_0000015",  # Process
                    "conflict_description": "Multiple principles might be in tension in this case"
                }
            })
        
        # 3. Operationalization Techniques
        # McLaren's operationalization techniques as BFO:Process
        triples.append({
            "subject": f"Case {case_id}",
            "predicate": f"{self.namespaces['mclaren']}usesOperationalizationTechnique",
            "object_uri": f"{self.namespaces['mclaren']}FactualApplication",
            "is_literal": False,
            "graph": f"{self.namespaces['proethica']}case-analysis",
            "triple_metadata": {
                "bfo_classification": f"{self.namespaces['bfo']}BFO_0000015",  # Process
                "technique_description": "Applying ethics principles to concrete facts of the case"
            }
        })
        
        # In a real implementation, we would use more sophisticated NLP or LLM-based analysis
        # to identify principles, conflicts, and operationalization techniques
        
        logger.info(f"Generated {len(triples)} McLaren extensional definition triples for case {case_id}")
        return triples
    
    def _generate_scenario_triples(self, case_data):
        """
        Generate triples based on the scenario-level semantic relationships.
        
        Args:
            case_data: Dictionary containing case information
            
        Returns:
            list: List of triple dictionaries
        """
        case_id = case_data.get('id')
        triples = []
        
        case_title = case_data.get('title', '')
        description = case_data.get('description', '')
        decision = case_data.get('decision', '')
        
        # Content to analyze
        content_to_analyze = description
        if decision:
            content_to_analyze += "\n\n" + decision
            
        # Fallback to full content if needed
        if not content_to_analyze and case_data.get('content'):
            content_to_analyze = case_data.get('content')
            
        # Skip if no content to analyze
        if not content_to_analyze:
            logger.warning(f"No content to analyze for case ID {case_id}")
            return []
            
        # Map role keywords to role types
        roles = {
            "EngineeringConsultantRole": ["consultant", "engineering firm", "professional engineer", "consulting engineer"],
            "ClientRole": ["client", "owner", "employer", "municipality", "city", "county", "state agency"],
            "RegulatoryAuthorityRole": ["authority", "regulator", "regulatory", "agency", "board", "commission", "inspector"],
            "EngineeringManagerRole": ["manager", "supervisor", "director", "chief engineer"],
            "GovernmentEngineerRole": ["government engineer", "public works", "municipal engineer", "city engineer"],
            "ContractorRole": ["contractor", "construction company", "builder", "subcontractor"]
        }
        
        # Map resource keywords to resource types
        resources = {
            "EngineeringReport": ["report", "study", "analysis", "assessment", "evaluation"],
            "EngineeringDesign": ["design", "plans", "specifications", "drawings", "schematics"],
            "Infrastructure": ["infrastructure", "facility", "building", "structure", "system"],
            "ContractDocument": ["contract", "agreement", "proposal", "bid", "tender", "procurement"],
            "ConstructionProject": ["project", "construction", "development", "work", "job"]
        }
        
        # Map event keywords to event types
        events = {
            "ProcurementProcess": ["procurement", "bidding", "selection", "competition", "request for proposals"],
            "RegulatoryReview": ["review", "inspection", "approval", "permit", "certification"],
            "ProjectFailure": ["failure", "collapse", "accident", "incident", "malfunction", "defect"],
            "ContractDispute": ["dispute", "conflict", "disagreement", "litigation", "lawsuit", "claim"]
        }
        
        # Map action keywords to action types
        actions = {
            "OfferingServices": ["offer", "providing", "delivering", "performing", "proposing"],
            "MakingDecision": ["decide", "judgment", "determination", "choice", "resolution"],
            "ReportingIssue": ["report", "disclose", "notify", "inform", "alert", "warn"],
            "ReviewingDocument": ["review", "examine", "analyze", "evaluate", "assess", "audit"]
        }
        
        # Map condition keywords to condition types
        conditions = {
            "RegulatoryRequirement": ["requirement", "regulation", "code", "standard", "rule", "law"],
            "EthicalObligation": ["obligation", "duty", "responsibility", "commitment"],
            "SafetyHazard": ["hazard", "danger", "risk", "threat", "safety concern", "unsafe"],
            "ConflictOfInterest": ["conflict of interest", "competing interest", "bias", "impartiality"]
        }
        
        # Simple pattern matching to generate scenario entity triples
        # In a real implementation, we would use NLP or LLMs for more accurate entity recognition
        
        # 1. Roles
        for role_type, keywords in roles.items():
            for keyword in keywords:
                if keyword.lower() in content_to_analyze.lower():
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}hasRole",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{role_type}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}scenario-entities",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000023",  # Role
                            "role_description": f"Entity playing a {role_type.replace('Role', ' role')} in this case",
                            "detected_from": keyword
                        }
                    })
                    break  # Only add once per role type
        
        # 2. Resources
        for resource_type, keywords in resources.items():
            for keyword in keywords:
                if keyword.lower() in content_to_analyze.lower():
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}involvesResource",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{resource_type}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}scenario-entities",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000004",  # IndependentContinuant
                            "resource_description": f"{resource_type} involved in this case",
                            "detected_from": keyword
                        }
                    })
                    break  # Only add once per resource type
        
        # 3. Events
        for event_type, keywords in events.items():
            for keyword in keywords:
                if keyword.lower() in content_to_analyze.lower():
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}involvesEvent",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{event_type}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}scenario-entities",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000015",  # Process
                            "event_description": f"{event_type} that occurred in this case",
                            "detected_from": keyword
                        }
                    })
                    break  # Only add once per event type
        
        # 4. Actions
        for action_type, keywords in actions.items():
            for keyword in keywords:
                if keyword.lower() in content_to_analyze.lower():
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}involvesAction",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{action_type}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}scenario-entities",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000015",  # Process
                            "action_description": f"{action_type} performed by someone in this case",
                            "detected_from": keyword
                        }
                    })
                    break  # Only add once per action type
        
        # 5. Conditions
        for condition_type, keywords in conditions.items():
            for keyword in keywords:
                if keyword.lower() in content_to_analyze.lower():
                    triples.append({
                        "subject": f"Case {case_id}",
                        "predicate": f"{self.namespaces['engineering-ethics']}involvesCondition",
                        "object_uri": f"{self.namespaces['engineering-ethics']}{condition_type}",
                        "is_literal": False,
                        "graph": f"{self.namespaces['proethica']}scenario-entities",
                        "triple_metadata": {
                            "bfo_classification": f"{self.namespaces['bfo']}BFO_0000019",  # Quality
                            "condition_description": f"{condition_type} present in this case",
                            "detected_from": keyword
                        }
                    })
                    break  # Only add once per condition type
                    
        # 6. Ethical verdict based on keywords in the decision section
        ethical_verdict = "UndeterminedVerdict"  # Default
        if decision:
            decision_lower = decision.lower()
            if "unethical" in decision_lower or "not ethical" in decision_lower:
                ethical_verdict = "UnethicalAction"
            elif "ethical" in decision_lower:
                ethical_verdict = "EthicalAction"
                
        triples.append({
            "subject": f"Case {case_id}",
            "predicate": f"{self.namespaces['engineering-ethics']}hasEthicalVerdict",
            "object_uri": f"{self.namespaces['engineering-ethics']}{ethical_verdict}",
            "is_literal": False,
            "graph": f"{self.namespaces['proethica']}scenario-entities",
            "triple_metadata": {
                "bfo_classification": f"{self.namespaces['bfo']}BFO_0000031",  # Generically Dependent Continuant
                "verdict_description": f"The ethical verdict of this case is {ethical_verdict.replace('Action', '').replace('Verdict', '')}",
                "verdict_authority": "Board of Ethical Review"
            }
        })
        
        logger.info(f"Generated {len(triples)} intermediate ontology triples for case {case_id}")
        return triples


def tag_case(case_data, clear_existing=True):
    """
    Apply semantic tagging to a case.
    
    Args:
        case_data: Dictionary containing case information
        clear_existing: Whether to clear existing triples
        
    Returns:
        dict: Result of tagging operation
    """
    tagger = SemanticTagger()
    return tagger.tag_case(case_data, clear_existing)
