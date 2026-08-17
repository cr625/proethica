"""One rule for the year encoded in an NSPE BER case number.

NSPE numbers Board of Ethical Review cases YY-N by the year of the decision,
with a two-digit year. The century pivot is 50: a two-digit year >= 50 is
19YY (the earliest cases date from 1958), otherwise 20YY. Case listing,
NSPE extraction and the case TTL header (decade) resolve the year through
this module rather than each keeping its own pivot.
"""
import re
from typing import Optional

CASE_NUMBER_RE = re.compile(r'^\s*(\d{2})-\d+\s*$')


def year_from_two_digit(yy: int) -> int:
    """The century pivot: 58 -> 1958, 24 -> 2024, 49 -> 2049."""
    return 1900 + yy if yy >= 50 else 2000 + yy


def year_from_case_number(case_number) -> Optional[int]:
    """'24-2' -> 2024; '58-1' -> 1958; None when the value is not of the form
    YY-N (surrounding whitespace tolerated)."""
    if case_number is None:
        return None
    m = CASE_NUMBER_RE.match(str(case_number))
    if not m:
        return None
    return year_from_two_digit(int(m.group(1)))
