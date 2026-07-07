"""Live-path guard for extraction_graph.pydantic_to_rdf_data (A/E properties review
regression). The 2026-07-07 dead-orchestrator deletion accidentally swallowed the
module constants the LIVE conversion path reads (_CONCEPT_CATEGORY_FIELD,
_CORE_PARENT); no test exercised the function, so every Pass-1/2 store failed at
runtime with NameError while the suite stayed green. This calls the real function
end to end for a role candidate + individual.
"""
from app.services.extraction.extraction_graph import pydantic_to_rdf_data
from app.services.extraction.schemas import (
    CandidateRoleClass, RoleIndividual, MatchDecision,
)


def _md():
    return MatchDecision(matches_existing=False, confidence=0.9, reasoning="new")


def test_role_class_and_individual_convert():
    cls = CandidateRoleClass(
        label="Test Engineer Role",
        definition="A test-only engineering role.",
        match_decision=_md(),
    )
    ind = RoleIndividual(
        name="Engineer T", role_classes=["Test Engineer Role"],
        match_decision=_md(),
    )
    out = pydantic_to_rdf_data(
        classes=[cls], individuals=[ind], concept_type="roles",
        case_id=999, section_type="facts", step_number=1,
    )
    assert out["new_classes"] and out["new_individuals"]
    assert out["new_classes"][0]["label"] == "Test Engineer Role"
