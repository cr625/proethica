"""Case-independent NSPE provision lookup API (app/routes/provisions_api.py),
backing the shared CaseCard provision popovers (UI normalization 2026-07-19).
The map loader parses the co-located NSPE Code TTL; these tests pin the
code -> display/text/url contract and the graceful degrade for values that
are not modern NSPE codes (historical Canons, duty names)."""
import pytest

from app.routes.provisions_api import _load_provision_map


def test_provision_map_loads_from_ttl():
    m = _load_provision_map()
    assert 'II.1.a' in m
    assert m['II.1.a']['text'].startswith("If engineers' judgment is overruled")
    assert m['II.1.a']['label'] == 'Rules of Practice II.1.a'
    assert 'Preamble' in m


def test_info_endpoint_resolves_and_degrades(client):
    resp = client.get('/api/provisions/info?codes=II.1.a,NSPE%20I.4.,Canon%203')
    assert resp.status_code == 200
    data = resp.get_json()

    assert data['II.1.a']['display_code'] == 'II.1.a'
    assert data['II.1.a']['url'].endswith('/entity/NSPE Code of Ethics/II_1_a')
    assert data['II.1.a']['text']

    # Raw spelling with prefix + trailing dot normalizes to the identifier.
    assert data['NSPE I.4.']['display_code'] == 'I.4'
    assert data['NSPE I.4.']['text']

    # Historical Canon: no modern identifier, renders as a plain tag.
    assert data['Canon 3']['display_code'] is None
    assert data['Canon 3']['url'] is None


def test_info_endpoint_empty_and_capped(client):
    assert client.get('/api/provisions/info').get_json() == {}
    too_many = ','.join(f'I.{i}' for i in range(101))
    assert client.get(f'/api/provisions/info?codes={too_many}').status_code == 400
