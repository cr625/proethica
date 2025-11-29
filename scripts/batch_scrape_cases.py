#!/usr/bin/env python
"""
Batch Scrape NSPE Cases

Scrapes multiple NSPE cases and adds them to the database with:
- Section extraction and HTML formatting
- Section embeddings for similarity search
- Precedent features for multi-factor matching

Uses the same pipeline as the /cases/process/url route.

Usage:
    cd /home/chris/onto/proethica
    source venv-proethica/bin/activate
    python scripts/batch_scrape_cases.py [--dry-run]

Configuration:
    Edit data/new_cases_to_scrape.json to specify cases to scrape.
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime

# Add parent directories to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
proethica_dir = os.path.dirname(script_dir)
onto_dir = os.path.dirname(proethica_dir)

sys.path.insert(0, proethica_dir)  # For app imports
sys.path.insert(0, onto_dir)  # For shared imports

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_cases_to_scrape():
    """Load case URLs from configuration file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'new_cases_to_scrape.json'
    )

    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        return []

    with open(config_path, 'r') as f:
        data = json.load(f)

    return data.get('cases', [])


def check_case_exists(url, db_session, Document):
    """Check if a case with this URL already exists."""
    existing = Document.query.filter_by(source=url).first()
    return existing is not None


def scrape_case(case_info, world_id, dry_run=False):
    """
    Scrape a single case using the existing pipeline.

    Args:
        case_info: Dict with url, case_number, title, year
        world_id: World ID to associate case with
        dry_run: If True, don't save to database

    Returns:
        Dict with status and details
    """
    from app import db
    from app.models import Document
    from app.models.document import PROCESSING_STATUS
    from app.services.case_processing.pipeline_manager import PipelineManager
    from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
    from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep
    from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep

    url = case_info['url']
    case_number = case_info.get('case_number', '')
    expected_title = case_info.get('title', '')

    logger.info(f"Processing case {case_number}: {url}")

    # Check if already exists
    if check_case_exists(url, db.session, Document):
        logger.warning(f"Case {case_number} already exists in database, skipping")
        return {'status': 'skipped', 'reason': 'already_exists', 'case_number': case_number}

    if dry_run:
        logger.info(f"[DRY RUN] Would scrape: {case_number} - {expected_title}")
        return {'status': 'dry_run', 'case_number': case_number}

    try:
        # Initialize pipeline
        pipeline = PipelineManager()
        pipeline.register_step('url_retrieval', URLRetrievalStep())
        pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())
        pipeline.register_step('document_structure', DocumentStructureAnnotationStep())

        # Run pipeline
        steps_to_run = ['url_retrieval', 'nspe_extraction', 'document_structure']
        result = pipeline.run_pipeline({'url': url}, steps_to_run)

        final_result = result.get('final_result', {})

        if final_result.get('status') == 'error':
            logger.error(f"Pipeline error for {case_number}: {final_result.get('message')}")
            return {'status': 'error', 'message': final_result.get('message'), 'case_number': case_number}

        # Extract case data
        title = final_result.get('title', expected_title or f'NSPE Case {case_number}')
        year = final_result.get('year', case_info.get('year', ''))
        full_date = final_result.get('full_date')
        date_parts = final_result.get('date_parts')
        pdf_url = final_result.get('pdf_url', '')
        subject_tags = final_result.get('subject_tags', [])

        # Get sections
        sections = final_result.get('sections', {})
        if not sections:
            sections = {
                'facts': final_result.get('facts', ''),
                'question': final_result.get('question_html', ''),
                'references': final_result.get('references', ''),
                'discussion': final_result.get('discussion', ''),
                'conclusion': final_result.get('conclusion', ''),
                'dissenting_opinion': final_result.get('dissenting_opinion', '')
            }

        questions_list = final_result.get('questions_list', [])
        conclusion_items = final_result.get('conclusion_items', [])

        # Build HTML content
        html_content = build_html_content(sections, questions_list, conclusion_items)

        # Build metadata
        metadata = {
            'case_number': case_number or final_result.get('case_number', ''),
            'year': year,
            'full_date': full_date,
            'date_parts': date_parts,
            'pdf_url': pdf_url,
            'subject_tags': subject_tags,
            'sections': sections,
            'questions_list': questions_list,
            'conclusion_items': conclusion_items,
            'extraction_method': 'batch_scrape',
            'scraped_at': datetime.utcnow().isoformat()
        }

        # Add dual format sections if available
        if 'sections_dual' in final_result:
            metadata['sections_dual'] = final_result['sections_dual']
        if 'sections_text' in final_result:
            metadata['sections_text'] = final_result['sections_text']

        # Create document
        document = Document(
            title=title,
            content=html_content,
            document_type='case_study',
            world_id=world_id,
            source=url,
            file_type='url',
            doc_metadata=metadata,
            processing_status=PROCESSING_STATUS['COMPLETED']
        )

        db.session.add(document)
        db.session.commit()

        logger.info(f"Created document ID {document.id} for case {case_number}")

        # Generate section embeddings
        from app.services.section_embedding_service import SectionEmbeddingService
        section_service = SectionEmbeddingService()
        embedding_result = section_service.process_document_sections(document.id)
        if embedding_result.get('success'):
            logger.info(f"Generated embeddings for {embedding_result.get('sections_embedded')} sections")
        else:
            raise RuntimeError(f"Failed to generate section embeddings: {embedding_result.get('error')}")

        # Generate precedent features
        from app.services.precedent.case_feature_extractor import CaseFeatureExtractor
        extractor = CaseFeatureExtractor()
        features = extractor.extract_precedent_features(document.id)
        extractor.save_features(features)
        logger.info(f"Extracted precedent features: outcome={features.outcome_type}, provisions={len(features.provisions_cited)}")

        return {
            'status': 'success',
            'case_number': case_number,
            'document_id': document.id,
            'title': title
        }

    except Exception as e:
        logger.error(f"Error processing case {case_number}: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'message': str(e), 'case_number': case_number}


def build_html_content(sections, questions_list, conclusion_items):
    """Build HTML content from sections."""
    html = ""

    # Facts
    if sections.get('facts'):
        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Facts</h5>
            </div>
            <div class="card-body">
                {sections['facts']}
            </div>
        </div>
    </div>
</div>
"""

    # Questions
    if sections.get('question') or questions_list:
        header = "Questions" if len(questions_list) > 1 else "Question"
        content = ""
        if questions_list:
            content = "<ol>\n"
            for q in questions_list:
                content += f"<li>{q}</li>\n"
            content += "</ol>"
        else:
            content = sections.get('question', '')

        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-info text-white">
                <h5 class="mb-0">{header}</h5>
            </div>
            <div class="card-body">
                {content}
            </div>
        </div>
    </div>
</div>
"""

    # References
    if sections.get('references'):
        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-secondary text-white">
                <h5 class="mb-0">NSPE Code of Ethics References</h5>
            </div>
            <div class="card-body">
                {sections['references']}
            </div>
        </div>
    </div>
</div>
"""

    # Discussion
    if sections.get('discussion'):
        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Discussion</h5>
            </div>
            <div class="card-body">
                {sections['discussion']}
            </div>
        </div>
    </div>
</div>
"""

    # Conclusion
    if sections.get('conclusion') or conclusion_items:
        header = "Conclusions" if len(conclusion_items) > 1 else "Conclusion"
        content = ""
        if conclusion_items:
            content = "<ol>\n"
            for c in conclusion_items:
                content += f"<li>{c}</li>\n"
            content += "</ol>"
        else:
            content = sections.get('conclusion', '')

        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-success text-white">
                <h5 class="mb-0">{header}</h5>
            </div>
            <div class="card-body">
                {content}
            </div>
        </div>
    </div>
</div>
"""

    # Dissenting Opinion
    if sections.get('dissenting_opinion'):
        html += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-warning">
                <h5 class="mb-0">Dissenting Opinion</h5>
            </div>
            <div class="card-body">
                {sections['dissenting_opinion']}
            </div>
        </div>
    </div>
</div>
"""

    return html


def main():
    parser = argparse.ArgumentParser(description='Batch scrape NSPE cases')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be scraped without saving')
    parser.add_argument('--world-id', type=int, default=1,
                        help='World ID for cases (default: 1 = Engineering)')
    args = parser.parse_args()

    print("="*60)
    print("NSPE Case Batch Scraper")
    print("="*60)

    # Load cases to scrape
    cases = load_cases_to_scrape()
    if not cases:
        print("No cases to scrape. Check data/new_cases_to_scrape.json")
        return 1

    print(f"\nFound {len(cases)} cases to process:")
    for case in cases:
        print(f"  - {case.get('case_number')}: {case.get('title', 'Unknown')[:50]}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    # Create Flask app context
    from app import create_app
    app = create_app()

    results = []
    with app.app_context():
        for i, case in enumerate(cases, 1):
            print(f"\n[{i}/{len(cases)}] Processing {case.get('case_number')}...")
            result = scrape_case(case, args.world_id, args.dry_run)
            results.append(result)

            status = result.get('status')
            if status == 'success':
                print(f"  SUCCESS: Created document ID {result.get('document_id')}")
            elif status == 'skipped':
                print(f"  SKIPPED: {result.get('reason')}")
            elif status == 'dry_run':
                print(f"  DRY RUN: Would create case")
            else:
                print(f"  ERROR: {result.get('message', 'Unknown error')}")

    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)

    success = sum(1 for r in results if r.get('status') == 'success')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')
    errors = sum(1 for r in results if r.get('status') == 'error')
    dry_run = sum(1 for r in results if r.get('status') == 'dry_run')

    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    if dry_run:
        print(f"  Dry run: {dry_run}")

    if not args.dry_run and success > 0:
        # Verify total case count
        with app.app_context():
            from app.models import Document
            total = Document.query.filter(
                Document.document_type.in_(['case', 'case_study'])
            ).count()
            print(f"\n  Total cases in database: {total}")

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
