"""empty message

Revision ID: d9c222ce7986
Revises: add_roles_table, replace_domain_with_world
Create Date: 2025-03-18 12:52:58.008543

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9c222ce7986'
down_revision = ('add_roles_table', 'replace_domain_with_world')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
