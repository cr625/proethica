from app.models import db

event_entity = db.Table(
    'event_entity',
    db.Column('event_id', db.Integer, db.ForeignKey('events.id'), primary_key=True),
    db.Column('entity_id', db.Integer, db.ForeignKey('entities.id'), primary_key=True)
)
