"""Prompt-builder extraction-class registry route."""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate, SectionPromptInstance, PromptTemplateVersion, LangExtractExample, LangExtractExampleExtraction
from sqlalchemy import func, text
import requests
import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def register_registry_routes(bp):
    @bp.route('/registry')
    @login_required
    def registry():
        """
    Prompt Registry - inventory of all LLM prompts used in extraction pipeline.

    Shows prompts organized by phase (Pass 1, 2, 3, Step 4, 5) with source file links.
    Designed for future NeMo/DSPy integration.
    """
        try:
            # Get all registered prompts
            prompts = db.session.execute(text("""
            SELECT
                id, prompt_key, phase, concept_type, section_type,
                source_file, source_function, description,
                academic_references, is_active,
                nemo_compatible, dspy_module, langsmith_id,
                created_at, updated_at
            FROM prompt_registry
            ORDER BY phase, concept_type
        """)).fetchall()

            # Group by phase
            phases = {
                'pass1': {'name': 'Pass 1: Contextual Framework', 'description': 'WHO-WHEN-WHAT: Roles, States, Resources', 'prompts': []},
                'pass2': {'name': 'Pass 2: Normative Requirements', 'description': 'Abstract to Concrete: Principles, Obligations, Constraints, Capabilities', 'prompts': []},
                'pass3': {'name': 'Pass 3: Temporal Dynamics', 'description': 'Actions and Events with Event Calculus', 'prompts': []},
                'step4': {'name': 'Step 4: Case Analysis', 'description': 'Provisions, Questions, Conclusions, Transformation, Arguments', 'prompts': []},
                'step5': {'name': 'Step 5: Interactive Scenario', 'description': 'Consequence generation and analysis', 'prompts': []},
            }

            for prompt in prompts:
                phase = prompt.phase
                if phase in phases:
                    phases[phase]['prompts'].append({
                        'id': prompt.id,
                        'prompt_key': prompt.prompt_key,
                        'concept_type': prompt.concept_type,
                        'section_type': prompt.section_type,
                        'source_file': prompt.source_file,
                        'source_function': prompt.source_function,
                        'description': prompt.description,
                        'academic_references': prompt.academic_references or [],
                        'is_active': prompt.is_active,
                        'nemo_compatible': prompt.nemo_compatible,
                        'dspy_module': prompt.dspy_module,
                        'langsmith_id': prompt.langsmith_id,
                    })

            # Get statistics
            stats = {
                'total_prompts': len(prompts),
                'by_phase': {phase: len(data['prompts']) for phase, data in phases.items()},
                'nemo_ready': sum(1 for p in prompts if p.nemo_compatible),
            }

            return render_template('prompt_builder/registry.html',
                                 phases=phases,
                                 stats=stats)

        except Exception as e:
            logger.error(f"Error loading prompt registry: {e}")
            flash(f'Error loading prompt registry: {e}', 'error')
            return render_template('prompt_builder/registry.html',
                                 phases={},
                                 stats={'total_prompts': 0, 'by_phase': {}, 'nemo_ready': 0})


