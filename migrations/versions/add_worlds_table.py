"""add worlds table and update scenarios table

Revision ID: add_worlds_table
Revises: e99487662b4f
Create Date: 2025-03-17 08:44:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_worlds_table'
down_revision = 'e99487662b4f'
branch_labels = None
depends_on = None


def upgrade():
    # Create worlds table
    op.create_table('worlds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ontology_source', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('world_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add world_id column to scenarios table
    op.add_column('scenarios', sa.Column('world_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_scenarios_world_id_worlds', 'scenarios', 'worlds', ['world_id'], ['id'])


def downgrade():
    # Remove foreign key constraint and world_id column from scenarios table
    op.drop_constraint('fk_scenarios_world_id_worlds', 'scenarios', type_='foreignkey')
    op.drop_column('scenarios', 'world_id')
    
    # Drop worlds table
    op.drop_table('worlds')
