"""
Patterns package for the Case URL Processor.

This package provides configurable pattern matchers for extracting
metadata from case study content, particularly for NSPE ethics cases.
"""

from .nspe_patterns import NSPEPatternMatcher

__all__ = ['NSPEPatternMatcher']
