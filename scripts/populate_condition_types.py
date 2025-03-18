"""
Script to populate condition types for different worlds.
Run this script after creating the condition_types table.
"""

import sys
import os
import json
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import World, ConditionType

app = create_app()

# Military Medical Triage condition types
military_medical_conditions = [
    {
        "name": "Hemorrhage",
        "description": "Severe bleeding that requires immediate intervention.",
        "category": "Injury",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#Hemorrhage"
    },
    {
        "name": "Tension Pneumothorax",
        "description": "Air trapped in the pleural space causing lung collapse and cardiovascular compromise.",
        "category": "Injury",
        "severity_range": {"min": 5, "max": 10},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#TensionPneumothorax"
    },
    {
        "name": "Airway Obstruction",
        "description": "Blockage of the airway that impedes breathing.",
        "category": "Injury",
        "severity_range": {"min": 4, "max": 10},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#AirwayObstruction"
    },
    {
        "name": "Burn",
        "description": "Tissue damage caused by heat, chemicals, electricity, or radiation.",
        "category": "Injury",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#Burn"
    },
    {
        "name": "Fracture",
        "description": "Break in the continuity of a bone.",
        "category": "Injury",
        "severity_range": {"min": 1, "max": 8},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#Fracture"
    },
    {
        "name": "Shock",
        "description": "Life-threatening condition that occurs when the body is not getting enough blood flow.",
        "category": "Physiological",
        "severity_range": {"min": 5, "max": 10},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#Shock"
    },
    {
        "name": "Hypothermia",
        "description": "Abnormally low body temperature that can be life-threatening.",
        "category": "Environmental",
        "severity_range": {"min": 2, "max": 9},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#Hypothermia"
    },
    {
        "name": "Heat Injury",
        "description": "Conditions caused by excessive heat exposure, including heat exhaustion and heat stroke.",
        "category": "Environmental",
        "severity_range": {"min": 2, "max": 9},
        "ontology_uri": "http://example.org/ontology/military_medical_triage#HeatInjury"
    }
]

# Engineering Ethics condition types
engineering_ethics_conditions = [
    {
        "name": "Budget Constraint",
        "description": "Limited financial resources affecting project decisions.",
        "category": "Resource",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/engineering_ethics#BudgetConstraint"
    },
    {
        "name": "Time Pressure",
        "description": "Urgent deadline affecting quality and safety considerations.",
        "category": "Operational",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/engineering_ethics#TimePressure"
    },
    {
        "name": "Safety Risk",
        "description": "Potential for harm to users or the public.",
        "category": "Safety",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/engineering_ethics#SafetyRisk"
    },
    {
        "name": "Environmental Impact",
        "description": "Potential negative effects on the environment.",
        "category": "Environmental",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/engineering_ethics#EnvironmentalImpact"
    }
]

# Law Practice condition types
law_practice_conditions = [
    {
        "name": "Conflict of Interest",
        "description": "Situation where professional judgment may be compromised.",
        "category": "Ethical",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/law_practice#ConflictOfInterest"
    },
    {
        "name": "Client Confidentiality Risk",
        "description": "Potential breach of client confidentiality.",
        "category": "Ethical",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/law_practice#ClientConfidentialityRisk"
    },
    {
        "name": "Legal Deadline",
        "description": "Time-sensitive legal filing or action required.",
        "category": "Procedural",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://example.org/ontology/law_practice#LegalDeadline"
    },
    {
        "name": "Resource Limitation",
        "description": "Limited access to legal resources or research materials.",
        "category": "Resource",
        "severity_range": {"min": 1, "max": 8},
        "ontology_uri": "http://example.org/ontology/law_practice#ResourceLimitation"
    }
]

def populate_condition_types():
    with app.app_context():
        # Get worlds
        military_world = World.query.filter_by(name="Military Medical Triage").first()
        engineering_world = World.query.filter_by(name="Engineering Ethics").first()
        law_world = World.query.filter_by(name="Law Practice").first()
        
        if not military_world or not engineering_world or not law_world:
            print("Error: One or more worlds not found. Please ensure worlds are created first.")
            return
        
        # Add Military Medical Triage condition types
        for condition_data in military_medical_conditions:
            condition_type = ConditionType(
                name=condition_data["name"],
                description=condition_data["description"],
                world_id=military_world.id,
                category=condition_data["category"],
                severity_range=condition_data["severity_range"],
                ontology_uri=condition_data["ontology_uri"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(condition_type)
        
        # Add Engineering Ethics condition types
        for condition_data in engineering_ethics_conditions:
            condition_type = ConditionType(
                name=condition_data["name"],
                description=condition_data["description"],
                world_id=engineering_world.id,
                category=condition_data["category"],
                severity_range=condition_data["severity_range"],
                ontology_uri=condition_data["ontology_uri"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(condition_type)
        
        # Add Law Practice condition types
        for condition_data in law_practice_conditions:
            condition_type = ConditionType(
                name=condition_data["name"],
                description=condition_data["description"],
                world_id=law_world.id,
                category=condition_data["category"],
                severity_range=condition_data["severity_range"],
                ontology_uri=condition_data["ontology_uri"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(condition_type)
        
        db.session.commit()
        print("Condition types populated successfully!")

if __name__ == "__main__":
    populate_condition_types()
