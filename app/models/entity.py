from app import db

class Entity(db.Model):
    __tablename__ = 'entities'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Relationship with events (many-to-many)
    events = db.relationship('Event', secondary='event_entity', back_populates='entities')
