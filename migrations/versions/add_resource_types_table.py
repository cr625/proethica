"""Add resource_types table and update resources table

Revision ID: add_resource_types_table
Revises: add_roles_table
Create Date: 2025-03-18 13:37:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_resource_types_table'
down_revision = 'add_roles_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create resource_types table
    op.create_table('resource_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('world_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('ontology_uri', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('resource_type_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add resource_type_id column to resources table
    op.add_column('resources', sa.Column('resource_type_id', sa.Integer(), nullable=True))
    op.add_column('resources', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('resources', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(None, 'resources', 'resource_types', ['resource_type_id'], ['id'])
    
    # Update existing resources to set created_at and updated_at
    op.execute("UPDATE resources SET created_at = NOW(), updated_at = NOW()")


def downgrade():
    # Drop foreign key constraint
    op.drop_constraint(None, 'resources', type_='foreignkey')
    
    # Drop columns from resources table
    op.drop_column('resources', 'updated_at')
    op.drop_column('resources', 'created_at')
    op.drop_column('resources', 'resource_type_id')
    
    # Drop resource_types table
    op.drop_table('resource_types')
