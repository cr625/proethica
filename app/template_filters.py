"""
Custom template filters for the application.
"""

import logging
import os
import re
import markdown
from datetime import datetime
from flask import current_app
from markupsafe import Markup
from app.services.concept_hierarchy_service import ConceptHierarchyService

def init_app(app):
    """Initialize template filters for the application."""

    @app.template_filter('group_properties')
    def group_properties_filter(rdf_json_ld):
        """Partition an entity's emitted fields into relations / content / assessment /
        derived / provenance (field_classification.group_properties), for the triple-vs-
        literal breakdown shown on the review pages."""
        from app.services.extraction.field_classification import group_properties
        return group_properties(rdf_json_ld or {})

    @app.template_filter('nspe_ontology_url')
    def nspe_ontology_url_filter(code):
        """OntServe entity-page URL for an NSPE provision code, or '' when
        the code does not map (historical Canon/Rule vocabulary). The
        fragment rule is drift-tested against the NSPE TTL
        (tests/unit/test_provision_references.py)."""
        from app.utils.provision_codes import nspe_provision_fragment
        frag = nspe_provision_fragment(code)
        if not frag:
            return ''
        base = current_app.config.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
        return f"{base}/entity/NSPE Code of Ethics/{frag}"

    @app.template_filter('upgrade_references')
    def upgrade_references_filter(html, provision_references):
        """Replace the baked 'NSPE Code of Ethics References' card body in
        extraction-style case HTML with the structured render from the parsed
        board-stated provision set (code linked to the NSPE Code ontology on
        OntServe, verbatim text, subject-reference chips). The baked HTML is
        ingestion-time derived data; this upgrades the display without
        rewriting document content. Returns the HTML unchanged when there is
        nothing to upgrade."""
        if not html or not provision_references:
            return Markup(html or '')
        try:
            from bs4 import BeautifulSoup
            from markupsafe import escape
            from app.utils.provision_codes import nspe_provision_fragment
            soup = BeautifulSoup(str(html), 'html.parser')
            header = next((h for h in soup.select('.card-header')
                           if 'NSPE Code of Ethics References' in h.get_text()), None)
            if header is None:
                return Markup(html)
            card = header.find_parent(class_='card')
            body = card.select_one('.card-body') if card else None
            if body is None:
                return Markup(html)
            base = current_app.config.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
            parts = []
            for ref in provision_references:
                frag = nspe_provision_fragment(ref.get('code', ''))
                code_html = (
                    f'<a href="{base}/entity/NSPE Code of Ethics/{frag}" target="_blank" '
                    f'class="fw-bold text-decoration-none" '
                    f'title="View this provision in the NSPE Code of Ethics ontology">'
                    f'{escape(ref.get("code_raw", ref.get("code", "")))} '
                    f'<i class="bi bi-box-arrow-up-right" style="font-size: 0.7rem;"></i></a>'
                    if frag else f'<span class="fw-bold">{escape(ref.get("code_raw", ""))}</span>')
                subjects = ''.join(
                    f'<span class="badge bg-light text-dark border me-1" '
                    f'style="font-size: 0.7rem;">{escape(s)}</span>'
                    for s in ref.get('subjects', []))
                subj_row = (f'<div class="mt-1"><small class="text-muted me-1">'
                            f'Subject Reference:</small>{subjects}</div>' if subjects else '')
                parts.append(f'<div class="mb-3"><div>{code_html} '
                             f'<span class="ms-1">{escape(ref.get("text", ""))}</span></div>'
                             f'{subj_row}</div>')
            body.clear()
            body.append(BeautifulSoup(''.join(parts), 'html.parser'))
            return Markup(str(soup))
        except Exception:
            logging.getLogger(__name__).exception('upgrade_references failed')
            return Markup(html)

    @app.template_filter('basename')
    def basename_filter(path):
        """Return the basename of a file path."""
        return os.path.basename(path) if path else ''
    
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """Convert newlines to HTML line breaks."""
        if not text:
            return ''
        text = str(text)
        return Markup(text.replace('\n', '<br>\n'))
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown text to HTML."""
        if not text:
            return ''
        text = str(text)
        # Convert markdown to HTML using the Python-Markdown library
        md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code'])
        return Markup(md.convert(text))
    
    @app.template_filter('slice')
    def slice_filter(iterable, start, end=None):
        """Slice an iterable and return a list."""
        if not iterable:
            return []
        if end is None:
            return list(iterable)[start:]
        return list(iterable)[start:end]
    
    @app.template_filter('parse_entries')
    def parse_entries_filter(value):
        """Parse stored role-individual ``relationships`` / ``attributes`` into Python
        objects for readable rendering in the review UI.

        They are stored as stringified Python dicts (single-quoted, e.g.
        "{'type': 'has_provider', 'target': 'Engineer A'}"), sometimes wrapped in a
        one-element list, so they are NOT valid JSON; ast.literal_eval is used rather
        than json.loads. Always returns a list of parsed objects, dropping anything
        unparseable (the commit serializer logs the same drops on its side)."""
        import ast
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        out = []
        for it in items:
            if isinstance(it, (dict, list)):
                out.append(it)
            elif isinstance(it, str):
                try:
                    out.append(ast.literal_eval(it))
                except (ValueError, SyntaxError):
                    continue
        return out

    @app.template_filter('camel_to_readable')
    def camel_to_readable_filter(text):
        """Convert camelCase or PascalCase to readable format with spaces.

        Examples:
            hasProfessionalScope -> Professional Scope
            hasDistinguishingFeature -> Distinguishing Feature
            initiatedBy -> Initiated By
        """
        if not text:
            return ''

        # Remove 'has' prefix if present
        if text.startswith('has'):
            text = text[3:]

        # Add space before capital letters (but not at the start)
        result = ''
        for i, char in enumerate(text):
            if i > 0 and char.isupper() and text[i-1].islower():
                result += ' '
            result += char

        # Capitalize properly
        return result.title()

    @app.template_filter('hash')
    def hash_filter(value):
        """Generate a hash value for the input."""
        if not value:
            return 0
        return hash(str(value))
    
    @app.template_filter('hash_participant_id')
    def hash_participant_id_filter(value):
        """Generate a participant ID based on hash of the input."""
        if not value:
            return "P0000"
        hash_value = abs(hash(str(value))) % 10000
        return f"P{hash_value:04d}"
    
    @app.template_filter('map_to_intermediate_type')
    def map_to_intermediate_type_filter(category):
        """Map concept categories to the 8 basic intermediate ontology types."""
        if not category:
            return "Concept"
        
        category_lower = str(category).lower()
        
        # Mapping dictionary
        mappings = {
            'principle': ['principle', 'value', 'ethical principle', 'standard', 'norm'],
            'obligation': ['obligation', 'duty', 'responsibility', 'requirement', 'must'],
            'role': ['stakeholder', 'role', 'position', 'actor', 'agent', 'party'],
            'action': ['action', 'activity', 'process', 'procedure', 'operation', 'practice'],
            'state': ['state', 'condition', 'situation', 'status', 'circumstance'],
            'capability': ['capability', 'competence', 'skill', 'ability', 'capacity'],
            'event': ['event', 'occurrence', 'incident', 'happening', 'case'],
            'resource': ['resource', 'constraint', 'limitation', 'asset', 'tool']
        }
        
        # Check each mapping
        for intermediate_type, keywords in mappings.items():
            if category_lower in keywords:
                return intermediate_type.capitalize()
        
        # If no mapping found, return the original category capitalized
        return category.capitalize()
    
    @app.template_filter('concept_hierarchy')
    def concept_hierarchy_filter(concept, format_type='breadcrumb'):
        """
        Display concept hierarchy showing ontological path.
        
        Args:
            concept: Dictionary with concept information
            format_type: 'breadcrumb', 'compact', 'tree'
            
        Returns:
            HTML string showing hierarchical path
        """
        try:
            hierarchy_service = ConceptHierarchyService()
            hierarchy = hierarchy_service.get_concept_hierarchy(concept)
            return Markup(hierarchy_service.format_hierarchy_for_display(hierarchy, format_type))
        except Exception as e:
            # Fallback to simple display
            concept_label = concept.get('label', 'Unknown Concept')
            semantic_label = concept.get('semantic_label') or concept.get('category') or concept.get('type')
            if semantic_label:
                return Markup(f'<small class="text-muted">{semantic_label.capitalize()}</small> → <strong>{concept_label}</strong>')
            return Markup(f'<strong>{concept_label}</strong>')
    
    @app.template_filter('primary_type_badge')
    def primary_type_badge_filter(concept):
        """
        Display primary type as a colored badge.
        
        Returns badge with appropriate color for the 8 intermediate types.
        """
        primary_type = (concept.get('primary_type') or concept.get('type', '')).lower()
        
        # Color mapping for the 8 intermediate types
        type_colors = {
            'role': 'bg-primary',
            'principle': 'bg-success', 
            'obligation': 'bg-warning',
            'state': 'bg-info',
            'resource': 'bg-secondary',
            'action': 'bg-danger',
            'event': 'bg-dark',
            'capability': 'bg-light text-dark'
        }
        
        color_class = type_colors.get(primary_type, 'bg-secondary')
        display_type = primary_type.capitalize() if primary_type else 'Concept'

        return Markup(f'<span class="badge {color_class}">{display_type}</span>')

    @app.template_filter('localtime')
    def localtime_filter(dt, format='full'):
        """
        Convert a UTC datetime to a span that JavaScript will convert to local time.

        Usage in templates:
            {{ some_datetime | localtime }}           -> Full datetime
            {{ some_datetime | localtime('short') }} -> Short format (date only)
            {{ some_datetime | localtime('time') }}  -> Time only

        The span contains data-utc attribute with ISO timestamp.
        JavaScript in base.html converts these to local timezone on page load.

        Args:
            dt: datetime object (assumed to be UTC)
            format: 'full' (default), 'short' (date only), 'time' (time only)

        Returns:
            HTML span element with data-utc attribute
        """
        if not dt:
            return ''

        # Handle both datetime objects and strings
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                return dt  # Return as-is if we can't parse

        # Format as ISO with Z suffix to indicate UTC
        iso_timestamp = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Fallback display (shown briefly before JS runs, or if JS disabled)
        fallback = dt.strftime('%Y-%m-%d %H:%M') + ' UTC'

        return Markup(
            f'<span class="local-time" data-utc="{iso_timestamp}" data-format="{format}">{fallback}</span>'
        )

    @app.template_filter('ontserve_entity_path')
    def ontserve_entity_path_filter(uri, ontology_target=None):
        """Compute OntServe entity URL path from an entity URI.

        Usage in templates:
            {{ entity.entity_uri | ontserve_entity_path(entity.ontology_target) }}
            -> '/entity/proethica-case-7/EngineerARole'
        """
        from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
        return UnifiedEntityResolver.compute_ontserve_path(uri or '', ontology_target)

    @app.template_filter('annotate_entities')
    def annotate_entities_filter(text, case_id):
        """Annotate text with ontology entity popovers.

        Usage in templates:
            {{ some_text | annotate_entities(case_id) }}

        Caches the TextAnnotator per case_id for the duration of the request.
        """
        if not text or not case_id:
            return text or ''
        try:
            from flask import g
            from app.services.annotation import TextAnnotator
            cache_key = f'_text_annotator_{case_id}'
            annotator = getattr(g, cache_key, None)
            if annotator is None:
                annotator = TextAnnotator(case_id=int(case_id))
                setattr(g, cache_key, annotator)
            return annotator.annotate_html(str(text))
        except Exception:
            return text
