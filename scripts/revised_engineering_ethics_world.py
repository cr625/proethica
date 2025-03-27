from app import create_app, db
from app.models.world import World

# Create app and push application context
app = create_app()
with app.app_context():
    # Find the Engineering Ethics (US) world
    world = World.query.filter_by(name="Engineering Ethics (US)").first()
    
    if world:
        # Update the description
        world.description = """This world represents the complex ethical landscape of engineering practice in the United States, where professionals navigate responsibilities governed by various engineering codes of ethics including those from IEEE and NSPE.

The setting encompasses diverse engineering environments including construction sites, design offices, manufacturing facilities, and regulatory inspection contexts across multiple disciplines: civil, mechanical, electrical, software, and chemical engineering. Professionals of various tiers—from junior engineers to chief engineers and directors—face ethical dilemmas that test their technical judgment, professional integrity, and commitment to public safety.

Key roles in this world include:
• Engineers at various career stages (junior engineers, professional engineers, senior engineers, chief engineers)
• Project managers and engineering directors responsible for project delivery and department oversight
• Regulatory personnel (compliance officers, safety inspectors) ensuring adherence to standards
• Clients (individuals, corporations, government entities) commissioning engineering services

Ethical conditions that commonly arise include:
• Safety issues - design defects and public safety risks requiring immediate attention
• Environmental impacts - balancing development with environmental protection
• Conflicts of interest - when personal interests conflict with professional duties
• Resource constraints - budget limitations and time pressures affecting engineering decisions
• Regulatory compliance - ensuring adherence to applicable codes and standards

Engineering professionals must utilize their capabilities—technical design, risk assessment, regulatory compliance, ethical judgment—to navigate these challenges while managing technical documents, testing equipment, and budgetary resources.

Events in this world include design reviews, safety incidents, regulatory inspections, and project milestones that require decisive action. Professionals may need to create or modify designs, conduct safety reviews, report violations, or implement corrective actions depending on the circumstances.

The world emphasizes that ethical engineering practice requires balancing competing priorities: technical excellence, public safety, client interests, and resource efficiency. Decisions have real consequences including potential harm to the public, environmental damage, or professional liability. Engineers must apply professional judgment informed by ethical principles rather than merely following rules.
"""
        
        # Commit the changes
        db.session.commit()
        
        print("Updated the description for 'Engineering Ethics (US)'")
        print("-" * 50)
        print(world.description)
    else:
        print("World 'Engineering Ethics (US)' not found")
