"""Decade and year derivation for the case TTL header: the NSPE two-digit-year
century pivot lives in app/utils/nspe_case_number.py and case_header.decade_from_case_number
falls back to the document year when the case number is not of the form YY-N."""
import pytest

from app.services.commit.case_header import decade_from_case_number
from app.utils.nspe_case_number import year_from_case_number


@pytest.mark.parametrize('case_number, year, expected', [
    ('24-2', None, '2020s'),
    ('58-1', None, '1950s'),
    ('50-1', None, '1950s'),
    ('49-1', None, '2040s'),
    ('76-4-1', 1976, '1970s'),
    (None, '2024-05', '2020s'),
    ('abc', None, None),
    (None, 'n/a', None),
    (None, 1899, None),
    (None, 2100, None),
])
def test_decade_from_case_number(case_number, year, expected):
    assert decade_from_case_number(case_number, year) == expected


@pytest.mark.parametrize('case_number, expected', [
    ('24-2', 2024),
    ('58-1', 1958),
    (' 97-13 ', 1997),
    ('24-2-1', None),
    ('BER 24-2', None),
    (None, None),
])
def test_year_from_case_number(case_number, expected):
    assert year_from_case_number(case_number) == expected
