"""Annotation-related blueprint registrations."""

from typing import Dict, List, Tuple
from flask import Blueprint

from app.routes.annotations import annotations_bp
from app.routes.api_document_annotations import bp as api_document_annotations_bp
from app.routes.annotation_review import bp as annotation_review_bp
from app.routes.annotation_versions import annotation_versions_bp
from app.routes.enhanced_annotations import bp as enhanced_annotations_bp
from app.routes.intelligent_annotations import intelligent_annotations_bp
from app.routes.llm_annotations import bp as llm_annotations_bp

BlueprintRegistration = Tuple[Blueprint, Dict]

ANNOTATION_BLUEPRINTS: List[BlueprintRegistration] = [
    (annotations_bp, {}),
    (intelligent_annotations_bp, {}),
    (enhanced_annotations_bp, {}),
    (llm_annotations_bp, {}),
    (annotation_review_bp, {}),
    (annotation_versions_bp, {}),
    (api_document_annotations_bp, {}),
]
