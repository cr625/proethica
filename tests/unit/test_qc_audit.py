"""Tests for scripts/analysis/run_qc_audit.py -- QC check logic.

Tests the pure-logic V4, V6, V7 checks without database.
V0, V1, V8, V9 require DB queries and are tested separately in integration tests.
"""
import re
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.analysis.run_qc_audit import (
    REQUIRED_TYPES,
    EMPIRICAL_RANGES,
    check_v7,
    run_audit,
)


# ===========================================================================
# V7: Count Sanity (accepts counts dict directly -- no DB needed)
# ===========================================================================

class TestCheckV7:
    """V7 count sanity check against empirical ranges."""

    def test_all_in_range_passes(self):
        """Counts within empirical ranges produce PASS."""
        counts = {t: (lo + hi) // 2 for t, (lo, hi) in EMPIRICAL_RANGES.items()}
        result = check_v7(999, counts)
        assert result['status'] == 'PASS'
        assert result['check_id'] == 'V7'
        assert len(result['details']['out_of_range']) == 0

    def test_below_range_flagged(self):
        """Count below minimum is flagged as INFO."""
        counts = {t: (lo + hi) // 2 for t, (lo, hi) in EMPIRICAL_RANGES.items()}
        counts['roles'] = 1  # Well below minimum of 6
        result = check_v7(999, counts)
        assert result['status'] == 'INFO'
        oor = result['details']['out_of_range']
        assert len(oor) == 1
        assert oor[0]['type'] == 'roles'
        assert oor[0]['deviation'] == 'below'

    def test_above_range_flagged(self):
        """Count above maximum is flagged as INFO."""
        counts = {t: (lo + hi) // 2 for t, (lo, hi) in EMPIRICAL_RANGES.items()}
        counts['constraints'] = 100  # Above max of 57
        result = check_v7(999, counts)
        assert result['status'] == 'INFO'
        oor = result['details']['out_of_range']
        assert any(o['type'] == 'constraints' and o['deviation'] == 'above' for o in oor)

    def test_multiple_out_of_range(self):
        """Multiple types out of range are all reported."""
        counts = {t: (lo + hi) // 2 for t, (lo, hi) in EMPIRICAL_RANGES.items()}
        counts['roles'] = 2
        counts['states'] = 50
        counts['ethical_question'] = 100
        result = check_v7(999, counts)
        assert result['status'] == 'INFO'
        types_flagged = {o['type'] for o in result['details']['out_of_range']}
        assert 'roles' in types_flagged
        assert 'states' in types_flagged
        assert 'ethical_question' in types_flagged

    def test_zero_count_not_flagged(self):
        """Zero count is not flagged by V7 (that's V6's job)."""
        counts = {t: (lo + hi) // 2 for t, (lo, hi) in EMPIRICAL_RANGES.items()}
        counts['roles'] = 0
        result = check_v7(999, counts)
        # V7 skips zero counts (cnt > 0 check)
        oor_types = {o['type'] for o in result['details']['out_of_range']}
        assert 'roles' not in oor_types

    def test_at_boundary_passes(self):
        """Counts exactly at boundary values pass."""
        counts = {}
        for t, (lo, hi) in EMPIRICAL_RANGES.items():
            counts[t] = lo  # Exactly at minimum
        result = check_v7(999, counts)
        assert result['status'] == 'PASS'

        counts2 = {}
        for t, (lo, hi) in EMPIRICAL_RANGES.items():
            counts2[t] = hi  # Exactly at maximum
        result2 = check_v7(999, counts2)
        assert result2['status'] == 'PASS'

    def test_total_computed(self):
        """Total entity count is computed from counts dict."""
        counts = {'roles': 10, 'states': 15}
        result = check_v7(999, counts)
        assert result['details']['total'] == 25

    def test_unknown_types_ignored(self):
        """Types not in EMPIRICAL_RANGES are not flagged."""
        counts = {'roles': 10, 'some_new_type': 999}
        result = check_v7(999, counts)
        oor_types = {o['type'] for o in result['details']['out_of_range']}
        assert 'some_new_type' not in oor_types

    def test_severity_is_info(self):
        """V7 severity is always INFO, never CRITICAL."""
        counts = {'roles': 1}
        result = check_v7(999, counts)
        assert result['severity'] == 'INFO'


# ===========================================================================
# V6: Completeness (test the logic, not the DB query)
# ===========================================================================

class TestV6Logic:
    """Test the completeness check logic used by V6."""

    def test_all_16_types_present(self):
        """All 16 required types yields no missing."""
        present = {t: 10 for t in REQUIRED_TYPES}
        missing = [t for t in REQUIRED_TYPES if t not in present]
        assert len(missing) == 0

    def test_missing_step4_types(self):
        """Missing Step 4 types are detected."""
        # Only Steps 1-3 types present
        step1_3 = ['roles', 'states', 'resources', 'principles', 'obligations',
                    'constraints', 'capabilities', 'temporal_dynamics_enhanced']
        present = {t: 10 for t in step1_3}
        missing = [t for t in REQUIRED_TYPES if t not in present]
        assert len(missing) == 8
        assert 'ethical_question' in missing
        assert 'canonical_decision_point' in missing

    def test_missing_step1_types(self):
        """Missing Step 1 types are detected."""
        present = {t: 10 for t in REQUIRED_TYPES if t != 'roles'}
        missing = [t for t in REQUIRED_TYPES if t not in present]
        assert missing == ['roles']

    def test_required_types_count(self):
        """Exactly 16 required types are defined."""
        assert len(REQUIRED_TYPES) == 16


# ===========================================================================
# V4: Decision Point Options (test the regex patterns)
# ===========================================================================

class TestV4Patterns:
    """Test the V4 decision point validation regex patterns."""

    def test_generic_label_pattern_matches(self):
        """Generic 'Option A', 'Option B' labels are caught."""
        pattern = re.compile(r'^Option\s+[A-Z]$', re.IGNORECASE)
        assert pattern.match('Option A')
        assert pattern.match('Option B')
        assert pattern.match('option c')

    def test_generic_label_pattern_rejects_descriptive(self):
        """Descriptive labels are not caught by generic pattern."""
        pattern = re.compile(r'^Option\s+[A-Z]$', re.IGNORECASE)
        assert not pattern.match('Disclose the conflict of interest')
        assert not pattern.match('Report to the licensing board')
        assert not pattern.match('Option to recuse')  # Not "Option X"

    def test_bad_desc_no_required(self):
        """'No ... required' pattern is caught."""
        bad_patterns = [
            (re.compile(r'^No\s+\w+\s+required'), 'Starts with "No ... required"'),
        ]
        assert bad_patterns[0][0].match('No action required')
        assert bad_patterns[0][0].match('No disclosure required')
        assert not bad_patterns[0][0].match('Notify the board of the issue')

    def test_descriptive_labels_pass(self):
        """Real descriptive decision point labels pass all checks."""
        pattern = re.compile(r'^Option\s+[A-Z]$', re.IGNORECASE)
        good_labels = [
            'Disclose the conflict to Client W',
            'Refuse the engagement',
            'Continue with AI-generated documents',
            'Seek peer review from another engineer',
            'The Drainage Board approves the modified design',
        ]
        for label in good_labels:
            assert not pattern.match(label), f"False positive on: {label}"


# ===========================================================================
# EMPIRICAL_RANGES consistency
# ===========================================================================

class TestEmpiricalRanges:
    """Validate the empirical range definitions."""

    def test_all_required_types_have_ranges(self):
        """Every required type has a corresponding empirical range."""
        for t in REQUIRED_TYPES:
            assert t in EMPIRICAL_RANGES, f"Missing range for {t}"

    def test_no_extra_ranges(self):
        """No ranges defined for types not in REQUIRED_TYPES."""
        for t in EMPIRICAL_RANGES:
            assert t in REQUIRED_TYPES, f"Extra range for {t}"

    def test_ranges_are_valid(self):
        """All ranges have lo <= hi and positive values."""
        for t, (lo, hi) in EMPIRICAL_RANGES.items():
            assert lo > 0, f"{t}: lo must be positive, got {lo}"
            assert hi >= lo, f"{t}: hi ({hi}) < lo ({lo})"

    def test_ranges_are_reasonable(self):
        """No absurdly wide ranges (sanity check on the ranges themselves)."""
        for t, (lo, hi) in EMPIRICAL_RANGES.items():
            assert hi < 100, f"{t}: hi ({hi}) seems too high"
            assert lo >= 1, f"{t}: lo ({lo}) too low"
