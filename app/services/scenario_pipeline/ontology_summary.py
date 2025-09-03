"""
STUB: Ontology Summary Module
This is a placeholder module to maintain backward compatibility.
Ontology summary functionality has moved to OntServe.
"""

def build_ontology_summary(events=None, participants=None):
    """
    Build ontology summary from events and participants.
    
    Args:
        events: List of events (optional)
        participants: List of participants (optional)
        
    Returns:
        dict: Ontology summary organized by categories
    """
    # Extract ontology categories from events and participants
    summary = {}
    
    # Initialize all 9 ProEthica categories
    categories = ["Role", "Principle", "Obligation", "State", "Resource", "Action", "Event", "Capability", "Constraint"]
    for category in categories:
        summary[category] = []
    
    # Extract from participants
    if participants:
        for participant in participants:
            if isinstance(participant, str):
                # Simple participant name
                summary["Role"].append(participant)
            elif isinstance(participant, dict):
                # Participant with role information
                role = participant.get('role', participant.get('name', 'Unknown'))
                if role not in summary["Role"]:
                    summary["Role"].append(role)
    
    # Extract from events
    if events:
        for event in events:
            if isinstance(event, dict):
                # Extract actions
                if event.get('kind') == 'action' or 'action' in event.get('text', '').lower():
                    action_text = event.get('text', '')[:50]
                    if action_text not in summary["Action"]:
                        summary["Action"].append(action_text)
                
                # Extract events
                if event.get('kind') == 'event':
                    event_text = event.get('text', '')[:50]
                    if event_text not in summary["Event"]:
                        summary["Event"].append(event_text)
                
                # Extract decisions/obligations
                if event.get('kind') == 'decision':
                    decision_text = event.get('text', '')[:50]
                    if decision_text not in summary["Obligation"]:
                        summary["Obligation"].append(decision_text)
    
    return summary

def get_ontology_entities(world=None, entity_type=None):
    """
    Stub function for getting ontology entities.
    
    Args:
        world: World object (optional)
        entity_type: Type of entity to filter by (optional)
        
    Returns:
        list: Empty list (entities now come from OntServe)
    """
    return []

def format_entity_summary(entity):
    """
    Stub function for formatting entity summaries.
    
    Args:
        entity: Entity object
        
    Returns:
        str: Placeholder message
    """
    return "Entity formatting moved to OntServe"
