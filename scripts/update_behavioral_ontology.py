#!/usr/bin/env python3
"""
Script to add Action, Event, State, and Capability subclasses to the ProEthica ontology.
Based on Chapter 2 literature review sections 2.2.4, 2.2.6, 2.2.7, and 2.2.8.

This follows the pattern established for Roles and Principles with scholarly grounding.
"""

import psycopg2
from psycopg2.extras import Json
import json
from datetime import datetime

# Database connection parameters
DB_CONFIG = {
    'dbname': 'ontserve',
    'user': 'postgres',
    'password': 'PASS',
    'host': 'localhost',
    'port': 5432
}

def add_action_subclasses(cursor, ontology_id):
    """Add Action subclasses based on Chapter 2.2.6 literature."""
    
    action_classes = [
        {
            'uri': 'http://proethica.org/ontology#DecisionAction',
            'label': 'DecisionAction',
            'comment': 'Professional choices between alternatives requiring judgment. Deliberate selection among options exercising professional discretion (Abbott 2020).',
            'parent_uri': 'http://proethica.org/ontology#Action',
            'properties': Json({
                'scholarly_grounding': 'Abbott (2020) - Professional actions as deliberate interventions',
                'volitional_aspect': 'Deliberate selection among options',
                'professional_context': 'Exercises professional discretion and expertise',
                'examples': ['Approve design', 'Reject proposal', 'Select contractor']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#InterventionAction',
            'label': 'InterventionAction',
            'comment': 'Direct modifications to situations or systems through intentional professional intervention (Sarmiento et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#Action',
            'properties': Json({
                'scholarly_grounding': 'Sarmiento et al. (2023) - Actions as volitional events with causal chains',
                'volitional_aspect': 'Intentional change to environment or state',
                'professional_context': 'Uses professional skills to alter conditions',
                'examples': ['Modify design', 'Implement safeguards', 'Correct deficiencies']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#CommunicationAction',
            'label': 'CommunicationAction',
            'comment': 'Information transmission with professional implications including deliberate disclosure or withholding (Dawson 1994).',
            'parent_uri': 'http://proethica.org/ontology#Action',
            'properties': Json({
                'scholarly_grounding': 'Dawson (1994) - Professional actions with special moral properties',
                'volitional_aspect': 'Deliberate disclosure or withholding',
                'professional_context': 'Professional reporting and documentation duties',
                'examples': ['Report violation', 'Disclose risks', 'Document findings']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#ReviewAction',
            'label': 'ReviewAction',
            'comment': 'Professional evaluation and verification activities using systematic assessment with professional standards (Berreby et al. 2017).',
            'parent_uri': 'http://proethica.org/ontology#Action',
            'properties': Json({
                'scholarly_grounding': 'Berreby et al. (2017) - Action Model for ethical agents',
                'volitional_aspect': 'Systematic assessment using professional standards',
                'professional_context': 'Quality assurance and peer review responsibilities',
                'examples': ['Review calculations', 'Verify compliance', 'Audit procedures']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#AuthorizationAction',
            'label': 'AuthorizationAction',
            'comment': 'Exercise of professional authority to permit or certify based on professional judgment (Govindarajulu & Bringsjord 2017).',
            'parent_uri': 'http://proethica.org/ontology#Action',
            'properties': Json({
                'scholarly_grounding': 'Govindarajulu & Bringsjord (2017) - Intention-based action evaluation',
                'volitional_aspect': 'Formal approval based on professional judgment',
                'professional_context': 'Legal/professional standing to authorize',
                'examples': ['Certify design', 'Approve payment', 'Authorize construction']
            })
        }
    ]
    
    for action_class in action_classes:
        # Check if entity already exists
        cursor.execute("""
            SELECT id FROM ontology_entities 
            WHERE ontology_id = %s AND uri = %s
        """, (ontology_id, action_class['uri']))
        
        if cursor.fetchone() is None:
            # Insert new entity
            cursor.execute("""
                INSERT INTO ontology_entities (ontology_id, uri, label, comment, entity_type, parent_uri, properties)
                VALUES (%s, %s, %s, %s, 'class', %s, %s)
            """, (ontology_id, action_class['uri'], action_class['label'], 
                  action_class['comment'], action_class['parent_uri'], 
                  action_class['properties']))
        else:
            # Update existing entity
            cursor.execute("""
                UPDATE ontology_entities 
                SET label = %s, comment = %s, parent_uri = %s, properties = %s
                WHERE ontology_id = %s AND uri = %s
            """, (action_class['label'], action_class['comment'], 
                  action_class['parent_uri'], action_class['properties'],
                  ontology_id, action_class['uri']))
    
    print(f"Added {len(action_classes)} Action subclasses")


def add_event_subclasses(cursor, ontology_id):
    """Add Event subclasses based on Chapter 2.2.7 literature."""
    
    event_classes = [
        {
            'uri': 'http://proethica.org/ontology#TriggeringEvent',
            'label': 'TriggeringEvent',
            'comment': 'Occurrences that initiate ethical obligations or constraints, marking transition points in ethical requirements (Berreby et al. 2017).',
            'parent_uri': 'http://proethica.org/ontology#Event',
            'properties': Json({
                'scholarly_grounding': 'Berreby et al. (2017) - Event Calculus and automatic events',
                'temporal_role': 'Marks transition points in ethical requirements',
                'causal_function': 'Begins causal chains requiring response',
                'examples': ['Conflict discovered', 'Safety risk identified', 'Deadline reached']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#OutcomeEvent',
            'label': 'OutcomeEvent',
            'comment': 'Results or consequences of actions or processes serving as endpoints of causal chains (Sarmiento et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#Event',
            'properties': Json({
                'scholarly_grounding': 'Sarmiento et al. (2023) - Events as nodes in causal chains',
                'temporal_role': 'Endpoints of causal chains',
                'causal_function': 'Effects requiring evaluation or further action',
                'examples': ['Project completed', 'Failure occurred', 'Harm resulted']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#MilestoneEvent',
            'label': 'MilestoneEvent',
            'comment': 'Significant points in professional processes marking phases requiring different obligations (Anderson & Anderson 2018).',
            'parent_uri': 'http://proethica.org/ontology#Event',
            'properties': Json({
                'scholarly_grounding': 'Anderson & Anderson (2018) - Temporal dynamics in ethics',
                'temporal_role': 'Marks phases requiring different obligations',
                'causal_function': 'Transitions between ethical contexts',
                'examples': ['Contract signed', 'Approval granted', 'Certification achieved']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#EmergencyEvent',
            'label': 'EmergencyEvent',
            'comment': 'Critical occurrences requiring immediate response that suspend normal obligations and activate emergency constraints (Zhang et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#Event',
            'properties': Json({
                'scholarly_grounding': 'Zhang et al. (2023) - Moral events classification',
                'temporal_role': 'Suspends normal obligations, activates emergency constraints',
                'causal_function': 'Overrides standard procedures',
                'examples': ['Structural failure', 'Safety breach', 'System compromise']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#DiscoveryEvent',
            'label': 'DiscoveryEvent',
            'comment': 'Revelations of previously unknown information changing knowledge state and affecting obligations (Almpani et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#Event',
            'properties': Json({
                'scholarly_grounding': 'Almpani et al. (2023) - Events triggering ethical consideration',
                'temporal_role': 'Changes knowledge state affecting obligations',
                'causal_function': 'Triggers reassessment and potential action',
                'examples': ['Defect discovered', 'Conflict revealed', 'Error detected']
            })
        }
    ]
    
    for event_class in event_classes:
        # Check if entity already exists
        cursor.execute("""
            SELECT id FROM ontology_entities 
            WHERE ontology_id = %s AND uri = %s
        """, (ontology_id, event_class['uri']))
        
        if cursor.fetchone() is None:
            # Insert new entity
            cursor.execute("""
                INSERT INTO ontology_entities (ontology_id, uri, label, comment, entity_type, parent_uri, properties)
                VALUES (%s, %s, %s, %s, 'class', %s, %s)
            """, (ontology_id, event_class['uri'], event_class['label'], 
                  event_class['comment'], event_class['parent_uri'], 
                  event_class['properties']))
        else:
            # Update existing entity
            cursor.execute("""
                UPDATE ontology_entities 
                SET label = %s, comment = %s, parent_uri = %s, properties = %s
                WHERE ontology_id = %s AND uri = %s
            """, (event_class['label'], event_class['comment'], 
                  event_class['parent_uri'], event_class['properties'],
                  ontology_id, event_class['uri']))
    
    print(f"Added {len(event_classes)} Event subclasses")


def add_state_subclasses(cursor, ontology_id):
    """Add State subclasses based on Chapter 2.2.4 literature."""
    
    state_classes = [
        {
            'uri': 'http://proethica.org/ontology#ConflictState',
            'label': 'ConflictState',
            'comment': 'Situations involving competing interests or obligations that trigger special disclosure and management requirements (Dennis et al. 2016).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Dennis et al. (2016) - Context-aware ethical reasoning',
                'persistence': 'Inertial - remains until resolved',
                'ethical_impact': 'Triggers special disclosure and management obligations',
                'examples': ['Conflict of interest exists', 'Competing duties present']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#RiskState',
            'label': 'RiskState',
            'comment': 'Conditions involving potential harm or danger that elevate safety obligations and precautionary duties (Rao et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Rao et al. (2023) - Context-dependence in ethical evaluation',
                'persistence': 'Variable - depends on mitigation actions',
                'ethical_impact': 'Elevates safety obligations and precautionary duties',
                'examples': ['Public safety at risk', 'Environmental hazard present']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#CompetenceState',
            'label': 'CompetenceState',
            'comment': 'Conditions regarding professional capability boundaries that limit available actions and trigger referral obligations (Almpani et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Almpani et al. (2023) - Environmental states determining priorities',
                'persistence': 'Inertial - changes with training or assignment',
                'ethical_impact': 'Limits available actions, triggers referral obligations',
                'examples': ['Outside area of competence', 'Qualified to perform']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#RelationshipState',
            'label': 'RelationshipState',
            'comment': 'Professional relationship contexts and boundaries that define applicable duties and constraints (Berreby et al. 2017).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Berreby et al. (2017) - Event Calculus for state representation',
                'persistence': 'Inertial - stable until formally changed',
                'ethical_impact': 'Defines applicable duties and constraints',
                'examples': ['Client relationship established', 'Employment terminated']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#InformationState',
            'label': 'InformationState',
            'comment': 'Conditions regarding knowledge and confidentiality that trigger disclosure or protection obligations (Sarmiento et al. 2023).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Sarmiento et al. (2023) - States emerging from causal chains',
                'persistence': 'Mixed - some permanent, some temporary',
                'ethical_impact': 'Triggers disclosure or protection obligations',
                'examples': ['Confidential information held', 'Public information available']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#EmergencyState',
            'label': 'EmergencyState',
            'comment': 'Critical conditions requiring immediate response that override normal procedures and activate emergency protocols (Coeckelbergh 2020).',
            'parent_uri': 'http://proethica.org/ontology#State',
            'properties': Json({
                'scholarly_grounding': 'Coeckelbergh (2020) - Context-dependent obligation activation',
                'persistence': 'Non-inertial - temporary urgency',
                'ethical_impact': 'Overrides normal procedures, activates emergency protocols',
                'examples': ['Emergency situation', 'Crisis conditions']
            })
        }
    ]
    
    for state_class in state_classes:
        # Check if entity already exists
        cursor.execute("""
            SELECT id FROM ontology_entities 
            WHERE ontology_id = %s AND uri = %s
        """, (ontology_id, state_class['uri']))
        
        if cursor.fetchone() is None:
            # Insert new entity
            cursor.execute("""
                INSERT INTO ontology_entities (ontology_id, uri, label, comment, entity_type, parent_uri, properties)
                VALUES (%s, %s, %s, %s, 'class', %s, %s)
            """, (ontology_id, state_class['uri'], state_class['label'], 
                  state_class['comment'], state_class['parent_uri'], 
                  state_class['properties']))
        else:
            # Update existing entity
            cursor.execute("""
                UPDATE ontology_entities 
                SET label = %s, comment = %s, parent_uri = %s, properties = %s
                WHERE ontology_id = %s AND uri = %s
            """, (state_class['label'], state_class['comment'], 
                  state_class['parent_uri'], state_class['properties'],
                  ontology_id, state_class['uri']))
    
    print(f"Added {len(state_classes)} State subclasses")


def add_capability_subclasses(cursor, ontology_id):
    """Add Capability subclasses based on Chapter 2.2.8 literature."""
    
    capability_classes = [
        {
            'uri': 'http://proethica.org/ontology#TechnicalCapability',
            'label': 'TechnicalCapability',
            'comment': 'Domain-specific professional skills and expertise enabling accurate assessment and competent performance (Tolmeijer et al. 2021).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Tolmeijer et al. (2021) - Essential capabilities taxonomy',
                'function': 'Enables accurate assessment and competent performance',
                'meta_aspect': 'Knowing limits of technical competence',
                'examples': ['Engineering analysis capability', 'Clinical diagnosis skill']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#EthicalReasoningCapability',
            'label': 'EthicalReasoningCapability',
            'comment': 'Abilities for moral judgment and norm management including processing ethical information and resolving conflicts (Berreby et al. 2017).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Berreby et al. (2017) - Action Model for agent capabilities',
                'function': 'Process ethical information, resolve conflicts',
                'meta_aspect': 'Understanding when principles conflict',
                'examples': ['Ethical evaluation ability', 'Conflict resolution skill']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#CommunicationCapability',
            'label': 'CommunicationCapability',
            'comment': 'Abilities for explanation, documentation, and reporting to justify decisions and maintain transparency (Langley 2019).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Langley (2019) - Explanation and justification capabilities',
                'function': 'Justify decisions, maintain transparency',
                'meta_aspect': 'Adapting communication to audience',
                'examples': ['Technical writing skill', 'Client communication ability']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#PerceptualCapability',
            'label': 'PerceptualCapability',
            'comment': 'Abilities to recognize ethically salient features and identify risks, conflicts, and obligations (Hallamaa & Kalliokoski 2022).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Hallamaa & Kalliokoski (2022) - Domain-specific competencies',
                'function': 'Identify risks, conflicts, and obligations',
                'meta_aspect': 'Recognizing limits of perception',
                'examples': ['Risk identification ability', 'Problem recognition skill']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#LearningCapability',
            'label': 'LearningCapability',
            'comment': 'Abilities to adapt and improve performance through updating knowledge and refining principles (Anderson & Anderson 2018).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Anderson & Anderson (2018) - Learning and adaptation capabilities',
                'function': 'Update knowledge, refine principles',
                'meta_aspect': 'Recognizing need for learning',
                'examples': ['Professional development capacity', 'Skill acquisition ability']
            })
        },
        {
            'uri': 'http://proethica.org/ontology#JudgmentCapability',
            'label': 'JudgmentCapability',
            'comment': 'Abilities for professional discretion and decision-making to exercise prudent judgment in complex situations (Wallach & Allen 2009).',
            'parent_uri': 'http://proethica.org/ontology#Capability',
            'properties': Json({
                'scholarly_grounding': 'Wallach & Allen (2009) - Complex decision-making capabilities',
                'function': 'Exercise prudent judgment in complex situations',
                'meta_aspect': 'Understanding judgment limitations',
                'examples': ['Professional judgment', 'Critical evaluation skill']
            })
        }
    ]
    
    for capability_class in capability_classes:
        # Check if entity already exists
        cursor.execute("""
            SELECT id FROM ontology_entities 
            WHERE ontology_id = %s AND uri = %s
        """, (ontology_id, capability_class['uri']))
        
        if cursor.fetchone() is None:
            # Insert new entity
            cursor.execute("""
                INSERT INTO ontology_entities (ontology_id, uri, label, comment, entity_type, parent_uri, properties)
                VALUES (%s, %s, %s, %s, 'class', %s, %s)
            """, (ontology_id, capability_class['uri'], capability_class['label'], 
                  capability_class['comment'], capability_class['parent_uri'], 
                  capability_class['properties']))
        else:
            # Update existing entity
            cursor.execute("""
                UPDATE ontology_entities 
                SET label = %s, comment = %s, parent_uri = %s, properties = %s
                WHERE ontology_id = %s AND uri = %s
            """, (capability_class['label'], capability_class['comment'], 
                  capability_class['parent_uri'], capability_class['properties'],
                  ontology_id, capability_class['uri']))
    
    print(f"Added {len(capability_classes)} Capability subclasses")


def main():
    """Main function to add all behavioral concept subclasses to the ontology."""
    
    conn = None
    cursor = None
    
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get the proethica-intermediate ontology ID
        cursor.execute("""
            SELECT id FROM ontologies 
            WHERE name = 'proethica-intermediate'
        """)
        result = cursor.fetchone()
        
        if not result:
            print("Error: proethica-intermediate ontology not found!")
            return
        
        ontology_id = result[0]
        print(f"Found proethica-intermediate ontology with ID: {ontology_id}")
        
        # Add all subclasses
        print("\nAdding Action subclasses...")
        add_action_subclasses(cursor, ontology_id)
        
        print("\nAdding Event subclasses...")
        add_event_subclasses(cursor, ontology_id)
        
        print("\nAdding State subclasses...")
        add_state_subclasses(cursor, ontology_id)
        
        print("\nAdding Capability subclasses...")
        add_capability_subclasses(cursor, ontology_id)
        
        # Commit changes
        conn.commit()
        print("\n✅ Successfully added all behavioral concept subclasses to the ontology!")
        
        # Verify the additions
        cursor.execute("""
            SELECT COUNT(*) FROM ontology_entities 
            WHERE ontology_id = %s 
            AND uri LIKE 'http://proethica.org/ontology#%%Action'
        """, (ontology_id,))
        action_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM ontology_entities 
            WHERE ontology_id = %s 
            AND uri LIKE 'http://proethica.org/ontology#%%Event'
        """, (ontology_id,))
        event_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM ontology_entities 
            WHERE ontology_id = %s 
            AND uri LIKE 'http://proethica.org/ontology#%%State'
        """, (ontology_id,))
        state_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM ontology_entities 
            WHERE ontology_id = %s 
            AND uri LIKE 'http://proethica.org/ontology#%%Capability'
        """, (ontology_id,))
        capability_count = cursor.fetchone()[0]
        
        print(f"\nVerification:")
        print(f"  Action subclasses: {action_count}")
        print(f"  Event subclasses: {event_count}")
        print(f"  State subclasses: {state_count}")
        print(f"  Capability subclasses: {capability_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()