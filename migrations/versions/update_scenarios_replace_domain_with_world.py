"""Update scenarios to replace domain with world

Revision ID: replace_domain_with_world
Revises: add_worlds_table
Create Date: 2025-03-18 06:53:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'replace_domain_with_world'
down_revision = 'add_worlds_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create a temporary column to store the world_id mapping
    op.execute("""
    -- First, ensure all scenarios have a world_id
    UPDATE scenarios
    SET world_id = (
        SELECT id FROM worlds 
        ORDER BY id 
        LIMIT 1
    )
    WHERE world_id IS NULL;
    """)
    
    # Make world_id NOT NULL
    op.alter_column('scenarios', 'world_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    
    # Drop the domain_id column
    op.drop_constraint('scenarios_domain_id_fkey', 'scenarios', type_='foreignkey')
    op.drop_column('scenarios', 'domain_id')


def downgrade():
    # Add domain_id column back
    op.add_column('scenarios', sa.Column('domain_id', sa.INTEGER(), autoincrement=False, nullable=True))
    
    # Create a default domain if none exists
    op.execute("""
    INSERT INTO domains (name, description)
    SELECT 'Default Domain', 'Default domain created during migration rollback'
    WHERE NOT EXISTS (SELECT 1 FROM domains LIMIT 1);
    """)
    
    # Set domain_id to the first domain
    op.execute("""
    UPDATE scenarios
    SET domain_id = (SELECT id FROM domains ORDER BY id LIMIT 1);
    """)
    
    # Make domain_id NOT NULL
    op.alter_column('scenarios', 'domain_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    
    # Add foreign key constraint
    op.create_foreign_key('scenarios_domain_id_fkey', 'scenarios', 'domains', ['domain_id'], ['id'])
    
    # Make world_id nullable again
    op.alter_column('scenarios', 'world_id',
               existing_type=sa.INTEGER(),
               nullable=True)
