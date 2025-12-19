#!/usr/bin/env python3
"""
Seed the prompt_registry table with the complete inventory of LLM prompts.

This script populates the registry with all prompts used across the ProEthica
extraction pipeline (Passes 1-3) and analysis steps (Steps 4-5).

Usage:
    python scripts/seed_prompt_registry.py [--clear]

Options:
    --clear     Clear existing registry entries before seeding
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text


# Complete inventory of prompts used in ProEthica
PROMPT_INVENTORY = [
    # ===== PASS 1: CONTEXTUAL FRAMEWORK (WHO-WHEN-WHAT) =====
    {
        "prompt_key": "pass1.roles",
        "phase": "pass1",
        "concept_type": "roles",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_roles_resources.py",
        "source_function": "get_enhanced_roles_prompt",
        "description": "Extract professional roles that bear obligations and make decisions. Uses Kong et al. (2020) four-category framework.",
        "academic_references": ["Kong et al. 2020", "Oakley & Cocking 2001"],
    },
    {
        "prompt_key": "pass1.states",
        "phase": "pass1",
        "concept_type": "states",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_states_capabilities.py",
        "source_function": "create_enhanced_states_prompt",
        "description": "Extract environmental conditions that determine when obligations activate. Uses Event Calculus for state persistence.",
        "academic_references": ["Berreby et al. 2017", "Rao et al. 2023"],
    },
    {
        "prompt_key": "pass1.resources",
        "phase": "pass1",
        "concept_type": "resources",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_roles_resources.py",
        "source_function": "get_enhanced_resources_prompt",
        "description": "Extract professional knowledge sources that ground ethical decisions. Includes codes, precedents, standards.",
        "academic_references": ["McLaren 2003"],
    },
    {
        "prompt_key": "pass1.combined",
        "phase": "pass1",
        "concept_type": "combined",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_roles_resources.py",
        "source_function": "get_enhanced_pass1_entities_prompt",
        "description": "Combined extraction of Roles and Resources in single LLM call for efficiency.",
        "academic_references": ["Kong et al. 2020", "McLaren 2003"],
    },

    # ===== PASS 2: NORMATIVE REQUIREMENTS (Abstract to Concrete) =====
    {
        "prompt_key": "pass2.principles",
        "phase": "pass2",
        "concept_type": "principles",
        "section_type": "discussion",
        "source_file": "app/services/extraction/enhanced_prompts_principles.py",
        "source_function": "EnhancedPrinciplesExtractor._generate_enhanced_prompt",
        "description": "Extract abstract ethical foundations from code. Uses extensional definition through precedents.",
        "academic_references": ["McLaren 2003", "Taddeo et al. 2024", "Anderson & Anderson 2018"],
    },
    {
        "prompt_key": "pass2.obligations",
        "phase": "pass2",
        "concept_type": "obligations",
        "section_type": "discussion",
        "source_file": "app/services/extraction/enhanced_prompts_obligations.py",
        "source_function": "create_enhanced_obligations_prompt",
        "description": "Extract concrete professional duties derived from principles. Uses deontic operators (MUST, SHOULD, etc.).",
        "academic_references": ["Wooldridge & Jennings 1995", "Dennis et al. 2016", "Kong et al. 2020"],
    },
    {
        "prompt_key": "pass2.constraints",
        "phase": "pass2",
        "concept_type": "constraints",
        "section_type": "discussion",
        "source_file": "app/services/extraction/enhanced_prompts_constraints.py",
        "source_function": "create_enhanced_constraints_prompt",
        "description": "Extract boundaries and limitations that restrict professional behavior. Includes defeasibility assessment.",
        "academic_references": ["Ganascia 2007", "Dennis et al. 2016", "Arkin 2008"],
    },
    {
        "prompt_key": "pass2.capabilities",
        "phase": "pass2",
        "concept_type": "capabilities",
        "section_type": "discussion",
        "source_file": "app/services/extraction/enhanced_prompts_states_capabilities.py",
        "source_function": "EnhancedCapabilitiesExtractor.extract",
        "description": "Extract competencies required for professional ethical decision-making. Uses Tolmeijer taxonomy.",
        "academic_references": ["Tolmeijer et al. 2021", "Berreby et al. 2017", "Anderson & Anderson 2018"],
    },

    # ===== PASS 3: TEMPORAL DYNAMICS (Actions & Events) =====
    {
        "prompt_key": "pass3.actions",
        "phase": "pass3",
        "concept_type": "actions",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_actions.py",
        "source_function": "create_enhanced_actions_prompt",
        "description": "Extract volitional professional decisions and interventions. Includes Pass 1 & 2 context for entity grounding.",
        "academic_references": ["Sarmiento et al. 2023", "Berreby et al. 2017", "Govindarajulu & Bringsjord 2017"],
    },
    {
        "prompt_key": "pass3.events",
        "phase": "pass3",
        "concept_type": "events",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_events.py",
        "source_function": "create_enhanced_events_prompt",
        "description": "Extract temporal occurrences that trigger ethical considerations. Uses Event Calculus formalism.",
        "academic_references": ["Berreby et al. 2017", "Zhang et al. 2023"],
    },
    {
        "prompt_key": "pass3.actions_events_alt",
        "phase": "pass3",
        "concept_type": "actions_events",
        "section_type": "all",
        "source_file": "app/services/extraction/enhanced_prompts_actions_events.py",
        "source_function": "create_enhanced_actions_prompt",
        "description": "Alternative simpler prompt for actions/events without full Pass context integration.",
        "academic_references": ["Berreby et al. 2017"],
    },

    # ===== STEP 4: CASE ANALYSIS =====
    {
        "prompt_key": "step4.provisions",
        "phase": "step4",
        "concept_type": "provisions",
        "section_type": "all",
        "source_file": "app/services/code_provision_linker.py",
        "source_function": "_create_linking_prompt",
        "description": "Link NSPE Code provisions to extracted case entities across all 9 concept types.",
        "academic_references": [],
    },
    {
        "prompt_key": "step4.decision_points",
        "phase": "step4",
        "concept_type": "decision_points",
        "section_type": "all",
        "source_file": "app/services/decision_focus_extractor.py",
        "source_function": "_create_extraction_prompt",
        "description": "Extract key decision points where ethical choices must be made. Entity-grounded with URIs.",
        "academic_references": ["Hobbs & Moore 2005"],
    },
    {
        "prompt_key": "step4.questions",
        "phase": "step4",
        "concept_type": "questions",
        "section_type": "all",
        "source_file": "app/services/question_analyzer.py",
        "source_function": "_get_board_questions",
        "description": "Extract Board's ethical questions. Two-stage: import parsed + LLM extraction, then analytical generation.",
        "academic_references": [],
    },
    {
        "prompt_key": "step4.questions_analytical",
        "phase": "step4",
        "concept_type": "questions",
        "section_type": "all",
        "source_file": "app/services/question_analyzer.py",
        "source_function": "_generate_analytical_questions",
        "description": "Generate analytical questions: implicit, principle_tension, theoretical, counterfactual types.",
        "academic_references": [],
    },
    {
        "prompt_key": "step4.conclusions",
        "phase": "step4",
        "concept_type": "conclusions",
        "section_type": "all",
        "source_file": "app/services/conclusion_analyzer.py",
        "source_function": "_get_board_conclusions",
        "description": "Extract Board conclusions. Two-stage: import parsed + LLM extraction, then analytical extensions.",
        "academic_references": [],
    },
    {
        "prompt_key": "step4.conclusions_analytical",
        "phase": "step4",
        "concept_type": "conclusions",
        "section_type": "all",
        "source_file": "app/services/conclusion_analyzer.py",
        "source_function": "_create_analytical_prompt",
        "description": "Generate analytical conclusions: extensions, question responses, principle synthesis.",
        "academic_references": [],
    },
    {
        "prompt_key": "step4.transformation",
        "phase": "step4",
        "concept_type": "transformation",
        "section_type": "all",
        "source_file": "app/services/case_analysis/transformation_classifier.py",
        "source_function": "_create_classification_prompt",
        "description": "Classify how ethical situation was resolved: transfer, stalemate, oscillation, or phase_lag.",
        "academic_references": ["Marchais-Roubelat & Roubelat 2015"],
    },
    {
        "prompt_key": "step4.arguments",
        "phase": "step4",
        "concept_type": "arguments",
        "section_type": "all",
        "source_file": "app/services/argument_generator.py",
        "source_function": "_create_argument_prompt",
        "description": "Generate Toulmin-structured pro/con arguments for decision options with provision citations.",
        "academic_references": ["Toulmin 1958"],
    },

    # ===== STEP 5: INTERACTIVE SCENARIO =====
    {
        "prompt_key": "step5.consequences",
        "phase": "step5",
        "concept_type": "consequences",
        "section_type": "all",
        "source_file": "app/services/interactive_scenario_service.py",
        "source_function": "_generate_consequences_llm",
        "description": "Generate consequences for user choices constrained by Event Calculus rules. Inline hardcoded prompt.",
        "academic_references": ["Berreby et al. 2017"],
    },
    {
        "prompt_key": "step5.analysis",
        "phase": "step5",
        "concept_type": "analysis",
        "section_type": "all",
        "source_file": "app/services/interactive_scenario_service.py",
        "source_function": "_generate_analysis_narrative",
        "description": "Compare user choices to Board's choices in interactive exploration. Final analysis narrative.",
        "academic_references": [],
    },
    {
        "prompt_key": "step5.option_labels",
        "phase": "step5",
        "concept_type": "option_labels",
        "section_type": "all",
        "source_file": "app/services/interactive_scenario_service.py",
        "source_function": "_generate_option_labels",
        "description": "Generate concise, action-oriented labels for ethical decision options.",
        "academic_references": [],
    },
]


def seed_registry(clear_first: bool = False):
    """Seed the prompt_registry table with inventory."""
    from app import create_app
    from app.models import db

    app = create_app()
    with app.app_context():
        if clear_first:
            result = db.session.execute(text("DELETE FROM prompt_registry"))
            db.session.commit()
            print(f"Cleared {result.rowcount} existing entries")

        # Insert each prompt
        inserted = 0
        updated = 0
        for prompt in PROMPT_INVENTORY:
            # Check if exists
            existing = db.session.execute(
                text("SELECT id FROM prompt_registry WHERE prompt_key = :key"),
                {"key": prompt["prompt_key"]}
            ).fetchone()

            if existing:
                # Update existing
                db.session.execute(
                    text("""
                        UPDATE prompt_registry SET
                            phase = :phase,
                            concept_type = :concept_type,
                            section_type = :section_type,
                            source_file = :source_file,
                            source_function = :source_function,
                            description = :description,
                            academic_references = :academic_references,
                            updated_at = NOW()
                        WHERE prompt_key = :prompt_key
                    """),
                    {
                        "prompt_key": prompt["prompt_key"],
                        "phase": prompt["phase"],
                        "concept_type": prompt["concept_type"],
                        "section_type": prompt["section_type"],
                        "source_file": prompt["source_file"],
                        "source_function": prompt["source_function"],
                        "description": prompt["description"],
                        "academic_references": prompt["academic_references"],
                    }
                )
                updated += 1
            else:
                # Insert new
                db.session.execute(
                    text("""
                        INSERT INTO prompt_registry
                            (prompt_key, phase, concept_type, section_type,
                             source_file, source_function, description, academic_references)
                        VALUES
                            (:prompt_key, :phase, :concept_type, :section_type,
                             :source_file, :source_function, :description, :academic_references)
                    """),
                    {
                        "prompt_key": prompt["prompt_key"],
                        "phase": prompt["phase"],
                        "concept_type": prompt["concept_type"],
                        "section_type": prompt["section_type"],
                        "source_file": prompt["source_file"],
                        "source_function": prompt["source_function"],
                        "description": prompt["description"],
                        "academic_references": prompt["academic_references"],
                    }
                )
                inserted += 1

        db.session.commit()
        print(f"Seeding complete: {inserted} inserted, {updated} updated")
        print(f"Total prompts in registry: {len(PROMPT_INVENTORY)}")

        # Print summary by phase
        phases = {}
        for p in PROMPT_INVENTORY:
            phases[p["phase"]] = phases.get(p["phase"], 0) + 1

        print("\nPrompts by phase:")
        for phase, count in sorted(phases.items()):
            print(f"  {phase}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Seed prompt_registry table")
    parser.add_argument("--clear", action="store_true", help="Clear existing entries first")
    args = parser.parse_args()

    seed_registry(clear_first=args.clear)


if __name__ == "__main__":
    main()
