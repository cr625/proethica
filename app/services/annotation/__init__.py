"""Annotation service package -- matches terms in text to ontology entities."""

from .text_annotator import TextAnnotator, AnnotatedSpan

__all__ = ['TextAnnotator', 'AnnotatedSpan']
