from app import create_app, db
from app.models.world import World

# Create app and push application context
app = create_app()
with app.app_context():
    # Find the Tactical Combat Casualty Care (US Army) world
    world = World.query.filter_by(name="Tactical Combat Casualty Care (US Army)").first()
    
    if world:
        # Update the description
        world.description = """This world represents the high-stakes environment of Tactical Combat Casualty Care (TCCC) in the US Army, where military medical personnel make life-or-death decisions under extreme conditions.

The setting encompasses diverse combat and disaster scenarios including forward-deployed field hospitals, mass casualty incidents (MASCAL), and prolonged casualty care situations where evacuation is delayed or impossible. These environments are characterized by limited resources, time constraints, and significant physical danger.

Key roles in this world include:
• All Service Members (ASM) with Tier 1 baseline TCCC training
• Combat Lifesavers (CLS) with Tier 2 additional first responder training
• Combat Medics/Corpsmen (CMC) with Tier 3 advanced medical training
• Combat Paramedics/Providers (CPP) with Tier 4 specialized medical expertise

Medical personnel face patients with traumatic injuries including:
• Hemorrhage (bleeding) requiring immediate control
• Penetration wounds from small arms fire or explosions
• Blast injuries from IEDs, artillery, or other explosives
• Fractures and burn injuries requiring specialized care

Triage decisions categorize patients into four critical groups:
• Immediate (Red) - requiring life-saving interventions
• Delayed (Yellow) - serious injuries that can wait for treatment
• Minimal (Green) - walking wounded with minor injuries
• Expectant (Black) - unlikely to survive given available resources

Medical personnel must utilize their capabilities—hemorrhage control, airway management, fluid resuscitation, medication administration—while managing limited resources including tourniquets, bandages, medications, and blood products.

Events in this world include combat incidents (explosions, small arms fire, IED detonations), triage events, treatment events, and evacuation operations. Personnel must perform assessment actions (check vital signs, perform triage), treatment actions (apply tourniquets, establish IV access), and evacuation actions (prepare for transport, request MEDEVAC).

The world emphasizes ethical dilemmas inherent in combat medicine: balancing duty to multiple casualties, allocating scarce resources, and making difficult triage decisions that may mean life or death. Medical personnel must apply protocols while adapting to chaotic, unpredictable situations where standard procedures may be impossible to follow.
"""
        
        # Commit the changes
        db.session.commit()
        
        print("Updated the description for 'Tactical Combat Casualty Care (US Army)'")
        print("-" * 50)
        print(world.description)
    else:
        print("World 'Tactical Combat Casualty Care (US Army)' not found")
