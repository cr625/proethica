"""
Citation-designator guard on the cross-pass semantic dedup (batch-2 review).

Distinct citations embed nearly identically ('BER Case 62-21' ~ 'BER Case
62-7' at cos 0.994), so the cosine merge collapsed two of case 143's four
cited precedents. Labels whose designator sets (case numbers, provision
codes) differ are never merged; designator-free labels keep the old behavior.
"""
from unittest.mock import MagicMock, patch

import app.services.entity.rdf_storage_service as rss


def test_label_designators_extraction():
    f = rss._label_designators
    assert f("BER Case 62-21") == frozenset({"62-21"})
    assert f("Cases 65-9 and 73-9 cited") == frozenset({"65-9", "73-9"})
    assert f("NSPE Code II.3.a") == frozenset({"II.3.A"})
    assert f("Public Welfare Obligation") == frozenset()


def _match(label, cand_label, sim=0.99):
    cand = MagicMock()
    cand.entity_label = cand_label
    cand.entity_definition = ""
    query = MagicMock()
    query.filter.return_value.all.return_value = [cand]
    with patch.object(rss, "TemporaryRDFStorage") as storage, \
         patch.object(rss, "_embed_text", return_value=(1.0, 0.0)):
        storage.query = query
        with patch("app.services.embedding.similarity_utils.cosine_similarity_list",
                   return_value=sim):
            return rss._find_semantic_match(143, label, "", "Resources")


def test_different_case_numbers_never_merge():
    assert _match("BER Case 62-21", "BER Case 62-7") is None
    assert _match("BER Case 63-5", "BER Case 62-7") is None


def test_designator_bearing_never_merges_with_designator_free():
    assert _match("BER Case 62-7", "Prior board precedent") is None


def test_same_designator_and_free_labels_still_merge():
    assert _match("BER Case 62-7 Precedent", "BER Case 62-7") is not None
    assert _match("Public Welfare Duty", "Paramount Public Welfare Duty") is not None
