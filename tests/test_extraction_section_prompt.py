#!/usr/bin/env python
"""
Test script for ExtractionSectionPrompt model.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from app.models import db
from app.models.extraction_section_prompt import ExtractionSectionPrompt
from config import Config

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Set database URL
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5432/ai_ethical_dm'

with app.app_context():
    db.init_app(app)

    print("=" * 80)
    print("Testing ExtractionSectionPrompt Model")
    print("=" * 80)

    # Test 1: Get specific prompt
    print("\nTest 1: Get Facts - Roles prompt")
    roles_prompt = ExtractionSectionPrompt.get_prompt_for_section(
        section_type='facts',
        extraction_pass=1,
        concept_type='roles'
    )
    if roles_prompt:
        print(f"✓ Found: {roles_prompt.prompt_name}")
        print(f"  Guidance: {roles_prompt.extraction_guidance[:100]}...")
    else:
        print("✗ Not found")

    # Test 2: Get all prompts for Facts Pass 1
    print("\nTest 2: Get all Facts Pass 1 prompts")
    pass1_prompts = ExtractionSectionPrompt.get_all_prompts_for_section(
        section_type='facts',
        extraction_pass=1
    )
    print(f"✓ Found {len(pass1_prompts)} prompts:")
    for prompt in pass1_prompts:
        print(f"  - {prompt.concept_type}: {prompt.prompt_name}")

    # Test 3: Get all prompts for Pass 2 (Normative)
    print("\nTest 3: Get all Pass 2 (Normative) prompts")
    pass2_prompts = ExtractionSectionPrompt.get_all_prompts_for_pass(extraction_pass=2)
    print(f"✓ Found {len(pass2_prompts)} prompts:")
    for (section, concept), prompt in sorted(pass2_prompts.items()):
        print(f"  - {section}/{concept}: {prompt.prompt_name}")

    # Test 4: Record usage
    print("\nTest 4: Record usage statistics")
    if roles_prompt:
        original_times_used = roles_prompt.times_used
        roles_prompt.record_usage(entities_extracted=5, avg_confidence=0.85)
        print(f"✓ Usage recorded:")
        print(f"  Times used: {original_times_used} → {roles_prompt.times_used}")
        print(f"  Avg entities: {roles_prompt.avg_entities_extracted}")
        print(f"  Avg confidence: {roles_prompt.avg_confidence}")

    # Test 5: Count total prompts
    print("\nTest 5: Total prompts in database")
    total = ExtractionSectionPrompt.query.count()
    active = ExtractionSectionPrompt.query.filter_by(is_active=True).count()
    print(f"✓ Total: {total}, Active: {active}")

    print("\n" + "=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)
