"""Add condition_types table and update conditions table

Revision ID: add_condition_types_table
Revises: add_resource_types_table
Create Date: 2025-03-18 17:23:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_condition_types_table'
down_revision = 'add_resource_types_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create condition_types table
    op.create_table('condition_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('world_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('severity_range', JSON, nullable=True),
        sa.Column('ontology_uri', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('condition_type_metadata', JSON, nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add condition_type_id column to conditions table
    op.add_column('conditions', sa.Column('condition_type_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_conditions_condition_type_id', 'conditions', 'condition_types', ['condition_type_id'], ['id'])


def downgrade():
    # Drop foreign key constraint and condition_type_id column from conditions table
    op.drop_constraint('fk_conditions_condition_type_id', 'conditions', type_='foreignkey')
    op.drop_column('conditions', 'condition_type_id')
    
    # Drop condition_types table
    op.drop_table('condition_types')
