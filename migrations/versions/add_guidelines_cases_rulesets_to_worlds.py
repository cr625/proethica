"""Add guidelines, cases, and rulesets to worlds

Revision ID: add_guidelines_cases_rulesets
Revises: add_worlds_table
Create Date: 2025-03-19 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_guidelines_cases_rulesets'
down_revision = 'add_worlds_table'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to the worlds table
    op.add_column('worlds', sa.Column('guidelines_url', sa.String(255), nullable=True))
    op.add_column('worlds', sa.Column('guidelines_text', sa.Text(), nullable=True))
    op.add_column('worlds', sa.Column('cases', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('worlds', sa.Column('rulesets', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remove the columns
    op.drop_column('worlds', 'guidelines_url')
    op.drop_column('worlds', 'guidelines_text')
    op.drop_column('worlds', 'cases')
    op.drop_column('worlds', 'rulesets')
