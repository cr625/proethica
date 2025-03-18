"""Add roles table and update characters table

Revision ID: add_roles_table
Revises: add_worlds_table
Create Date: 2025-03-18 12:48:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_roles_table'
down_revision = 'add_worlds_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create roles table
    op.create_table('roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('world_id', sa.Integer(), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=True),
        sa.Column('ontology_uri', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('role_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add role_id column to characters table
    op.add_column('characters', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'characters', 'roles', ['role_id'], ['id'])


def downgrade():
    # Drop foreign key constraint and role_id column from characters table
    op.drop_constraint(None, 'characters', type_='foreignkey')
    op.drop_column('characters', 'role_id')
    
    # Drop roles table
    op.drop_table('roles')
