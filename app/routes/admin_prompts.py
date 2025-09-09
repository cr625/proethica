"""
Administrative routes for prompt template management.

Provides web interface for managing the database-based prompt builder system.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate, SectionPromptInstance
from app.utils.prompt_seeder import seed_initial_prompt_templates
import logging

logger = logging.getLogger(__name__)

# Create the admin prompts blueprint
admin_prompts_bp = Blueprint('admin_prompts', __name__, url_prefix='/admin/prompts')


@admin_prompts_bp.route('/')
@login_required
def index():
    """
    Display prompt template management dashboard.
    """
    try:
        # Get template counts by domain
        templates = SectionPromptTemplate.query.all()
        
        stats = {
            'total_templates': len(templates),
            'domains': {},
            'section_types': {}
        }
        
        for template in templates:
            # Count by domain
            if template.domain not in stats['domains']:
                stats['domains'][template.domain] = 0
            stats['domains'][template.domain] += 1
            
            # Count by section type
            if template.section_type not in stats['section_types']:
                stats['section_types'][template.section_type] = 0
            stats['section_types'][template.section_type] += 1
        
        return render_template('admin/prompts/index.html', 
                             templates=templates, 
                             stats=stats)
    
    except Exception as e:
        logger.error(f"Error loading prompt admin: {e}")
        flash(f'Error loading prompt templates: {e}', 'error')
        return render_template('admin/prompts/index.html', 
                             templates=[], 
                             stats={'total_templates': 0, 'domains': {}, 'section_types': {}})


@admin_prompts_bp.route('/seed', methods=['POST'])
@login_required
def seed_templates():
    """
    Manually trigger seeding of initial prompt templates.
    """
    try:
        # Create tables if they don't exist
        db.create_all()
        
        # Run seeding
        success = seed_initial_prompt_templates()
        
        if success:
            flash('Prompt templates seeded successfully!', 'success')
        else:
            flash('Error seeding prompt templates. Check logs for details.', 'error')
    
    except Exception as e:
        logger.error(f"Error seeding templates: {e}")
        flash(f'Error seeding templates: {e}', 'error')
    
    return redirect(url_for('admin_prompts.index'))


@admin_prompts_bp.route('/status')
def status():
    """
    Get prompt template system status as JSON.
    """
    try:
        # Check if tables exist
        from sqlalchemy import text
        
        table_check = db.session.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'section_prompt_templates'
        """)).scalar()
        
        tables_exist = table_check > 0
        
        if tables_exist:
            template_count = SectionPromptTemplate.query.count()
            instance_count = SectionPromptInstance.query.count()
            
            # Get domain breakdown
            domain_stats = db.session.execute(text("""
                SELECT domain, COUNT(*) as count 
                FROM section_prompt_templates 
                WHERE active = true 
                GROUP BY domain
            """)).fetchall()
            
            return jsonify({
                'status': 'ready',
                'tables_exist': True,
                'template_count': template_count,
                'instance_count': instance_count,
                'domains': {row.domain: row.count for row in domain_stats},
                'migration_complete': template_count > 0
            })
        else:
            return jsonify({
                'status': 'needs_setup',
                'tables_exist': False,
                'template_count': 0,
                'instance_count': 0,
                'domains': {},
                'migration_complete': False
            })
    
    except Exception as e:
        logger.error(f"Error checking prompt system status: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'tables_exist': False,
            'migration_complete': False
        }), 500


@admin_prompts_bp.route('/template/<int:template_id>')
@login_required  
def view_template(template_id):
    """
    View details of a specific prompt template.
    """
    try:
        template = SectionPromptTemplate.query.get_or_404(template_id)
        
        # Get usage statistics
        instance_count = SectionPromptInstance.query.filter_by(template_id=template_id).count()
        recent_instances = SectionPromptInstance.query.filter_by(template_id=template_id)\
            .order_by(SectionPromptInstance.created_at.desc())\
            .limit(10).all()
        
        return render_template('admin/prompts/template_detail.html',
                             template=template,
                             instance_count=instance_count, 
                             recent_instances=recent_instances)
    
    except Exception as e:
        logger.error(f"Error viewing template {template_id}: {e}")
        flash(f'Error loading template: {e}', 'error')
        return redirect(url_for('admin_prompts.index'))