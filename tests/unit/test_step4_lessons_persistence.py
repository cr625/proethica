"""Case 8 (NSPE 24-1) review, lesson L6: the Q&C run persists the
question-conclusion linker call (concept_type qc_link) next to the analyzer
prompts, and no save path slices prompt_text or raw_response (rows 8616 and
8617 of case 8 were cut at 10000 characters by a slice removed in 35a80006).

Hermetic: ExtractionPrompt rows are constructed in memory, never added to a
session.
"""
import re
from pathlib import Path
from types import SimpleNamespace

from app.services.step4_synthesis.qc_prompt_rows import build_qc_prompt_rows, QC_LINK_CONCEPT_TYPE

REPO = Path(__file__).resolve().parents[2]

LONG_PROMPT = "PROMPT " * 4000       # 28000 chars, well past the former 10000 slice
LONG_RESPONSE = "RESPONSE " * 3000   # 27000 chars


def _rows():
    qa = SimpleNamespace(last_prompt=LONG_PROMPT + "Q", last_response=LONG_RESPONSE + "Q")
    ca = SimpleNamespace(last_prompt=LONG_PROMPT + "C", last_response=LONG_RESPONSE + "C")
    linker = SimpleNamespace(last_prompt=LONG_PROMPT + "L", last_response=LONG_RESPONSE + "L")
    return build_qc_prompt_rows(8, "sess", qa, ca, linker, questions_total=17, conclusions_total=17,
                                board_q_count=2, board_c_count=2, qc_links_count=20, llm_model="model-x")


def test_linker_call_is_persisted_as_a_qc_link_row():
    rows = _rows()
    by_type = {r.concept_type: r for r in rows}
    assert set(by_type) == {"ethical_question", "ethical_conclusion", QC_LINK_CONCEPT_TYPE}
    link = by_type[QC_LINK_CONCEPT_TYPE]
    assert link.case_id == 8 and link.step_number == 4 and link.section_type == "synthesis"
    assert link.extraction_session_id == "sess" and link.llm_model == "model-x"
    assert link.prompt_text == LONG_PROMPT + "L"
    assert link.raw_response == LONG_RESPONSE + "L"
    assert '"qc_links": 20' in link.results_summary


def test_save_paths_never_slice_prompt_or_response():
    for r in _rows():
        assert len(r.prompt_text) > 10000 and len(r.raw_response) > 10000
        assert r.prompt_text.endswith(("Q", "C", "L")) and r.raw_response.endswith(("Q", "C", "L"))


def test_no_linker_prompt_means_no_qc_link_row():
    qa = SimpleNamespace(last_prompt="q", last_response="")
    ca = SimpleNamespace(last_prompt="c", last_response="")
    linker = SimpleNamespace(last_prompt=None, last_response=None)
    rows = build_qc_prompt_rows(8, "s", qa, ca, linker, questions_total=1, conclusions_total=1,
                                board_q_count=1, board_c_count=1, qc_links_count=0, llm_model="m")
    assert [r.concept_type for r in rows] == ["ethical_question", "ethical_conclusion"]
    assert rows[0].prompt_text == "q" and rows[0].raw_response == ""


_SLICE = re.compile(r"(prompt_text|raw_response)\s*=\s*[^,\n]*\[\s*:\s*\d+\s*\]")

SAVE_SITES = [
    "app/services/step4_synthesis/step4_synthesis_service.py",
    "app/services/step4_synthesis/qc_prompt_rows.py",
    "app/services/step4_synthesis/step4_data_helpers.py",
    "app/services/narrative/trace_capture.py",
    "app/services/entity/entity_graph_service.py",
    "app/routes/scenario_pipeline/step4/qc_extraction.py",
    "app/routes/scenario_pipeline/step4/phase3.py",
    "app/routes/scenario_pipeline/step4/phase4.py",
    "app/routes/scenario_pipeline/step4/rich_analysis.py",
    "app/routes/scenario_pipeline/step4/transformation.py",
    "app/routes/scenario_pipeline/step4/provisions.py",
    "app/routes/scenario_pipeline/step4/precedents.py",
]


def test_extraction_prompt_save_sites_carry_no_slice():
    """Source guard for the 35a80006 fix: an ExtractionPrompt text column is
    never assigned a sliced expression at any Step-4 save site."""
    offenders = []
    for rel in SAVE_SITES:
        path = REPO / rel
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if _SLICE.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "\n".join(offenders)
