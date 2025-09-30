"""
Admin routes for ProEthica Authentication System.

Provides admin-only interfaces for:
- User management
- Test data reset operations
- System statistics and monitoring
- Audit logging
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import sys
import os
import requests
import psycopg2
import json
from app.utils.auth_utils import admin_required
from app.utils.environment_auth import admin_required_production
from app.services.test_data_reset_service import TestDataResetService
from app.models.user import User
from app.models.world import World
from app.models import Document
from app.models.guideline import Guideline
from app.models.scenario import Scenario
from app.models.ontology import Ontology
from app.models.entity_triple import EntityTriple
from app.models.document_section import DocumentSection
from app.models.deconstructed_case import DeconstructedCase
from app.services.ontology_entity_service import OntologyEntityService
from app.services.guideline_triple_cleanup_service import get_guideline_triple_cleanup_service
from app import db, create_app
import traceback

import psutil

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def get_ontology_sync_status():
    """Check synchronization status between TTL files and database."""
    import hashlib
    
    sync_status = {
        'core_ontologies': [],
        'guideline_ontologies': [],
        'last_sync': None,
        'needs_sync': False
    }
    
    try:
        # Check core ontology files
        core_ontologies = ['bfo', 'proethica-intermediate', 'engineering-ethics']
        for domain in core_ontologies:
            ttl_path = f'ontologies/{domain}.ttl'
            
            if os.path.exists(ttl_path):
                # Get file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(ttl_path))
                
                # Check database version
                db_ontology = Ontology.query.filter_by(domain_id=domain).first()
                
                status_info = {
                    'domain': domain,
                    'file_exists': True,
                    'file_modified': file_mtime.isoformat(),
                    'in_database': db_ontology is not None,
                    'synced': False
                }
                
                if db_ontology:
                    status_info['db_updated'] = db_ontology.updated_at.isoformat() if db_ontology.updated_at else None
                    # Simple check: if file is newer than DB, needs sync
                    if db_ontology.updated_at:
                        status_info['synced'] = file_mtime <= db_ontology.updated_at
                    
                sync_status['core_ontologies'].append(status_info)
                
                if not status_info['synced']:
                    sync_status['needs_sync'] = True
        
        # Check guideline-derived ontologies
        guideline_onts = Ontology.query.filter(
            Ontology.domain_id.like('guideline-%')
        ).limit(5).all()
        
        for ont in guideline_onts:
            sync_status['guideline_ontologies'].append({
                'domain': ont.domain_id,
                'name': ont.name,
                'triple_count': len(ont.content.split('\n')) if ont.content else 0
            })
            
    except Exception as e:
        sync_status['error'] = str(e)
    
    return sync_status

@admin_bp.route('/')
@admin_required_production
def dashboard():
    """Admin dashboard with system overview and management tools."""
    
    # Get comprehensive system statistics
    stats = {
        'users': {
            'total': User.query.count(),
            'admin': User.query.filter_by(is_admin=True).count(),
            'test_users': User.query.filter_by(is_admin=False).count(),
            'active_last_30_days': User.query.filter(
                User.last_login >= datetime.utcnow() - timedelta(days=30)
            ).count() if User.query.filter(User.last_login.isnot(None)).count() > 0 else 0
        },
        'data': {
            'total_worlds': World.query.count(),
            'system_worlds': World.query.filter_by(data_type='system').count(),
            'user_worlds': World.query.filter_by(data_type='user').count(),
            'total_documents': Document.query.count(),
            'system_documents': Document.query.filter_by(data_type='system').count(),
            'user_documents': Document.query.filter_by(data_type='user').count(),
            'total_guidelines': Document.query.filter_by(document_type='guideline').count(),
            'system_guidelines': Document.query.filter_by(document_type='guideline', data_type='system').count(),
            'user_guidelines': Document.query.filter_by(document_type='guideline', data_type='user').count(),
            'total_cases': Document.query.filter(
                Document.doc_metadata.op('->>')('case_number').isnot(None)
            ).count(),
            'total_scenarios': Scenario.query.count()
        },
        'ontology': {
            'total_ontologies': Ontology.query.count(),
            'entity_triples': EntityTriple.query.count(),
            'guideline_derived': Ontology.query.filter(
                Ontology.domain_id.like('guideline-%')
            ).count()
        },
        'processing': {
            'embedded_sections': DocumentSection.query.filter(
                DocumentSection.embedding.isnot(None)
            ).count(),
            'total_sections': DocumentSection.query.count(),
            'processed_docs': Document.query.filter(
                Document.doc_metadata.op('->>')('document_structure').isnot(None)
            ).count(),
            'deconstructed_cases': DeconstructedCase.query.count()
        }
    }
    
    # Calculate workflow completion
    workflow_steps = [
        ('Document Import', stats['data']['total_documents'] > 0),
        ('Structure Annotation', stats['processing']['processed_docs'] > 0),
        ('Section Embedding', stats['processing']['embedded_sections'] > 0),
        ('Concept Extraction', EntityTriple.query.count() > 0),
        ('Association Generation', stats['processing']['processed_docs'] > 5),
        ('Decision Visualization', stats['data']['total_scenarios'] > 0),
        ('Recommendation Engine', False),  # Not yet implemented
        ('Outcome Tracking', False)  # Not yet implemented
    ]
    
    stats['workflow'] = {
        'steps': workflow_steps,
        'completion': sum(1 for _, completed in workflow_steps) / len(workflow_steps) * 100
    }
    
    # Get recent user activity
    recent_users = User.query.order_by(User.last_login.desc().nullslast()).limit(10).all()
    
    # Get users with reset history
    reset_users = User.query.filter(User.data_reset_count > 0).order_by(
        User.last_data_reset.desc()
    ).limit(5).all()
    
    # Get recent documents
    recent_docs = Document.query.order_by(Document.created_at.desc()).limit(5).all()
    
    # Get ontology sync status
    ontology_status = get_ontology_sync_status()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         reset_users=reset_users,
                         recent_docs=recent_docs,
                         ontology_status=ontology_status)

# Cleanup endpoint for guideline triples
@admin_bp.route('/cleanup/guideline-triples', methods=['POST'])
@admin_required_production
def cleanup_guideline_triples():
    """Delete non-core guideline triples and nullify orphan references.

    JSON body parameters (all optional):
    - world_id: int, scope cleanup to a world.
    - exclude_guideline_ids: list[int], guidelines to keep untouched.
    - delete_non_core: bool, default true.
    - nullify_core_if_orphan_guideline: bool, default true.
    - dry_run: bool, default true.
    """
    payload = request.get_json(silent=True) or {}
    service = get_guideline_triple_cleanup_service()

    result = service.cleanup(
        world_id=payload.get('world_id'),
        exclude_guideline_ids=payload.get('exclude_guideline_ids'),
        delete_non_core=payload.get('delete_non_core', True),
        nullify_core_if_orphan_guideline=payload.get('nullify_core_if_orphan_guideline', True),
        dry_run=payload.get('dry_run', True),
    )

    status = 200 if 'error' not in result else 500
    return jsonify(result), status

@admin_bp.route('/users')
@admin_required_production
def users():
    """User management interface."""
    
    # Get all users with their data counts
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Enhance user data with content counts
    user_data = []
    for user in users:
        user_info = user.to_dict()
        
        # Count user-created content
        user_info['content_counts'] = {
            'worlds': World.query.filter_by(created_by=user.id, data_type='user').count(),
            'documents': Document.query.filter_by(created_by=user.id, data_type='user').count(),
            'guidelines': Guideline.query.filter_by(created_by=user.id, data_type='user').count()
        }
        
        # Calculate total user content
        user_info['total_content'] = sum(user_info['content_counts'].values())
        
        user_data.append(user_info)
    
    return render_template('admin/users.html', users=user_data)

@admin_bp.route('/user/<int:user_id>/summary')
@admin_required_production
def user_data_summary(user_id):
    """Get detailed data summary for a specific user."""
    
    reset_service = TestDataResetService()
    summary = reset_service.get_user_data_summary(user_id)
    
    if 'error' in summary:
        return jsonify({'error': summary['error']}), 404
    
    return jsonify(summary)

@admin_bp.route('/user/<int:user_id>/reset', methods=['POST'])
@admin_required_production
def reset_user_data(user_id):
    """Reset data for a specific user."""
    
    data = request.get_json()
    confirm = data.get('confirm', False)
    dry_run = data.get('dry_run', False)
    
    if not confirm and not dry_run:
        return jsonify({'error': 'Reset must be confirmed or run in dry-run mode'}), 400
    
    reset_service = TestDataResetService()
    result = reset_service.reset_user_data(user_id, confirm=confirm, dry_run=dry_run)
    
    if result.get('success'):
        if not dry_run:
            flash(f"Successfully reset data for user {result['username']}", 'success')
        return jsonify(result)
    else:
        return jsonify(result), 500

@admin_bp.route('/users/bulk-reset', methods=['POST'])
@admin_required_production
def bulk_reset_users():
    """Reset data for all test users."""
    
    data = request.get_json()
    confirm = data.get('confirm', False)
    dry_run = data.get('dry_run', False)
    
    if not confirm and not dry_run:
        return jsonify({'error': 'Bulk reset must be confirmed or run in dry-run mode'}), 400
    
    reset_service = TestDataResetService()
    result = reset_service.bulk_reset_all_test_users(confirm=confirm, dry_run=dry_run)
    
    if result.get('success'):
        if not dry_run:
            flash(f"Successfully reset data for {result['overall_stats']['users_processed']} users", 'success')
        return jsonify(result)
    else:
        return jsonify(result), 500

    # --- Guideline management ----------------------------------------------------

    @admin_bp.route('/guidelines/<int:guideline_id>/delete', methods=['POST'])
    @admin_required_production
    def delete_guideline_by_id(guideline_id: int):
        """Hard delete a guideline and cascade-related records.

        Behavior:
        - Deletes the guideline row (guidelines.id = guideline_id)
        - Because of FK ondelete='CASCADE', related EntityTriple, GuidelineSection,
          GuidelineSemanticTriple, GuidelineTermCandidate, PendingConceptType, etc.
          should be removed by the DB.
        - Additionally, deletes Document rows whose doc_metadata.guideline_id equals the target
          (these are wrappers/entries for the same guideline in the documents table).

        Optional JSON body:
        { "delete_documents": true }  # default true
        { "dry_run": true }           # default false
        """
        try:
            payload = request.get_json(silent=True) or {}
            delete_documents = bool(payload.get('delete_documents', True))
            dry_run = bool(payload.get('dry_run', False))

            g = Guideline.query.get(guideline_id)
            if not g:
                return jsonify({
                    'success': False,
                    'message': f'Guideline {guideline_id} not found'
                }), 404

            # Collect impacts
            impacts = {
                'guideline': {'id': g.id, 'title': g.title},
                'entity_triples': EntityTriple.query.filter_by(guideline_id=guideline_id).count(),
                'documents_to_delete': 0,
            }

            docs_to_delete = []
            if delete_documents:
                try:
                    # Find documents whose doc_metadata.guideline_id matches
                    q = Document.query.filter(Document.doc_metadata.isnot(None)).all()
                    for doc in q:
                        meta = doc.doc_metadata or {}
                        if str(meta.get('guideline_id')) == str(guideline_id):
                            docs_to_delete.append(doc)
                except Exception:
                    # Fallback: no-op if JSONB operator unsupported on some setups
                    pass
                impacts['documents_to_delete'] = len(docs_to_delete)

            if dry_run:
                return jsonify({'success': True, 'dry_run': True, 'impacts': impacts})

            # Perform deletions
            if delete_documents and docs_to_delete:
                for doc in docs_to_delete:
                    db.session.delete(doc)

            db.session.delete(g)

            # Safety net: ensure dangling triples are cleaned if FK cascade is missing
            try:
                from sqlalchemy import text as _text
                db.session.execute(
                    _text("DELETE FROM entity_triples WHERE guideline_id = :gid"),
                    { 'gid': guideline_id }
                )
            except Exception:
                # Ignore if FK cascade already handled this
                pass

            db.session.commit()

            return jsonify({
                'success': True,
                'deleted_guideline_id': guideline_id,
                'deleted_documents': impacts['documents_to_delete'],
                'deleted_triples_estimate': impacts['entity_triples']
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Failed to delete guideline')
            return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/data-overview')
@admin_required_production
def data_overview():
    """Detailed data breakdown and management interface."""
    
    # Get counts for each data type
    worlds_total = World.query.count()
    worlds_system = World.query.filter_by(data_type='system').count()
    worlds_user = World.query.filter_by(data_type='user').count()
    
    documents_total = Document.query.count()
    documents_system = Document.query.filter_by(data_type='system').count()
    documents_user = Document.query.filter_by(data_type='user').count()
    
    guidelines_total = Guideline.query.count()
    guidelines_system = Guideline.query.filter_by(data_type='system').count()
    guidelines_user = Guideline.query.filter_by(data_type='user').count()
    
    scenarios_total = Scenario.query.count()
    scenarios_system = Scenario.query.filter_by(data_type='system').count() if hasattr(Scenario, 'data_type') else 0
    scenarios_user = Scenario.query.filter_by(data_type='user').count() if hasattr(Scenario, 'data_type') else scenarios_total
    
    # Structure data to match template expectations
    data_stats = {
        'system': {
            'total': worlds_system + documents_system + guidelines_system + scenarios_system,
            'worlds': worlds_system,
            'documents': documents_system,
            'guidelines': guidelines_system,
            'scenarios': scenarios_system
        },
        'user': {
            'total': worlds_user + documents_user + guidelines_user + scenarios_user,
            'worlds': worlds_user,
            'documents': documents_user,
            'guidelines': guidelines_user,
            'scenarios': scenarios_user
        },
        # Keep additional detailed data for potential future use
        'detailed': {
            'worlds': {
                'total': worlds_total,
                'system': worlds_system,
                'user': worlds_user,
                'by_creator': db.session.query(
                    User.username,
                    db.func.count(World.id).label('count')
                ).join(World, User.id == World.created_by).group_by(User.username).all()
            },
            'documents': {
                'total': documents_total,
                'system': documents_system,
                'user': documents_user,
                'by_type': db.session.query(
                    Document.document_type,
                    db.func.count(Document.id).label('count')
                ).group_by(Document.document_type).all(),
                'cases': Document.query.filter(Document.document_type.ilike('%case%')).count()
            },
            'guidelines': {
                'total': guidelines_total,
                'system': guidelines_system,
                'user': guidelines_user,
                'by_world': db.session.query(
                    World.name,
                    db.func.count(Guideline.id).label('count')
                ).join(Guideline, World.id == Guideline.world_id).group_by(World.name).all()
            }
        }
    }
    
    return render_template('admin/data_overview.html', data_stats=data_stats)

@admin_bp.route('/audit-log')
@admin_required_production
def audit_log():
    """View audit log of admin actions."""
    
    # For now, this is a placeholder
    # In a full implementation, you'd have an audit log table
    # that tracks all admin actions with timestamps and details
    
    audit_entries = [
        {
            'timestamp': datetime.utcnow() - timedelta(hours=2),
            'admin_user': current_user.username,
            'action': 'User Data Reset',
            'target': 'test@proethica.org',
            'details': 'Reset user data: 3 worlds, 5 documents, 2 guidelines deleted'
        },
        {
            'timestamp': datetime.utcnow() - timedelta(days=1),
            'admin_user': current_user.username,
            'action': 'Bulk User Reset',
            'target': 'All test users',
            'details': 'Bulk reset completed: 2 users processed'
        }
    ]
    
    return render_template('admin/audit_log.html', audit_entries=audit_entries)

@admin_bp.route('/system-health')
@admin_required_production
def system_health():
    """System diagnostics page showing real-time technical status and debugging information."""
    
    # Get actual system uptime
    try:
        # Get Flask process info
        current_process = psutil.Process(os.getpid())
        process_create_time = datetime.fromtimestamp(current_process.create_time())
        uptime_delta = datetime.now() - process_create_time
        uptime_hours = round(uptime_delta.total_seconds() / 3600, 2)
    except:
        uptime_hours = 0
    
    # Initialize diagnostic data
    diagnostics = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": sys.version.split()[0],
        "app_name": current_app.name,
        "debug_mode": current_app.debug,
        "uptime_hours": uptime_hours,
        "system_status": {
            "mcp_server": {"status": "unknown", "detail": {}, "error": None},
            "database": {"status": "unknown", "detail": {}, "error": None},
            "memory": {"status": "unknown", "detail": {}, "error": None},
            "disk": {"status": "unknown", "detail": {}, "error": None}
        }
    }
    
    # Check MCP server status
    try:
        mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:5001")
        response = requests.post(
            f"{mcp_url}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result and isinstance(result["result"], dict) and "tools" in result["result"]:
                tools = result["result"]["tools"]
                guideline_tools = [t for t in tools if "guideline" in t["name"].lower()]
                
                diagnostics["system_status"]["mcp_server"] = {
                    "status": "online",
                    "detail": {
                        "url": mcp_url,
                        "tool_count": len(tools),
                        "available_tools": [t["name"] for t in tools],
                        "guideline_tools_available": len(guideline_tools) > 0,
                        "guideline_tools": [t["name"] for t in guideline_tools]
                    },
                    "error": None
                }
                
                # Set ontology status based on available tools
                if any("entity" in t["name"].lower() for t in tools) or any(t["name"] == "get_world_entities" for t in tools):
                    try:
                        from app.models.ontology import Ontology
                        ontologies = Ontology.query.all()
                        
                        diagnostics["system_status"]["ontology"] = {
                            "status": "available",
                            "detail": {
                                "entity_tools_available": True,
                                "entity_tools": [t["name"] for t in tools if "entity" in t["name"].lower() or t["name"] == "get_world_entities"],
                                "ontology_count": len(ontologies),
                                "ontologies": [
                                    {
                                        "id": o.id,
                                        "name": o.name,
                                        "triple_count": len(o.content.split('\n')) if o.content else 0
                                    } 
                                    for o in ontologies[:5]
                                ] if ontologies else []
                            },
                            "error": None
                        }
                    except Exception as e:
                        diagnostics["system_status"]["ontology"] = {
                            "status": "available",
                            "detail": {
                                "entity_tools_available": True,
                                "entity_tools": [t["name"] for t in tools if "entity" in t["name"].lower() or t["name"] == "get_world_entities"],
                                "db_error": str(e)
                            },
                            "error": None
                        }
                
                # Set guidelines status
                if guideline_tools:
                    diagnostics["system_status"]["guidelines"] = {
                        "status": "available",
                        "detail": {
                            "guideline_tools_available": True,
                            "guideline_tools": [t["name"] for t in guideline_tools]
                        },
                        "error": None
                    }
            else:
                diagnostics["system_status"]["mcp_server"] = {
                    "status": "error",
                    "detail": {"response": result},
                    "error": "Invalid response format from MCP server"
                }
        else:
            diagnostics["system_status"]["mcp_server"] = {
                "status": "error",
                "detail": {"status_code": response.status_code},
                "error": f"MCP server returned HTTP {response.status_code}"
            }
    except Exception as e:
        diagnostics["system_status"]["mcp_server"] = {
            "status": "offline",
            "detail": {},
            "error": str(e)
        }
    
    # Check database connection and performance
    try:
        # Test query performance
        import time
        start_time = time.time()
        
        # Try multiple ways to get the database URL
        db_url = None
        
        # First try Flask config
        if hasattr(current_app, 'config') and current_app.config:
            db_url = current_app.config.get("DATABASE_URL") or current_app.config.get("SQLALCHEMY_DATABASE_URI")
        
        # Then try environment variables
        if not db_url:
            db_url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
        
        if db_url:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # Get database info
            cur.execute("SELECT version();")
            db_version = cur.fetchone()[0].split('(')[0].strip()
            
            # Get database size
            cur.execute("""
                SELECT pg_database_size(current_database()) / 1024 / 1024 AS size_mb;
            """)
            db_size_mb = round(cur.fetchone()[0], 2)
            
            # Get connection count
            cur.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE datname = current_database();
            """)
            connection_count = cur.fetchone()[0]
            
            # Get table count and check for critical tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public'
                ORDER BY table_name;
            """)
            all_rows = cur.fetchall()
            tables = [row[0] for row in all_rows]
            
            
            # Check for critical tables
            critical_tables = ['users', 'documents', 'worlds', 'guidelines', 'ontologies']
            missing_tables = [t for t in critical_tables if t not in tables]
            
            conn.close()
            
            query_time = round((time.time() - start_time) * 1000, 2)  # Convert to ms
            
            
            diagnostics["system_status"]["database"] = {
                "status": "connected",
                "detail": {
                    "version": db_version,
                    "size_mb": db_size_mb,
                    "table_count": len(tables),
                    "tables": tables,  # Include all table names
                    "connection_count": connection_count,
                    "query_time_ms": query_time,
                    "missing_tables": missing_tables,
                    "has_critical_tables": len(missing_tables) == 0,
                    "db_url_found": db_url is not None,
                    "db_url_source": "Flask config" if hasattr(current_app, 'config') and current_app.config and current_app.config.get("DATABASE_URL") else "Environment"
                },
                "error": None
            }
            
        else:
            diagnostics["system_status"]["database"] = {
                "status": "error",
                "detail": {},
                "error": "DATABASE_URL not configured"
            }
    except Exception as e:
        diagnostics["system_status"]["database"] = {
            "status": "error",
            "detail": {},
            "error": str(e)
        }
    
    # Get memory usage
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        process_mb = round(current_process.memory_info().rss / (1024**2), 2)
        
        diagnostics["system_status"]["memory"] = {
            "status": "ok" if memory.percent < 80 else "warning",
            "detail": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent,
                "process_mb": process_mb
            },
            "error": None
        }
        
        diagnostics["system_status"]["disk"] = {
            "status": "ok" if disk.percent < 80 else "warning",
            "detail": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_percent": disk.percent
            },
            "error": None
        }
    except Exception as e:
        diagnostics["system_status"]["memory"] = {
            "status": "error",
            "detail": {},
            "error": str(e)
        }
        diagnostics["system_status"]["disk"] = {
            "status": "error", 
            "detail": {},
            "error": str(e)
        }
    
    # Get actual data statistics
    total_users = User.query.count()
    total_data_items = World.query.count() + Document.query.count() + Scenario.query.count()
    
    # Check for data integrity issues
    alerts = []
    try:
        unclassified_worlds = World.query.filter(World.data_type.is_(None)).count()
        unclassified_docs = Document.query.filter(Document.data_type.is_(None)).count()
        unclassified_guidelines = Guideline.query.filter(Guideline.data_type.is_(None)).count()
        
        if unclassified_worlds > 0 or unclassified_docs > 0 or unclassified_guidelines > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'exclamation-triangle',
                'title': 'Data Classification Issue',
                'message': f'Found unclassified data: {unclassified_worlds} worlds, {unclassified_docs} documents, {unclassified_guidelines} guidelines'
            })
        
        orphaned_worlds = World.query.filter(World.created_by.is_(None)).count()
        if orphaned_worlds > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'unlink',
                'title': 'Orphaned Data',
                'message': f'Found {orphaned_worlds} worlds without creators'
            })
        
    except Exception as e:
        alerts.append({
            'type': 'danger',
            'icon': 'exclamation-circle',
            'title': 'System Error',
            'message': f'Error checking data integrity: {str(e)}'
        })
    
    # Get recent user activity
    recent_user_activity = []
    recent_users = User.query.order_by(User.last_login.desc().nullslast()).limit(5).all()
    for user in recent_users:
        if user.last_login:
            recent_user_activity.append({
                'username': user.username,
                'action': 'Login',
                'timestamp': user.last_login.strftime('%m/%d %I:%M %p'),
                'type': 'login'
            })
    
    # Prepare health statistics for template with real data
    health_stats = {
        'total_users': total_users,
        'active_sessions': User.query.filter(
            User.last_login >= datetime.now() - timedelta(hours=1)
        ).count(),
        'total_data_items': total_data_items,
        'system_uptime': uptime_hours,
        'alerts': alerts,
        'db_tables': len(diagnostics["system_status"]["database"]["detail"].get("tables", [])) if diagnostics["system_status"]["database"]["status"] == "connected" else 0,
        'db_connections': diagnostics["system_status"]["database"]["detail"].get("connection_count", 0) if diagnostics["system_status"]["database"]["status"] == "connected" else 0,
        'db_response_time': diagnostics["system_status"]["database"]["detail"].get("query_time_ms", 0) if diagnostics["system_status"]["database"]["status"] == "connected" else 0,
        'db_size': diagnostics["system_status"]["database"]["detail"].get("size_mb", 0) if diagnostics["system_status"]["database"]["status"] == "connected" else 0,
        'recent_admin_actions': [
            {
                'action': 'System Health Check',
                'timestamp': datetime.now().strftime('%I:%M %p'),
                'status': 'Complete',
                'status_color': 'info'
            }
        ],
        'recent_user_activity': recent_user_activity,
        'environment': diagnostics["environment"],
        'debug_mode': diagnostics["debug_mode"],
        'session_timeout': current_app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(minutes=30)).total_seconds() / 60,
        'secure_cookies': current_app.config.get('SESSION_COOKIE_SECURE', False),
        # Add real diagnostic data
        'technical_status': diagnostics,
        'memory_usage': diagnostics["system_status"]["memory"]["detail"] if diagnostics["system_status"]["memory"]["status"] != "error" else {},
        'disk_usage': diagnostics["system_status"]["disk"]["detail"] if diagnostics["system_status"]["disk"]["status"] != "error" else {}
    }
    
    # Return either JSON or HTML based on Accept header or query parameter
    if "application/json" in request.headers.get("Accept", "") or request.args.get('format') == 'json':
        return jsonify(diagnostics)
    else:
        return render_template('admin/system_health.html', health_stats=health_stats)

# Error handlers for admin routes
@admin_bp.errorhandler(403)
def admin_forbidden(error):
    """Handle 403 errors in admin routes."""
    flash('Admin access required for this operation.', 'error')
    return redirect(url_for('index.home'))

@admin_bp.errorhandler(404)
def admin_not_found(error):
    """Handle 404 errors in admin routes."""
    flash('Admin resource not found.', 'error')
    return redirect(url_for('admin.dashboard'))
