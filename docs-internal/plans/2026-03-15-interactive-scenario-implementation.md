# Interactive Scenario Exploration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace runtime LLM-based interactive scenario exploration with pre-computed consequence data and a card-based traversal UI with branching analysis view.

**Architecture:** Phase 4 extraction pipeline is extended with a consequence generation sub-stage (Stage 4.3b) that pre-computes consequence narratives for every option at every decision point. The interactive service becomes a pure data reader. The UI splits into three templates: sequential traversal (one card per decision), summary (post-traversal choices list), and branching analysis (mini decision tree + tabbed comparison cards).

**Tech Stack:** Flask/Jinja2, Bootstrap 5, vanilla JS, CSS View Transition API, PostgreSQL (JSON columns), Anthropic Claude API (extraction-time only)

**Spec:** `docs-internal/specs/2026-03-15-interactive-scenario-design.md`

---

## Chunk 1: Data Layer

### Task 1: Extend dataclasses with consequence fields

**Files:**
- Modify: `app/services/narrative/scenario_seed_generator.py:28-59`
- Test: `tests/unit/test_consequence_dataclasses.py` (create)

- [x] **Step 1: Write test for extended ScenarioOption serialization**

```python
# tests/unit/test_consequence_dataclasses.py
"""Tests for consequence-extended dataclasses."""
import pytest
from app.services.narrative.scenario_seed_generator import (
    ScenarioOption, ScenarioBranch
)


def test_scenario_option_consequence_fields_default_empty():
    """New consequence fields default to empty values."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test Option",
        description="A test",
    )
    assert opt.consequence_narrative == ""
    assert opt.consequence_obligations == []
    assert opt.consequence_fluent_changes == {}


def test_scenario_option_consequence_fields_populated():
    """Consequence fields serialize correctly when populated."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Resign First",
        description="Leave before signing",
        action_uris=["case-1#Resign"],
        is_board_choice=True,
        consequence_narrative="By resigning first, the engineer avoids conflict.",
        consequence_obligations=["Duty of Loyalty"],
        consequence_fluent_changes={
            "initiated": ["Clean_Separation"],
            "terminated": ["Active_Employment"]
        },
    )
    from dataclasses import asdict
    d = asdict(opt)
    assert d["consequence_narrative"] == "By resigning first, the engineer avoids conflict."
    assert d["consequence_obligations"] == ["Duty of Loyalty"]
    assert d["consequence_fluent_changes"]["initiated"] == ["Clean_Separation"]


def test_scenario_branch_consequence_fields_default_empty():
    """Branch-level consequence fields default to empty."""
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="Test context",
        question="What should happen?",
        decision_point_uri="dp_1",
        decision_maker_uri="uri:maker",
        decision_maker_label="Engineers",
    )
    assert branch.board_rationale == ""
    assert branch.competing_obligation_labels == []


def test_scenario_branch_to_dict_includes_consequence_fields():
    """to_dict() includes the new consequence fields."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test",
        description="",
        consequence_narrative="Consequence text",
    )
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="Context",
        question="Question?",
        decision_point_uri="dp_1",
        decision_maker_uri="uri:maker",
        decision_maker_label="Engineers",
        options=[opt],
        board_rationale="The board chose this because...",
        competing_obligation_labels=["Duty of Loyalty", "Right to Mobility"],
    )
    d = branch.to_dict()
    assert d["board_rationale"] == "The board chose this because..."
    assert d["competing_obligation_labels"] == ["Duty of Loyalty", "Right to Mobility"]
    assert d["options"][0]["consequence_narrative"] == "Consequence text"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_consequence_dataclasses.py -v`

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'consequence_narrative'`

- [x] **Step 3: Add consequence fields to ScenarioOption**

In `app/services/narrative/scenario_seed_generator.py`, add three fields to `ScenarioOption` after `leads_to`:

```python
@dataclass
class ScenarioOption:
    """An option within a scenario branch."""
    option_id: str
    label: str
    description: str
    action_uris: List[str] = field(default_factory=list)
    is_board_choice: bool = False
    leads_to: Optional[str] = None  # Next branch ID
    # Consequence data (populated by consequence generator, Stage 4.3b)
    consequence_narrative: str = ""
    consequence_obligations: List[str] = field(default_factory=list)
    consequence_fluent_changes: Dict[str, List[str]] = field(default_factory=dict)
```

- [x] **Step 4: Add consequence fields to ScenarioBranch**

In the same file, add two fields to `ScenarioBranch` after `options`:

```python
@dataclass
class ScenarioBranch:
    """A branch point in the scenario."""
    branch_id: str
    context: str
    question: str
    decision_point_uri: str
    decision_maker_uri: str
    decision_maker_label: str
    involved_obligation_uris: List[str] = field(default_factory=list)
    options: List[ScenarioOption] = field(default_factory=list)
    # Consequence data (populated by consequence generator, Stage 4.3b)
    board_rationale: str = ""
    competing_obligation_labels: List[str] = field(default_factory=list)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_consequence_dataclasses.py -v`

Expected: 4 tests PASS

- [x] **Step 6: Commit**

```bash
git add app/services/narrative/scenario_seed_generator.py tests/unit/test_consequence_dataclasses.py
git commit -m "feat: add consequence fields to ScenarioOption and ScenarioBranch dataclasses"
```

---

### Task 2: Create consequence generator module

**Files:**
- Create: `app/services/scenario_generation/consequence_generator.py`
- Test: `tests/unit/test_consequence_generator.py` (create)

The consequence generator takes a `ScenarioSeeds` object (with branches and options already populated) plus supporting data (causal links, resolution, entity lookup), and fills in the consequence fields on each option and branch. One LLM call per decision point.

- [x] **Step 1: Write test for consequence generation with mocked LLM**

```python
# tests/unit/test_consequence_generator.py
"""Tests for the consequence generator module."""
import json
import pytest
from unittest.mock import MagicMock, patch
from app.services.narrative.scenario_seed_generator import (
    ScenarioOption, ScenarioBranch, ScenarioSeeds
)
from app.services.scenario_generation.consequence_generator import (
    generate_consequences_for_seeds,
    _build_consequence_prompt,
    _parse_consequence_response,
)


@pytest.fixture
def sample_seeds():
    """Minimal ScenarioSeeds with two branches, each with two options."""
    return ScenarioSeeds(
        case_id=1,
        opening_context="You are an engineer facing a decision.",
        initial_state_description="Active employment.",
        protagonist_uri="uri:engineer",
        protagonist_label="Engineer",
        branches=[
            ScenarioBranch(
                branch_id="branch_0",
                context="The engineer discovers a conflict.",
                question="Should the engineer disclose or stay silent?",
                decision_point_uri="dp_0",
                decision_maker_uri="uri:engineer",
                decision_maker_label="Engineer",
                involved_obligation_uris=[
                    "uri:obligation-duty-of-candor",
                    "uri:obligation-loyalty-to-employer",
                ],
                options=[
                    ScenarioOption(
                        option_id="opt_0_0",
                        label="Disclose the conflict",
                        description="",
                        action_uris=["case-1#Disclose"],
                        is_board_choice=True,
                    ),
                    ScenarioOption(
                        option_id="opt_0_1",
                        label="Stay silent",
                        description="",
                        action_uris=["case-1#Stay_Silent"],
                        is_board_choice=False,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_resolution():
    return {
        "resolution_type": "violation",
        "summary": "The Board found the engineer violated the duty of candor.",
        "conclusions": [
            {"uri": "c1", "text": "The engineer should have disclosed."}
        ],
    }


@pytest.fixture
def sample_causal_links():
    return [
        {
            "source_uri": "case-1#Disclose",
            "source_label": "Disclose",
            "target_uri": "uri:obligation-duty-of-candor",
            "target_label": "Duty of Candor",
            "link_type": "fulfills",
        },
        {
            "source_uri": "case-1#Stay_Silent",
            "source_label": "Stay Silent",
            "target_uri": "uri:obligation-duty-of-candor",
            "target_label": "Duty of Candor",
            "link_type": "violates",
        },
    ]


@pytest.fixture
def sample_entity_lookup():
    return {
        "uri:obligation-duty-of-candor": {"label": "Duty of Candor"},
        "uri:obligation-loyalty-to-employer": {"label": "Loyalty to Employer"},
    }


def test_build_consequence_prompt(sample_seeds, sample_causal_links, sample_resolution):
    """Prompt includes branch question, all options, causal links, and resolution."""
    prompt = _build_consequence_prompt(
        branch=sample_seeds.branches[0],
        causal_links=sample_causal_links,
        resolution=sample_resolution,
    )
    assert "Disclose the conflict" in prompt
    assert "Stay silent" in prompt
    assert "Duty of Candor" in prompt
    assert "The Board found" in prompt


def test_parse_consequence_response_valid():
    """Parse a well-formed LLM response into consequence data."""
    llm_response = json.dumps({
        "options": [
            {
                "option_id": "opt_0_0",
                "consequence_narrative": "Disclosure leads to transparency.",
                "consequence_obligations": ["Duty of Candor"],
                "consequence_fluent_changes": {
                    "initiated": ["Transparency_Active"],
                    "terminated": ["Conflict_Hidden"],
                },
            },
            {
                "option_id": "opt_0_1",
                "consequence_narrative": "Silence preserves the status quo but risks discovery.",
                "consequence_obligations": ["Loyalty to Employer"],
                "consequence_fluent_changes": {
                    "initiated": ["Undisclosed_Conflict"],
                    "terminated": [],
                },
            },
        ],
        "board_rationale": "The Board emphasized candor as a core obligation.",
    })
    result = _parse_consequence_response(llm_response, num_options=2)
    assert len(result["options"]) == 2
    assert result["options"][0]["consequence_narrative"] == "Disclosure leads to transparency."
    assert result["board_rationale"] == "The Board emphasized candor as a core obligation."


def test_parse_consequence_response_malformed():
    """Malformed response returns empty defaults."""
    result = _parse_consequence_response("not json at all", num_options=2)
    assert len(result["options"]) == 2
    assert result["options"][0]["consequence_narrative"] == ""
    assert result["board_rationale"] == ""


@patch("app.services.scenario_generation.consequence_generator.get_llm_client")
def test_generate_consequences_populates_fields(
    mock_get_client, sample_seeds, sample_causal_links, sample_resolution, sample_entity_lookup
):
    """generate_consequences_for_seeds populates consequence fields on the ScenarioSeeds object."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps({
            "options": [
                {
                    "option_id": "opt_0_0",
                    "consequence_narrative": "Disclosure works.",
                    "consequence_obligations": ["Duty of Candor"],
                    "consequence_fluent_changes": {"initiated": ["Transparent"], "terminated": []},
                },
                {
                    "option_id": "opt_0_1",
                    "consequence_narrative": "Silence fails.",
                    "consequence_obligations": ["Loyalty to Employer"],
                    "consequence_fluent_changes": {"initiated": [], "terminated": []},
                },
            ],
            "board_rationale": "Candor is required.",
        }))]
    )

    generate_consequences_for_seeds(
        seeds=sample_seeds,
        causal_links=sample_causal_links,
        resolution=sample_resolution,
        entity_lookup=sample_entity_lookup,
    )

    # Verify options were populated
    branch = sample_seeds.branches[0]
    assert branch.options[0].consequence_narrative == "Disclosure works."
    assert branch.options[1].consequence_narrative == "Silence fails."
    assert branch.board_rationale == "Candor is required."
    assert branch.competing_obligation_labels == ["Duty of Candor", "Loyalty to Employer"]

    # Verify LLM was called once (one branch = one call)
    assert mock_client.messages.create.call_count == 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_consequence_generator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.scenario_generation.consequence_generator'`

- [x] **Step 3: Create consequence_generator.py**

```python
# app/services/scenario_generation/consequence_generator.py
"""
Consequence Generator (Stage 4.3b)

Generates pre-computed consequence narratives for every option at every
decision point in a case's scenario seeds. Runs during Phase 4 extraction,
not at interactive session runtime.

Input: ScenarioSeeds with branches/options populated (from Stage 4.3)
Output: Same ScenarioSeeds with consequence_narrative, consequence_obligations,
        consequence_fluent_changes, board_rationale, and competing_obligation_labels
        populated on each option and branch.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from app.utils.llm_utils import get_llm_client
from model_config import ModelConfig
from app.services.narrative.scenario_seed_generator import (
    ScenarioSeeds, ScenarioBranch, ScenarioOption
)

logger = logging.getLogger(__name__)


def generate_consequences_for_seeds(
    seeds: ScenarioSeeds,
    causal_links: List[Dict],
    resolution: Dict,
    entity_lookup: Dict,
) -> None:
    """
    Populate consequence fields on all branches and options in-place.

    One LLM call per branch (decision point). Modifies the ScenarioSeeds
    object directly -- does not return a new object.

    Args:
        seeds: ScenarioSeeds with branches already populated (Stage 4.3 output)
        causal_links: List of causal link dicts from timeline
        resolution: Resolution dict from narrative_elements
        entity_lookup: Dict mapping URIs to entity dicts (for label resolution)
    """
    client = get_llm_client()

    for branch in seeds.branches:
        # Resolve obligation URIs to labels
        branch.competing_obligation_labels = [
            entity_lookup.get(uri, {}).get("label", uri.split("#")[-1] if "#" in uri else uri)
            for uri in branch.involved_obligation_uris
        ]

        # Build prompt and call LLM
        prompt = _build_consequence_prompt(
            branch=branch,
            causal_links=causal_links,
            resolution=resolution,
        )

        try:
            response = client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            parsed = _parse_consequence_response(response_text, num_options=len(branch.options))
        except Exception as e:
            logger.error(f"Consequence generation failed for {branch.branch_id}: {e}")
            parsed = _parse_consequence_response("", num_options=len(branch.options))

        # Apply parsed data to branch and options
        branch.board_rationale = parsed["board_rationale"]

        for i, opt in enumerate(branch.options):
            if i < len(parsed["options"]):
                opt_data = parsed["options"][i]
                opt.consequence_narrative = opt_data.get("consequence_narrative", "")
                opt.consequence_obligations = opt_data.get("consequence_obligations", [])
                opt.consequence_fluent_changes = opt_data.get("consequence_fluent_changes", {})

    logger.info(
        f"Generated consequences for case {seeds.case_id}: "
        f"{len(seeds.branches)} branches, "
        f"{sum(len(b.options) for b in seeds.branches)} options"
    )


def _build_consequence_prompt(
    branch: ScenarioBranch,
    causal_links: List[Dict],
    resolution: Dict,
) -> str:
    """Build the LLM prompt for consequence generation for one decision point."""

    # Filter causal links relevant to this branch's options
    option_action_uris = set()
    for opt in branch.options:
        option_action_uris.update(opt.action_uris)

    relevant_links = [
        link for link in causal_links
        if link.get("source_uri", "") in option_action_uris
        or link.get("source_label", "") in [uri.split("#")[-1] for uri in option_action_uris if "#" in uri]
    ]

    links_text = ""
    if relevant_links:
        links_text = "## Causal Links (from case analysis)\n"
        for link in relevant_links:
            links_text += (
                f"- {link.get('source_label', '?')} "
                f"--[{link.get('link_type', '?')}]--> "
                f"{link.get('target_label', '?')}\n"
            )

    resolution_text = ""
    if resolution:
        resolution_text = f"## Board Resolution\n{resolution.get('summary', '')}\n"
        for c in resolution.get("conclusions", [])[:2]:
            resolution_text += f"- {c.get('text', '')[:300]}\n"

    options_text = ""
    for i, opt in enumerate(branch.options):
        board_marker = " [BOARD'S CHOICE]" if opt.is_board_choice else ""
        options_text += f"{i+1}. {opt.label}{board_marker}\n"
        if opt.description:
            options_text += f"   {opt.description}\n"

    return f"""Generate consequence narratives for each option at this decision point in a professional engineering ethics case.

## Decision Point
Decision maker: {branch.decision_maker_label}
Question: {branch.question}
Context: {branch.context}

## Options
{options_text}

{links_text}

{resolution_text}

## Task
For each option, generate:
1. A consequence narrative (2-3 sentences describing what follows from this choice)
2. A list of obligation labels that this choice activates or implicates
3. Fluent changes: what conditions are initiated (become true) and terminated (become false)

Also generate a board_rationale (2-3 sentences explaining why the board chose as they did).

Respond in JSON:
{{
    "options": [
        {{
            "option_id": "opt_N_M",
            "consequence_narrative": "...",
            "consequence_obligations": ["Obligation Label 1", "..."],
            "consequence_fluent_changes": {{
                "initiated": ["condition_1"],
                "terminated": ["condition_2"]
            }}
        }}
    ],
    "board_rationale": "..."
}}

Return one entry per option, in the same order as listed above."""


def _parse_consequence_response(response_text: str, num_options: int) -> Dict[str, Any]:
    """
    Parse LLM response into consequence data.

    Returns dict with 'options' list and 'board_rationale' string.
    On parse failure, returns empty defaults matching num_options.
    """
    empty_option = {
        "consequence_narrative": "",
        "consequence_obligations": [],
        "consequence_fluent_changes": {},
    }
    empty_result = {
        "options": [dict(empty_option) for _ in range(num_options)],
        "board_rationale": "",
    }

    if not response_text or not response_text.strip():
        return empty_result

    try:
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            return empty_result

        data = json.loads(json_match.group())
        options = data.get("options", [])

        # Pad or truncate to match expected count
        while len(options) < num_options:
            options.append(dict(empty_option))
        options = options[:num_options]

        return {
            "options": [
                {
                    "consequence_narrative": opt.get("consequence_narrative", ""),
                    "consequence_obligations": opt.get("consequence_obligations", []),
                    "consequence_fluent_changes": opt.get("consequence_fluent_changes", {}),
                }
                for opt in options
            ],
            "board_rationale": data.get("board_rationale", ""),
        }
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to parse consequence response: {e}")
        return empty_result
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_consequence_generator.py -v`

Expected: 5 tests PASS

- [x] **Step 5: Commit**

```bash
git add app/services/scenario_generation/consequence_generator.py tests/unit/test_consequence_generator.py
git commit -m "feat: add consequence generator module for Phase 4 pre-computation"
```

---

### Task 3: Integrate consequence generator into Phase 4 pipeline

**Files:**
- Modify: `app/services/narrative/__init__.py:198-209`
- Test: `tests/unit/test_consequence_dataclasses.py` (extend)

The consequence generator runs as Stage 4.3b, between scenario seed generation (4.3) and insight derivation (4.4). It modifies the `ScenarioSeeds` object in place.

- [x] **Step 1: Write test for pipeline integration**

Append to `tests/unit/test_consequence_dataclasses.py`:

```python
def test_phase4_result_includes_consequence_data():
    """Verify that Phase4NarrativeResult.to_dict() includes consequence fields
    when they are populated on the scenario seeds."""
    from app.services.narrative.scenario_seed_generator import ScenarioSeeds, ScenarioBranch, ScenarioOption
    from app.services.narrative import Phase4NarrativeResult

    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test",
        description="",
        consequence_narrative="Test consequence",
        consequence_obligations=["Duty X"],
        consequence_fluent_changes={"initiated": ["A"], "terminated": ["B"]},
    )
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="",
        question="Q?",
        decision_point_uri="dp",
        decision_maker_uri="uri",
        decision_maker_label="Engineer",
        options=[opt],
        board_rationale="Board chose because...",
        competing_obligation_labels=["Duty X", "Duty Y"],
    )
    seeds = ScenarioSeeds(
        case_id=1,
        opening_context="",
        initial_state_description="",
        protagonist_uri="",
        protagonist_label="",
        branches=[branch],
    )

    d = seeds.to_dict()
    assert d["branches"][0]["board_rationale"] == "Board chose because..."
    assert d["branches"][0]["competing_obligation_labels"] == ["Duty X", "Duty Y"]
    assert d["branches"][0]["options"][0]["consequence_narrative"] == "Test consequence"
```

- [x] **Step 2: Run test to verify it passes** (dataclass changes from Task 1 should make this pass already)

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_consequence_dataclasses.py::test_phase4_result_includes_consequence_data -v`

Expected: PASS (the `to_dict()` method uses `asdict()` which includes all fields)

- [x] **Step 3: Add Stage 4.3b call to construct_phase4_narrative()**

In `app/services/narrative/__init__.py`, after the Stage 4.3 block (line ~209) and before Stage 4.4, add:

```python
    # Stage 4.3b: Generate consequences for scenario options
    if use_llm and scenario_seeds and scenario_seeds.branches:
        try:
            from app.services.scenario_generation.consequence_generator import (
                generate_consequences_for_seeds
            )
            # Build entity lookup for URI-to-label resolution
            entity_lookup = {}
            if foundation:
                for entity_type in ['Obligations', 'Principles', 'Constraints', 'Capabilities']:
                    for entity in getattr(foundation, entity_type.lower(), []):
                        uri = getattr(entity, 'uri', '') or getattr(entity, 'entity_uri', '')
                        label = getattr(entity, 'label', '') or getattr(entity, 'entity_label', '')
                        if uri:
                            entity_lookup[uri] = {'label': label}

            # NarrativeResolution is a dataclass -- convert to dict for the generator
            resolution = {}
            if narrative_elements and hasattr(narrative_elements, 'resolution') and narrative_elements.resolution:
                resolution = narrative_elements.resolution.to_dict() if hasattr(
                    narrative_elements.resolution, 'to_dict'
                ) else {}

            generate_consequences_for_seeds(
                seeds=scenario_seeds,
                causal_links=causal_normative_links,
                resolution=resolution,
                entity_lookup=entity_lookup,
            )
            stages_completed.append('4.3b_consequences')
            logger.info(f"[Phase4] Stage 4.3b: Generated consequences for {len(scenario_seeds.branches)} branches")
        except Exception as e:
            logger.error(f"[Phase4] Stage 4.3b consequence generation failed: {e}")
            # Non-fatal: interactive exploration works without consequences (empty fields)
```

- [x] **Step 4: Run full test suite to verify no regressions**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/ -v --timeout=30`

Expected: All existing tests pass

- [x] **Step 5: Commit**

```bash
git add app/services/narrative/__init__.py tests/unit/test_consequence_dataclasses.py
git commit -m "feat: integrate consequence generator as Stage 4.3b in Phase 4 pipeline"
```

---

## Chunk 2: Service and Route Layer

### Task 4: Refactor InteractiveScenarioService to pure data reader

**Files:**
- Modify: `app/services/interactive_scenario_service.py`
- Test: `tests/unit/test_interactive_scenario_service.py` (modify)

Remove all LLM-related methods and add `get_analysis_data()`. The service becomes a thin layer over Phase 4 data.

- [x] **Step 1: Write test for get_analysis_data()**

Add to `tests/unit/test_interactive_scenario_service.py` (or create if the fixture structure requires it):

```python
# tests/unit/test_interactive_service_refactor.py
"""Tests for refactored InteractiveScenarioService (pure data reader)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.interactive_scenario_service import InteractiveScenarioService


@pytest.fixture
def service():
    return InteractiveScenarioService()


@pytest.fixture
def sample_phase4_data():
    """Phase 4 narrative data with consequence fields populated."""
    return {
        "scenario_seeds": {
            "opening_context": "You are an engineer.",
            "branches": [
                {
                    "branch_id": "branch_0",
                    "decision_maker_label": "Engineer",
                    "question": "Disclose or not?",
                    "context": "A conflict exists.",
                    "decision_point_uri": "dp_0",
                    "decision_maker_uri": "uri:eng",
                    "involved_obligation_uris": ["uri:obl1"],
                    "competing_obligation_labels": ["Duty of Candor", "Loyalty"],
                    "board_rationale": "Candor is paramount.",
                    "options": [
                        {
                            "option_id": "opt_0_0",
                            "label": "Disclose",
                            "description": "",
                            "is_board_choice": True,
                            "action_uris": [],
                            "consequence_narrative": "Disclosure leads to resolution.",
                            "consequence_obligations": ["Duty of Candor"],
                            "consequence_fluent_changes": {"initiated": ["Transparent"], "terminated": []},
                        },
                        {
                            "option_id": "opt_0_1",
                            "label": "Stay silent",
                            "description": "",
                            "is_board_choice": False,
                            "action_uris": [],
                            "consequence_narrative": "Silence risks discovery.",
                            "consequence_obligations": ["Loyalty"],
                            "consequence_fluent_changes": {"initiated": ["Hidden_Conflict"], "terminated": []},
                        },
                    ],
                },
            ],
            "canonical_path": ["Disclose"],
        },
        "narrative_elements": {
            "resolution": {
                "resolution_type": "violation",
                "summary": "Board found a violation.",
                "conclusions": [{"uri": "c1", "text": "Engineer should have disclosed."}],
            },
        },
    }


def test_get_analysis_data_builds_comparison(service, sample_phase4_data):
    """get_analysis_data builds a comparison of user choices vs board choices."""
    mock_session = MagicMock()
    mock_session.case_id = 1
    mock_session.choices = [
        MagicMock(
            decision_point_index=0,
            chosen_option_index=1,  # User chose "Stay silent" (not board choice)
            chosen_option_label="Stay silent",
            board_choice_index=0,
            board_choice_label="Disclose",
            matches_board_choice=False,
            time_spent_seconds=30,
        ),
    ]

    with patch.object(service, '_load_phase4_data', return_value=sample_phase4_data):
        analysis = service.get_analysis_data(mock_session)

    assert analysis["total_decisions"] == 1
    assert analysis["matches_with_board"] == 0
    assert len(analysis["decisions"]) == 1

    decision = analysis["decisions"][0]
    assert decision["user_choice"]["label"] == "Stay silent"
    assert decision["user_choice"]["consequence_narrative"] == "Silence risks discovery."
    assert decision["board_choice"]["label"] == "Disclose"
    assert decision["board_choice"]["consequence_narrative"] == "Disclosure leads to resolution."
    assert decision["board_rationale"] == "Candor is paramount."
    assert decision["matched"] is False
    assert len(decision["alternatives"]) == 0  # User chose one, board chose the other, no remaining

    assert analysis["resolution"]["summary"] == "Board found a violation."
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_interactive_service_refactor.py -v`

Expected: FAIL with `AttributeError: 'InteractiveScenarioService' object has no attribute 'get_analysis_data'`

- [x] **Step 3a: Remove all LLM methods from the service**

Delete these methods from `interactive_scenario_service.py`:
- `_get_llm_client` (lines 36-40)
- `_generate_consequences` (lines 284-357)
- `generate_final_analysis` (lines 363-411)
- `_generate_analysis_narrative` (lines 413-445)
- `_generate_option_label` (lines 542-588)
- `_generate_default_options` (lines 590-610)
- `_ensure_option_labels` (lines 514-540)
- `_load_event_calculus_rules` (lines 641-657)

Also remove `self.llm_client = None` from `__init__` and the imports `from app.utils.llm_utils import get_llm_client` and `from model_config import ModelConfig`.

- [x] **Step 3b: Add `_load_phase4_data()` method**

```python
def _load_phase4_data(self, case_id: int) -> Dict:
    """Load the full phase4_narrative JSON for a case."""
    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if prompt and prompt.raw_response:
        try:
            return json.loads(prompt.raw_response)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}
```

- [x] **Step 3c: Simplify `process_choice()` to record-only**

Replace the body of `process_choice()`. No LLM call, no fluent tracking. Populates board comparison fields from Phase 4 data at write time:

```python
def process_choice(self, session, chosen_option_index, time_spent_seconds=None):
    decision_points = self._load_decision_points(session.case_id)
    if session.current_decision_index >= len(decision_points):
        raise ValueError("No more decisions to make")

    dp = decision_points[session.current_decision_index]
    options = dp.get('options', [])
    if chosen_option_index >= len(options):
        raise ValueError(f"Invalid option index: {chosen_option_index}")

    chosen_option = options[chosen_option_index]

    # Idempotency: check for existing choice (page refresh)
    existing = ScenarioExplorationChoice.query.filter_by(
        session_id=session.id,
        decision_point_index=session.current_decision_index
    ).first()
    if existing:
        is_complete = (session.current_decision_index + 1) >= len(decision_points)
        return {'choice_recorded': True, 'is_complete': is_complete, 'already_existed': True}

    # Find board choice from Phase 4 data
    board_choice_index, board_choice_label = None, None
    for i, opt in enumerate(options):
        if opt.get('is_board_choice'):
            board_choice_index = i
            board_choice_label = opt.get('label', '')
            break

    choice = ScenarioExplorationChoice(
        session_id=session.id,
        decision_point_index=session.current_decision_index,
        decision_point_uri=dp.get('uri', ''),
        decision_point_label=dp.get('decision_maker_label', dp.get('label', '')),
        chosen_option_index=chosen_option_index,
        chosen_option_label=chosen_option.get('label', ''),
        chosen_option_uri=chosen_option.get('uri', ''),
        board_choice_index=board_choice_index,
        board_choice_label=board_choice_label,
        matches_board_choice=(chosen_option_index == board_choice_index),
        time_spent_seconds=time_spent_seconds,
    )
    db.session.add(choice)

    session.current_decision_index += 1
    session.last_activity_at = datetime.utcnow()
    is_complete = session.current_decision_index >= len(decision_points)
    if is_complete:
        session.status = 'completed'
        session.completed_at = datetime.utcnow()
    db.session.commit()

    return {'choice_recorded': True, 'is_complete': is_complete}
```

- [x] **Step 3d: Simplify `get_current_decision()` to include obligation labels**

```python
def get_current_decision(self, session):
    decision_points = self._load_decision_points(session.case_id)
    if session.current_decision_index >= len(decision_points):
        return None

    dp = decision_points[session.current_decision_index]
    context = ""
    if session.current_decision_index == 0:
        phase4_data = self._load_phase4_data(session.case_id)
        context = phase4_data.get('scenario_seeds', {}).get('opening_context', '')
    else:
        context = dp.get('context', '')

    return {
        'decision_index': session.current_decision_index,
        'total_decisions': len(decision_points),
        'decision_point': {
            'uri': dp.get('uri', ''),
            'label': dp.get('label', dp.get('decision_maker_label', '')),
            'question': dp.get('question', dp.get('description', '')),
            'decision_maker_label': dp.get('decision_maker_label', ''),
        },
        'options': [
            {'label': opt.get('label', ''), 'option_id': opt.get('option_id', '')}
            for opt in dp.get('options', [])
        ],
        'competing_obligation_labels': dp.get('competing_obligation_labels', []),
        'context': context,
    }
```

- [x] **Step 3e: Add `get_analysis_data()` and `get_all_decision_points_for_stepper()`**

```python
def get_analysis_data(self, session):
    """Build analysis comparison from Phase 4 data + session choices."""
    phase4_data = self._load_phase4_data(session.case_id)
    branches = phase4_data.get('scenario_seeds', {}).get('branches', [])
    resolution = phase4_data.get('narrative_elements', {}).get('resolution', {})

    decisions = []
    matches = 0
    for choice in session.choices:
        idx = choice.decision_point_index
        if idx >= len(branches):
            continue
        branch = branches[idx]
        options = branch.get('options', [])

        user_opt = options[choice.chosen_option_index] if choice.chosen_option_index < len(options) else {}
        board_opt, board_idx = {}, None
        for i, opt in enumerate(options):
            if opt.get('is_board_choice'):
                board_opt, board_idx = opt, i
                break

        matched = choice.matches_board_choice
        if matched:
            matches += 1

        alternatives = [
            {'label': opt.get('label', ''), 'consequence_narrative': opt.get('consequence_narrative', ''),
             'consequence_obligations': opt.get('consequence_obligations', [])}
            for i, opt in enumerate(options)
            if i != choice.chosen_option_index and i != board_idx
        ]

        decisions.append({
            'decision_index': idx,
            'decision_maker_label': branch.get('decision_maker_label', ''),
            'question': branch.get('question', ''),
            'matched': matched,
            'board_rationale': branch.get('board_rationale', ''),
            'competing_obligation_labels': branch.get('competing_obligation_labels', []),
            'user_choice': {
                'label': user_opt.get('label', ''),
                'consequence_narrative': user_opt.get('consequence_narrative', ''),
                'consequence_obligations': user_opt.get('consequence_obligations', []),
            },
            'board_choice': {
                'label': board_opt.get('label', ''),
                'consequence_narrative': board_opt.get('consequence_narrative', ''),
                'consequence_obligations': board_opt.get('consequence_obligations', []),
            },
            'alternatives': alternatives,
        })

    return {
        'session_uuid': session.session_uuid, 'case_id': session.case_id,
        'total_decisions': len(decisions), 'matches_with_board': matches,
        'decisions': decisions, 'resolution': resolution,
    }

def get_all_decision_points_for_stepper(self, case_id):
    """Minimal info for each decision point (for stepper display)."""
    return [
        {'index': i, 'decision_maker_label': dp.get('decision_maker_label', f'Decision {i+1}')}
        for i, dp in enumerate(self._load_decision_points(case_id))
    ]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_interactive_service_refactor.py -v`

Expected: PASS

- [x] **Step 5: Run existing tests to check for regressions**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/unit/test_interactive_scenario_service.py -v`

Expected: Some tests may fail if they mock removed methods. Update or remove tests that test LLM-dependent behavior. Tests that test session management and choice recording should still pass.

- [x] **Step 6: Commit**

```bash
git add app/services/interactive_scenario_service.py tests/unit/test_interactive_service_refactor.py tests/unit/test_interactive_scenario_service.py
git commit -m "refactor: strip LLM from InteractiveScenarioService, add get_analysis_data"
```

---

### Task 5: Update routes

**Files:**
- Modify: `app/routes/scenario_pipeline/step5_interactive.py`

- [x] **Step 1: Update auth decorators on all interactive routes**

Change all three `@auth_required_for_llm` decorators to `@auth_required_for_write`:
- `start_interactive_exploration` (line 33)
- `start_interactive_exploration_ajax` (line 59)
- `make_choice` (line 148)

Update the import line accordingly (replace `auth_required_for_llm` with `auth_required_for_write` if `auth_required_for_llm` is no longer imported elsewhere in the file).

Note: If study participants are unauthenticated, these may need to change to `@auth_optional` during study preparation (April). For now, `@auth_required_for_write` is correct for development. The spec acknowledges this as a study infrastructure decision to finalize later.

- [x] **Step 2: Simplify make_choice route**

Remove the inner consequence-generation provenance block (`prov.record_extraction_results` with `entity_type='interactive_choice_result'`). Keep the outer `prov.track_activity(activity_type='interaction', ...)` wrapper for study auditing, but change `agent_type` from `'user_interaction'` to `'user_interaction'` (unchanged) and remove the consequence preview from the results dict. The route should:
1. Get session and validate
2. Get choice from request
3. Track with `prov.track_activity(activity_type='interaction', agent_type='user_interaction', ...)`
4. Call `interactive_scenario_service.process_choice()` (now a simple data write)
5. Record minimal results in provenance: `{'chosen_option_index': ..., 'is_complete': ...}`
6. Redirect to next decision or summary page

- [x] **Step 3: Add interactive_summary route**

Add a new route after `interactive_analysis`:

```python
@bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>/summary')
@auth_optional
def interactive_summary(case_id, session_uuid):
    """Summary page between traversal and analysis (board reveal)."""
    case = Document.query.get_or_404(case_id)
    session = interactive_scenario_service.get_session(session_uuid)

    if not session or session.case_id != case_id:
        flash('Session not found', 'error')
        return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

    if session.status != 'completed':
        return redirect(url_for('step5.interactive_exploration',
                               case_id=case_id, session_uuid=session_uuid))

    choices_summary = session.get_choices_summary()
    pipeline_status = PipelineStatusService.get_step_status(case_id)

    return render_template(
        'scenarios/step5_summary.html',
        case=case,
        session=session,
        choices_summary=choices_summary,
        current_step=5,
        pipeline_status=pipeline_status,
    )
```

- [x] **Step 4: Update make_choice redirect to go to summary instead of analysis**

When `result['is_complete']` is True, redirect to `interactive_summary` instead of `interactive_analysis`.

- [x] **Step 5: Update interactive_analysis to use get_analysis_data()**

Remove the provenance-wrapped `generate_final_analysis()` block (lines 250-277 which use `agent_type='llm_model'`). Replace with:

```python
# For new sessions, build analysis from Phase 4 data (no LLM)
if session.final_analysis:
    analysis = session.final_analysis  # Legacy sessions
else:
    analysis = interactive_scenario_service.get_analysis_data(session)
```

No provenance tracking needed here -- analysis is a pure data read, not a generation step.

- [x] **Step 6: Commit**

```bash
git add app/routes/scenario_pipeline/step5_interactive.py
git commit -m "refactor: simplify routes, add summary page, remove LLM from choice processing"
```

---

## Chunk 3: UI Layer

### Task 6: Create traversal template and CSS

**Files:**
- Create: `app/templates/scenarios/step5_traversal.html`
- Create: `app/static/css/scenario-traversal.css`
- Modify: `app/templates/scenarios/base_step.html` (add CSS link)

- [x] **Step 1: Create scenario-traversal.css**

CSS for: decision-maker pill stepper, decision card styling, View Transition API crossfade with fallback, option card selection states.

Key selectors:
- `.scenario-stepper` -- flexbox row of pills
- `.scenario-stepper .step-pill` -- individual step pill
- `.scenario-stepper .step-pill.active` -- current step
- `.scenario-stepper .step-pill.completed` -- completed step
- `.scenario-stepper .step-pill.future` -- upcoming step
- `.decision-card` -- the single decision card
- `.option-card` -- selectable option within the card
- `.option-card.selected` -- selected option
- `::view-transition-old(decision-card)`, `::view-transition-new(decision-card)` -- transition pseudo-elements
- `.no-view-transitions .decision-card` -- opacity fallback

- [x] **Step 2: Create step5_traversal.html**

Extends `scenarios/base_step.html`. Blocks: `step_title`, `step_content`, `step_styles`, `step_scripts`.

Structure:
1. Stepper bar: loop over `decision_points` to render pills. Mark completed/active/future based on `current_decision.decision_index`.
2. Decision card: context block, question, competing obligation badges, option buttons, "Make This Choice" submit.
3. JS: View Transition API feature detection, form submission handler (POST choice, apply transition to next page load), option card click selection, time tracking.

Template receives: `case`, `session`, `current_decision`, `decision_points` (list of all decision point labels/makers for stepper), `previous_choices`.

- [x] **Step 3: Update route to render the new template**

In `step5_interactive.py`, change the `interactive_exploration` route to render `scenarios/step5_traversal.html` instead of `scenarios/step5_interactive.html`. Pass `decision_points` (list of dicts with `decision_maker_label` and `index`) for the stepper.

- [x] **Step 4: Link CSS in base_step.html or include in template**

Add `<link rel="stylesheet" href="{{ url_for('static', filename='css/scenario-traversal.css') }}">` in the `step_styles` block of the traversal template.

- [x] **Step 5: Commit**

```bash
git add app/templates/scenarios/step5_traversal.html app/static/css/scenario-traversal.css app/routes/scenario_pipeline/step5_interactive.py
git commit -m "feat: add traversal template with decision-maker stepper and view transitions"
```

---

### Task 7: Create summary template

**Files:**
- Create: `app/templates/scenarios/step5_summary.html`

- [x] **Step 1: Create step5_summary.html**

Extends `scenarios/base_step.html`. Simple layout:
1. Header: "You have completed all N decisions."
2. Choices list: numbered list of decision labels + user's choice at each (plain text, no color coding, no board comparison).
3. "View Analysis" button linking to `interactive_analysis` route.

Template receives: `case`, `session`, `choices_summary`.

- [x] **Step 2: Commit**

```bash
git add app/templates/scenarios/step5_summary.html
git commit -m "feat: add post-traversal summary template"
```

---

### Task 8: Create analysis template with mini-tree and tabbed cards

**Files:**
- Create: `app/templates/scenarios/step5_branching_analysis.html`
- Modify: `app/static/css/scenario-traversal.css` (add tree and tab styles)

This is the most complex template. It has four sections: mini decision tree, stats bar, tabbed detail cards (one per decision), and resolution section.

- [x] **Step 1: Add CSS for mini decision tree and analysis cards**

Append to `scenario-traversal.css`:
- `.decision-tree` -- flexbox row
- `.decision-tree .tree-node` -- circle/rounded rect
- `.decision-tree .tree-connector` -- line between nodes (pseudo-element)
- `.decision-tree .tree-node.match` -- green
- `.decision-tree .tree-node.diverge` -- amber
- `.decision-tree .tree-node:hover` -- pointer cursor, slight lift
- `@media (max-width: 575.98px)` -- vertical stack layout for tree

- [x] **Step 2: Create step5_branching_analysis.html**

Extends `scenarios/base_step.html`. Four sections:

**Section 1 -- Mini Decision Tree:**
```html
<div class="decision-tree d-flex justify-content-center align-items-center gap-0 mb-4">
    {% for decision in analysis.decisions %}
    <div class="tree-node {{ 'match' if decision.matched else 'diverge' }}"
         data-target="decision-{{ loop.index0 }}"
         title="Decision {{ loop.index }}: {{ decision.decision_maker_label }}">
        <span class="tree-step-num">{{ loop.index }}</span>
    </div>
    {% if not loop.last %}
    <div class="tree-connector"></div>
    {% endif %}
    {% endfor %}
</div>
```

**Section 2 -- Stats Bar:**
Single line: `{{ analysis.matches_with_board }} of {{ analysis.total_decisions }} aligned with board`

**Section 3 -- Tabbed Detail Cards:**
One card per decision, stacked vertically. Each card uses Bootstrap tabs:
- Tab "Your Choice": option label + `consequence_narrative` + obligation badges
- Tab "Board's Choice": same structure, or "Same as your choice" if matched
- Tab "Alternative: [label]": for each remaining option not chosen by user or board
- Collapsed "Board's Rationale" section within Board's Choice tab

**Section 4 -- Resolution:**
Board's resolution text, resolution type badge, conclusions list.

Template receives: `case`, `session`, `analysis` (from `get_analysis_data()`).

**JS:** Click handler on tree nodes to scroll to corresponding card. Smooth scroll behavior.

- [x] **Step 3: Update route to render new analysis template**

In `step5_interactive.py`, change the `interactive_analysis` route to render `scenarios/step5_branching_analysis.html`.

- [x] **Step 4: Commit**

```bash
git add app/templates/scenarios/step5_branching_analysis.html app/static/css/scenario-traversal.css app/routes/scenario_pipeline/step5_interactive.py
git commit -m "feat: add branching analysis template with decision tree and tabbed comparison"
```

---

## Chunk 4: Integration and Batch Processing

### Task 9: Batch consequence generation script

**Files:**
- Create: `scripts/generate_consequences.py`

A standalone script that loads existing Phase 4 data for specified cases (or all cases with `phase4_narrative` data) and runs the consequence generator, updating the stored JSON in place.

- [x] **Step 1: Create the batch script**

```python
# scripts/generate_consequences.py
"""
Batch generate consequence data for existing cases.

Usage:
    python scripts/generate_consequences.py              # All cases with Phase 4 data
    python scripts/generate_consequences.py --case-ids 7 25 102  # Specific cases
    python scripts/generate_consequences.py --dry-run    # Preview without saving
"""
import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, ExtractionPrompt, TemporaryRDFStorage
from app.services.scenario_generation.consequence_generator import (
    generate_consequences_for_seeds,
)
from app.services.narrative.scenario_seed_generator import (
    ScenarioSeeds, ScenarioBranch, ScenarioOption,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def load_seeds_from_json(data: dict) -> ScenarioSeeds:
    """Reconstruct ScenarioSeeds from stored JSON."""
    seeds_data = data.get('scenario_seeds', {})
    branches = []
    for b in seeds_data.get('branches', []):
        options = [
            ScenarioOption(
                option_id=o.get('option_id', ''),
                label=o.get('label', ''),
                description=o.get('description', ''),
                action_uris=o.get('action_uris', []),
                is_board_choice=o.get('is_board_choice', False),
                leads_to=o.get('leads_to'),
                # Preserve existing consequence data if present
                consequence_narrative=o.get('consequence_narrative', ''),
                consequence_obligations=o.get('consequence_obligations', []),
                consequence_fluent_changes=o.get('consequence_fluent_changes', {}),
            )
            for o in b.get('options', [])
        ]
        branches.append(ScenarioBranch(
            branch_id=b.get('branch_id', ''),
            context=b.get('context', ''),
            question=b.get('question', ''),
            decision_point_uri=b.get('decision_point_uri', ''),
            decision_maker_uri=b.get('decision_maker_uri', ''),
            decision_maker_label=b.get('decision_maker_label', ''),
            involved_obligation_uris=b.get('involved_obligation_uris', []),
            options=options,
            # Preserve existing consequence data if present
            board_rationale=b.get('board_rationale', ''),
            competing_obligation_labels=b.get('competing_obligation_labels', []),
        ))

    return ScenarioSeeds(
        case_id=seeds_data.get('case_id', 0),
        opening_context=seeds_data.get('opening_context', ''),
        initial_state_description=seeds_data.get('initial_state_description', ''),
        protagonist_uri=seeds_data.get('protagonist_uri', ''),
        protagonist_label=seeds_data.get('protagonist_label', ''),
        branches=branches,
        canonical_path=seeds_data.get('canonical_path', []),
        transformation_type=seeds_data.get('transformation_type', ''),
    )


def main():
    parser = argparse.ArgumentParser(description='Batch generate consequence data')
    parser.add_argument('--case-ids', nargs='+', type=int, help='Specific case IDs')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        query = ExtractionPrompt.query.filter_by(concept_type='phase4_narrative')
        if args.case_ids:
            query = query.filter(ExtractionPrompt.case_id.in_(args.case_ids))

        prompts = query.order_by(ExtractionPrompt.case_id).all()
        # Deduplicate: keep latest per case_id
        seen = {}
        for p in prompts:
            if p.case_id not in seen or p.created_at > seen[p.case_id].created_at:
                seen[p.case_id] = p
        prompts = list(seen.values())

        logger.info(f"Processing {len(prompts)} cases")

        for prompt in prompts:
            try:
                data = json.loads(prompt.raw_response)
                seeds = load_seeds_from_json(data)

                if not seeds.branches:
                    logger.warning(f"Case {prompt.case_id}: no branches, skipping")
                    continue

                # Check if consequences already generated
                first_opt = seeds.branches[0].options[0] if seeds.branches[0].options else None
                if first_opt and first_opt.consequence_narrative:
                    logger.info(f"Case {prompt.case_id}: consequences already present, skipping")
                    continue

                # Load supporting data
                causal_links_raw = TemporaryRDFStorage.query.filter_by(
                    case_id=prompt.case_id, extraction_type='causal_normative_link'
                ).all()
                causal_links = [
                    link.rdf_json_ld if link.rdf_json_ld else {}
                    for link in causal_links_raw
                ]

                resolution = data.get('narrative_elements', {}).get('resolution', {})

                entity_lookup = {}
                for etype in ['Obligations', 'Principles', 'Constraints']:
                    entities = TemporaryRDFStorage.query.filter_by(
                        case_id=prompt.case_id, entity_type=etype
                    ).all()
                    for e in entities:
                        if e.entity_uri:
                            entity_lookup[e.entity_uri] = {'label': e.entity_label or ''}

                logger.info(f"Case {prompt.case_id}: {len(seeds.branches)} branches, "
                           f"{len(causal_links)} causal links")

                if args.dry_run:
                    logger.info(f"  [DRY RUN] Would generate consequences")
                    continue

                generate_consequences_for_seeds(
                    seeds=seeds,
                    causal_links=causal_links,
                    resolution=resolution,
                    entity_lookup=entity_lookup,
                )

                # Write back to JSON
                data['scenario_seeds'] = seeds.to_dict()
                prompt.raw_response = json.dumps(data)
                db.session.commit()

                logger.info(f"Case {prompt.case_id}: consequences generated and saved")

            except Exception as e:
                logger.error(f"Case {prompt.case_id}: failed - {e}")
                db.session.rollback()

        logger.info("Done")


if __name__ == '__main__':
    main()
```

- [x] **Step 2: Test with dry-run on a single case**

Run: `cd /home/chris/onto/proethica && source venv-proethica/bin/activate && python scripts/generate_consequences.py --case-ids 102 --dry-run`

Expected: Output showing case 102 has N branches, M causal links, and "[DRY RUN] Would generate consequences"

- [x] **Step 3: Run on a single case for real**

Run: `cd /home/chris/onto/proethica && source venv-proethica/bin/activate && python scripts/generate_consequences.py --case-ids 102`

Expected: "Case 102: consequences generated and saved"

- [x] **Step 4: Verify the stored data**

Run: `cd /home/chris/onto/proethica && source venv-proethica/bin/activate && python -c "
import json
from app import create_app
from app.models import ExtractionPrompt
app = create_app()
with app.app_context():
    p = ExtractionPrompt.query.filter_by(case_id=102, concept_type='phase4_narrative').order_by(ExtractionPrompt.created_at.desc()).first()
    data = json.loads(p.raw_response)
    b = data['scenario_seeds']['branches'][0]
    print(f'Board rationale: {b.get(\"board_rationale\", \"MISSING\")[:100]}')
    print(f'Competing labels: {b.get(\"competing_obligation_labels\", \"MISSING\")}')
    for opt in b['options']:
        print(f'  {opt[\"label\"]}: {opt.get(\"consequence_narrative\", \"MISSING\")[:80]}')
"`

Expected: All fields populated with non-empty strings.

- [x] **Step 5: Commit**

```bash
git add scripts/generate_consequences.py
git commit -m "feat: add batch consequence generation script for existing cases"
```

---

### Task 10: End-to-end smoke test

**Files:**
- Test: `tests/integration/test_interactive_traversal.py` (create)

- [x] **Step 1: Write integration test**

```python
# tests/integration/test_interactive_traversal.py
"""End-to-end test for the interactive scenario traversal flow."""
import pytest
from app import create_app
from app.models import db


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_full_traversal_flow(client):
    """Start session -> make choices -> view summary -> view analysis."""
    # Find a case with phase4_narrative data
    from app.models import ExtractionPrompt
    with client.application.app_context():
        prompt = ExtractionPrompt.query.filter_by(
            concept_type='phase4_narrative'
        ).first()
        if not prompt:
            pytest.skip("No phase4_narrative data available")
        case_id = prompt.case_id

    # Routes are under /scenario_pipeline blueprint prefix
    prefix = '/scenario_pipeline'

    # Start session
    response = client.post(f'{prefix}/case/{case_id}/step5/interactive/start', follow_redirects=False)
    assert response.status_code in (302, 303)
    location = response.headers.get('Location', '')
    assert '/step5/interactive/' in location

    # Extract session UUID from redirect URL
    session_uuid = location.split('/step5/interactive/')[-1].rstrip('/')

    # Load first decision
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}')
    assert response.status_code == 200
    assert b'decision' in response.data.lower()

    # Make choices until complete (max 10 to avoid infinite loop)
    for i in range(10):
        response = client.post(
            f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/choose',
            data={'option_index': 0, 'time_spent_seconds': 5},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        location = response.headers.get('Location', '')

        if '/summary' in location:
            break  # Traversal complete

    # View summary
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/summary')
    assert response.status_code == 200

    # View analysis
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/analysis')
    assert response.status_code == 200
```

- [x] **Step 2: Run integration test**

Run: `cd /home/chris/onto/proethica && PYTHONPATH=/home/chris/onto:$PYTHONPATH pytest tests/integration/test_interactive_traversal.py -v`

Expected: PASS (requires at least one case with Phase 4 data in the database)

- [x] **Step 3: Manual browser test**

Start the app and walk through a case manually:
```bash
cd /home/chris/onto/proethica && source venv-proethica/bin/activate && python run.py
```
Navigate to `http://localhost:5000/case/102/step5/interactive/start` (POST via the case page UI) and verify:
- Stepper shows decision-maker labels
- Cards display questions and options
- Choosing advances to next card
- Summary page shows choices
- Analysis page shows tree, tabs, and consequence data

- [x] **Step 4: Commit**

```bash
git add tests/integration/test_interactive_traversal.py
git commit -m "test: add end-to-end integration test for interactive traversal"
```

---

## Implementation Order Summary

| Task | Chunk | Description | Dependencies |
|------|-------|-------------|--------------|
| 1 | Data | Extend dataclasses with consequence fields | None |
| 2 | Data | Create consequence generator module | Task 1 |
| 3 | Data | Integrate into Phase 4 pipeline | Task 2 |
| 4 | Service | Refactor service to pure data reader | Task 1 |
| 5 | Service | Update routes (auth, summary, analysis) | Task 4 |
| 6 | UI | Traversal template + CSS | Task 5 |
| 7 | UI | Summary template | Task 5 |
| 8 | UI | Analysis template (tree + tabs) | Task 5 |
| 9 | Integration | Batch consequence generation script | Task 2 |
| 10 | Integration | End-to-end smoke test | Tasks 6-9 |

Tasks 1-3 are sequential (data layer). Tasks 4-5 are sequential (service layer). Tasks 6-8 can be parallelized (independent templates, same route file). Task 9 is independent of 4-8 (only needs the generator). Task 10 requires everything.
