"""Case structure and embedding routes."""

import logging
from flask import render_template, redirect, url_for, flash
from app.utils.environment_auth import auth_optional, auth_required_for_write
from app.models import Document
from app import db

logger = logging.getLogger(__name__)

COMPONENT_ORDER = ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']


def _sync_embeddings_to_precedent_features(case_id):
    """Sync section embeddings from document_sections to case_precedent_features."""
    try:
        exists = db.session.execute(
            db.text("SELECT 1 FROM case_precedent_features WHERE case_id = :id"),
            {'id': case_id}
        ).fetchone()

        if not exists:
            logger.info(f"No precedent features row for case {case_id}, skipping sync")
            return

        for section_type, column in [('facts', 'facts_embedding'),
                                      ('discussion', 'discussion_embedding'),
                                      ('conclusion', 'conclusion_embedding')]:
            db.session.execute(
                db.text(f"""
                    UPDATE case_precedent_features cpf
                    SET {column} = ds.embedding
                    FROM document_sections ds
                    WHERE ds.document_id = cpf.case_id
                      AND ds.section_type = :section_type
                      AND ds.embedding IS NOT NULL
                      AND cpf.case_id = :case_id
                """),
                {'section_type': section_type, 'case_id': case_id}
            )

        db.session.commit()
        logger.info(f"Synced embeddings to precedent features for case {case_id}")
    except Exception as e:
        logger.warning(f"Failed to sync embeddings to precedent features: {e}")


def register_structure_embedding_routes(bp):

    @bp.route('/<int:id>/structure', methods=['GET'])
    @auth_optional
    def view_case_structure(id):
        """View document structure and embeddings for a case."""
        from app.models.document_section import DocumentSection

        case = Document.query.get_or_404(id)

        sections = DocumentSection.query.filter_by(document_id=id).order_by(DocumentSection.section_type).all()

        sections_dual = {}
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            sections_dual = case.doc_metadata.get('sections_dual', {})

        section_stats = []
        for section in sections:
            has_embedding = section.embedding is not None
            embed_dim = None
            if has_embedding:
                try:
                    result = db.session.execute(
                        db.text("SELECT vector_dims(embedding) FROM document_sections WHERE id = :id"),
                        {'id': section.id}
                    ).fetchone()
                    embed_dim = result[0] if result else None
                except Exception:
                    embed_dim = 384

            html_len = 0
            text_len = 0
            if section.section_type in sections_dual:
                dual_data = sections_dual[section.section_type]
                html_len = len(dual_data.get('html', '')) if dual_data.get('html') else 0
                text_len = len(dual_data.get('text', '')) if dual_data.get('text') else 0

            section_stats.append({
                'id': section.id,
                'section_type': section.section_type,
                'section_id': section.section_id,
                'content_len': len(section.content) if section.content else 0,
                'html_len': html_len,
                'text_len': text_len,
                'has_embedding': has_embedding,
                'embed_dim': embed_dim,
                'created_at': section.created_at,
                'updated_at': section.updated_at,
                'content': section.content
            })

        total_sections = len(section_stats)
        sections_with_embeddings = sum(1 for s in section_stats if s['has_embedding'])
        embedding_coverage = (sections_with_embeddings / total_sections * 100) if total_sections > 0 else 0

        dimensions = set(s['embed_dim'] for s in section_stats if s['embed_dim'])
        has_dimension_issue = len(dimensions) > 1 or (dimensions and 1536 in dimensions)

        from app.models.temporary_rdf_storage import TemporaryRDFStorage
        from app.services.precedent.case_feature_extractor import (
            EXTRACTION_TYPE_TO_COMPONENT, ENTITY_TYPE_TO_COMPONENT, COMPONENT_WEIGHTS
        )

        COMPONENT_LABELS = {
            'R': 'Roles', 'P': 'Principles', 'O': 'Obligations',
            'S': 'States', 'Rs': 'Resources', 'A': 'Actions',
            'E': 'Events', 'Ca': 'Capabilities', 'Cs': 'Constraints',
        }

        entities = TemporaryRDFStorage.query.filter_by(case_id=id).all()
        component_data = {code: {'label': COMPONENT_LABELS[code], 'weight': COMPONENT_WEIGHTS[code],
                                 'entities': [], 'has_embedding': False}
                          for code in COMPONENT_ORDER}

        for entity in entities:
            comp_code = None
            if entity.extraction_type in EXTRACTION_TYPE_TO_COMPONENT:
                comp_code = EXTRACTION_TYPE_TO_COMPONENT[entity.extraction_type]
            elif entity.extraction_type == 'temporal_dynamics_enhanced' and entity.entity_type:
                comp_code = ENTITY_TYPE_TO_COMPONENT.get(entity.entity_type.lower())
            if comp_code and entity.entity_label:
                component_data[comp_code]['entities'].append({
                    'label': entity.entity_label,
                    'definition': entity.entity_definition,
                    'uri': entity.entity_uri,
                })

        try:
            embed_cols = ', '.join(f'embedding_{code} IS NOT NULL as has_{code}' for code in COMPONENT_ORDER)
            embed_result = db.session.execute(
                db.text(f"SELECT combined_embedding IS NOT NULL as has_combined, {embed_cols} "
                        f"FROM case_precedent_features WHERE case_id = :case_id"),
                {'case_id': id}
            ).fetchone()
            if embed_result:
                has_combined_embedding = embed_result[0]
                for i, code in enumerate(COMPONENT_ORDER):
                    component_data[code]['has_embedding'] = embed_result[i + 1]
            else:
                has_combined_embedding = False
        except Exception:
            has_combined_embedding = False

        total_entities = sum(len(c['entities']) for c in component_data.values())
        components_populated = sum(1 for c in component_data.values() if c['entities'])
        components_with_embeddings = sum(1 for c in component_data.values() if c['has_embedding'])

        return render_template('case_structure.html',
            case=case,
            sections_dual=sections_dual,
            section_stats=section_stats,
            total_sections=total_sections,
            sections_with_embeddings=sections_with_embeddings,
            embedding_coverage=embedding_coverage,
            has_dimension_issue=has_dimension_issue,
            dimensions=list(dimensions),
            component_data=component_data,
            component_order=COMPONENT_ORDER,
            total_entities=total_entities,
            components_populated=components_populated,
            components_with_embeddings=components_with_embeddings,
            has_combined_embedding=has_combined_embedding
        )

    @bp.route('/<int:id>/structure/generate-embeddings', methods=['POST'])
    @auth_required_for_write
    def generate_case_embeddings(id):
        """Generate or regenerate embeddings for a case's sections."""
        from app.services.section_embedding_service import SectionEmbeddingService

        case = Document.query.get_or_404(id)

        try:
            service = SectionEmbeddingService()
            result = service.process_document_sections(id)

            if result.get('success'):
                _sync_embeddings_to_precedent_features(id)
                flash(f'Generated embeddings for {result.get("sections_embedded", 0)} sections', 'success')
            else:
                flash(f'Error generating embeddings: {result.get("error", "Unknown error")}', 'danger')
        except Exception as e:
            logger.error(f"Error generating embeddings for case {id}: {e}")
            flash(f'Error: {str(e)}', 'danger')

        return redirect(url_for('cases.view_case_structure', id=id))
