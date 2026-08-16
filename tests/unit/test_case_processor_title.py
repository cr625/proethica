"""Title-selection guard in case_url_processor.case_processor: a title that is
only the BER case number ("Case Number 58-1") must not be preferred over a
descriptive title (cases 90 and 102 were ingested that way from old PDFs)."""
import pytest

from app.services.case_url_processor.case_processor import is_number_only_title


@pytest.mark.parametrize('title', [
    'Case Number 58-1', 'BER Case 60-3', 'Case 24-2', ' case number: 12-4 ', 'NSPE BER Case No. 97-13',
])
def test_number_only_titles(title):
    assert is_number_only_title(title)


@pytest.mark.parametrize('title', [
    'Case 24-2: Use of AI in Engineering', 'Use of Artificial Intelligence in Engineering Practice', '', None,
])
def test_descriptive_titles(title):
    assert not is_number_only_title(title)
