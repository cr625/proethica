"""Case 24-1 review lesson L6 on the obligation-engagement pass.

The deterministic reconciliation and the prompt assembly are tested without a
database or a model: the engagement template is stubbed, and the reconcile step
is driven with hand-built contexts.
"""
from app.services.extraction import obligation_engagement as oe
from app.services.extraction.obligation_engagement_apply import _reconcile_to_pool
from app.services.extraction.schemas import PerActionEngagement


def _ctx(label, fulfills, violates=(), raises=(), modality="performed", description=""):
    return oe.ActionEngagementContext(
        iri=f"http://proethica.org/ontology/case/8#Action_{label.replace(' ', '_')}",
        label=label, description=description, sequence=1,
        fulfills=list(fulfills), violates=list(violates), raises=list(raises),
        modality=modality)


def _pa(ctx, fulfills=(), violates=(), raises=()):
    return PerActionEngagement(action_iri=ctx.iri, fulfills=list(fulfills),
                               violates=list(violates), raises=list(raises))


def test_prescribed_action_fulfils_nothing():
    """Refusal_to_Acquiesce ("Engineer L must not continue work", "Present, unresolved
    endpoint") was stored as performed with fulfillsObligation edges. A prescribed
    action's fulfills land in raises whatever the model answered."""
    ctx = _ctx("Refusal to Acquiesce", fulfills=["Public Safety Duty"],
               raises=["Faithful Agent Duty"], modality="prescribed")
    stats = {}
    f, v, r = _reconcile_to_pool(ctx, _pa(ctx, fulfills=["Public Safety Duty"],
                                          raises=["Faithful Agent Duty"]), stats=stats)
    assert f == []
    assert v == []
    assert r == ["Public Safety Duty", "Faithful Agent Duty"]
    assert stats == {"prescribed_fulfills_demoted": 1}


def test_met_obligation_cited_by_the_action_stays_fulfilled():
    """Risk_Notification discharged two disclosure duties (complianceStatus met, the
    notification quoted as text reference); the engagement pass had moved one to
    raised. A met status the action's text references attest cannot be contradicted."""
    ctx = _ctx("Risk Notification", fulfills=["Duty to Disclose Runoff Risk",
                                               "Duty to Inform the Client"])
    statuses = {
        "duty to disclose runoff risk": oe.ObligationStatusContext(
            "Duty to Disclose Runoff Risk", "met",
            ["Engineer L notified Client X of the runoff risk"]),
        "duty to inform the client": oe.ObligationStatusContext(
            "Duty to Inform the Client", "met", []),   # no refs: the met judgment stands
    }
    pa = _pa(ctx, raises=["Duty to Disclose Runoff Risk", "Duty to Inform the Client"])
    stats = {}
    f, v, r = _reconcile_to_pool(ctx, pa, statuses=statuses, stats=stats)
    assert f == ["Duty to Disclose Runoff Risk", "Duty to Inform the Client"]
    assert r == []
    assert stats == {"met_fulfills_restored": 2}


def test_unmet_or_otherwise_attested_obligations_follow_the_model():
    ctx = _ctx("Risk Notification", fulfills=["Duty to Disclose Runoff Risk", "Duty of Care"])
    statuses = {
        # unmet: the model's move to raises stands
        "duty to disclose runoff risk": oe.ObligationStatusContext(
            "Duty to Disclose Runoff Risk", "unmet",
            ["Engineer L notified Client X of the runoff risk"]),
        # met, but the text references cite another action
        "duty of care": oe.ObligationStatusContext(
            "Duty of Care", "met", ["Client X refused the added safeguards"]),
    }
    pa = _pa(ctx, raises=["Duty to Disclose Runoff Risk", "Duty of Care"])
    stats = {}
    f, v, r = _reconcile_to_pool(ctx, pa, statuses=statuses, stats=stats)
    assert f == []
    assert r == ["Duty to Disclose Runoff Risk", "Duty of Care"]
    assert stats == {}


def test_reconcile_still_drops_extras_and_restores_drops():
    ctx = _ctx("Action A", fulfills=["O1", "O2"])
    f, v, r = _reconcile_to_pool(ctx, _pa(ctx, fulfills=["O1"], raises=["O3 carried in"]))
    assert f == ["O1", "O2"]      # O2 dropped by the model is restored to its bucket
    assert r == []                # O3 is not in the pool


class _StubTemplate:
    def render(self, **kw):
        return kw["actions_block"]


def test_prompt_carries_modality_and_obligation_status(monkeypatch):
    monkeypatch.setattr(oe, "_load_obligation_engagement_template", lambda: _StubTemplate())
    actions = [_ctx("Refusal to Acquiesce", fulfills=["Public Safety Duty"], modality="prescribed",
                    description="Per the BER's conclusion, Engineer L must not continue work"),
               _ctx("Risk Notification", fulfills=["Duty to Disclose Runoff Risk"])]
    statuses = [oe.ObligationStatusContext("Duty to Disclose Runoff Risk", "met",
                                           ["Engineer L notified Client X of the runoff risk"])]
    prompt = oe.build_user_prompt(8, "Case 24-1", actions, "", obligations=statuses)
    assert "Modality: prescribed" in prompt
    assert "Modality: performed" in prompt
    assert "OBLIGATION STATUS" in prompt
    assert "Duty to Disclose Runoff Risk: complianceStatus=met" in prompt
    assert "text reference: Engineer L notified Client X of the runoff risk" in prompt
    assert "PRESCRIBED action" in prompt
    # Without status contexts the prompt stays as before (no status block).
    bare = oe.build_user_prompt(8, "Case 24-1", actions, "")
    assert "OBLIGATION STATUS" not in bare
    assert "Modality: prescribed" in bare


def test_extractor_holds_the_status_context():
    statuses = [oe.ObligationStatusContext("Duty A", "met", [])]
    ext = oe.ObligationEngagementExtractor(obligations=statuses)
    assert ext.obligation_statuses == statuses
    assert oe.ObligationEngagementExtractor().obligation_statuses is None
