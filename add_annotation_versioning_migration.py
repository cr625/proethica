"""
Database migration script to add versioning fields to document concept annotations.

This script updates the document_concept_annotations table to support:
- Annotation versioning with version numbers
- Annotation groups to link related versions
- Approval stages (llm_extracted, llm_approved, user_approved)
- User edit tracking
"""

import sqlalchemy as sa
from alembic import op
import uuid

revision = 'add_annotation_versioning'
down_revision = None  # Set this to your previous migration's revision ID
branch_labels = None
depends_on = None

def upgrade():
    """Add versioning fields to document_concept_annotations table."""

    # Add new columns for versioning
    op.add_column('document_concept_annotations',
                  sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'))

    op.add_column('document_concept_annotations',
                  sa.Column('annotation_group_id', sa.String(36), nullable=False))

    op.add_column('document_concept_annotations',
                  sa.Column('approval_stage', sa.String(20), nullable=False,
                           server_default='llm_extracted'))

    op.add_column('document_concept_annotations',
                  sa.Column('parent_annotation_id', sa.Integer(),
                           sa.ForeignKey('document_concept_annotations.id'), nullable=True))

    op.add_column('document_concept_annotations',
                  sa.Column('user_edits', sa.JSON(), nullable=True))

    # Create indexes for efficient querying
    op.create_index('idx_annotation_versions', 'document_concept_annotations',
                   ['annotation_group_id', 'version_number'])

    op.create_index('idx_annotation_stages', 'document_concept_annotations',
                   ['approval_stage', 'is_current'])

    # For existing annotations, assign them to individual groups and set initial values
    conn = op.get_bind()

    # Get all existing annotation IDs
    existing_annotations = conn.execute(
        sa.text("SELECT id FROM document_concept_annotations")
    ).fetchall()

    # Create a unique group ID for each existing annotation
    for annotation in existing_annotations:
        group_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                UPDATE document_concept_annotations
                SET annotation_group_id = :group_id,
                    version_number = 1,
                    approval_stage = 'llm_extracted'
                WHERE id = :annotation_id
            """),
            {'group_id': group_id, 'annotation_id': annotation[0]}
        )

def downgrade():
    """Remove versioning fields from document_concept_annotations table."""

    # Drop indexes
    op.drop_index('idx_annotation_stages', table_name='document_concept_annotations')
    op.drop_index('idx_annotation_versions', table_name='document_concept_annotations')

    # Drop columns (reverse order)
    op.drop_column('document_concept_annotations', 'user_edits')
    op.drop_column('document_concept_annotations', 'parent_annotation_id')
    op.drop_column('document_concept_annotations', 'approval_stage')
    op.drop_column('document_concept_annotations', 'annotation_group_id')
    op.drop_column('document_concept_annotations', 'version_number')
