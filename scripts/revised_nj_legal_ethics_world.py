from app import create_app, db
from app.models.world import World

# Create app and push application context
app = create_app()
with app.app_context():
    # Find the Legal Ethics World (New Jersey)
    world = World.query.filter_by(name="Legal Ethics World (New Jersey)").first()
    
    if world:
        # Update the description
        world.description = """This world represents the complex ethical landscape of legal practice in New Jersey, where attorneys navigate professional responsibilities governed by the New Jersey Rules of Professional Conduct (RPC).

The setting encompasses diverse legal environments including courtrooms, law offices, and client meeting spaces across New Jersey's municipal, superior, and appellate courts. Legal professionals of various tiers—from junior associates to managing partners—face ethical dilemmas that test their professional judgment and integrity.

Key roles in this world include:
• Attorneys in various practice settings (solo practitioners, associates, partners, public defenders, prosecutors, corporate counsel)
• Clients (individuals, corporations, government entities)
• Judges and court personnel
• Paralegals and support staff

Ethical conditions that commonly arise include:
• Confidentiality issues (RPC 1.6) - when client disclosures may involve future crimes or fraud
• Conflicts of interest (RPC 1.7) - between current clients or between attorney and client interests
• Client perjury concerns (RPC 3.3) - balancing duties to clients against candor to the tribunal
• Evidence handling dilemmas (RPC 3.4) - proper treatment of documentary and physical evidence
• Fee arrangement questions (RPC 1.5) - ensuring fees remain reasonable and transparent

Legal professionals must utilize their capabilities—legal research, client counseling, ethical judgment, negotiation skills—to navigate these challenges while managing case files, evidence, and court time as limited resources.

Events in this world include hearings, trials, depositions, client meetings, and ethical dilemmas that require decisive action. Professionals may need to file motions, provide advice, withdraw from representation, or report misconduct depending on the circumstances.

The world emphasizes that ethical practice requires balancing competing duties: zealous advocacy for clients, candor to the tribunal, fairness to opposing parties, and maintaining the integrity of the legal profession. Decisions have real consequences including disciplinary review, harm to clients, or potential miscarriages of justice.
"""
        
        # Commit the changes
        db.session.commit()
        
        print("Updated the description for 'Legal Ethics World (New Jersey)'")
        print("-" * 50)
        print(world.description)
    else:
        print("World 'Legal Ethics World (New Jersey)' not found")
