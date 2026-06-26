"""Role classes must end in 'Role' at commit (deterministic hard enforcement).

The extraction prompt only soft-biases the convention; OntServeCommitService applies it
deterministically so a suffixless extraction maps onto the canonical promoted class.
"""
from app.services.commit.ontserve_commit_service import OntServeCommitService

_f = OntServeCommitService._enforce_role_suffix


def test_appends_role_to_uri_and_label_when_missing():
    assert _f("DesignEngineer", "Design Engineer", "Role") == (
        "DesignEngineerRole", "Design Engineer Role")


def test_idempotent_when_already_suffixed():
    assert _f("EngineerRole", "Engineer Role", "Role") == ("EngineerRole", "Engineer Role")


def test_noop_for_non_role_categories():
    assert _f("RiskState", "Risk State", "State") == ("RiskState", "Risk State")
    assert _f("Foo", "Foo", None) == ("Foo", "Foo")
