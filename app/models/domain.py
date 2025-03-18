from app import db

class Domain(db.Model):
    """Domain model representing a category of ethical decision-making scenarios."""
    __tablename__ = 'domains'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Domain {self.name}>'
    
    def to_dict(self):
        """Convert domain to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }
