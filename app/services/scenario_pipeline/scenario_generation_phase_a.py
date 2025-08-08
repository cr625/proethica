"""Scenario Generation Phase A Service.

Generates a minimal structured scenario timeline (events + decisions) directly from a Case (Document)
without requiring prior deconstruction. Saves versioned scenario data in Document.doc_metadata['scenario_versions'].
"""
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime, timezone
import hashlib
import os

from app.models import Document, db
from sqlalchemy.orm.attributes import flag_modified
from .segmenter import segment_sections
from .classifier import classify_sentences
from .temporal import extract_temporal
from .assembler import assemble_events
from .decisions import enrich_decisions
from .participant_extractor import extract_participants
from .ontology_summary import build_ontology_summary
from .ontology_mapper import map_events
from .ordering import build_ordering
from .llm_decision_refiner import refine_decisions_with_llm

PIPELINE_VERSION = 'phase_a_v1'

class DirectScenarioPipelineService:
    def __init__(self):
        pass

    def generate(self, case: Document, overwrite: bool = False) -> Dict[str, Any]:
        metadata = case.doc_metadata or {}
        sections = metadata.get('sections') or metadata.get('document_structure', {}).get('sections', {}) or {}

        # 1. Segmentation & sentence-level annotations
        segmentation = segment_sections(sections)
        sentences = segmentation['sentences']
        classification = classify_sentences(sentences)
        temporal = extract_temporal(sentences)

        # 2. Assemble events
        events = assemble_events(sentences, classification)
        for ev in events:
            if ev['sentence_ids']:
                tinfo = temporal.get(ev['sentence_ids'][0])
                if tinfo:
                    ev['temporal'] = tinfo

        # 3. Participants extraction (optional enrich) then heuristic decision enrichment
        participant_meta = extract_participants(events) if os.environ.get('DIRECT_SCENARIO_INCLUDE_PARTICIPANTS', 'true').lower() != 'false' else {'unique_participants': []}
        enrich_decisions(events)

        # 4. Optional LLM refinement
        refine_decisions_with_llm(events)

        # 4b. Fill generic options if any refined decision lacks options
        for ev in events:
            if ev.get('kind') == 'decision' and not ev.get('options'):
                # minimal generic options fallback
                ev['options'] = [
                    {'label': 'Escalate', 'description': 'Escalate to appropriate oversight'},
                    {'label': 'Proceed Quietly', 'description': 'Continue without broader disclosure'},
                    {'label': 'Pause & Reassess', 'description': 'Delay action pending more information'}
                ]

        # 5. Ontology mapping & ordering
        map_events(events)
        ordering = build_ordering(events)

        # 6. Stats
        stats = {
            'event_count': len(events),
            'decision_count': sum(1 for e in events if e['kind'] == 'decision'),
            'sentence_count': len(sentences)
        }

        ontology_summary = build_ontology_summary(events, participant_meta.get('unique_participants'))
        scenario_data = {
            'pipeline_version': PIPELINE_VERSION,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'case_id': case.id,
            'events': events,
            'ordering': ordering,
            'stats': stats,
            'participants': participant_meta.get('unique_participants'),
            'ontology_summary': ontology_summary
        }

        versions = metadata.get('scenario_versions', [])
        content_hash = hashlib.sha256(str(stats).encode('utf-8')).hexdigest()[:12]
        scenario_data['hash'] = content_hash
        scenario_data['version_number'] = len(versions) + 1

        if overwrite:
            versions.append(scenario_data)
        else:
            if not versions or versions[-1].get('hash') != content_hash:
                versions.append(scenario_data)

        metadata['scenario_versions'] = versions
        metadata['latest_scenario'] = scenario_data
        case.doc_metadata = dict(metadata)
        flag_modified(case, 'doc_metadata')
        db.session.add(case)
        db.session.commit()
        return scenario_data
