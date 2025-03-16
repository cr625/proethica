from app import db

class Resource(db.Model):
    """Resource model representing available resources in a scenario."""
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(100))  # E.g., medical, personnel, equipment
    quantity = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Resource {self.name} ({self.quantity})>'
    
    def to_dict(self):
        """Convert resource to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'type': self.type,
            'quantity': self.quantity,
            'description': self.description
        }
