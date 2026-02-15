#!/usr/bin/env python
"""
Test the unified extraction pipeline on a single concept for a single case.

Usage:
    # Show prompt only (no LLM call):
    python scripts/test_unified_extraction.py 15 roles

    # Show prompt and run extraction:
    python scripts/test_unified_extraction.py 15 roles --execute

    # Use a specific model:
    python scripts/test_unified_extraction.py 15 obligations --execute --model claude-haiku-4-5-20251022

    # Run all 9 concepts:
    python scripts/test_unified_extraction.py 15 all --execute
"""

import argparse
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_APP', 'run.py')


def main():
    parser = argparse.ArgumentParser(description='Test unified extraction on one concept')
    parser.add_argument('case_id', type=int, help='Case ID to extract from')
    parser.add_argument('concept', help='Concept type (roles, states, resources, principles, '
                        'obligations, constraints, capabilities, actions, events, all)')
    parser.add_argument('--execute', action='store_true', help='Actually call the LLM')
    parser.add_argument('--model', default=None, help='Override LLM model')
    parser.add_argument('--section', default=None, help='Section type (facts, discussion)')
    parser.add_argument('--no-store', action='store_true',
                        help='Skip storing results to DB (useful for testing)')
    args = parser.parse_args()

    from app import create_app
    app = create_app()

    with app.app_context():
        from app.models.document import Document
        from app.services.extraction.schemas import EXTRACTION_STEPS

        case = Document.query.get(args.case_id)
        if not case:
            print(f"Case {args.case_id} not found")
            sys.exit(1)

        # Load case sections
        metadata = case.doc_metadata or {}
        sections_data = metadata.get('sections_dual', {})
        sections = {}
        for key in ('facts', 'discussion', 'questions', 'conclusion'):
            val = sections_data.get(key, '')
            if isinstance(val, dict):
                val = val.get('text', '')
            sections[key] = val

        print(f"Case {args.case_id}: {case.title}")
        print(f"  Facts: {len(sections.get('facts', ''))} chars")
        print(f"  Discussion: {len(sections.get('discussion', ''))} chars")
        print()

        # Determine concepts to extract
        if args.concept == 'all':
            concepts = []
            for step_concepts in EXTRACTION_STEPS.values():
                concepts.extend(step_concepts)
        else:
            concepts = [args.concept]

        for concept in concepts:
            extract_concept(
                case_id=args.case_id,
                concept_type=concept,
                sections=sections,
                model=args.model,
                section_override=args.section,
                execute=args.execute,
                store=not args.no_store,
            )


def extract_concept(case_id, concept_type, sections, model, section_override,
                    execute, store):
    """Extract a single concept and display results."""
    from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor, CONCEPT_CONFIG

    config = CONCEPT_CONFIG.get(concept_type)
    if not config:
        print(f"Unknown concept: {concept_type}")
        print(f"Valid: {list(CONCEPT_CONFIG.keys())}")
        return

    step = config['step']

    # Default section based on step
    if section_override:
        section_type = section_override
    elif step == 1:
        section_type = 'facts'
    else:
        section_type = 'discussion'

    case_text = sections.get(section_type, '')
    if not case_text:
        print(f"No {section_type} text available for case {case_id}")
        return

    print("=" * 78)
    print(f"  CONCEPT: {concept_type}  |  STEP: {step}  |  SECTION: {section_type}")
    print("=" * 78)

    # Initialize extractor
    extractor = UnifiedDualExtractor(
        concept_type=concept_type,
        model=model,
    )

    print(f"Model: {extractor.model_name}")
    print(f"Template: {'DB v' + str(extractor.template.version) if extractor.template else 'NONE'}")
    print(f"Existing classes from MCP: {len(extractor.existing_classes)}")
    print()

    # Build and display prompt
    try:
        prompt = extractor._build_prompt(case_text, section_type)
    except RuntimeError as e:
        print(f"Cannot build prompt: {e}")
        return

    print("--- PROMPT (first 3000 chars) ---")
    print(prompt[:3000])
    if len(prompt) > 3000:
        print(f"\n... ({len(prompt)} total chars, truncated for display)")
    print("--- END PROMPT ---")
    print()

    if not execute:
        print("[Dry run - pass --execute to call the LLM]")
        print()
        return

    # Run extraction
    print(f"Calling LLM ({extractor.model_name})...")
    import time
    start = time.time()

    classes, individuals = extractor.extract(
        case_text=case_text,
        case_id=case_id,
        section_type=section_type,
    )

    elapsed = time.time() - start
    print(f"Extracted in {elapsed:.1f}s: {len(classes)} classes, {len(individuals)} individuals")
    print()

    # Display classes
    if classes:
        print("--- CANDIDATE CLASSES ---")
        for c in classes:
            match_info = ""
            if c.match_decision.matches_existing:
                match_info = f" [MATCH: {c.match_decision.matched_label}]"
            cat_field = {
                'roles': 'role_category',
                'principles': 'principle_category',
                'obligations': 'obligation_type',
                'states': 'state_category',
                'resources': 'resource_category',
                'actions': 'action_category',
                'events': 'event_category',
                'capabilities': 'capability_category',
                'constraints': 'constraint_type',
            }.get(concept_type)
            cat_val = getattr(c, cat_field, None) if cat_field else None
            cat_str = f" [{cat_val.value}]" if cat_val and hasattr(cat_val, 'value') else ""

            print(f"  {c.label}{cat_str}{match_info}")
            defn = c.definition
            if len(defn) > 120:
                defn = defn[:117] + '...'
            print(f"    {defn}")
        print()

    # Display individuals
    if individuals:
        print("--- INDIVIDUALS ---")
        for ind in individuals:
            name = getattr(ind, 'name', '') or getattr(ind, 'identifier', '') or '(unnamed)'
            ref_field = CONCEPT_CONFIG[concept_type]['class_ref_field']
            ref = getattr(ind, ref_field, '?')
            print(f"  {name} -> {ref}")
        print()

    # Store results
    if store and (classes or individuals):
        import uuid
        from app.services.extraction.extraction_graph import pydantic_to_rdf_data
        from app.models import TemporaryRDFStorage
        from app.services.extraction.schemas import CONCEPT_EXTRACTION_TYPES
        from app import db

        session_id = str(uuid.uuid4())
        rdf_data = pydantic_to_rdf_data(
            classes=classes,
            individuals=individuals,
            concept_type=concept_type,
            case_id=case_id,
            section_type=section_type,
        )

        extraction_type = CONCEPT_EXTRACTION_TYPES.get(concept_type, concept_type)
        stored = TemporaryRDFStorage.store_extraction_results(
            case_id=case_id,
            extraction_session_id=session_id,
            extraction_type=extraction_type,
            rdf_data=rdf_data,
            extraction_model=extractor.model_name,
            provenance_data={'section_type': section_type},
        )
        db.session.commit()

        print(f"Stored {len(stored)} entities to temporary_rdf_storage (session {session_id[:8]}...)")

        # Save prompt record
        from app.models.extraction_prompt import ExtractionPrompt
        try:
            ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type=concept_type,
                prompt_text=extractor.last_prompt or prompt,
                raw_response=extractor.last_raw_response,
                step_number=CONCEPT_CONFIG[concept_type]['step'],
                section_type=section_type,
                llm_model=extractor.model_name,
                extraction_session_id=session_id,
                results_summary={
                    'classes': len(classes),
                    'individuals': len(individuals),
                },
            )
            db.session.commit()
            print(f"Saved prompt to extraction_prompts table")
        except Exception as e:
            print(f"Warning: could not save prompt record: {e}")

    elif not store:
        print("[--no-store: results not saved to DB]")

    print()


if __name__ == '__main__':
    main()
