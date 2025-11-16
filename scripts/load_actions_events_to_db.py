#!/usr/bin/env python3
"""
Load Action and Event Subclasses to Database

This script directly loads Action and Event subclasses into the ontology_entities table
following the same pattern used for obligations, constraints, and capabilities.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Add OntServe to path
ontserve_root = project_root.parent / 'OntServe'
sys.path.insert(0, str(ontserve_root))

def load_actions_events_to_database():
    """Load Action and Event subclasses directly to database."""
    print("=== Loading Action/Event Subclasses to Database ===")
    
    try:
        # Set up database environment
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5432/ontserve'
        os.environ['FLASK_CONFIG'] = 'development'
        
        from web.models import db, Ontology, OntologyEntity
        from flask import Flask
        from web.config import Config
        
        # Create Flask app
        app = Flask(__name__)
        app.config.from_object(Config)
        
        # Initialize database
        from web.models import init_db
        init_db(app)
        
        with app.app_context():
            # Find proethica-intermediate ontology
            ontology = Ontology.query.filter_by(name='proethica-intermediate').first()
            if not ontology:
                print("❌ proethica-intermediate ontology not found!")
                return False
            
            print(f"Found ontology: {ontology.name} (ID: {ontology.id})")
            
            # Get base URIs for Action and Event
            base_action_uri = "http://proethica.org/ontology/core#Action"
            base_event_uri = "http://proethica.org/ontology/core#Event"
            
            # Define Action subclasses based on our TTL definitions
            action_subclasses = [
                {
                    'uri': 'http://proethica.org/ontology/intermediate#CommunicationAction',
                    'label': 'Communication Action',
                    'comment': 'Professional actions involving disclosure, informing, notifying stakeholders, and communicating relevant information per Tolmeijer et al. (2021) explanation requirements and McLaren (2003) transparency obligations.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#PreventionAction',
                    'label': 'Prevention Action', 
                    'comment': 'Professional actions aimed at avoiding, preventing, minimizing, or eliminating risks and harms per Anderson & Anderson (2018) harm prevention principles and Arkin (2008) safety obligations.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#MaintenanceAction',
                    'label': 'Maintenance Action',
                    'comment': 'Professional actions involving maintaining, upholding, preserving, and protecting professional standards and values per Oakley & Cocking (2001) role requirements and Kong et al. (2020) integrity principles.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#PerformanceAction',
                    'label': 'Performance Action',
                    'comment': 'Professional actions involving performing, executing, conducting, and implementing professional services within areas of competence per professional obligation frameworks (NSPE II.2).',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#EvaluationAction',
                    'label': 'Evaluation Action',
                    'comment': 'Professional actions involving evaluating, assessing, analyzing, reviewing, and examining professional work, conditions, or decisions per Berreby et al. (2017) assessment processes and Tolmeijer et al. (2021) situational awareness.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#CollaborationAction',
                    'label': 'Collaboration Action',
                    'comment': 'Professional actions involving consulting, collaborating, coordinating, and cooperating with colleagues, clients, and stakeholders per Dennis et al. (2016) multi-agent frameworks and professional peer obligations.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#CreationAction',
                    'label': 'Creation Action',
                    'comment': 'Professional actions involving designing, developing, creating, building, and constructing professional solutions per technical competence requirements and innovation obligations.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#MonitoringAction',
                    'label': 'Monitoring Action',
                    'comment': 'Professional actions involving monitoring, supervising, overseeing, managing, and controlling professional processes per Arkin (2008) responsibility documentation and oversight requirements.',
                    'parent_uri': base_action_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#DisclosureAction',
                    'label': 'Disclosure Action',
                    'comment': 'Professional action of revealing conflicts, limitations, or risks to stakeholders per NSPE requirements and transparency principles.',
                    'parent_uri': 'http://proethica.org/ontology/intermediate#CommunicationAction'
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#CompetenceAction',
                    'label': 'Competence Action',
                    'comment': 'Professional action performed within demonstrated areas of competence per NSPE competence requirements and professional boundaries.',
                    'parent_uri': 'http://proethica.org/ontology/intermediate#PerformanceAction'
                }
            ]
            
            # Define Event subclasses based on our TTL definitions
            event_subclasses = [
                {
                    'uri': 'http://proethica.org/ontology/intermediate#CrisisEvent',
                    'label': 'Crisis Event',
                    'comment': 'Events involving failures, accidents, emergencies, crises, and disasters that require immediate professional response and may override normal procedures per Berreby et al. (2017) automatic event modeling.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#ComplianceEvent',
                    'label': 'Compliance Event',
                    'comment': 'Events involving violations, breaches, non-compliance, misconduct, or errors that trigger regulatory or professional review processes per Dennis et al. (2016) ethical policy frameworks.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#ConflictEvent',
                    'label': 'Conflict Event',
                    'comment': 'Events involving conflicts, disputes, disagreements, controversies, or issues between stakeholders that require professional mediation or resolution per Rao et al. (2023) context-dependent moral evaluation.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#ProjectEvent',
                    'label': 'Project Event',
                    'comment': 'Events involving deadlines, milestones, completions, deliveries, and launches that affect project timelines and professional obligations per Sarmiento et al. (2023) temporal reasoning.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#SafetyEvent',
                    'label': 'Safety Event',
                    'comment': 'Events involving injuries, harm, damage, losses, threats, or risks that trigger safety obligations and public welfare protections per Anderson & Anderson (2018) harm-based ethical evaluation.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#EvaluationEvent',
                    'label': 'Evaluation Event',
                    'comment': 'Events involving inspections, audits, reviews, assessments, and evaluations that trigger professional scrutiny and accountability requirements per Arkin (2008) responsibility documentation.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#DiscoveryEvent',
                    'label': 'Discovery Event',
                    'comment': 'Events involving discoveries, findings, identifications, detections, or reports of new information that may affect professional obligations per Zhang et al. (2023) moral event classification.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#ChangeEvent',
                    'label': 'Change Event',
                    'comment': 'Events involving changes, modifications, alterations, updates, or revisions to systems, procedures, or requirements that affect professional practice per Almpani et al. (2023) dynamic priority adjustment.',
                    'parent_uri': base_event_uri
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#EmergencyEvent',
                    'label': 'Emergency Event',
                    'comment': 'Critical event requiring immediate response that may override normal professional procedures and activate emergency protocols.',
                    'parent_uri': 'http://proethica.org/ontology/intermediate#CrisisEvent'
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#DeadlineEvent',
                    'label': 'Deadline Event',
                    'comment': 'Temporal event marking project deadline or milestone that affects professional priorities and resource allocation decisions.',
                    'parent_uri': 'http://proethica.org/ontology/intermediate#ProjectEvent'
                },
                {
                    'uri': 'http://proethica.org/ontology/intermediate#SafetyIncident',
                    'label': 'Safety Incident',
                    'comment': 'Event involving actual or potential harm triggering safety reporting obligations and corrective measures per public welfare protection requirements.',
                    'parent_uri': 'http://proethica.org/ontology/intermediate#SafetyEvent'
                }
            ]
            
            # Load Action subclasses
            print("Loading Action subclasses...")
            loaded_actions = 0
            
            for action_class in action_subclasses:
                # Check if already exists
                existing = OntologyEntity.query.filter_by(
                    uri=action_class['uri'],
                    ontology_id=ontology.id
                ).first()
                
                if existing:
                    print(f"  ⚠️ {action_class['label']} already exists")
                    continue
                
                # Create new entity
                entity = OntologyEntity(
                    ontology_id=ontology.id,
                    uri=action_class['uri'],
                    label=action_class['label'],
                    entity_type='class',
                    comment=action_class['comment'],
                    parent_uri=action_class['parent_uri']
                )
                
                db.session.add(entity)
                loaded_actions += 1
                print(f"  ✅ Added {action_class['label']}")
            
            # Load Event subclasses
            print("Loading Event subclasses...")
            loaded_events = 0
            
            for event_class in event_subclasses:
                # Check if already exists
                existing = OntologyEntity.query.filter_by(
                    uri=event_class['uri'],
                    ontology_id=ontology.id
                ).first()
                
                if existing:
                    print(f"  ⚠️ {event_class['label']} already exists")
                    continue
                
                # Create new entity
                entity = OntologyEntity(
                    ontology_id=ontology.id,
                    uri=event_class['uri'],
                    label=event_class['label'],
                    entity_type='class',
                    comment=event_class['comment'],
                    parent_uri=event_class['parent_uri']
                )
                
                db.session.add(entity)
                loaded_events += 1
                print(f"  ✅ Added {event_class['label']}")
            
            # Commit changes
            db.session.commit()
            
            print(f"\n✅ Database loading complete!")
            print(f"Loaded {loaded_actions} Action subclasses")
            print(f"Loaded {loaded_events} Event subclasses")
            
            # Verify loading
            print("\nVerifying database contents...")
            
            action_count_query = """
                SELECT COUNT(*) 
                FROM ontology_entities 
                WHERE ontology_id = %s 
                AND entity_type = 'class'
                AND (label ILIKE '%Action%' OR uri ILIKE '%Action%')
            """
            
            event_count_query = """
                SELECT COUNT(*) 
                FROM ontology_entities 
                WHERE ontology_id = %s 
                AND entity_type = 'class'
                AND (label ILIKE '%Event%' OR uri ILIKE '%Event%')
            """
            
            action_count = db.session.execute(action_count_query, [ontology.id]).scalar()
            event_count = db.session.execute(event_count_query, [ontology.id]).scalar()
            
            print(f"Total Action entities in database: {action_count}")
            print(f"Total Event entities in database: {event_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Database loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = load_actions_events_to_database()
    
    if success:
        print("\n🎉 Action/Event entities loaded successfully!")
        print("\nNext steps:")
        print("1. Test MCP integration: python scripts/test_actions_events_mcp.py")
        print("2. Test UI functionality: Start ProEthica and navigate to a case step 3")
    else:
        print("\n❌ Failed to load Action/Event entities!")
    
    sys.exit(0 if success else 1)
